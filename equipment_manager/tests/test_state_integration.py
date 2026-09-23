import unittest

from database import Database


class EquipmentStateIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.db = Database("sqlite:///:memory:")
        self.db.save_equipment(
            {
                "equipment_id": "ETCH-01",
                "name": "Etcher 01",
                "owner": "EE-A",
                "criticality": "Critical",
            },
            user="tester",
            workstation="CI",
        )

    def test_creation_generates_initial_state_event(self):
        eq = self.db.get_equipment("ETCH-01")
        self.assertEqual(eq.status, "Available")
        events = self.db.list_equipment_state_events("ETCH-01")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].reason_code, "INITIAL_STATE")
        self.assertEqual(events[0].to_state, "Available")

    def test_master_edit_cannot_bypass_state_workflow(self):
        eq = self.db.get_equipment("ETCH-01")
        self.db.save_equipment(
            {
                "equipment_id": "ETCH-01",
                "name": "Etcher 01A",
                "status": "Down",
                "disposition": "Safety Hold",
            },
            expected_version=eq.version,
            user="tester",
            workstation="CI",
        )
        refreshed = self.db.get_equipment("ETCH-01")
        self.assertEqual(refreshed.name, "Etcher 01A")
        self.assertEqual(refreshed.status, "Available")
        self.assertEqual(refreshed.disposition, "Released")

    def test_state_transition_is_version_checked_and_evented(self):
        eq = self.db.get_equipment("ETCH-01")
        self.db.transition_equipment_state(
            "ETCH-01",
            "Production",
            reason_code="RELEASED",
            reason_text="Initial qualification completed",
            user="engineer",
            workstation="CI",
            expected_version=eq.version,
        )
        running = self.db.get_equipment("ETCH-01")
        self.assertEqual(running.status, "Production")

        self.db.transition_equipment_state(
            "ETCH-01",
            "Down",
            reason_code="FAILURE",
            reason_text="RF generator interlock trip during processing",
            related_ticket="INC-0001",
            owner="EE-A",
            user="engineer",
            workstation="CI",
            expected_version=running.version,
        )
        down = self.db.get_equipment("ETCH-01")
        self.assertEqual(down.status, "Down")

        events = self.db.list_equipment_state_events("ETCH-01")
        self.assertEqual([e.to_state for e in events[:3]], ["Down", "Production", "Available"])
        self.assertTrue(events[0].downtime)
        self.assertEqual(events[0].related_ticket, "INC-0001")

    def test_stale_state_change_is_rejected(self):
        eq = self.db.get_equipment("ETCH-01")
        stale_version = eq.version
        self.db.save_equipment(
            {"equipment_id": "ETCH-01", "name": "Updated"},
            expected_version=stale_version,
        )
        with self.assertRaises(RuntimeError):
            self.db.transition_equipment_state(
                "ETCH-01",
                "Production",
                reason_code="RELEASED",
                reason_text="Release",
                user="engineer",
                expected_version=stale_version,
            )


if __name__ == "__main__":
    unittest.main()
