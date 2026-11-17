"""Reproducible demo seed. WARNING: --reset deletes only the local maintenance_demo.db."""
import argparse
from datetime import timedelta
from maintenance_engine import init_db,set_scenario,simulate_tick,run_scheduler,connect,now,iso
p=argparse.ArgumentParser();p.add_argument('--reset',action='store_true');a=p.parse_args()
init_db(reset=a.reset)
set_scenario('ASM-BRG-02','degrading')
set_scenario('FRM-RECT-01','critical')
set_scenario('ASM-SEN-03','sensor_fault')
for i in range(18): simulate_tick(seed=100+i)
# Demonstrate a due PM on one asset, without modifying any real maintenance system.
with connect() as c:
    c.execute('UPDATE pm_plans SET next_due=? WHERE asset_id=?',(iso(now()-timedelta(days=1)),'FIN-MTR-01'))
run_scheduler()
print('Seed complete: 108 readings, predictive work orders, alerts, a due PM, and warranty/life alerts.')
print('Open Streamlit with: streamlit run app.py')
