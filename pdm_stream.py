"""Continuous acquisition + ML inference. Run in a second VS Code terminal."""
import argparse,time
from maintenance_engine import init_db,simulate_tick,run_scheduler
from pdm_ml import score_latest,MODEL_DIR
p=argparse.ArgumentParser();p.add_argument('--interval',type=float,default=3);p.add_argument('--ticks',type=int,default=1000)
a=p.parse_args()
if a.interval<=0:raise ValueError('interval must be positive')
if not (MODEL_DIR/'pdm_models.joblib').exists():raise SystemExit('Run: python pdm_ml.py train')
init_db()
try:
    for i in range(a.ticks):
        simulate_tick();run_scheduler();result=score_latest()
        print(f'Tick {i+1}: '+', '.join(f'{r["asset_id"]}:{r["level"]},RUL={r["rul_acquisition_cycles"]:.0f} cycles' for r in result),flush=True)
        if i+1<a.ticks:time.sleep(a.interval)
except KeyboardInterrupt:print('Stopped')
