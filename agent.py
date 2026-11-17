import json, os
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from rca_engine import list_events,get_event_evidence,rank_hypotheses,similar_events
load_dotenv()
@tool
def list_recent_downtime_events(limit:int=20)->str:
    """List simulated downtime events and valid event IDs."""
    return json.dumps(list_events(limit),default=str)
@tool
def retrieve_multisource_evidence(event_id:str)->str:
    """Retrieve PLC alarms, MES context, historian measurements and maintenance work orders for an event."""
    return json.dumps(get_event_evidence(event_id),default=str)
@tool
def rank_root_cause_hypotheses(event_id:str)->str:
    """Rank possible causes from deterministic alarm, MES and historian rules. Scores are not probabilities."""
    return json.dumps(rank_hypotheses(event_id),default=str)
@tool
def find_similar_downtime_events(event_id:str,limit:int=5)->str:
    """Find recent events on the same machine or line with work-order actions."""
    return json.dumps(similar_events(event_id,limit),default=str)
SYSTEM_PROMPT_DIRCA='''You are a Downtime Investigator and Root Cause Intelligence specialist for battery manufacturing. Always retrieve evidence and rank hypotheses before recommending. Structure the response: (1) incident summary, (2) timeline, (3) evidence by PLC/MES/historian/maintenance, (4) ranked hypotheses with supporting and conflicting evidence, (5) safe diagnostic checks ordered by value, (6) confidence label and reason, (7) data gaps, (8) suggested owner and next action. Do not call a hypothesis confirmed unless records prove it. Scores are rule weights, never probabilities. Distinguish correlation from causation. Do not invent data, limits or work orders. Never suggest bypassing safety interlocks. This is read-only; no machine commands. Simulated evidence does not prove real-world cause.'''


# Maintenance intelligence tools are optional extensions of the existing RCA agent.
from maintenance_engine import dashboard as maintenance_dashboard, health_snapshot as maintenance_health_snapshot
from knowledge_base import search_maintenance_knowledge

@tool
def get_predictive_maintenance_status() -> str:
    """Read current simulated asset health, open maintenance work orders and maintenance alerts."""
    d=maintenance_dashboard()
    return json.dumps({'health':maintenance_health_snapshot(),'work_orders':d['work_orders'][:30],'alerts':d['alerts'][:30]},default=str)

@tool
def get_spare_parts_and_pm_status() -> str:
    """Read simulated spare inventory, installed-component warranty/life and preventive schedules."""
    d=maintenance_dashboard()
    return json.dumps({k:d[k] for k in ('parts','installations','pm_plans','transactions')},default=str)

@tool
def search_maintenance_manuals_and_sops(query: str) -> str:
    """Retrieve relevant simulated maintenance SOP/manual passages for evidence-grounded guidance."""
    return json.dumps(search_maintenance_knowledge(query,k=4),default=str)

SYSTEM_PROMPT_PDM='''You also act as a read-only Predictive/Preventive Maintenance Copilot. When asked about asset health, maintenance alerts, work orders, spare parts, warranties, or PM schedules, retrieve the relevant tools first. For corrective instructions search maintenance manuals/SOPs and cite source names. All manuals are SIMULATED and not approved for plant execution. Risk index is a heuristic, NOT failure probability or calibrated time-to-failure. Never claim exact remaining useful life. Never autonomously close WOs, consume stock, control equipment, or approve work. Treat maintenance alerts and work orders as simulated records. Clearly separate observed evidence, heuristic inference, and recommendations. Require authorized maintenance personnel and approved OEM/site procedures for physical work.''' 
SYSTEM_PROMPT_RAG='''You are an AI-powered Maintenance Knowledge Assistant for battery manufacturing.
 1) Retrieve PLC, MES, Historian and Maintenance evidence.
 2) After retrieving incident evidence and ranking hypotheses, search relevant Service Manuals and SOPs using search_maintenance_manuals_and_sops tool for the leading hypothesis and relevant asset/process context.
 3) Provide step-by-step corrective guidance strictly based on retrieved documentation. Never invent repair steps, values, torque settings, isolation points, acceptance limits, charging settings or restart criteria.
 4) Separate operator-level observations from work restricted to authorized maintenance/electrical staff.
 5) Display source filename, document ID/title and revision with the guidance.
 6) These documents are simulated PoC examples, NOT approved procedures or work authorization.
 7) If no relevant procedure is found, say so and refer the user to the supervisor and controlled OEM/site document system.
 8) Never advise bypassing guards, interlocks, protective trips or safety devices.
 9) Never issue PLC/SCADA commands or claim equipment is safe to restart. 
 10) Require qualified human verification and site authorization before corrective action.

Structure the response as:
 1) Incident Summary and evidence timeline
 2) Ranked Root Cause Hypotheses (scores are rule weights, not probabilities)
 3) Supporting Evidence
 4) Relevant Service Manual / SOP references (source, ID, revision)
 5) Operator-level safe observations
 6) Authorized maintenance checks
 7) Step-by-Step Corrective Guidance
 8) Safety Precautions and prohibited actions
 9) Verification and return-to-service requirements
 10) Data gaps, escalation owner and human approval required

Never present a hypothesis as a confirmed root cause.
'''
SYSTEM_PROMPT= SYSTEM_PROMPT_DIRCA + "\n\n" + SYSTEM_PROMPT_PDM + "\n\n" + SYSTEM_PROMPT_RAG

def build_agent():
    if not os.getenv('OPENAI_API_KEY'):
        raise RuntimeError('OPENAI_API_KEY missing. Create .env from .env.example.')
    llm=ChatOpenAI(model=os.getenv('OPENAI_MODEL','gpt-5.5'),temperature=0)
    return create_agent(model=llm,tools=[list_recent_downtime_events,retrieve_multisource_evidence,rank_root_cause_hypotheses,find_similar_downtime_events,get_predictive_maintenance_status,get_spare_parts_and_pm_status,search_maintenance_manuals_and_sops],system_prompt=SYSTEM_PROMPT)

def investigate(question:str)->str:
    result=build_agent().invoke({'messages':[{'role':'user','content':question}]})
    return result['messages'][-1].content