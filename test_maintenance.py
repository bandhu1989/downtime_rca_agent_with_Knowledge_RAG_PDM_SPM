"""Unit tests use isolated temporary SQLite DB and never touch the demo database."""
import tempfile,unittest
from pathlib import Path
import maintenance_engine as m
class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.old=m.DB;m.DB=Path(self.temp.name)/'test.db';m.init_db()
    def tearDown(self):m.DB=self.old;self.temp.cleanup()
    def test_predictive_wo_is_deduplicated(self):
        m.set_scenario('ASM-BRG-02','critical')
        for i in range(6):m.simulate_tick(seed=i)
        w=[w for w in m.dashboard()['work_orders'] if w['asset_id']=='ASM-BRG-02' and w['kind']=='PREDICTIVE']
        self.assertEqual(len(w),1)
    def test_stock_issue_and_warranty(self):
        m.set_scenario('FRM-RECT-01','critical');m.simulate_tick(seed=1)
        wo=next(w for w in m.dashboard()['work_orders'] if w['asset_id']=='FRM-RECT-01')
        before=next(p['qty_on_hand'] for p in m.dashboard()['parts'] if p['part_id']=='RECT-FAN-24V')
        m.close_work_order(wo['id'],'RECT-FAN-24V',1)
        after=next(p['qty_on_hand'] for p in m.dashboard()['parts'] if p['part_id']=='RECT-FAN-24V')
        self.assertEqual(after,before-1)
        self.assertTrue(any(x['wo_id']==wo['id'] for x in m.dashboard()['installations']))
        with self.assertRaises(ValueError):m.close_work_order(wo['id'],'RECT-FAN-24V',1)
    def test_pm_idempotent_and_advances_on_close(self):
        with m.connect() as c:c.execute('UPDATE pm_plans SET next_due=? WHERE asset_id=?',(m.iso(m.now()-m.timedelta(days=1)),'FIN-MTR-01'))
        m.run_scheduler();m.run_scheduler()
        pm=[w for w in m.dashboard()['work_orders'] if w['kind']=='PREVENTIVE' and w['asset_id']=='FIN-MTR-01']
        self.assertEqual(len(pm),1)
        m.close_work_order(pm[0]['id'])
        self.assertGreater(m.dashboard()['pm_plans'][-1]['interval_days'],0)
    def test_reject_overissue_without_closure(self):
        m.set_scenario('FRM-RECT-02','critical');m.simulate_tick(seed=2)
        wo=next(w for w in m.dashboard()['work_orders'] if w['asset_id']=='FRM-RECT-02')
        with self.assertRaises(ValueError):m.close_work_order(wo['id'],'RECT-FAN-24V',999)
        self.assertNotEqual(next(w['status'] for w in m.dashboard()['work_orders'] if w['id']==wo['id']),'CLOSED')
if __name__=='__main__':unittest.main()
