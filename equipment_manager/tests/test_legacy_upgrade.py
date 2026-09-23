import os
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import delete, select

from database import (
    Database, Equipment, EquipmentStateEvent, Ticket, TicketStateEvent,
)


class LegacyUpgradeTests(unittest.TestCase):
    def test_missing_baseline_events_are_backfilled_idempotently(self):
        with tempfile.TemporaryDirectory() as root:
            path=str(Path(root)/"legacy.db")
            url=f"sqlite:///{path}"
            db=Database(url)
            db.save_equipment(
                {"equipment_id":"LEGACY-ETCH","name":"Legacy Etcher","owner":"EE-A"},
                user="seed",
            )
            db.save_ticket({
                "ticket_no":"LEGACY-INC-1",
                "equipment_id":"LEGACY-ETCH",
                "title":"Legacy active issue",
                "description":"Imported issue",
                "severity":"S2",
                "priority":"P2",
                "owner":"EE-A",
                "created_by":"seed",
            })

            # Simulate a pre-governed database: records exist, event tables are empty,
            # and one ticket uses the old free-form "In Progress" state.
            with db.session() as s:
                s.execute(delete(EquipmentStateEvent))
                s.execute(delete(TicketStateEvent))
                ticket=s.scalar(select(Ticket).where(Ticket.ticket_no=="LEGACY-INC-1"))
                ticket.status="In Progress"

            upgraded=Database(url)
            eq_events=upgraded.list_equipment_state_events("LEGACY-ETCH")
            ticket_events=upgraded.list_ticket_state_events("LEGACY-INC-1")
            self.assertEqual(len(eq_events),1)
            self.assertEqual(eq_events[0].reason_code,"INITIAL_STATE")
            self.assertEqual(eq_events[0].changed_by,"system-migration")
            self.assertEqual(len(ticket_events),1)
            self.assertEqual(ticket_events[0].to_state,"Investigation")
            self.assertEqual(upgraded.list_tickets()[0].status,"Investigation")

            # Reopening again must not duplicate migration history.
            reopened=Database(url)
            self.assertEqual(len(reopened.list_equipment_state_events("LEGACY-ETCH")),1)
            self.assertEqual(len(reopened.list_ticket_state_events("LEGACY-INC-1")),1)


if __name__=="__main__":
    unittest.main()
