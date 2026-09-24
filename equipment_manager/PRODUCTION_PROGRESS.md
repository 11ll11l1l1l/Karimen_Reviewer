# Equipment Management System — Production Program Progress

This file is the persistent progress tracker for the full-production roadmap.

## Current baseline

**Program state:** Internal Alpha — connected engineering workflow transformation

**Canonical base main:** `623550a18bb3a4e1db532c21c8f39bbd4348d5ea`

**Active development wave:** `ems/internal-alpha-wave5`

The production backend remains intact while the user-facing product is being rebuilt around connected operational workspaces, Office interoperability, evidence capture, maintenance execution, engineering analytics, reporting, logistics, collaboration, configurable workflows and plant-level configuration.

## Milestone status

| Milestone | Status | Current implementation / remaining gate |
|---|---|---|
| M0 Product baseline / UX architecture | **COMPLETE** | Full roadmap, workflow inventory and modular workspace architecture established. |
| M1 Shell / navigation / productivity | **COMPLETE** | Global Search, My Work, recents/favorites, Ctrl+K, back/forward, persistent multi-equipment tabs, account-saved table views and deep routing implemented. |
| M2 Equipment 360 / relationship graph | **COMPLETE** | Equipment 360 combines state, incidents, alarms, PM, work orders, labor, return-to-service, components, meters, parts, documents, handover/disposition, evidence, unified timeline and directly navigable related records. Wave 5 adds direct qualification/release/timeline routing. |
| M3 Universal evidence / attachments | **COMPLETE** | Shared evidence supports multi-file attach, drag/drop, Ctrl+V screenshots, preview, metadata/tags, annotation, copy-to-record provenance and integrity hashes. Wave 5 adds global Ctrl+Shift+V quick screenshot capture into the active Equipment/Incident/PM/Work Order/Return-to-Service context. |
| M4 Excel-first / bulk operations | **AT GATE / ROUND-TRIP CORE COVERED** | Shared tables support copy/XLSX export/saved views. Equipment, inventory and incident/ticket round-trip reconciliation use preview/diff + optimistic conflict protection. PM backlog/spec imports exist. Wave 4 adds controlled qualification protocol/checklist round-trip with revision creation and shift-handover round-trip while protecting lifecycle/acknowledgment fields. Remaining richer per-row conflict resolution and broader optional datasets are enhancement work. |
| M5 PM planning / execution redesign | **AT GATE** | Maintenance Planner provides schedule/calendar/capacity, bulk assignment/rescheduling, due-window and parts/cert readiness. Wave 5 adds a draggable planning timeline/Gantt-like view with controlled rescheduling. Technician Runner keeps SOP, evidence, work timing, requirements, inline parts and abnormal-result workflow in one task surface. |
| M6 Alarm / incident / RCA / CAPA | **IN PROGRESS / CONNECTED FOUNDATION** | Incident workspace includes containment/SLA, lifecycle, troubleshooting, 5-Why, causal factors, CAPA, recurrence and evidence. Alarm console supports incident linking and deterministic burst correlation. Wave 4 adds persisted plant burst policy, count/window/min-severity thresholds, automatic `ALARM_BURST` workflow trigger, cooldown and continued-alarm linkage to the existing incident. Remaining richer notification/escalation channels and advanced correlation patterns. |
| M7 Work order / qualification / release | **AT GATE** | Work orders link source incident/PM, labor, evidence, qualification and release. Wave 5 adds guided Advance Closeout sequencing, approved-release closeout gating, and a unified Return-to-Service workspace with inline qualification checks/evidence plus release precheck/checklist/verification/approval and PPTX/XLSX/PDF reporting. |
| M8 Inventory / components / logistics | **IN PROGRESS / LOGISTICS FOUNDATION** | Inventory Logistics workspace supports keyboard/barcode scan lookup, receiving, transfer, cycle count, reorder queue, supplier/barcode catalog, approved substitutes, PM kits and reservations. PM execution consumes/reserves parts inline. Remaining rotable/repairable lifecycle, supplier order workflow and richer kit staging. |
| M9 Shift / My Work / collaboration | **AT GATE** | My Work, automatic handover, comments, @mentions and watchers are integrated. Wave 5 upgrades My Work into a filtered action center with explicit mention acknowledgment, watchlist activity and a live header badge. Remaining notification preferences/team-channel refinements are enhancements. |
| M10 Analytics / engineering intelligence | **AT GATE** | Engineering Analytics includes chronic-tool/fleet reliability, downtime/alarm/incident Pareto, PM compliance, Wave 5 fleet time-series trends, selected-tool comparison and meter/condition trends with drill-down/exportable tables. Advanced statistical reliability models remain enhancement work. |
| M11 Office reporting / PPT / Excel / PDF | **AT GATE** | Editable PPTX/XLSX packs cover core workflows and weekly reviews. Wave 5 adds centrally configured site PowerPoint templates automatically resolved by report/equipment context plus native controlled PDF packs for Equipment, Incident, PM, Work Order, Qualification, Release and Weekly Review. |
| M12 Integration Studio / orchestration | **IN PROGRESS / OUTBOUND OPS + RULE ENGINE** | Transactional outbox, FILE/HTTP adapters and Workflow Automation Studio are implemented. Configurable triggers include ALARM_ACTIVE, PM_ABNORMAL_RESULT, QUALIFICATION_APPROVED, RELEASE_APPROVED and Wave 4 ALARM_BURST. Actions include CREATE_INCIDENT, CREATE_WORK_ORDER, CREATE_HANDOVER and SET_DISPOSITION with linked-context propagation. Wave 4 adds integration delivery operations: detailed status, manual dispatch, replay/requeue and dead-letter controls. Remaining inbound connectors, visual mapping/transforms and broader connector/action catalog. |
| M13 Configurable forms / templates | **IN PROGRESS / POLICY ENGINE ADDED** | Configuration Studio, reference options, entity templates, typed custom fields and configuration packages remain. Wave 5 adds concurrent-safe configurable numbering schemes, default-owner rules, SLA policies and guided policy administration; these policies now drive new tickets/work orders/qualification runs. Richer form sections and additional PM/qualification template UX remain. |
| M14 Product polish / performance / accessibility | **IN PROGRESS** | Wave 5 adds non-blocking success feedback, global Quick Create (Ctrl+N), global screenshot capture (Ctrl+Shift+V), live My Work count, direct deep navigation and replacement of legacy qualification/release routing with Return-to-Service. Large-data model/view scaling, accessibility and autosave/recovery remain. |
| M15 UAT / pilot / production rollout | **NOT STARTED** | Requires completion of product gates followed by representative plant UAT/pilot. |

## Immediate execution order

1. Freeze Wave 5 code and run the consolidated EMS-only validation cycle.
2. Fix any unit/PostgreSQL/Windows/PySide6/packaging regressions found on the exact Wave 5 head.
3. Merge Wave 5 only when the final exact code-bearing head is green.
4. Continue M8 rotable/repairable lifecycle and supplier/order workflow.
5. Continue M13 configurable form sections and PM/qualification template UX.
6. Continue M14 large-data model/view scaling, accessibility, draft recovery and remaining modal reduction.
7. Begin M15 representative plant UAT/pilot only after the remaining product gates are closed.

## EMS development execution policy

**This policy applies only to the Equipment Management System. It does not change BibleQuest development or testing rules.**

- Implement the planned EMS code wave first.
- Do not stop after each individual feature solely to run regression/CI.
- Use targeted checks during coding only when they are required to resolve a coding uncertainty.
- When the wave is substantially complete, run one consolidated validation cycle covering unit/regression, PostgreSQL integration/concurrency, Windows/PySide6 GUI smoke and packaging/startup where affected.
- Fix the consolidated failures as a batch.
- Merge only when the final exact code-bearing head is green.
- Testing is deferred within the wave, not removed from the Definition of Done.

## Reporting rule

Every EMS development update must report:
- Done
- In progress
- Next
- Remaining milestone work
- Regression / CI
- Production readiness

The roadmap file `FULL_PRODUCTION_ROADMAP.md` remains the source of truth for milestone acceptance.
