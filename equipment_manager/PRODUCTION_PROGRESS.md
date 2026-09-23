# Equipment Management System — Production Program Progress

This file is the persistent progress tracker for the full-production roadmap.

## Current baseline

**Program state:** Internal Alpha — connected engineering workflow transformation

**Current main:** `23446f359239926618e6915d3cccefa396226dca`

**Active development wave:** `ems/internal-alpha-wave2`

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
| M7 Work order / qualification / release | **IN PROGRESS** | Governed Work Order model/lifecycle/links added with source conversion from ticket/PM, My Work/Search/Equipment 360 integration, labor/evidence workspace and direct incident/PM routing. Remaining: automatic qualification/release packet orchestration and richer parts/component linkage. |
| M8 Inventory / components / logistics | **NOT STARTED AS REDESIGN** | Strong inventory/component backend plus PM inline parts workflow exists; barcode/receiving/transfer/kits/substitutes/logistics workspace remain. |
| M9 Shift / My Work / collaboration | **IN PROGRESS / HANDOVER GATE MET** | My Work exists and the new Shift Operations workspace automatically assembles candidates from abnormal states, incidents, alarms, PM, work orders, qualification/release and restrictions; supervisors can bulk publish/acknowledge with evidence. Comments/@mentions/watchers remain. |
| M10 Analytics / engineering intelligence | **NOT STARTED AS REDESIGN** | Reliability metrics exist; interactive charts/Pareto/trends/drill-down workbench remains. |
| M11 Office reporting / PPT / Excel / PDF | **IN PROGRESS** | One-click editable PPTX/XLSX incident review and Equipment 360 review packs are implemented, including evidence slides and structured data sheets. Site templates, PM/qualification/release packs and PDF output remain. |
| M12 Integration Studio / orchestration | **PARTIAL FOUNDATION** | Transactional outbox/adapters exist; visual mapping, inbound connectors, replay/dead-letter tools and configurable orchestration rules remain. |
| M13 Configurable forms / templates | **NOT STARTED** | Major gap. |
| M14 Product polish / performance / accessibility | **INCREMENTAL** | Smart shell/workspaces substantially improve usability; full performance/accessibility/modal-reduction pass remains. |
| M15 UAT / pilot / production rollout | **NOT STARTED** | Requires product milestones and site pilot. |

## Immediate execution order

1. Keep Wave 2 green and merge the connected PM/alarm/work-order changes.
2. Close M4 round-trip Excel diff/reconciliation for equipment and inventory, then expand to qualification/checklists.
3. Continue M5 with technician result history/trends and planner timeline/Gantt interaction.
4. Continue M6 with alarm grouping/correlation and direct incident operational-control editing.
5. Continue M7 with automatic work-order → qualification → release packet orchestration.
6. Start M10 engineering analytics workbench with native interactive trends/Pareto/drill-down.
7. Extend M11 report packs to PM, work order, qualification/release and site-defined PowerPoint templates.
8. Start M8 logistics redesign only after M5/M7 part flows stabilize.

## Reporting rule

Every EMS development update must report:
- Done
- In progress
- Next
- Remaining milestone work
- Regression / CI
- Production readiness

The roadmap file `FULL_PRODUCTION_ROADMAP.md` remains the source of truth for milestone acceptance.
