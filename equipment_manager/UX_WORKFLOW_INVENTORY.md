# EMS UX / Workflow Migration Inventory

This inventory closes M0 by mapping the current user-facing application into the full-production workspace model. It prevents future work from adding isolated CRUD pages without a defined product destination.

| Current surface | Current responsibility | Target production surface | Milestone | Disposition |
|---|---|---|---|---|
| Login / First Admin | Authentication/bootstrap | Application shell | M1 | Retain, polish only |
| SmartDashboardPage / DashboardPage | Counts and exception queue | Operations Command Center | M1/M9/M10 | Rebuild incrementally |
| EquipmentPage | Master data, components, meters, state history | Equipment 360 + Registry Admin | M2 | Operational use moves to Equipment 360; registry remains for bulk/master administration |
| LayoutPage / SmartLayoutPage | FAB map | Equipment 360 / Live FAB Map | M2 | Retain and deep-link |
| PMPage Definitions | PM configuration | Maintenance Planning Studio | M5/M13 | Rebuild |
| PMPage Backlog | PM schedule/execution launch | Maintenance Planning Studio / My Work | M5 | Rebuild |
| PMPage Checklist/Specs | PM step definitions | PM Template Editor | M5/M13 | Rebuild |
| PMPage Requirements | PM prerequisites | PM Template Editor / execution runner | M5 | Rebuild |
| PMPage Deferrals | Deferral approvals | My Work / Maintenance Planning | M5/M9 | Integrate |
| PM Usage/Condition Triggers | Automatic PM generation | PM Template Editor / Integration & Rules | M5/M12 | Integrate |
| PMExecutionDialog | Checklist execution | Technician PM Runner | M5 | Replace modal workflow |
| TicketPage | Incident list and lifecycle | Incident / RCA Workspace | M6 | Rebuild |
| TicketDialog | Ticket editing | Incident Workspace inline editor | M6 | Replace modal workflow |
| TicketStateDialog | Lifecycle transition | Incident contextual actions | M6 | Replace modal workflow |
| InvestigationDialog | Troubleshooting step | Investigation timeline / RCA workspace | M6 | Replace modal workflow |
| TicketOperationalControlDialog | Containment/SLA | Incident Workspace | M6 | Replace modal workflow |
| AlarmPage | Alarm history/Pareto | Alarm Console + Equipment 360 | M6/M10 | Rebuild |
| QualificationPage | Protocols and runs | Qualification Studio / Runner | M7/M13 | Rebuild |
| Qualification dialogs | Protocol/result workflow | Qualification Runner / Template Editor | M7 | Replace modal workflow |
| ControlPage | Disposition/release | Equipment 360 + Release Packet | M7 | Integrate |
| WorkLogPage | Labor start/stop | Active Work dock / Work Order | M7/M9 | Rebuild |
| EndorsementPage | Manual shift handover | Shift Operations Board | M9 | Rebuild |
| InventoryPage | Parts/locations/reservations | Parts & Logistics + inline work execution | M8 | Rebuild |
| DocumentPage | Linked/controlled files | Document Center + inline SOP/evidence preview | M3/M5/M13 | Rebuild |
| ReliabilityPage | Reliability table | Engineering Analytics Workbench | M10 | Replace table-only experience |
| AdminPage users/scopes/certs | Administration | Administration Studio | M13/M14 | Reorganize |
| Admin integration tab | Outbox/endpoints | Integration Studio | M12 | Move/rebuild |
| Backup/admin tools | Operational support | System Operations | M15 | Retain |
| Global search (new) | Cross-entity lookup | Application shell | M1 | New foundation |
| My Work (new) | Personal queue | Application shell | M1/M9 | New foundation |
| Equipment 360 (new) | Cross-feature equipment workspace | Equipment 360 | M2 | New foundation |
| AttachmentPanel (new) | Universal evidence | Shared platform service | M3 | New foundation |
| Excel Import Studio (new) | Mapping/preview | Shared Office productivity service | M4 | New foundation |

## Global interaction standards

All rebuilt production surfaces must converge on these patterns:

- Global search and deep links rather than manual module traversal.
- Persistent workspace context with back/forward history.
- Inline or side-panel editing for frequent actions; modal dialogs reserved for short confirmations or exceptional decisions.
- Universal evidence panel with drag/drop, Ctrl+V screenshot, preview, metadata and provenance.
- Excel copy/export on all tables and Import Studio for bulk workflows.
- Related records shown as clickable entities, never only as opaque text IDs.
- My Work for assignments, verification, approvals and escalations.
- Equipment 360 as the primary operational context for tool-specific work.
- Configurable templates/rules instead of area-specific source-code forks.
- One shared activity timeline model for important operational events.
- Consistent empty/loading/error states and non-blocking feedback.

## M0 acceptance

Every current primary user-facing surface is mapped above to a target production workspace or retained administrative responsibility. The new architecture is already reflected in the Smart shell through Global Search, My Work, Equipment 360, reusable evidence and shared Office productivity utilities.

**M0 status: COMPLETE.**
