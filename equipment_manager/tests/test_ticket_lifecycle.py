import unittest

from database import Database
from domain import TransitionRuleViolation, validate_ticket_transition


class TicketLifecycleRuleTests(unittest.TestCase):
    def test_invalid_jump_is_rejected(self):
        with self.assertRaises(TransitionRuleViolation):
            validate_ticket_transition("Open", "Closed", reason_code="VERIFY_PASS")

    def test_waiting_parts_requires_matching_reason(self):
        with self.assertRaises(TransitionRuleViolation):
            validate_ticket_transition(
                "Assigned", "Waiting Parts",
                reason_code="START_INVESTIGATION",
                owner="EE-A",
            )

    def test_reopen_requires_note(self):
        with self.assertRaises(TransitionRuleViolation):
            validate_ticket_transition(
                "Resolved", "Investigation",
                reason_code="REOPEN",
                owner="EE-A",
            )


class TicketLifecycleIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.db = Database("sqlite:///:memory:")
        self.db.save_equipment({"equipment_id": "ETCH-01", "name": "Etcher"}, user="tester")
        self.db.save_ticket(
            {
                "ticket_no": "INC-0001",
                "equipment_id": "ETCH-01",
                "title": "Vacuum instability",
                "description": "Pressure oscillation during process",
                "severity": "S2",
                "priority": "P2",
                "owner": "",
                "root_cause": "",
                "corrective_action": "",
                "verification": "",
                "created_by": "operator",
            },
            workstation="CI",
        )

    def test_creation_is_evented_and_status_edit_is_blocked(self):
        ticket = self.db.list_tickets()[0]
        self.assertEqual(ticket.status, "Open")
        events = self.db.list_ticket_state_events("INC-0001")
        self.assertEqual(events[0].reason_code, "INITIAL_STATE")

        self.db.save_ticket(
            {
                "ticket_no": "INC-0001",
                "equipment_id": "ETCH-01",
                "title": "Vacuum instability updated",
                "status": "Closed",
                "owner": "",
                "root_cause": "",
                "corrective_action": "",
                "verification": "",
            },
            expected_version=ticket.version,
        )
        updated = self.db.list_tickets()[0]
        self.assertEqual(updated.status, "Open")
        self.assertEqual(updated.title, "Vacuum instability updated")

    def test_full_resolution_and_verification_lifecycle(self):
        ticket = self.db.list_tickets()[0]
        self.db.transition_ticket_state(
            "INC-0001", "Assigned",
            reason_code="ASSIGN",
            owner="EE-A",
            user="lead",
            expected_version=ticket.version,
        )
        ticket = self.db.list_tickets()[0]
        self.db.transition_ticket_state(
            "INC-0001", "Investigation",
            reason_code="START_INVESTIGATION",
            owner="EE-A",
            user="EE-A",
            expected_version=ticket.version,
        )

        ticket = self.db.list_tickets()[0]
        self.db.save_ticket(
            {
                "ticket_no": ticket.ticket_no,
                "equipment_id": ticket.equipment_id,
                "title": ticket.title,
                "description": ticket.description,
                "severity": ticket.severity,
                "priority": ticket.priority,
                "owner": ticket.owner,
                "root_cause": "Loose vacuum fitting",
                "corrective_action": "Reseated fitting and leak checked",
                "verification": "",
            },
            expected_version=ticket.version,
        )

        ticket = self.db.list_tickets()[0]
        self.db.transition_ticket_state(
            "INC-0001", "Resolved",
            reason_code="RESOLVE",
            owner="EE-A",
            user="EE-A",
            expected_version=ticket.version,
        )
        ticket = self.db.list_tickets()[0]
        self.db.transition_ticket_state(
            "INC-0001", "Verification",
            reason_code="VERIFY_START",
            owner="EE-A",
            user="Verifier",
            expected_version=ticket.version,
        )

        ticket = self.db.list_tickets()[0]
        with self.assertRaises(ValueError):
            self.db.transition_ticket_state(
                "INC-0001", "Closed",
                reason_code="VERIFY_PASS",
                owner="EE-A",
                user="Verifier",
                expected_version=ticket.version,
            )

        self.db.save_ticket(
            {
                "ticket_no": ticket.ticket_no,
                "equipment_id": ticket.equipment_id,
                "title": ticket.title,
                "description": ticket.description,
                "severity": ticket.severity,
                "priority": ticket.priority,
                "owner": ticket.owner,
                "root_cause": ticket.root_cause,
                "corrective_action": ticket.corrective_action,
                "verification": "Three production-equivalent verification runs passed",
            },
            expected_version=ticket.version,
        )
        ticket = self.db.list_tickets()[0]
        self.db.transition_ticket_state(
            "INC-0001", "Closed",
            reason_code="VERIFY_PASS",
            owner="EE-A",
            user="Verifier",
            expected_version=ticket.version,
        )
        closed = self.db.list_tickets()[0]
        self.assertEqual(closed.status, "Closed")
        lifecycle = self.db.list_ticket_state_events("INC-0001")
        self.assertEqual(lifecycle[0].to_state, "Closed")
        self.assertEqual(lifecycle[-1].to_state, "Open")


if __name__ == "__main__":
    unittest.main()
