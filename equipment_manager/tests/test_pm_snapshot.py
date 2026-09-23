import unittest
from datetime import datetime

from database import Database


class PMSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.db = Database("sqlite:///:memory:")
        self.db.save_equipment({"equipment_id": "ETCH-01", "name": "Etcher"}, user="tester")
        self.db.upsert_pm_spec({
            "pm_id": "PM-CHAMBER",
            "step_no": 1,
            "activity": "Verify chamber pressure",
            "method": "Gauge reading",
            "input_type": "Numeric",
            "unit": "Pa",
            "spec_low": 0.0,
            "spec_high": 10.0,
            "revision": 1,
            "active": True,
        })
        self.task = self.db.upsert_pm_task({
            "equipment_id": "ETCH-01",
            "pm_id": "PM-CHAMBER",
            "pm_name": "Chamber PM",
            "original_due_date": datetime(2026, 9, 23),
            "scheduled_date": datetime(2026, 9, 23),
            "status": "Scheduled",
        })

    def test_execution_freezes_spec_revision(self):
        ex = self.db.start_pm_execution(self.task.id, "tech_a")
        frozen = self.db.list_pm_execution_specs(ex.id)
        self.assertEqual(len(frozen), 1)
        self.assertEqual(frozen[0].source_revision, 1)
        self.assertEqual(frozen[0].spec_high, 10.0)

        self.db.upsert_pm_spec({
            "pm_id": "PM-CHAMBER",
            "step_no": 1,
            "activity": "Verify chamber pressure",
            "method": "Gauge reading",
            "input_type": "Numeric",
            "unit": "Pa",
            "spec_low": 0.0,
            "spec_high": 5.0,
            "active": True,
        }, create_revision=True)

        active = self.db.list_pm_specs("PM-CHAMBER")
        self.assertEqual(active[0].revision, 2)
        self.assertEqual(active[0].spec_high, 5.0)

        still_frozen = self.db.list_pm_execution_specs(ex.id)
        self.assertEqual(still_frozen[0].source_revision, 1)
        self.assertEqual(still_frozen[0].spec_high, 10.0)

    def test_database_recalculates_result_from_frozen_spec(self):
        ex = self.db.start_pm_execution(self.task.id, "tech_a")
        result = self.db.save_pm_result(
            ex.id,
            1,
            {
                "value_text": "15",
                "value_numeric": 15.0,
                "result": "PASS",
                "entered_by": "tech_a",
            },
        )
        self.assertEqual(result.result, "SPECIFICATION FAILURE")
        with self.assertRaises(ValueError):
            self.db.complete_pm_execution(ex.id, "tech_a")

    def test_mid_execution_revision_does_not_change_acceptance_limit(self):
        ex = self.db.start_pm_execution(self.task.id, "tech_a")
        self.db.upsert_pm_spec({
            "pm_id": "PM-CHAMBER",
            "step_no": 1,
            "activity": "Verify chamber pressure",
            "method": "Gauge reading",
            "input_type": "Numeric",
            "unit": "Pa",
            "spec_low": 0.0,
            "spec_high": 5.0,
            "active": True,
        }, create_revision=True)

        result = self.db.save_pm_result(
            ex.id,
            1,
            {
                "value_text": "8",
                "value_numeric": 8.0,
                "result": "FAIL",
                "entered_by": "tech_a",
            },
        )
        self.assertEqual(result.result, "PASS")
        completed = self.db.complete_pm_execution(ex.id, "tech_a")
        self.assertEqual(completed.status, "Completed")

    def test_unknown_execution_step_is_rejected(self):
        ex = self.db.start_pm_execution(self.task.id, "tech_a")
        with self.assertRaises(ValueError):
            self.db.save_pm_result(
                ex.id,
                99,
                {"value_text": "1", "value_numeric": 1.0, "result": "PASS", "entered_by": "tech_a"},
            )


if __name__ == "__main__":
    unittest.main()
