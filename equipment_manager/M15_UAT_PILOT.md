# EMS M15 Site UAT and Pilot Runbook

This runbook is the production gate for the Equipment Management System. Software CI can prove code behavior; it cannot certify the plant LAN, SMB permissions, endpoint security, users, the selected data topology, integrations, or operational fit. Those items require evidence from the actual site.

## Entry criteria

- M0-M14 software acceptance gates are closed or have an explicitly accepted exception.
- The exact candidate commit has green EMS core, serverless synchronization fixtures, Windows GUI and Windows package jobs; optional PostgreSQL jobs remain green where supported.
- Production preflight returns no FAIL checks on every pilot workstation.
- A verified backup exists and a scratch restore has succeeded.
- The pilot equipment group, users, support owner and rollback owner are named.

## Required role scenarios

Use EMSCLI.exe uat-template <path> to create the controlled JSON evidence file. Every required scenario must be marked PASS with tester and evidence.

- UAT-EE-01 — Equipment Engineer: alarm -> incident -> containment -> RCA/CAPA -> work order -> qualification -> release.
- UAT-MT-01 — Maintenance Technician: PM execution with frozen controlled revision, measurement entry, evidence, parts and abnormal-result handling.
- UAT-OP-01 — Operator: alarm acknowledgement, tool-state context, incident link/create and shift handover.
- UAT-PE-01 — Process Engineer: qualification evidence review and independent verification.
- UAT-SL-01 — Shift Leader: automatically assembled handover, edit/contextualize, publish and next-shift acknowledgement.
- UAT-EM-01 — Equipment Manager: reliability/Pareto review, weekly report pack, action queue and drill-down.
- UAT-DC-01 — Document Controller: revision creation, independent approval, effective/superseded state and tamper detection.
- UAT-AD-01 — Administrator: role/scope, configurable form/template, workflow rule and integration mapping.
- UAT-RTS-01 — Independent Approver: verify segregation of requester/verifier/approver and final return-to-service.
- UAT-OFFICE-01 — Engineer: Excel export/edit/re-import preview/diff and editable PPTX/PDF report creation.
- UAT-REC-01 — Site Admin: create/verify backup and complete scratch restore drill.
- UAT-RES-01 — Site Admin: temporary shared-folder interruption, clear error state and client recovery without silent local success.
- UAT-MW-01 — Site Team: two-workstation concurrent edit with conflict detection and controlled retry.

## Pilot execution

Run against a limited real equipment group before general rollout. Record the exact EMS build, database schema, workstation names, pilot equipment, users and integrations. Compare task duration and duplicate manual work against the current process for PM execution, incident closure, shift handover and weekly reporting.

Daily pilot triage must classify defects as P0/P1/P2/P3. P0 and P1 block release. The allowed open P2 threshold is an explicit site decision and is passed to the readiness command rather than hard-coded.

## Failure and recovery exercises

The pilot must include client restart during an unfinished draft; unavailable SMB/shared state; stale concurrent edit from two workstations; write-lease contention; crash after local commit before shared publish; inbound integration bad payload/quarantine/replay; backup verification; scratch restore; upgrade rehearsal; rollback to the preserved prior application build. Optional PostgreSQL deployments must additionally test database outage/reconnect.

## Release command

After the evidence JSON is complete, run:

    EMSCLI.exe production-readiness --uat-evidence C:\EMS\uat-evidence.json --report C:\EMS\production-readiness.json --max-open-p2 0

Exit code 0 means every hard software/site gate represented by the command passed. A nonzero exit blocks release. The generated report is retained with the release package and UAT evidence.

## Production signoff

Release requires no open P0/P1, P2 at/below the agreed threshold, restore drill PASS, rollback rehearsal PASS, site integrations PASS, training complete, named support owner, all required role scenarios PASS, and explicit site signoff in the UAT evidence file.
