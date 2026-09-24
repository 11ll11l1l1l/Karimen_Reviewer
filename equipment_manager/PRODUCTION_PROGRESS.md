# Equipment Management System — Production Program Progress

This file is the persistent progress tracker for the full-production roadmap.

## Current baseline

**Program state:** Internal Alpha — connected engineering workflow transformation

**Current main:** `041810cded3979c8247d8c85d39fa50c1d10f111`

**Active development wave:** `ems/internal-alpha-wave3`

The production backend remains intact while the user-facing product is being rebuilt around connected operational workspaces, Office interoperability, universal evidence, planning/execution, collaboration, configurable local fields/templates, and cross-feature orchestration.

## Milestone status

| Milestone | Status | Current implementation / remaining gate |
|---|---|---|
| M0 Product baseline / UX architecture | **COMPLETE** | Roadmap, workflow inventory and modular workspace architecture established. |
| M1 Shell / navigation / productivity | **COMPLETE** | Global Search, My Work, recents/favorites, Ctrl+K, back/forward, persistent multi-equipment tabs, account-saved table views, actionable command-center drill-through, last-workspace and window restoration. |
| M2 Equipment 360 / relationship graph | **AT GATE** | State, incidents, alarms, PM, work orders, labor, qualification/release, components, meters, parts, documents, handover/disposition, evidence, discussion, custom fields, unified timeline and related-record navigation are consolidated. Richer tool comparison/collections remain enhancement work. |
| M3 Universal evidence / attachments | **AT GATE** | Multi-file attach, drag/drop, Ctrl+V screenshots, preview, metadata/tags, image annotation, copy-to-record provenance and integrity hashes are available across the major operational workspaces. Richer gallery/bulk attachment management remains. |
| M4 Excel-first / bulk operations | **IN PROGRESS** | Shared tables support copy/XLSX export/saved views. Import Studio + saved mappings covers PM, equipment and inventory; reconciliation guards and bulk equipment/inventory updates exist; Qualification Runner supports controlled multi-row clipboard result paste. Ticket/handover round-trip workflows remain. |
| M5 PM planning / execution redesign | **AT GATE** | Planner includes schedule/calendar/capacity, bulk assign/reschedule, due-window control and parts/cert readiness. Technician runner includes frozen checklist, SOP context, evidence, work timing, abnormal-result incident creation, work-order linkage and in-run part reservation/consumption. Richer drag/Gantt planning and historical trend context remain. |
| M6 Alarm / incident / RCA / CAPA | **AT GATE** | Incident Workspace includes containment/SLA, troubleshooting, 5-Why, causal factors, CAPA/effectiveness, recurrence, evidence and team discussion. Alarm burst correlation is deterministic, raw IDs are preserved, correlated bursts create one linked incident, and alarm→incident workflows can be automated. Richer fishbone visualization and recurrence intelligence remain. |
| M7 Work order / qualification / release | **AT GATE** | Governed Work Orders connect source ticket/PM, labor, evidence, closeout, qualification and release. New task-focused Qualification Runner provides frozen checks, check inspector, bulk result paste, evidence, discussion, custom fields, submit/verify/approve/reject and Office reporting. Remaining: modern dedicated release workspace and deeper component/part closeout visualization. |
| M8 Inventory / components / logistics | **IN PROGRESS** | Dedicated Logistics workspace includes scanner lookup, receiving, transfer, cycle count, reorder queue, part catalog/supplier/barcode/lead-time data, approved substitutes, PM kit readiness and reservation. Remaining: repairable/rotable lifecycle and stronger purchasing/vendor flow. |
| M9 Shift / My Work / collaboration | **AT GATE** | My Work plus automatic Shift Operations candidate assembly are implemented. Persistent comments, @mentions, watchers and unread record notifications feed back into My Work and are embedded in Equipment, Incident, PM and Work Order workspaces. Remaining: richer team queues/subscriptions and collaboration reporting. |
| M10 Analytics / engineering intelligence | **IN PROGRESS** | Engineering Analytics provides fleet reliability/chronic-tool matrix, downtime/alarm/incident Pareto, PM compliance, drill-down and bounded time-series trends for availability, unplanned downtime and failures. Remaining: tool-to-tool comparison, subsystem/component breakdown and advanced reliability analysis. |
| M11 Office reporting / PPT / Excel / PDF | **AT GATE** | Editable PPTX/XLSX packs now cover incidents, Equipment 360, PM execution, Work Orders, Qualification, Release and fleet Engineering Review. Long tables paginate and `EMS_PPT_TEMPLATE` supports site PowerPoint templates. Remaining: PDF output and richer site-defined section/template controls. |
| M12 Integration Studio / orchestration | **IN PROGRESS** | Visual Integration Studio provides endpoint configuration, controlled field-mapping revisions, payload preview, delivery monitor, retry/dead-letter replay, inbound receipt monitoring and declarative rules. Outbound FILE/HTTP mappings execute at dispatch; inbound events are idempotent; a LAN JSON drop adapter quarantines processed/duplicate/rejected files; rules can perform alarm→incident, incident→work-order and controlled disposition actions exactly once. Remaining: specialized SECS/GEM/MES/FDC/ERP adapters, richer transformations and more governed rule actions. |
| M13 Configurable forms / templates | **IN PROGRESS** | Configuration Studio provides scoped custom fields and reusable record templates. Scoped definitions override global defaults. Configured fields are embedded in Equipment, Incident and Work Order; engineering work-order creation can use equipment-type templates. Remaining: configurable reason codes, form sections, approval/workflow templates and broader entity template adoption. |
| M14 Product polish / performance / accessibility | **IN PROGRESS** | Smart shell/workspaces substantially reduce CRUD navigation; command-center items are actionable, incident edits have debounced crash-recovery drafts, and per-user window/last-workspace state is restored. Remaining: high-volume model/view conversion, accessibility pass, modal reduction, background loading and realistic performance/soak targets. |
| M15 UAT / pilot / production rollout | **NOT STARTED** | Requires completed product gates plus real-site LAN/PostgreSQL/SMB pilot and role-based UAT. |

## Done in Wave 3

- Collaboration comments, @mentions, watchers and My Work notification routing.
- Expanded Office reporting and site PowerPoint template support.
- Deterministic alarm-correlation ordering regression fix.
- Integration Studio, mapping revisions, dead-letter/replay, inbound idempotency and LAN drop adapter.
- Declarative exactly-once alarm→incident→work-order and controlled-disposition orchestration.
- Configuration Studio, scoped custom fields and record templates.
- Fleet reliability trends and engineering-review PPTX/XLSX.
- Incident draft recovery and Smart-shell workspace/window recovery.
- Modern Qualification Runner and direct qualification routing.
- Actionable Operations Command Center drill-through.

## In progress

- Exact-head CI validation for the newest Wave 3 commits.
- Continued M10/M12/M13/M14 gate closure.
- Reconciliation against `main` before merge if parallel changes land.

## Next

1. Fix any exact-head CI regression and merge Wave 3 once green.
2. Add a dedicated modern Release workspace and close M7 user-flow gaps.
3. Extend custom configuration to reason codes/workflow/approval templates.
4. Add tool comparison and subsystem/component analytics.
5. Continue M14 with model/view scalability, background loading and accessibility.
6. Prepare M15 executable site-acceptance/UAT pack after product gates stabilize.

## Remaining milestone work

Production release still requires the remaining M4/M7/M8/M10/M12/M13/M14 gaps plus M15 real-site validation. A milestone is not complete merely because a backend API exists; the acceptance gate in `FULL_PRODUCTION_ROADMAP.md` remains authoritative.

## Regression / CI

Wave 3 contains dedicated tests for collaboration, Office report packs, Integration Studio/orchestration, inbound drop processing and Configuration Studio in addition to the existing PostgreSQL, Windows GUI and packaging gates. Intermediate Wave 3 heads through the Qualification/recovery foundation have completed successfully; the newest head must be green before merge.

## Production readiness

**Current classification: Internal Alpha.**

The program is substantially beyond the original CRUD prototype, but it is not yet a Production Candidate. M15 UAT/pilot has not started.

## Reporting rule

Every EMS development update must report:
- Done
- In progress
- Next
- Remaining milestone work
- Regression / CI
- Production readiness

The roadmap file `FULL_PRODUCTION_ROADMAP.md` remains the source of truth for milestone acceptance.
