# Battery Manufacturing AI Maintenance Extension — Step-by-step VS Code Guide

## Scope and limitations

This bundle combines the ORIGINAL downtime RCA project, the simulated Maintenance SOP RAG extension, and a new predictive/preventive maintenance simulator. It is a **local demonstration**, not a production CMMS/ERP/PLC integration. A rule-based risk **index** is not a calibrated probability of failure, and warranty/expected-life dates are illustrative. The agent is read-only; Streamlit demo controls update local SQLite records only. All manuals are simulated, unapproved training materials.

## Step 1: Install

1. Extract the ZIP, open `downtime_rca_agent` as the folder in VS Code.
2. Open VS Code Terminal → New Terminal.
3. Windows PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks activation, use `.venv\Scripts\python.exe` in place of `python` and `.venv\Scripts\pip.exe` in place of `pip`.

4. Copy `.env.example` to `.env` and set `OPENAI_API_KEY` and `OPENAI_MODEL`. Keep `.env` private. OpenAI API calls are only required for the AI investigator and embedding index; simulator and rule engine work offline.

## Step 2: Generate a rich synthetic demo

```powershell
python seed_maintenance_demo.py --reset
```

**WARNING:** `--reset` deletes and recreates **only** `data/maintenance_demo.db` and its SQLite sidecars. It does **not** delete the original `data/plant.db` used by downtime RCA. Do not use reset if you want to keep local maintenance transactions.

Seed scenarios:
- `ASM-BRG-02` degrading bearing vibration → risk escalation and predictive WO.
- `FRM-RECT-01` critical rectifier temperature → urgent predictive WO.
- `ASM-SEN-03` intermittent sensor fault → noisy alarms.
- `FIN-MTR-01` overdue preventive maintenance → PM WO.
- Installed sensor nearing warranty expiry; rectifier fan nearing expected service-life end.
- Spare balances near reorder thresholds.

## Step 3: Launch dashboard

```powershell
streamlit run app.py
```

Your original downtime RCA tabs remain in the top portion of the app. Scroll down to **Predictive & Preventive Maintenance Command Center**.

## Step 4: Make it near real-time

In a **second VS Code terminal**, with the same venv active:

```powershell
python simulate_stream.py --interval 3 --ticks 1000
```

This appends readings to local SQLite every three seconds, updates heuristic risk, opens deduplicated predictive WOs, runs PM and inventory/lifecycle checks. Refresh the Streamlit browser page to see new readings. There is no PLC connection and no push notification service in this version.

## Step 5: Exercise six end-to-end scenarios

### A. Bearing failure warning
1. Simulator controls → asset `ASM-BRG-02` → `degrading` → Apply.
2. Generate 12 ticks.
3. Review Asset health, Work orders, Alerts.
4. Verify one active predictive WO for this asset (repeated ticks do not duplicate it).

### B. Critical formation rectifier
1. Asset `FRM-RECT-02` → `critical`.
2. Generate next tick.
3. Confirm a HIGH/CRITICAL warning and assigned Electrical-team WO.

### C. Spare issue and stock threshold
1. Work orders → select an open WO → choose `RECT-FAN-24V` (or relevant part).
2. Enter quantity `1` and click **Close WO and post confirmed spare consumption**.
3. Verify Parts balance decremented, a stock transaction recorded, and a low-stock alert if balance <= safety stock.
4. **Demo only:** the app permits selecting any part; production must validate asset/part compatibility and require technician confirmation.

### D. Installed spare lifecycle and warranty
1. Close a WO with one spare issued.
2. Inspect Installed parts / lifecycle: `installed_at`, `warranty_end`, `life_end`.
3. Run scheduler to detect items within 30 days of warranty/expected-life dates.
4. Inspect Alerts. Warranty end and expected service-life end are separate concepts.

### E. Preventive maintenance
1. Run scheduler.
2. Find `FIN-MTR-01` preventive WO.
3. Close the WO (no spare required) and verify its `next_due` advances by seven days.
4. Re-run scheduler: the same due cycle does not duplicate.

### F. Stock receipt and alert acknowledgement
1. Parts → receive stock.
2. Verify receipt in stock transaction ledger.
3. Alerts → acknowledge a warning. Acknowledgement does not automatically resolve underlying risk.

## Step 6: Enable SOP RAG and AI Copilot

```powershell
python build_knowledge_index.py
```

This step uses OpenAI embeddings and incurs API usage. It creates `data/maintenance_chroma` locally. The original `agent.py` has been extended with three **read-only** tools:
- `get_predictive_maintenance_status`
- `get_spare_parts_and_pm_status`
- `search_maintenance_manuals_and_sops`

Try these prompts in the AI investigator tab:

- "Review the current bearing vibration anomalies and explain why predictive work orders were created."
- "Which preventive maintenance work orders are overdue, and which teams own them?"
- "Show low-stock parts, current on-hand quantities and replenishment priorities."
- "Which installed parts have warranties or expected life ending within 30 days?"
- "Investigate a formation rectifier temperature warning and cite relevant simulated SOP guidance."

If the knowledge index has not been built, SOP retrieval can fail; build it before asking manual-based questions.

## Step 7: Run automated tests

```powershell
python -m unittest -v test_maintenance.py
```

Tests cover predictive WO deduplication, spare issue and installation metadata, PM idempotence, and rejection of over-issuing inventory. They use an isolated temporary SQLite database.

## File map

| File | Responsibility |
|---|---|
| `maintenance_engine.py` | DB schema, synthetic signals, heuristic risk, alerts, WOs, spare ledger, warranty/lifecycle, PM scheduler |
| `maintenance_ui.py` | Streamlit maintenance dashboard and local demo actions |
| `simulate_stream.py` | Near-real-time background simulator (foreground terminal process) |
| `seed_maintenance_demo.py` | Deterministic scenario setup |
| `test_maintenance.py` | Automated smoke tests |
| `agent.py` | Existing RCA agent + read-only maintenance and SOP tools |
| `knowledge_base.py` | Chroma/OpenAI embedding retrieval |
| `knowledge_base/` | Simulated SOPs and service manual |
| `app.py` | Existing RCA UI + new maintenance UI |
| `data/plant.db` | Original downtime/RCA demo DB |
| `data/maintenance_demo.db` | Maintenance simulator DB, including seeded demo records |

## Data model and logic

`readings(asset_id,ts,signal,value,scenario)` → normalized severity + short trend → risk index 0–100 → WATCH/HIGH/CRITICAL → deduplicated predictive WO and alert.

Risk score is **illustrative and uncalibrated**: 65% normalized current severity + 25% positive trend + 10% persistence bonus, clipped to 0–100. It is **not** an actual failure probability or time-to-failure estimate. A production model requires equipment-specific baseline validation, sensor quality checks, training labels, lead-time analysis and precision/recall/false-alert monitoring.

`work_orders` have OPEN → IN_PROGRESS → CLOSED; `close_work_order()` atomically posts confirmed spare issues and installation metadata. `parts` holds on-hand quantity and safety stock; `stock_transactions` is an immutable ledger of simulated issues/receipts. PM due dates advance on completed PM, not simply on scheduler execution. Alerts are deduplicated by event keys.

## Important production gaps

- No real email, Teams, SMS or CMMS/SAP PM work-order dispatch. Alerts are stored in SQLite and displayed in the app. Add adapters only after authorization, authentication, retry, audit and approval design.
- No role-based access control or approval workflow; anyone with local UI access can close demo WOs. Production requires authenticated technicians, signatures and supervisor approval as appropriate.
- No actual ML failure prediction or remaining useful life model. Use historical run-to-failure and censored maintenance data to train/validate models; measure false alarms, detection lead time, precision and recall.
- No serialized inventory traceability, purchase-order linkage, multi-warehouse reservations, returns, batch/lot verification, or vendor warranty verification.
- The demo auto-creates **local** WOs for high risk, but must not automatically dispatch real work or initiate equipment actions without explicit human-controlled integration policy.
- SQLite is suitable for a single-user demo, not a multi-user plant deployment. Use a transactional DB, durable scheduler, event bus, idempotent integration adapter and observability.
- Maintenance history from original RCA DB is displayed by original tabs but not yet joined into the predictive risk formula. For production, build asset ID normalization and validated failure labels across PLC/MES/historian/CMMS records.
- The UI updates on manual refresh; use Streamlit refresh/polling or a real message push channel for production.

## Suggested phase 2

1. Ingest real OPC UA/MQTT historian events with UTC timestamps and data-quality flags.
2. Map plant asset hierarchy to SAP PM functional locations/equipment IDs.
3. Add isolation forest / gradient-boosted failure classifier only after obtaining adequate labeled historical data; calibrate by asset class.
4. Implement CMMS connector with sandbox first, human approval, idempotency keys, audit and retry.
5. Implement email/Teams alert adapter with escalation matrix and suppression rules.
6. Add serialized spare ID, OEM warranty proof, supplier lead time, reserved stock and reorder point logic.
7. Add SOP metadata (revision, approval, site, equipment applicability) and retrieval authorization.
