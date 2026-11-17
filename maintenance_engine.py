"""SQLite-backed simulated maintenance execution. No external writes or PLC control."""
import sqlite3, json, math, os, random
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB = Path(__file__).resolve().parent / 'data' / 'maintenance_demo.db'
ASSETS = [
 ('ASM-MTR-01','Assembly','Conveyor drive motor','motor_current',11.0,16.0,'BEARING-6205','Mechanical'),
 ('ASM-BRG-02','Assembly','Conveyor bearing','vibration_mm_s',3.2,6.0,'BEARING-6205','Mechanical'),
 ('ASM-SEN-03','Assembly','Photoelectric sensor','photoeye_transitions_min',75.0,35.0,'PHOTOEYE-24V','Automation'),
 ('FRM-RECT-01','Formation','Formation rectifier','rectifier_temp_c',62.0,80.0,'RECT-FAN-24V','Electrical'),
 ('FRM-RECT-02','Formation','Formation rectifier','rectifier_temp_c',62.0,80.0,'RECT-FAN-24V','Electrical'),
 ('FIN-MTR-01','Finishing','Finishing motor','motor_current',11.0,16.0,'MOTOR-CONTACTOR','Electrical'),
]
PARTS = [
 ('BEARING-6205','Conveyor bearing 6205',5,3,2,120,365),
 ('PHOTOEYE-24V','Photoelectric sensor 24V',3,2,2,90,270),
 ('RECT-FAN-24V','Rectifier cooling fan',4,2,3,180,365),
 ('MOTOR-CONTACTOR','Motor contactor',6,3,2,180,365),
]

def now(): return datetime.now(timezone.utc)
def iso(dt): return dt.isoformat(timespec='seconds')
def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    con=sqlite3.connect(DB, timeout=15)
    con.row_factory=sqlite3.Row
    con.execute('PRAGMA journal_mode=WAL')
    con.execute('PRAGMA foreign_keys=ON')
    return con

def init_db(reset=False):
    if reset:
        for suffix in ('','-wal','-shm'):
            p=Path(str(DB)+suffix)
            if p.exists(): p.unlink()
    with connect() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS assets(asset_id TEXT PRIMARY KEY, area TEXT, description TEXT, signal TEXT, baseline REAL, threshold REAL, part_id TEXT, team TEXT);
        CREATE TABLE IF NOT EXISTS readings(id INTEGER PRIMARY KEY AUTOINCREMENT, asset_id TEXT, ts TEXT, signal TEXT, value REAL, scenario TEXT);
        CREATE INDEX IF NOT EXISTS idx_readings_asset ON readings(asset_id,id);
        CREATE TABLE IF NOT EXISTS alerts(id INTEGER PRIMARY KEY AUTOINCREMENT, dedupe_key TEXT UNIQUE, asset_id TEXT, ts TEXT, severity TEXT, category TEXT, message TEXT, status TEXT DEFAULT 'OPEN');
        CREATE TABLE IF NOT EXISTS work_orders(id INTEGER PRIMARY KEY AUTOINCREMENT, dedupe_key TEXT UNIQUE, asset_id TEXT, kind TEXT, priority TEXT, assigned_team TEXT, description TEXT, status TEXT DEFAULT 'OPEN', created_at TEXT, closed_at TEXT, part_id TEXT, qty_used INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS parts(part_id TEXT PRIMARY KEY, description TEXT, qty_on_hand INTEGER CHECK(qty_on_hand>=0), safety_stock INTEGER, reorder_qty INTEGER, warranty_days INTEGER, expected_life_days INTEGER);
        CREATE TABLE IF NOT EXISTS stock_transactions(id INTEGER PRIMARY KEY AUTOINCREMENT, part_id TEXT, wo_id INTEGER, ts TEXT, movement TEXT, qty INTEGER, balance_after INTEGER);
        CREATE TABLE IF NOT EXISTS installations(id INTEGER PRIMARY KEY AUTOINCREMENT, asset_id TEXT, part_id TEXT, wo_id INTEGER, installed_at TEXT, warranty_end TEXT, life_end TEXT, status TEXT DEFAULT 'ACTIVE');
        CREATE TABLE IF NOT EXISTS pm_plans(asset_id TEXT PRIMARY KEY, interval_days INTEGER, last_done TEXT, next_due TEXT, team TEXT);
        CREATE TABLE IF NOT EXISTS scenarios(asset_id TEXT PRIMARY KEY, name TEXT, step INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT);
        ''')
        c.executemany('INSERT OR IGNORE INTO assets VALUES(?,?,?,?,?,?,?,?)',ASSETS)
        c.executemany('INSERT OR IGNORE INTO parts VALUES(?,?,?,?,?,?,?)',PARTS)
        for a in ASSETS:
            c.execute('INSERT OR IGNORE INTO scenarios(asset_id,name,step) VALUES(?,?,0)',(a[0],'normal'))
            last=now()-timedelta(days=4)
            c.execute('INSERT OR IGNORE INTO pm_plans VALUES(?,?,?,?,?)',(a[0],7,iso(last),iso(last+timedelta(days=7)),a[7]))
        c.execute("INSERT OR IGNORE INTO settings VALUES('tick','0')")
        # Seed one near-expiry installed component and one approaching useful life
        t=now()
        c.execute('INSERT OR IGNORE INTO installations(asset_id,part_id,wo_id,installed_at,warranty_end,life_end,status) SELECT ?,?,NULL,?,?,?,? WHERE NOT EXISTS(SELECT 1 FROM installations WHERE asset_id=?)',('ASM-SEN-03','PHOTOEYE-24V',iso(t-timedelta(days=85)),iso(t+timedelta(days=5)),iso(t+timedelta(days=185)),'ACTIVE','ASM-SEN-03'))
        c.execute('INSERT OR IGNORE INTO installations(asset_id,part_id,wo_id,installed_at,warranty_end,life_end,status) SELECT ?,?,NULL,?,?,?,? WHERE NOT EXISTS(SELECT 1 FROM installations WHERE asset_id=?)',('FRM-RECT-01','RECT-FAN-24V',iso(t-timedelta(days=350)),iso(t-timedelta(days=170)),iso(t+timedelta(days=15)),'ACTIVE','FRM-RECT-01'))

def rows(query,args=()):
    c=connect()
    try: return [dict(r) for r in c.execute(query,args).fetchall()]
    finally: c.close()

def set_scenario(asset_id,scenario):
    if scenario not in ('normal','degrading','critical','recovery','sensor_fault'): raise ValueError('Invalid scenario')
    with connect() as c:
        if not c.execute('SELECT 1 FROM assets WHERE asset_id=?',(asset_id,)).fetchone(): raise ValueError('Unknown asset')
        c.execute('UPDATE scenarios SET name=?,step=0 WHERE asset_id=?',(scenario,asset_id))

def _alert(c,key,asset_id,severity,category,message,ts):
    c.execute('INSERT OR IGNORE INTO alerts(dedupe_key,asset_id,ts,severity,category,message) VALUES(?,?,?,?,?,?)',(key,asset_id,ts,severity,category,message))

def _wo(c,key,asset_id,kind,priority,team,description,ts):
    c.execute('INSERT OR IGNORE INTO work_orders(dedupe_key,asset_id,kind,priority,assigned_team,description,created_at) VALUES(?,?,?,?,?,?,?)',(key,asset_id,kind,priority,team,description,ts))

def _risk(c,asset,reading,ts):
    """Illustrative normalized severity + trend; score is NOT calibrated failure probability."""
    aid=asset['asset_id']; baseline=asset['baseline']; threshold=asset['threshold']
    history=[r['value'] for r in c.execute('SELECT value FROM readings WHERE asset_id=? ORDER BY id DESC LIMIT 8',(aid,))]
    history.reverse()
    high_bad = threshold>baseline
    denominator=abs(threshold-baseline) or 1
    severity=(reading-baseline)/denominator if high_bad else (baseline-reading)/denominator
    slope=(history[-1]-history[0])/denominator if len(history)>=4 else 0
    if not high_bad: slope=-slope
    risk=max(0,min(100,round(65*max(0,severity)+25*max(0,slope)+10*(len(history)>=4 and severity>0.5))))
    level='CRITICAL' if risk>=85 else 'HIGH' if risk>=65 else 'WATCH' if risk>=40 else 'NORMAL'
    # Persistent active risk => one open corrective WO per asset, not one per tick.
    if level in ('HIGH','CRITICAL'):
        existing=c.execute("SELECT id FROM work_orders WHERE asset_id=? AND kind='PREDICTIVE' AND status IN ('OPEN','IN_PROGRESS')",(aid,)).fetchone()
        if not existing:
            key=f'PRED-{aid}-{int(datetime.fromisoformat(ts).timestamp())}'
            _wo(c,key,aid,'PREDICTIVE','URGENT' if level=='CRITICAL' else 'HIGH',asset['team'],f'{level} anomaly on {asset["signal"]}; risk index {risk}/100. Verify evidence and approved SOP before maintenance.',ts)
            _alert(c,key,aid,level,'PREDICTIVE',f'{aid}: {level} anomaly, risk index {risk}/100; predictive WO opened.',ts)
    return {'asset_id':aid,'value':round(reading,2),'signal':asset['signal'],'risk_index':risk,'level':level,'trend_normalized':round(slope,3)}

def simulate_tick(seed=None):
    """One simulated acquisition cycle. Call repeatedly or use Streamlit Auto-refresh."""
    rng=random.Random(seed) if seed is not None else random.Random()
    timestamp=iso(now()); result=[]
    with connect() as c:
        for asset in [dict(r) for r in c.execute('SELECT * FROM assets')]:
            aid=asset['asset_id']; sc=c.execute('SELECT name,step FROM scenarios WHERE asset_id=?',(aid,)).fetchone()
            step=sc['step']+1; name=sc['name']; base=asset['baseline']; limit=asset['threshold']; direction=1 if limit>base else -1
            noise=rng.gauss(0,abs(limit-base)*0.045)
            fraction={'normal':0.05,'degrading':min(1.4,0.10+step*0.11),'critical':1.4,'recovery':max(0.02,1.2-step*0.17),'sensor_fault':(1.5 if step%3==0 else 0.03)}[name]
            value=round(max(0,base+direction*abs(limit-base)*fraction+noise),3)
            c.execute('INSERT INTO readings(asset_id,ts,signal,value,scenario) VALUES(?,?,?,?,?)',(aid,timestamp,asset['signal'],value,name))
            c.execute('UPDATE scenarios SET step=? WHERE asset_id=?',(step,aid))
            result.append(_risk(c,asset,value,timestamp))
        c.execute("UPDATE settings SET value=CAST(CAST(value AS INTEGER)+1 AS TEXT) WHERE key='tick'")
    return result

def run_scheduler(reference=None):
    t=reference or now(); timestamp=iso(t)
    with connect() as c:
        for p in [dict(r) for r in c.execute('SELECT * FROM pm_plans')]:
            due=datetime.fromisoformat(p['next_due'])
            if due<=t:
                # One WO for a due cycle. Does not silently advance PM due date until completion.
                key=f'PM-{p["asset_id"]}-{p["next_due"]}'
                _wo(c,key,p['asset_id'],'PREVENTIVE','MEDIUM',p['team'],f'Scheduled {p["interval_days"]}-day PM due {p["next_due"]}; follow approved PM checklist.',timestamp)
                _alert(c,key,p['asset_id'],'MEDIUM','PM',f'Preventive maintenance due for {p["asset_id"]}',timestamp)
        for p in [dict(r) for r in c.execute('SELECT * FROM parts')]:
            if p['qty_on_hand']<=p['safety_stock']:
                key=f'STOCK-{p["part_id"]}-{p["qty_on_hand"]}'
                _alert(c,key,None,'HIGH','LOW_STOCK',f'{p["part_id"]}: on hand {p["qty_on_hand"]}, safety stock {p["safety_stock"]}; suggest reorder {p["reorder_qty"]}.',timestamp)
        for inst in [dict(r) for r in c.execute("SELECT * FROM installations WHERE status='ACTIVE'")]:
            for field,category in [('warranty_end','WARRANTY'),('life_end','EXPECTED_LIFE')]:
                days=(datetime.fromisoformat(inst[field])-t).total_seconds()/86400
                if days<=30:
                    key=f'{category}-{inst["id"]}'
                    severity='HIGH' if days<=0 else 'MEDIUM'
                    _alert(c,key,inst['asset_id'],severity,category,f'{inst["part_id"]} on {inst["asset_id"]}: {category.lower()} date {inst[field]} ({math.ceil(days)} days remaining). Review with maintenance.',timestamp)

def start_work_order(wo_id):
    with connect() as c:
        result=c.execute("UPDATE work_orders SET status='IN_PROGRESS' WHERE id=? AND status='OPEN'",(wo_id,))
        if result.rowcount!=1: raise ValueError('WO not OPEN or unknown')

def close_work_order(wo_id,part_id=None,qty=0):
    """Atomic closure and stock issue. No automatic spare consumption before confirmed human entry."""
    if not isinstance(qty,int) or qty<0: raise ValueError('Quantity must be non-negative integer')
    if bool(part_id)!=(qty>0): raise ValueError('Supply both part_id and positive qty, or neither')
    t=now(); timestamp=iso(t)
    with connect() as c:
        wo=c.execute('SELECT * FROM work_orders WHERE id=?',(wo_id,)).fetchone()
        if not wo or wo['status'] not in ('OPEN','IN_PROGRESS'): raise ValueError('WO already closed or not found')
        if qty:
            p=c.execute('SELECT * FROM parts WHERE part_id=?',(part_id,)).fetchone()
            if not p: raise ValueError('Unknown part')
            if p['qty_on_hand']<qty: raise ValueError('Insufficient stock; no changes committed')
            balance=p['qty_on_hand']-qty
            c.execute('UPDATE parts SET qty_on_hand=? WHERE part_id=?',(balance,part_id))
            c.execute('INSERT INTO stock_transactions(part_id,wo_id,ts,movement,qty,balance_after) VALUES(?,?,?,?,?,?)',(part_id,wo_id,timestamp,'ISSUE',-qty,balance))
            # Demo assumes one installed serialized-equivalent part for a one-unit replacement.
            # For multi-unit issues, inventory is consumed but installation records require individual confirmation.
            if qty==1:
                c.execute("UPDATE installations SET status='REPLACED' WHERE asset_id=? AND part_id=? AND status='ACTIVE'",(wo['asset_id'],part_id))
                c.execute('INSERT INTO installations(asset_id,part_id,wo_id,installed_at,warranty_end,life_end) VALUES(?,?,?,?,?,?)',(wo['asset_id'],part_id,wo_id,timestamp,iso(t+timedelta(days=p['warranty_days'])),iso(t+timedelta(days=p['expected_life_days']))))
            if balance<=p['safety_stock']:
                _alert(c,f'STOCK-{part_id}-{balance}',None,'HIGH','LOW_STOCK',f'{part_id}: balance {balance} at/below safety stock {p["safety_stock"]}.',timestamp)
        c.execute("UPDATE work_orders SET status='CLOSED',closed_at=?,part_id=?,qty_used=? WHERE id=?",(timestamp,part_id,qty,wo_id))
        if wo['kind']=='PREVENTIVE':
            plan=c.execute('SELECT interval_days FROM pm_plans WHERE asset_id=?',(wo['asset_id'],)).fetchone()
            if plan:
                c.execute('UPDATE pm_plans SET last_done=?,next_due=? WHERE asset_id=?',(timestamp,iso(t+timedelta(days=plan['interval_days'])),wo['asset_id']))
    run_scheduler()

def receive_stock(part_id,qty):
    if not isinstance(qty,int) or qty<=0: raise ValueError('Quantity must be positive integer')
    with connect() as c:
        p=c.execute('SELECT qty_on_hand FROM parts WHERE part_id=?',(part_id,)).fetchone()
        if not p: raise ValueError('Unknown part')
        balance=p['qty_on_hand']+qty
        c.execute('UPDATE parts SET qty_on_hand=? WHERE part_id=?',(balance,part_id))
        c.execute('INSERT INTO stock_transactions(part_id,wo_id,ts,movement,qty,balance_after) VALUES(?,?,?,?,?,?)',(part_id,None,iso(now()),'RECEIPT',qty,balance))

def acknowledge_alert(alert_id):
    with connect() as c: c.execute("UPDATE alerts SET status='ACKNOWLEDGED' WHERE id=? AND status='OPEN'",(alert_id,))

def dashboard():
    return {key:rows(query) for key,query in {
      'assets':'SELECT a.*,s.name AS scenario,s.step FROM assets a JOIN scenarios s USING(asset_id) ORDER BY a.asset_id',
      'readings':'SELECT * FROM readings ORDER BY id DESC LIMIT 300',
      'work_orders':'SELECT * FROM work_orders ORDER BY id DESC LIMIT 150',
      'alerts':'SELECT * FROM alerts ORDER BY id DESC LIMIT 150',
      'parts':'SELECT * FROM parts ORDER BY part_id',
      'transactions':'SELECT * FROM stock_transactions ORDER BY id DESC LIMIT 100',
      'installations':'SELECT * FROM installations ORDER BY id DESC LIMIT 100',
      'pm_plans':'SELECT * FROM pm_plans ORDER BY next_due',
    }.items()}

def health_snapshot():
    result=[]
    with connect() as c:
        for asset in [dict(r) for r in c.execute('SELECT * FROM assets')]:
            r=c.execute('SELECT value,ts FROM readings WHERE asset_id=? ORDER BY id DESC LIMIT 1',(asset['asset_id'],)).fetchone()
            if r:
                baseline,limit=asset['baseline'],asset['threshold']
                ratio=((r['value']-baseline)/(limit-baseline)) if limit!=baseline else 0
                result.append({'asset_id':asset['asset_id'],'signal':asset['signal'],'latest_value':r['value'],'threshold':limit,'normalized_severity':round(ratio,2),'observed_at':r['ts']})
    return result
