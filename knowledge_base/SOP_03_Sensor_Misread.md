# Simulated SOP — Sensor / Photoeye Misread
**ID:** SIM-SOP-SNS-001 | **Rev:** 0.1 | **Training / PoC only**

> Never force PLC I/O, bridge wiring, bypass guarding or change logic/settings outside approved change control.

**Trigger:** PLC_S017, abnormal photoeye transitions or missed product detection.

**Operator response**
1. Record sensor tag, alarm, time, product and line condition.
2. Observe target path from outside guarded areas.
3. Check visible contamination only if external cleaning is permitted.
4. Report repeated false counts or unexpected motion immediately.
5. Do not enter conveyors/guarded zones, disconnect wiring or force PLC inputs.

**Authorized maintenance**
1. Stop/isolate and apply LOTO before entering hazardous zones.
2. Confirm sensor tag against approved drawings and I/O list.
3. Inspect lens, reflector, bracket, cable and connector.
4. Verify supply and PLC input using authorized test methods.
5. Check alignment, target distance and configuration against OEM settings.
6. Correct fault without bypassing or forcing I/O.
7. Test representative targets under approved commissioning procedure.
8. Record evidence and obtain production acceptance.

**Close-out:** confirm physical detection agrees with HMI/PLC; no bypass remains; update work/change records.
