# Simulated SOP — Material Shortage / Line Starvation
**ID:** SIM-SOP-MAT-001 | **Rev:** 0.1 | **Training / PoC only**

> Never substitute unreleased material or override quality/traceability holds.

**Trigger:** PLC_P009, MES SHORTAGE, low buffer or line starvation.

**Operator / production response**
1. Record line, order, material/lot and time.
2. Check MES order/material status and approved replenishment signals.
3. Identify upstream stoppage, blockage or quality hold.
4. Notify production planning/material handling and supervisor.
5. Do not use unverified or unreleased material.

**Authorized investigation**
1. Verify order, material code, lot and quality-release status.
2. Trace flow from source to point of use.
3. Check buffer and transfer status using approved HMI/work instructions.
4. Inspect conveyors/feeders only under required isolation by authorized personnel.
5. Reconcile physical stock with MES transactions/genealogy.
6. Restore supply only after quality and traceability checks.
7. Verify stable replenishment during controlled restart.
8. Record constraint and preventive-action owner.

**Close-out:** reconcile MES/physical stock, confirm correct lot release and stable flow, maintain traceability.
