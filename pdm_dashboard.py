"""ML dashboard embedded in the existing Streamlit application."""
import json
import pandas as pd
import streamlit as st
import plotly.express as px
from pdm_ml import MODEL_DIR,score_latest,snapshot,train,schema
from maintenance_engine import dashboard

@st.fragment(run_every="10s")
def _refresh_ml_data():
    """Refresh predictions, trends and notifications."""

    metrics = MODEL_DIR / "training_metrics.json"

def render():
    st.header('🧠 ML Predictive Maintenance & RUL')
    st.warning('Training, failure labels and sensor readings are synthetic. Predictions are not validated for live equipment or real failure lead time.')
    schema()
    x,y=st.columns(2)
    with x:
        if st.button('Train simulated failure/RUL models'):
            with st.spinner('Training models on synthetic run-to-failure episodes...'):
                st.json(train())
    with y:
        if st.button('Score latest asset data'):
            try:st.dataframe(pd.DataFrame(score_latest()),use_container_width=True)
            except FileNotFoundError as e:st.error(str(e))
    metrics=MODEL_DIR/'training_metrics.json'
    if metrics.exists():
        with st.expander('Holdout evaluation — synthetic episodes only'):
            st.json(json.loads(metrics.read_text()))
    data=snapshot()
    tabs=st.tabs(['Predictions & RUL','Condition trends','Notification queue','Production windows'])
    with tabs[0]:
        if data['predictions']:
            df=pd.DataFrame(data['predictions'])
            st.dataframe(df[['asset_id','ts','failure_probability','rul_ticks','anomaly_score','level','model_version']],use_container_width=True)
            st.caption('Probability: model score for failure within next 12 simulated acquisition cycles. RUL: simulated cycles, not hours/days.')
        else:st.info('Generate at least eight ticks per asset, train, and score.')
    with tabs[1]:
        h=pd.DataFrame(data['history'])
        if not h.empty:
            a=st.selectbox('Asset',[x['asset_id'] for x in dashboard()['assets']],key='ml_asset')
            sub=h[h.asset_id==a].sort_values('id')
            if not sub.empty:
                st.plotly_chart(px.line(sub,x='id',y=['failure_probability','anomaly_score'],title=f'{a}: model outputs by acquisition'),use_container_width=True)
                st.plotly_chart(px.line(sub,x='id',y='rul_ticks',title=f'{a}: estimated RUL (acquisition cycles)'),use_container_width=True)
    with tabs[2]:
        st.dataframe(pd.DataFrame(data['notifications']),use_container_width=True)
        st.caption('Notifications are queued in local SQLite; external email/Teams/SAP integrations are not enabled.')
    with tabs[3]:
        st.dataframe(pd.DataFrame(data['windows']),use_container_width=True)
        st.caption('Windows are simulated proposals; maintenance requires production coordination and human authorization.')
