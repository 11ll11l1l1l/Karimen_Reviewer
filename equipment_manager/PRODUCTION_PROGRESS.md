# Equipment Management System — Production Program Progress

This file is the persistent progress tracker for the full-production roadmap.

## Current baseline

**Program state:** Internal Alpha — connected engineering workflow transformation

**Canonical base main:** `9a904f034d6658a3bbcba4cbf9ec5d07b2532c4c`

**Active development wave:** `ems/internal-alpha-wave4`

The production backend remains intact while the user-facing product is being rebuilt around connected operational workspaces, Office interoperability, evidence capture, maintenance execution, engineering analytics, reporting, logistics, collaboration, configurable workflows and plant-level configuration.

## Milestone status

| Milestone | Status | Current implementation / remaining gate |
|---|---|---|
| M0 Product baseline / UX architecture | **COMPLETE** | Full roadmap, workflow inventory and modular workspace architecture established. |
| M1 Shell / navigation / productivity | **COMPLETE** | Global Search, My Work, recents/favorites, Ctrl+K, back/forward, persistent multi-equipment tabs, account-saved table views and deep routing implemented. |
| M2 Equipment 360 / relationship graph | **AT GATE** | One equipment workspace now combines state, incidents, alarms, PM, work orders, labor, qualification/release, components, meters, parts, documents, handover/disposition, evidence, unified timeline and clickable related records. Remaining compare/collection tools are enhancements, not core gate blockers. |
| M3 Universal evidence / attachments | **AT GATE** | Shared evidence supports multi-file attach, drag/drop, Ctrl+V screenshots, preview, metadata/tags, image annotation, copy-to-record with provenance and integrity hashes across major operational workflows. Remaining richer gallery/bulk attachment management is enhancement work. |
| M4 Excel-first / bulk operations | **AT GATE / ROUND-TRIP CORE COVERED** | Shared tables support copy/XLSX export/saved views. Equipment, inventory and incident/ticket round-trip reconciliation use preview/diff + optimistic conflict protection. PM backlog/spec imports exist. Wave 4 adds controlled qualification protocol/checklist round-trip with revision creation and shift-handover round-trip while protecting lifecycle/acknowledgment fields. Remaining richer per-row conflict resolution and broader optional datasets are enhancement work. |
| M5 PM planning / execution redesign | **IN PROGRESS / STRONG FOUNDATION** | Maintenance Planner provides schedule/calendar/capacity views, bulk assignment/rescheduling, due-window control and parts/cert readiness. Technician Runner provides task-focused checklist, SOP, evidence, work timing, requirement acknowledgment, inline part reservation/consumption and abnormal-result incident creation. Wave 4 adds previous same-tool/same-PM/same-step result history plus numeric trend context. Remaining richer Gantt/drag scheduling and configurable conditional branching. |
| M6 Alarm / incident / RCA / CAPA | **IN PROGRESS / CONNECTED FOUNDATION** | Incident workspace includes containment/SLA, lifecycle, troubleshooting, 5-Why, causal factors, CAPA, recurrence and evidence. Alarm console supports incident linking and deterministic burst correlation. Wave 4 adds persisted plant burst policy, count/window/min-severity thresholds, automatic `ALARM_BURST` workflow trigger, cooldown and continued-alarm linkage to the existing incident. Remaining richer notification/escalation channels and advanced correlation patterns. |
| M7 Work order / qualification / release | **IN PROGRESS / CLOSEOUT CHAIN CONNECTED** | Governed work orders link source incident/PM, labor, evidence, qualification and release. Qualification/release creation is scoped to the work order. Wave 4 adds one-click return-to-service PPTX/XLSX closeout packets combining work scope, source incident, labor, parts, qualification checks/results, release checklist/status, evidence and traceability. Remaining deeper component/repair-part linkage and optional automatic closeout sequencing. |
| M8 Inventory / components / logistics | **IN PROGRESS / LOGISTICS FOUNDATION** | Inventory Logistics workspace supports keyboard/barcode scan lookup, receiving, transfer, cycle count, reorder queue, supplier/barcode catalog, approved substitutes, PM kits and reservations. PM execution consumes/reserves parts inline. Remaining rotable/repairable lifecycle, supplier order workflow and richer kit staging. |
| M9 Shift / My Work / collaboration | **IN PROGRESS / FOUNDATION MET** | My Work, automatic Shift Operations/Handover, record comments, @mentions and watchers are integrated into core workspaces. Remaining richer team queues, activity notification preferences and collaboration filtering. |
| M10 Analytics / engineering intelligence | **IN PROGRESS / INTERACTIVE FOUNDATION** | Engineering Analytics provides fleet reliability/chronic-tool matrix, downtime Pareto, alarm Pareto, incident Pareto, PM compliance charts and drill-down to Equipment 360. Remaining broader trend/control charts, tool comparison and advanced reliability analysis. |
| M11 Office reporting / PPT / Excel / PDF | **IN PROGRESS / REVIEW WORKFLOW STRONG** | Editable PPTX/XLSX packs cover Incident, Equipment 360, PM Execution, Work Orders, Qualification and Release. Wave 4 adds weekly engineering review PPTX/XLSX packs with fleet scorecard, chronic tools, alarm Pareto, critical incidents, PM exceptions and priorities, plus optional site PowerPoint template use and one-click work-order return-to-service packs. Remaining controlled PDF output and report-template administration. |
| M12 Integration Studio / orchestration | **IN PROGRESS / OUTBOUND OPS + RULE ENGINE** | Transactional outbox, FILE/HTTP adapters and Workflow Automation Studio are implemented. Configurable triggers include ALARM_ACTIVE, PM_ABNORMAL_RESULT, QUALIFICATION_APPROVED, RELEASE_APPROVED and Wave 4 ALARM_BURST. Actions include CREATE_INCIDENT, CREATE_WORK_ORDER, CREATE_HANDOVER and SET_DISPOSITION with linked-context propagation. Wave 4 adds integration delivery operations: detailed status, manual dispatch, replay/requeue and dead-letter controls. Remaining inbound connectors, visual mapping/transforms and broader connector/action catalog. |
| M13 Configurable forms / templates | **IN PROGRESS / CORE CONFIGURATION FOUNDATION** | Configuration Studio, configurable reference options, entity templates, typed custom fields and versioned configuration-package import/export are merged. Workflow rules are included in packages. Remaining richer configurable form sections, numbering/SLA/default-owner rules and PM/qualification-specific template administration. |
| M14 Product polish / performance / accessibility | **INCREMENTAL** | Smart shell, workspaces, reduced navigation friction, saved views and task-focused runners substantially improve usability. Full modal-reduction, model/view scaling, accessibility, autosave/recovery and large-data performance pass remain. |
| M15 UAT / pilot / production rollout | **NOT STARTED** | Requires completion of product gates followed by representative plant UAT/pilot. |

## Immediate execution order

1. Keep Wave 4 exact-head core/PostgreSQL/Windows GUI gates green and merge without losing parallel work.
2. Continue M12 with inbound connector architecture, field mapping/transforms, quarantine/replay and idempotent inbound processing.
3. Continue M7 with optional work-order closeout orchestration and deeper parts/component traceability.
4. Continue M5 with richer visual planning/Gantt interactions and configurable abnormal-result branching.
5. Continue M10 with trend/control charts, tool comparison and component/subsystem reliability drilldown.
6. Continue M11 with controlled PDF output and report-template administration.
7. Continue M13 with numbering, SLA/default-owner rules, PM/qualification templates and configurable form sections.
8. Run M14 usability/performance/accessibility sweep after the remaining workflow layers stabilize.
9. Begin M15 only after product milestone acceptance gates are satisfied.

## Reporting rule

Every EMS development update must report:
- Done
- In progress
- Next
- Remaining milestone work
- Regression / CI
- Production readiness

The roadmap file `FULL_PRODUCTION_ROADMAP.md` remains the source of truth for milestone acceptance.
