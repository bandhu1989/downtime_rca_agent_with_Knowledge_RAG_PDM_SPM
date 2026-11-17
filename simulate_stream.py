"""Optional foreground simulator: python simulate_stream.py --interval 3 --ticks 100"""
import argparse,time
from maintenance_engine import init_db,simulate_tick,run_scheduler
p=argparse.ArgumentParser(); p.add_argument('--interval',type=float,default=3); p.add_argument('--ticks',type=int,default=100)
a=p.parse_args(); init_db()
try:
    for i in range(a.ticks):
        report=simulate_tick(); run_scheduler()
        print(f'Tick {i+1}: '+', '.join(f'{r["asset_id"]}={r["risk_index"]}({r["level"]})' for r in report),flush=True)
        if i<a.ticks-1: time.sleep(a.interval)
except KeyboardInterrupt: print('Simulator stopped')
