# Equipment Management System — Production Program Progress

This file is the persistent progress tracker for the full-production roadmap.

## Current baseline

**Program state:** Internal Alpha — connected engineering workflow transformation

**Canonical base main:** `19c149f9bf8a0804284987e4559dac11f51a3439`

**Active development wave:** `ems/internal-alpha-wave6`

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
| M6 Alarm / incident / RCA / CAPA | **AT GATE** | Incident workspace includes containment/SLA, lifecycle, troubleshooting, 5-Why, causal factors, CAPA, recurrence and evidence. Alarm burst correlation and workflow triggering are configurable. Wave 6 adds persistent user notifications for escalation with direct record navigation and autosaved/recoverable incident drafts. Advanced statistical/alarm-pattern correlation remains enhancement work. |
| M7 Work order / qualification / release | **AT GATE** | Work orders link source incident/PM, labor, evidence, qualification and release. Wave 5 adds guided Advance Closeout sequencing, approved-release closeout gating, and a unified Return-to-Service workspace with inline qualification checks/evidence plus release precheck/checklist/verification/approval and PPTX/XLSX/PDF reporting. |
| M8 Inventory / components / logistics | **AT GATE** | Inventory Logistics supports scan lookup, receiving, transfer, cycle count, reorder, catalog/substitutes, PM reservations and inline PM consumption. Wave 6 adds governed supplier purchase orders with line-level partial receipt, serialized rotable/repairable lifecycle and vendor repair history, plus PM kit staging/issue/completion states. |
| M9 Shift / My Work / collaboration | **AT GATE** | My Work, automatic handover, comments, @mentions and watchers are integrated. Wave 5 added the action center and live badge. Wave 6 adds a persistent Notification Center, unread badge, read/dismiss state and direct deep links for escalations/work-order ownership events. Team-channel/external notification preferences remain optional enhancements. |
| M10 Analytics / engineering intelligence | **AT GATE** | Engineering Analytics includes chronic-tool/fleet reliability, downtime/alarm/incident Pareto, PM compliance, Wave 5 fleet time-series trends, selected-tool comparison and meter/condition trends with drill-down/exportable tables. Advanced statistical reliability models remain enhancement work. |
| M11 Office reporting / PPT / Excel / PDF | **AT GATE** | Editable PPTX/XLSX packs cover core workflows and weekly reviews. Wave 5 adds centrally configured site PowerPoint templates automatically resolved by report/equipment context plus native controlled PDF packs for Equipment, Incident, PM, Work Order, Qualification, Release and Weekly Review. |
| M12 Integration Studio / orchestration | **AT GATE** | Transactional outbound FILE/HTTP, workflow rule engine, replay/dead-letter operations and inbound FILE_JSON/FILE_CSV ingestion for ALARM/METER are implemented with validation, quarantine and idempotency. Wave 6 adds a dedicated Integration Studio with field-by-field mappings, non-mutating sample preview, feed processing, receipt/record inspection and replay. Protocol-specific MES/SECS-GEM/FDC adapters remain site integration work/enhancements. |
| M13 Configurable forms / templates | **AT GATE** | Configuration Studio includes reference options, templates, typed custom fields, numbering/owner/SLA/report policies and configuration packages. Wave 6 adds configurable form sections, field placement/help/placeholder metadata, grouped runtime rendering, V2 package portability, PM-definition templates and qualification-protocol templates. |
| M14 Product polish / performance / accessibility | **IN PROGRESS / RECOVERY ADDED** | Wave 5 adds Quick Create, Quick Screenshot, live My Work count and deep navigation. Wave 6 adds persistent per-user autosaved drafts with restore/discard for Incident/RCA and editable Work Order details, plus notifications and dedicated integration/logistics workspaces. Remaining primary gate: large-data model/view scaling, accessibility pass and further modal reduction. |
| M15 UAT / pilot / production rollout | **NOT STARTED** | Requires completion of product gates followed by representative plant UAT/pilot. |

## Immediate execution order

1. Run the consolidated Wave 6 EMS-only validation cycle now that feature coding is substantially complete.
2. Fix Wave 6 unit/schema/PostgreSQL/Windows/PySide6/packaging regressions as one batch.
3. Merge Wave 6 only when the final exact code-bearing head is green.
4. Continue M14 large-data model/view scaling, accessibility and remaining modal reduction.
5. Begin M15 representative plant UAT/pilot after remaining product gates are accepted.

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
