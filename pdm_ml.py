"""Simulation-only ML predictive maintenance: grouped training, online inference, auditable local actions.
No PLC control or external notification. Time unit is acquisition cycles, not real-world hours.
"""
from __future__ import annotations
import argparse, json, math, os, random, sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestRegressor, IsolationForest
from sklearn.metrics import average_precision_score, mean_absolute_error, precision_score, recall_score
from sklearn.model_selection import GroupShuffleSplit
from maintenance_engine import connect, init_db, rows, _alert, _wo, iso, now

ROOT=Path(__file__).resolve().parent
MODEL_DIR=ROOT/'models'
FEATURES=['deviation','slope','volatility','alarm_density','age_fraction','mean_deviation','downtime_count']
HORIZON=12  # future acquisition cycles, NOT real-time hours
RUL_CAP=120


def schema():
    init_db()
    with connect() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS ml_predictions(
          id INTEGER PRIMARY KEY AUTOINCREMENT,asset_id TEXT NOT NULL, ts TEXT NOT NULL,
          failure_probability REAL NOT NULL, rul_ticks REAL NOT NULL, anomaly_score REAL NOT NULL,
          level TEXT NOT NULL, model_version TEXT NOT NULL, features_json TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_ml_predictions_asset ON ml_predictions(asset_id,id);
        CREATE TABLE IF NOT EXISTS ml_notifications(
          id INTEGER PRIMARY KEY AUTOINCREMENT, asset_id TEXT, created_at TEXT,
          channel TEXT NOT NULL DEFAULT 'LOCAL_QUEUE', recipient TEXT NOT NULL,
          message TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'PENDING', work_order_id INTEGER);
        CREATE TABLE IF NOT EXISTS production_windows(
          asset_id TEXT PRIMARY KEY, next_window_start TEXT NOT NULL, duration_minutes INTEGER NOT NULL);
        ''')
        for a in c.execute('SELECT asset_id FROM assets').fetchall():
            aid=a['asset_id']
            t=now()+timedelta(hours=12)
            c.execute('INSERT OR IGNORE INTO production_windows VALUES(?,?,?)',(aid,iso(t),120))


def make_training_data(runs=240, length=100, seed=42):
    """Synthetic independent degradation episodes, including false alarms and nonfailure runs.
    Labels are simulator-generated; do not interpret validation as plant predictive performance.
    """
    rng=np.random.default_rng(seed); X=[]; Y=[]; R=[]; groups=[]
    for run in range(runs):
        fail=bool(rng.random()<0.7)
        failure_at=int(rng.integers(55,length+10)) if fail else length+200
        shape=float(rng.uniform(.8,1.6)); phase=float(rng.uniform(0,.6))
        d=[]; alarms=[]
        for tick in range(length):
            progress=max(0,tick/failure_at)
            degradation=(progress**(2.2*shape))*1.7 if fail else .08+.08*tick/length
            drift=.08*math.sin(tick/9+phase)
            shock=(.8 if rng.random()<.015 else 0)
            value=max(0,degradation+drift+shock+rng.normal(0,.07))
            d.append(value); alarms.append(int(value>1.0))
            if tick<7:continue
            window=np.array(d[-8:]); alarm_window=np.array(alarms[-8:]); remaining=failure_at-tick
            age=tick/length
            f=[float(d[-1]),float((window[-1]-window[0])/7),float(window.std()),
               float(alarm_window.mean()),age,float(window.mean()),float(sum(alarms[max(0,tick-24):]))]
            X.append(f); Y.append(int(0<remaining<=HORIZON));R.append(float(min(RUL_CAP,max(0,remaining))));groups.append(run)
            if remaining<=0:break
    return np.asarray(X),np.asarray(Y),np.asarray(R),np.asarray(groups)


def train(runs=240,seed=42):
    MODEL_DIR.mkdir(exist_ok=True);X,y,r,g=make_training_data(runs=runs,seed=seed)
    train_ix,test_ix=next(GroupShuffleSplit(n_splits=1,test_size=.25,random_state=seed).split(X,y,g))
    clf=HistGradientBoostingClassifier(max_iter=120,max_leaf_nodes=15,l2_regularization=2,random_state=seed)
    reg=RandomForestRegressor(n_estimators=65,min_samples_leaf=5,max_depth=12,n_jobs=-1,random_state=seed)
    anomaly=IsolationForest(n_estimators=100,contamination=.07,random_state=seed,n_jobs=-1)
    clf.fit(X[train_ix],y[train_ix]);reg.fit(X[train_ix],r[train_ix]);anomaly.fit(X[train_ix][y[train_ix]==0])
    prob=clf.predict_proba(X[test_ix])[:,1];pred=(prob>=.5).astype(int)
    metrics={'synthetic_only':True,'train_runs':int(len(set(g[train_ix]))),'test_runs':int(len(set(g[test_ix]))),
             'test_samples':len(test_ix),'positive_rate':round(float(y[test_ix].mean()),3),
             'precision_at_0_5':round(float(precision_score(y[test_ix],pred,zero_division=0)),3),
             'recall_at_0_5':round(float(recall_score(y[test_ix],pred,zero_division=0)),3),
             'average_precision':round(float(average_precision_score(y[test_ix],prob)),3),
             'rul_mae_ticks':round(float(mean_absolute_error(r[test_ix],reg.predict(X[test_ix]))),2),
             'horizon_ticks':HORIZON,'feature_names':FEATURES,
             'limitations':'Simulator labels; model has no validated asset failure probability, physical RUL or lead-time guarantee.'}
    joblib.dump({'classifier':clf,'regressor':reg,'anomaly':anomaly,'metrics':metrics,'version':'synthetic-v1'},MODEL_DIR/'pdm_models.joblib')
    (MODEL_DIR/'training_metrics.json').write_text(json.dumps(metrics,indent=2))
    return metrics


def extract_live_features(c,asset):
    history=c.execute('SELECT value,scenario FROM readings WHERE asset_id=? ORDER BY id DESC LIMIT 25',(asset['asset_id'],)).fetchall()
    if len(history)<8:return None
    history=list(reversed(history));v=np.array([x['value'] for x in history]);b=asset['baseline'];threshold=asset['threshold'];scale=abs(threshold-b) or 1
    sign=1 if threshold>b else -1
    normalized=np.maximum(0,sign*(v-b)/scale)
    w=normalized[-8:]
    alarms=(normalized>1.0).astype(int)
    # Time since last known maintenance isn't available in legacy schema; proxy is capped observation count.
    total_readings=c.execute("SELECT COUNT(*) AS n FROM readings WHERE asset_id=?",(asset["asset_id"],)).fetchone()["n"]
    age_fraction=min(1.0,total_readings/100)
    return np.array([[float(w[-1]),float((w[-1]-w[0])/7),float(w.std()),float(alarms[-8:].mean()),
                      age_fraction,float(w.mean()),float(alarms.sum())]])


def score_latest(prob_threshold=.65,rul_threshold=15, anomaly_threshold=-.08):
    """Score latest observations, persist evidence and create one active WO per asset.
    Warning thresholds are demonstration choices, not plant-validated operating limits.
    """
    schema();path=MODEL_DIR/'pdm_models.joblib'
    if not path.exists():raise FileNotFoundError('Train model first: python pdm_ml.py train')
    m=joblib.load(path);results=[]
    with connect() as c:
        assets=[dict(x) for x in c.execute('SELECT * FROM assets')]
        for a in assets:
            f=extract_live_features(c,a)
            if f is None:continue
            prob=float(m['classifier'].predict_proba(f)[0,1]);rul=float(max(0,m['regressor'].predict(f)[0]));anom=float(m['anomaly'].decision_function(f)[0])
            abnormal=anom<anomaly_threshold
            level='CRITICAL' if prob>=.85 or (rul<=7 and abnormal) else 'HIGH' if prob>=prob_threshold or (rul<=rul_threshold and abnormal) else 'WATCH' if abnormal or prob>=.4 else 'NORMAL'
            ts=iso(now());aid=a['asset_id'];features=dict(zip(FEATURES,[round(float(x),4) for x in f[0]]))
            c.execute('INSERT INTO ml_predictions(asset_id,ts,failure_probability,rul_ticks,anomaly_score,level,model_version,features_json) VALUES(?,?,?,?,?,?,?,?)',
                      (aid,ts,prob,rul,anom,level,m['version'],json.dumps(features)))
            wo_id=None
            if level in ('HIGH','CRITICAL'):
                existing=c.execute("SELECT id FROM work_orders WHERE asset_id=? AND kind IN ('PREDICTIVE','ML_PREDICTIVE') AND status IN ('OPEN','IN_PROGRESS') ORDER BY id DESC LIMIT 1",(aid,)).fetchone()
                if existing:
                    wo_id=existing['id']
                    queued=c.execute('SELECT 1 FROM ml_notifications WHERE asset_id=? AND work_order_id=?',(aid,wo_id)).fetchone()
                    if not queued:
                        c.execute('INSERT INTO ml_notifications(asset_id,created_at,recipient,message,work_order_id) VALUES(?,?,?,?,?)',
                                  (aid,ts,a['team'],f'{level} ML prediction for {aid}; review existing WO-{wo_id}. Local demo queue only.',wo_id))
                else:
                    key=f'ML-{aid}-{int(now().timestamp())}'
                    window=c.execute('SELECT * FROM production_windows WHERE asset_id=?',(aid,)).fetchone()
                    schedule=f"Suggested production window {window['next_window_start']} ({window['duration_minutes']} min), subject to production approval." if window else 'Production scheduling approval required.'
                    desc=(f"Synthetic ML warning; probability of simulated failure within {HORIZON} acquisition cycles={prob:.2f}; "
                          f"estimated RUL={rul:.1f} cycles; anomaly={anom:.3f}. {schedule} Confirm via approved SOP; no auto-shutdown.")
                    _wo(c,key,aid,'ML_PREDICTIVE','URGENT' if level=='CRITICAL' else 'HIGH',a['team'],desc,ts)
                    wo_id=c.execute('SELECT id FROM work_orders WHERE dedupe_key=?',(key,)).fetchone()['id']
                    _alert(c,key,aid,level,'ML_PREDICTIVE',f'{aid}: model warning, WO-{wo_id} created; review during approved production window.',ts)
                    c.execute('INSERT INTO ml_notifications(asset_id,created_at,recipient,message,work_order_id) VALUES(?,?,?,?,?)',
                              (aid,ts,a['team'],f'{level} predictive maintenance alert for {aid}; review WO-{wo_id}. Local demo queue only.',wo_id))
            results.append({'asset_id':aid,'failure_probability_simulated':round(prob,3),'rul_acquisition_cycles':round(rul,1),
                            'anomaly_score':round(anom,3),'level':level,'wo_id':wo_id,'features':features})
    return results


def snapshot():
    schema()
    return {'predictions':rows('SELECT * FROM ml_predictions WHERE id IN (SELECT MAX(id) FROM ml_predictions GROUP BY asset_id) ORDER BY failure_probability DESC'),
            'history':rows('SELECT * FROM ml_predictions ORDER BY id DESC LIMIT 400'),
            'notifications':rows('SELECT * FROM ml_notifications ORDER BY id DESC LIMIT 100'),
            'windows':rows('SELECT * FROM production_windows ORDER BY asset_id')}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['train','score','status']);p.add_argument('--runs',type=int,default=240)
    args=p.parse_args()
    if args.command=='train':print(json.dumps(train(args.runs),indent=2))
    elif args.command=='score':print(json.dumps(score_latest(),indent=2))
    else:print(json.dumps(snapshot(),indent=2))
