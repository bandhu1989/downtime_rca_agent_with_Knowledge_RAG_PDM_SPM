"""Four-section navigation for the battery manufacturing maintenance demo."""
import os
import streamlit as st
import pandas as pd
import plotly.express as px
import subprocess
import sys
import threading
from datetime import datetime
from dotenv import load_dotenv
from generate_data import make_data
from rca_engine import list_events, get_event_evidence, rank_hypotheses, similar_events

load_dotenv()
st.set_page_config(page_title='Downtime Investigator | Root Cause Analysis | Maintenance Intelligence', page_icon='🏭', layout='wide')
st.title('🏭 Downtime Investigator | Root Cause | Maintenance Intelligence')
st.caption('Synthetic plant data · Downtime RCA · AI knowledge assistant · ML Based Predictive maintenance · Remaining Useful Life Detection · Warranty & Spare Parts Management')

# Ensure database exists BEFORE starting the stream simulator
if not os.path.exists('data/plant.db'):
    make_data()

# Load initial event IDs 
events = pd.DataFrame(list_events(100))
if events.empty:
    st.error('No downtime events found. Run `python generate_data.py` and reload.')
    st.stop()
event_ids = events['event_id'].tolist()

# Start pdm_stream.py once in the background
@st.cache_resource
def start_simulation():
    def run_script():
        subprocess.run([
            sys.executable, "pdm_stream.py", 
            "--interval", "3", 
            "--ticks", "1000"
        ])
    
    thread = threading.Thread(target=run_script, daemon=True)
    thread.start()
    return thread

start_simulation() 

# Streamlit tabs open the first tab by default. All four pages remain independently accessible.
downtime_tab, chat_tab, maintenance_tab, ml_tab = st.tabs([
    '🔎 Downtime Investigation',
    '💬 AI Investigator',
    '🛠️ Predictive & Preventive Maintenance Command Center',
    '🧠 ML Predictive Maintenance & RUL',
])


@st.fragment(run_every="10s")
def _refresh_downtime_data():
    """Refresh downtime data without generating new ticks."""
    live_events = pd.DataFrame(list_events(100))
    latest_event = live_events[0]['event_id'] if not live_events.empty else "None"
    st.caption(
        f"🟢 **Live Stream Active** | Last UI Refresh: `{datetime.now().strftime('%H:%M:%S')}` "
        f"| Total Events: `{len(live_events)}` | Latest Event: `{latest_event}`"
    )
    
with downtime_tab:
    st.subheader('Downtime Investigation')
    selected = st.selectbox('Select Downtime Event', event_ids, key='selected_downtime_event',
                            help='Choose a simulated downtime event to review its evidence and hypotheses.')
    ev = get_event_evidence(selected)
    event = ev['event']
    a, b, c, d = st.columns(4)
    a.metric('Event', event['event_id'])
    b.metric('Duration', f"{event['duration_min']} min")
    c.metric('Line', event['line'])
    d.metric('Machine', event['machine'])
    evidence_tab, hypotheses_tab, similar_tab = st.tabs([
        'Evidence overview', 'Root-cause hypotheses', 'Similar events'
    ])
    with evidence_tab:
        st.write(f"**Start:** {event['start_time']} | **Shift:** {event['shift']} | **Reported category:** {event['reported_category']}")
        st.write(f"**Operator note:** {event['operator_note']}")
        # PLC and MES context share the top row.
        plc_col, mes_col = st.columns(2, gap='medium')
        with plc_col:
            st.markdown('#### PLC alarms')
            st.dataframe(pd.DataFrame(ev['plc_alarms']), use_container_width=True)
        with mes_col:
            st.markdown('#### MES context')
            st.dataframe(pd.DataFrame(ev['mes_context']), use_container_width=True)

        # Maintenance work orders occupy the full available page width.
        st.markdown('#### Maintenance work orders')
        st.dataframe(pd.DataFrame(ev['maintenance_work_orders']), use_container_width=True)

        # Both historian panels start at exactly the same vertical position.
        st.markdown('#### Historian Signals Around the Downtime Event')
        historian_graph_col, historian_table_col = st.columns(2, gap='medium', vertical_alignment='top')
        h = pd.DataFrame(ev['historian_signals'])
        with historian_graph_col:
            if not h.empty:
                st.plotly_chart(
                    px.line(h, x='timestamp', y='value', color='signal', markers=True,
                            title=None),
                    use_container_width=True,
                )
            else:
                st.info('No historian signals available for this event.')
        with historian_table_col:
            st.dataframe(h, use_container_width=True)
    with hypotheses_tab:
        result = rank_hypotheses(selected)
        st.info(result['interpretation_note'])
        df = pd.DataFrame(result['ranked_hypotheses'])
        st.dataframe(df, use_container_width=True)
        if not df.empty:
            st.write('**Leading hypothesis:**', df.iloc[0]['hypothesis'])
            for item in df.iloc[0]['evidence']:
                st.write('- ' + item)
    with similar_tab:
        st.dataframe(pd.DataFrame(similar_events(selected)), use_container_width=True)

with chat_tab:
    st.subheader('AI Investigator')
    st.caption('Ask questions in a conversational format. Answers are grounded in simulated evidence and available SOPs; human verification is required.')
    current_event = st.session_state.get('selected_downtime_event', event_ids[0])
    examples = [
        f'Investigate {current_event}. Explain evidence, competing hypotheses, data gaps, confidence and next checks.',
        f'Summarize the PLC alarms, historian trends and MES context for {current_event}.',
        f'For {current_event}, identify the leading root-cause hypotheses and the evidence supporting or contradicting each.',
        f'Find similar downtime incidents to {current_event} and explain what can be learned.',
        f'For {current_event}, find the relevant maintenance SOP and summarize safe checks and escalation steps.',
        'Which assets currently have high predictive maintenance risk or open maintenance work orders?',
    ]
    st.markdown('**Suggested questions — click to populate the chat:**')
    for i, suggestion in enumerate(examples):
        if st.button(suggestion, key=f'suggested_prompt_{i}', use_container_width=True):
            st.session_state['chat_pending_prompt'] = suggestion
    if 'investigator_messages' not in st.session_state:
        st.session_state['investigator_messages'] = [
            {'role': 'assistant', 'content': 'Hello! I can investigate downtime events, compare root-cause hypotheses, review simulated PLC/MES/historian evidence and search maintenance SOPs. Choose a suggested question or type your own below.'}
        ]
    if st.button('Clear conversation', key='clear_investigator_chat'):
        st.session_state['investigator_messages'] = []
        st.session_state.pop('chat_pending_prompt', None)
        st.rerun()
    for message in st.session_state['investigator_messages']:
        with st.chat_message(message['role']):
            st.markdown(message['content'])
    typed_prompt = st.chat_input('Ask about a downtime event, equipment condition, RCA or maintenance SOP…')
    prompt = typed_prompt or st.session_state.pop('chat_pending_prompt', None)
    if prompt:
        st.session_state['investigator_messages'].append({'role': 'user', 'content': prompt})
        with st.chat_message('user'):
            st.markdown(prompt)
        with st.chat_message('assistant'):
            if not os.getenv('OPENAI_API_KEY'):
                answer = 'To use the AI Investigator, set `OPENAI_API_KEY` in your `.env` file and restart Streamlit. The deterministic Downtime Investigation tab works without an API key.'
                st.warning(answer)
            else:
                with st.spinner('Investigating evidence and knowledge sources…'):
                    try:
                        from agent import investigate
                        # Include recent turns as context; the agent itself remains stateless.
                        history = st.session_state['investigator_messages'][:-1][-6:]
                        context = '\n'.join(f"{m['role'].upper()}: {m['content']}" for m in history)
                        question = (f'Previous conversation for context only:\n{context}\n\nCurrent user question:\n{prompt}'
                                    if context else prompt)
                        answer = investigate(question)
                        st.markdown(answer)
                    except Exception as ex:
                        answer = f'Investigation could not complete: {ex}'
                        st.error(answer)
        st.session_state['investigator_messages'].append({'role': 'assistant', 'content': answer})

with maintenance_tab:
    from maintenance_ui import render as render_maintenance
    render_maintenance()

with ml_tab:
    from pdm_dashboard import render as render_ml_predictive
    render_ml_predictive()

st.divider()
st.caption('Demo safeguards: all plant data and maintenance workflows are simulated · model results are not plant-validated · no PLC write-back · authorized human approval required.')
