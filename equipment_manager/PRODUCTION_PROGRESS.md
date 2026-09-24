# Equipment Management System — Production Program Progress

This file is the persistent progress tracker for the full-production roadmap.

## Current baseline

**Program state:** Internal Alpha — connected engineering workflow transformation

**Current main:** `041810cded3979c8247d8c85d39fa50c1d10f111`

**Active development wave:** `ems/internal-alpha-wave2-reconciled`

The production backend remains intact while the user-facing product is being rebuilt around connected operational workspaces, Office interoperability, universal evidence, planning/execution and cross-feature orchestration.

## Milestone status

| Milestone | Status | Current implementation / remaining gate |
|---|---|---|
| M0 Product baseline / UX architecture | **COMPLETE** | Full roadmap, workflow inventory and modular workspace architecture established. |
| M1 Shell / navigation / productivity | **COMPLETE** | Global Search, My Work, recents/favorites, Ctrl+K, back/forward, persistent multi-equipment tabs, account-saved table column views and deep routing implemented. Acceptance intent met. |
| M2 Equipment 360 / relationship graph | **AT GATE** | Equipment 360 now combines state, incidents, alarms, PM, work orders, labor, qualification/release, components, meters, parts, documents, handover/disposition, evidence, unified timeline and clickable related records. Remaining: richer compare/collection tools are enhancement rather than core gate blockers. |
| M3 Universal evidence / attachments | **AT GATE** | Reusable evidence panel supports multi-file attach, drag/drop, Ctrl+V screenshots, preview, metadata/tags, image annotation, copy-to-record with provenance and integrity hashes across major operational workflows. Remaining: richer gallery/bulk attachment management. |
| M4 Excel-first / bulk operations | **IN PROGRESS** | Shared tables support copy/XLSX export/saved views. Import Studio with preview/mapping/saved mappings now covers PM, equipment master and inventory; bulk equipment/inventory edits exist. Remaining: true round-trip diff/reconciliation and expansion to qualification/tickets/handover. |
| M5 PM planning / execution redesign | **IN PROGRESS** | Maintenance Planner has schedule/calendar/capacity views, bulk assign/reschedule, due-window control, parts/cert readiness. Technician PM Runner has task-focused checklist, SOP, evidence, work timing, abnormal-result incident creation, in-run part reservation/consumption. Remaining: richer Gantt/drag scheduling, previous-value/trend context and deeper conditional branching. |
| M6 Alarm / incident / RCA / CAPA | **IN PROGRESS** | Structured Incident Workspace includes summary, containment/SLA, lifecycle, troubleshooting, 5-Why, causal factors, CAPA/actions, recurrence and evidence. Alarm console can now create/link/open incidents directly. Alarm burst correlation service now groups adjacent alarms deterministically, preserves raw alarm IDs, ranks severity, and is covered by regression tests. Burst incident creation now validates a single-equipment scope, selects the highest-severity source for incident priority, links every source alarm, and rejects incompatible pre-linked incidents. Alarm Console now exposes a Correlated Bursts tab, burst incident creation, and a user-configurable correlation window. Remaining: persist plant-specific defaults and add automatic burst escalation/notifications. |
| M7 Work order / qualification / release | **IN PROGRESS** | Governed Work Order model/lifecycle/links added with source conversion from ticket/PM, My Work/Search/Equipment 360 integration, labor/evidence workspace and direct incident/PM routing. Closeout readiness is now scoped to qualification/release records explicitly linked to the work order, preventing cross-job leakage on shared equipment. Remaining: automatic qualification/release packet orchestration and richer parts/component linkage. |
| M8 Inventory / components / logistics | **NOT STARTED AS REDESIGN** | Strong inventory/component backend plus PM inline parts workflow exists; barcode/receiving/transfer/kits/substitutes/logistics workspace remain. |
| M9 Shift / My Work / collaboration | **IN PROGRESS / HANDOVER + COLLABORATION FOUNDATION MET** | My Work and Shift Operations automatically assemble actionable work. Reusable record comments, @mentions, watchers and My Work mention routing are now integrated into Equipment 360, Incident, Work Order and PM Execution. Remaining: richer activity notifications, team queues and collaboration preferences. |
| M10 Analytics / engineering intelligence | **NOT STARTED AS REDESIGN** | Reliability metrics exist; interactive charts/Pareto/trends/drill-down workbench remains. |
| M11 Office reporting / PPT / Excel / PDF | **IN PROGRESS** | One-click editable PPTX/XLSX packs now cover Incident, Equipment 360, PM Execution and Work Orders with evidence slides and structured worksheets. Remaining: Qualification/Release packs, site-defined templates and controlled PDF output. |
| M12 Integration Studio / orchestration | **IN PROGRESS** | Transactional outbox/adapters plus a Workflow Automation Studio now support configurable ALARM_ACTIVE, PM_ABNORMAL_RESULT, QUALIFICATION_APPROVED and RELEASE_APPROVED triggers with CREATE_INCIDENT, CREATE_WORK_ORDER, CREATE_HANDOVER and SET_DISPOSITION actions, idempotent execution history and templates. Remaining: inbound connectors, visual field mapping/transforms, replay/dead-letter tools and broader action catalog. |
| M13 Configurable forms / templates | **NOT STARTED** | Major gap. |
| M14 Product polish / performance / accessibility | **INCREMENTAL** | Smart shell/workspaces substantially improve usability; full performance/accessibility/modal-reduction pass remains. |
| M15 UAT / pilot / production rollout | **NOT STARTED** | Requires product milestones and site pilot. |

## Immediate execution order

1. Keep the reconciled Wave 2 head green and merge it into main.
2. Close M4 round-trip reconciliation expansion for qualification/checklists and ticket/handover bulk workflows.
3. Continue M5 with technician previous-result/trend context and richer planning timeline/Gantt interaction.
4. Continue M6 with automatic burst escalation/notifications and richer direct operational-control editing.
5. Continue M7 with automatic work-order → qualification → release packet orchestration.
6. Extend M11 with Qualification/Release packs, controlled PDF output and site-defined PowerPoint templates.
7. Continue M12 with inbound connectors, visual mapping/transforms and replay/dead-letter operations.
8. Continue M9 with team queues and richer activity/notification preferences.

## Reporting rule

Every EMS development update must report:
- Done
- In progress
- Next
- Remaining milestone work
- Regression / CI
- Production readiness

The roadmap file `FULL_PRODUCTION_ROADMAP.md` remains the source of truth for milestone acceptance.
