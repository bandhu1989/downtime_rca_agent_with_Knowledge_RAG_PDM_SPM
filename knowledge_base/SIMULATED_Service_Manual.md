# Simulated Equipment Service & Troubleshooting Manual
**Document ID:** SIM-SM-001 | **Revision:** 0.1 | **Status:** Training / PoC only

> SAFETY NOTICE: This is a simulated learning document, not an OEM manual or approved site SOP. It contains no validated electrical values, torque settings, PLC parameters, rectifier recipes, isolation points or restart criteria. Never use it to authorize work. Real interventions require current approved OEM documentation, site procedures, LOTO, permits and competent-person authorization.

## Common rules
- Protect people first. Escalate smoke, fire, exposed conductors, unusual heat/noise, damaged guarding or uncertain hazardous conditions.
- Operators perform only tasks allowed by their training and site procedures.
- Intrusive electrical/mechanical work requires authorized personnel and applicable isolation/LOTO.
- Never defeat guards, interlocks, emergency stops or protective trips.
- Do not repeatedly reset a trip without identifying the cause.
- Record event ID, asset, alarm, timestamps, symptoms, actions, procedure revision and verification.
- AI guidance is advisory; a qualified person validates asset-specific applicability and authorizes work.

## 1. Motor overload
**PoC signature:** PLC_A102; elevated `motor_current`; maintenance code may be MTR-OVER.

**Possible causes:** excessive driven load/jam; bearing, coupling, belt or gearbox issue; motor/drive electrical fault; process overload; measurement fault.

**Operator observations:** record alarm/time/machine state; observe from safe position for abnormal noise, smell, visible obstruction or vibration; check HMI and upstream/downstream status. Do not open panels, remove guards, reach into equipment or repeatedly reset. Notify authorized maintenance.

**Authorized maintenance checks:** consult asset-specific OEM procedure; apply approved shutdown and LOTO before intrusive inspection; inspect mechanical load path for binding/damage/lubrication issues; authorized electrical specialist reviews motor, drive, cable and protection records; compare findings with approved nameplate/configuration/engineering limits; repair using approved instructions and parts; restore guards and complete authorized return-to-service checks; perform controlled test and monitor trend.

**Prohibited:** increasing overload settings to suppress trips; bypassing relay/drive protection/interlocks; unauthorized electrical testing; restarting with unknown cause.

**Verification:** cause and work order documented; protective devices/guards intact; controlled test accepted; trend within approved limits; authorized owner accepts return-to-service.

## 2. Bearing vibration
**PoC signature:** PLC_M241; elevated `vibration_mm_s`; maintenance code may be MECH-VIB.

**Possible causes:** bearing wear; lubrication issue; misalignment, looseness or imbalance; mounting/foundation issue; process-induced vibration; sensor mounting fault.

**Operator observations:** record alarm/time/load/speed changes; observe from safe distance for noise, heat indication, leakage or movement; do not touch rotating equipment or lubricate/adjust unless explicitly permitted; escalate severe or worsening vibration.

**Authorized maintenance checks:** apply approved isolation/LOTO before intrusive work; review trends under comparable operating conditions; inspect bearing housing, mounting, lubrication, coupling and alignment per OEM; verify sensor mounting/instrument health; use approved measurement methods and OEM criteria; repair under approved work instruction; reassemble, guard, obtain authorization and record post-work readings.

**Prohibited:** unapproved lubricant/quantity; adjusting rotating assemblies while energized; diagnosing bearing failure from one reading alone; operating with severe vibration pending assessment.

**Verification:** measurement method and operating condition recorded; cause/action in CMMS; post-work trend accepted by reliability; no abnormal noise/temperature/repeat alarm during controlled test.

## 3. Sensor misread / photoeye fault
**PoC signature:** PLC_S017; abnormal `photoeye_transitions_min`; maintenance code may be SENS-CHK.

**Possible causes:** dirty/obstructed optical path; misalignment; damaged sensor/reflector/cable; unstable supply/noise; incorrect target presentation; input mapping/configuration issue.

**Operator observations:** record sensor tag/alarm/time/product condition; observe target path from outside guarded areas; perform external cleaning only if site procedure explicitly permits; do not enter guarded zones, disconnect wiring or force PLC inputs; escalate unexpected machine motion.

**Authorized maintenance checks:** isolate/LOTO before entering hazardous zones; confirm sensor tag against drawings/I/O list; inspect lens, reflector, bracket, cable and connector; verify supply and PLC input using authorized methods; check alignment/target distance/configuration against OEM; correct fault without bypassing/forcing inputs; test representative targets under approved commissioning procedure; record evidence and obtain production acceptance.

**Prohibited:** forcing I/O, bridging wiring, defeating guards, changing PLC logic/configuration without approved change control.

**Verification:** correct tag confirmed; sensor detects approved test targets; PLC/HMI agrees with physical state; no temporary bypass remains; work/change records complete.

## 4. Material shortage / line starvation
**PoC signature:** PLC_P009; MES material status SHORTAGE; low `buffer_level_pct`; maintenance code may be MAT-FEED.

**Possible causes:** upstream process stopped; low buffer/replenishment delay; material not released/staged; transfer equipment fault; inventory/status mismatch.

**Operator/production observations:** record line/order/material/lot/time; check MES status and approved replenishment signals; identify upstream stoppage or quality hold; notify production/material handling; do not substitute unreleased material.

**Authorized investigation:** verify order, material code, lot and quality release; trace flow from source to point of use; check buffer/transfer status through approved HMI/work instructions; inspect conveyors/feeders only under required isolation by authorized personnel; reconcile physical stock and MES genealogy; restore supply only after quality/traceability confirmation; verify stable flow during controlled restart; assign systemic constraint owner.

**Prohibited:** using unverified material; bypassing quality holds/traceability; reaching into conveyors without isolation; falsifying MES transactions.

**Verification:** correct material/lot released; physical and MES quantities reconciled; flow stable; traceability maintained; preventive action owner assigned.

## 5. Rectifier overtemperature
**PoC signature:** PLC_E330; elevated `rectifier_temp_c`; maintenance code may be RECT-TEMP.

**Possible causes:** airflow restriction/fan failure; high ambient temperature; damaged/loose connection; internal component fault; excessive duty/load; temperature sensor fault.

**Operator observations:** record rectifier ID/alarm/temperature indication/mode/time; observe from safe distance for blocked external airflow, abnormal fan noise, smoke or smell; follow approved alarm response; do not open covers, touch terminals, change charging settings or repeatedly reset; escalate smoke/burning smell/visible damage.

**Authorized electrical checks:** follow OEM shutdown and site electrical LOTO/permit; verify isolation and stored-energy controls using approved methods; inspect ventilation path/filters/fans per OEM; authorized specialist checks connections, cooling components, internal condition and event logs; validate sensing and duty against approved OEM/site criteria; repair with approved parts; do not alter protective settings; conduct approved functional test and monitor temperature trend.

**Prohibited:** opening energized enclosure; bypassing thermal protection; changing charging recipes/current limits/trip values to suppress alarm; restarting without authorized assessment.

**Verification:** cause/work documented; cooling and sensing verified; protection intact; controlled test accepted; temperature trend monitored.

## Agent retrieval rules
1. Retrieve only approved, current, site/asset-applicable documents in real deployment.
2. Show title, ID, revision and relevant section for every instruction.
3. Separate operator observations from authorized maintenance tasks.
4. Never invent values, settings, torque, isolation points, acceptance limits or restart criteria.
5. If no procedure is found, say so and direct the user to the supervisor and controlled OEM/site document system.
6. Never advise bypassing safety devices or claim equipment is safe to restart.
7. Treat retrieved instructions as reference, not work authorization.
