"""Streamlit fragment embedded in original app.py; UI controls mutate only local demo DB."""
import pandas as pd
import streamlit as st
import plotly.express as px
from maintenance_engine import (init_db,simulate_tick,run_scheduler,set_scenario,dashboard,
                                start_work_order,close_work_order,receive_stock,acknowledge_alert)

@st.fragment(run_every="10s")
def _refresh_maintenance_data():
    """Refresh maintenance data without generating new ticks."""

    data = dashboard()

    orders = data["work_orders"]
    alerts = data["alerts"]

def render():
    st.header('🛠️ Predictive & Preventive Maintenance Command Center')
    st.caption('Synthetic simulation • Local SQLite only • Work orders/alerts are not transmitted to external teams or CMMS')
    init_db()
    with st.expander('Simulator controls',expanded=True):
        c1,c2,c3=st.columns(3)
        with c1:
            if st.button('Generate next simulated tick',type='primary'):
                simulate_tick();run_scheduler();st.rerun()
        with c2:
            if st.button('Generate 12 ticks quickly'):
                for _ in range(12):simulate_tick()
                run_scheduler();st.rerun()
        with c3:
            if st.button('Run PM / warranty / inventory scheduler'):
                run_scheduler();st.rerun()
        data=dashboard(); asset=st.selectbox('Asset to simulate',[a['asset_id'] for a in data['assets']]); scenario=st.selectbox('Scenario',['normal','degrading','critical','recovery','sensor_fault'])
        if st.button('Apply scenario'):
            set_scenario(asset,scenario);st.success(f'{asset}: {scenario}');st.rerun()
        st.info('For continuous updates, run `python simulate_stream.py --interval 3 --ticks 1000` in a second VS Code terminal, then refresh this page.')
    data=dashboard(); orders=data['work_orders']; alerts=data['alerts']
    m1,m2,m3,m4=st.columns(4)
    m1.metric('Open WOs',sum(w['status']!='CLOSED' for w in orders))
    m2.metric('Unacknowledged alerts',sum(a['status']=='OPEN' for a in alerts))
    m3.metric('Low-stock parts',sum(p['qty_on_hand']<=p['safety_stock'] for p in data['parts']))
    m4.metric('Assets monitored',len(data['assets']))
    tabs=st.tabs(['Asset health','Work orders','Alerts','Spare parts','Installed parts / lifecycle','Preventive maintenance'])
    with tabs[0]:
        if data['readings']:
            df=pd.DataFrame(data['readings']); selected=st.selectbox('Trend asset',[a['asset_id'] for a in data['assets']],key='trend_asset')
            sub=df[df.asset_id==selected].sort_values('id')
            st.plotly_chart(px.line(sub,x='id',y='value',markers=True,title=f'{selected}: simulated reading by sample'),use_container_width=True)
        st.dataframe(pd.DataFrame(data['assets']),use_container_width=True)
    with tabs[1]:
        st.dataframe(pd.DataFrame(orders),use_container_width=True)
        active=[w for w in orders if w['status']!='CLOSED']
        if active:
            chosen=st.selectbox('Select active WO',active,format_func=lambda w:f'WO-{w["id"]} | {w["asset_id"]} | {w["kind"]} | {w["status"]}')
            x,y=st.columns(2)
            with x:
                if st.button('Start selected WO'):
                    try:start_work_order(chosen['id']);st.rerun()
                    except ValueError as e:st.error(str(e))
            with y:
                parts=['No spare consumed']+[p['part_id'] for p in data['parts']]
                part=st.selectbox('Part issued on closure',parts)
                qty=st.number_input('Confirmed quantity issued',min_value=0,max_value=50,value=0,step=1)
                if st.button('Close WO and post confirmed spare consumption'):
                    try:
                        close_work_order(chosen['id'],None if part=='No spare consumed' else part,int(qty));st.success('WO closed; inventory updated');st.rerun()
                    except ValueError as e:st.error(str(e))
        else:st.info('No open work orders. Try a critical or degrading scenario.')
    with tabs[2]:
        st.dataframe(pd.DataFrame(alerts),use_container_width=True)
        open_alerts=[a for a in alerts if a['status']=='OPEN']
        if open_alerts:
            a=st.selectbox('Acknowledge alert',open_alerts,format_func=lambda a:f'#{a["id"]} {a["category"]}: {a["message"][:70]}')
            if st.button('Acknowledge'):acknowledge_alert(a['id']);st.rerun()
    with tabs[3]:
        st.dataframe(pd.DataFrame(data['parts']),use_container_width=True)
        part=st.selectbox('Receive part',[p['part_id'] for p in data['parts']]); qty=st.number_input('Quantity received',min_value=1,value=2,step=1)
        if st.button('Post simulated stock receipt'):
            receive_stock(part,int(qty));st.rerun()
        st.write('Stock movement ledger');st.dataframe(pd.DataFrame(data['transactions']),use_container_width=True)
    with tabs[4]:
        st.dataframe(pd.DataFrame(data['installations']),use_container_width=True)
        st.caption('Warranty and expected-life dates are simulated metadata. Actual part warranties require vendor, batch/serial and purchase/installation evidence.')
    with tabs[5]:
        st.dataframe(pd.DataFrame(data['pm_plans']),use_container_width=True)
        st.caption('A PM cycle advances only after its work order is closed. Due cycles create one deduplicated work order.')
