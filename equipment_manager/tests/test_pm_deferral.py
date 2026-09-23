import unittest
from datetime import datetime, timedelta

from database import Database


class PMDeferralWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.db = Database("sqlite:///:memory:")
        self.db.save_equipment({"equipment_id":"ETCH-01","name":"Etcher"},user="tester")
        due=datetime(2026,9,23)
        self.task=self.db.upsert_pm_task({
            "equipment_id":"ETCH-01",
            "pm_id":"PM-001",
            "pm_name":"Quarterly chamber PM",
            "original_due_date":due,
            "scheduled_date":due,
            "status":"Scheduled",
        })

    def test_request_does_not_change_due_date_until_approved(self):
        requested=self.task.original_due_date+timedelta(days=7)
        row=self.db.request_pm_deferral(
            self.task.id,
            requested,
            "Production cannot release tool",
            "Extension adds wear risk but no safety exposure",
            "Daily pressure verification and restricted recipe set",
            "engineer_a",
            workstation="CI",
            expected_task_version=self.task.version,
        )
        task=self.db.get_pm_task(self.task.id)
        self.assertEqual(row.status,"Pending")
        self.assertEqual(task.status,"Scheduled")
        self.assertEqual(task.scheduled_date,self.task.original_due_date)

    def test_requester_cannot_approve_own_deferral(self):
        row=self.db.request_pm_deferral(
            self.task.id,
            self.task.original_due_date+timedelta(days=3),
            "No production window",
            "Low risk",
            "Daily check",
            "engineer_a",
            expected_task_version=self.task.version,
        )
        with self.assertRaises(ValueError):
            self.db.review_pm_deferral(row.id,True,"engineer_a",expected_version=row.version)

    def test_independent_approval_updates_schedule_and_history(self):
        requested=self.task.original_due_date+timedelta(days=5)
        row=self.db.request_pm_deferral(
            self.task.id,
            requested,
            "Vendor part delay",
            "Seal degradation risk",
            "Daily leak check; stop if trend worsens",
            "engineer_a",
            workstation="WS-A",
            expected_task_version=self.task.version,
        )
        approved=self.db.review_pm_deferral(
            row.id,
            True,
            "supervisor_b",
            "Risk controls accepted for five-day extension",
            workstation="WS-B",
            expected_version=row.version,
        )
        self.assertEqual(approved.status,"Approved")
        task=self.db.get_pm_task(self.task.id)
        self.assertEqual(task.status,"Deferred")
        self.assertEqual(task.scheduled_date,requested)
        self.assertIn("Vendor part delay",task.deferral_reason)
        actions={a.action for a in self.db.list_audit(20)}
        self.assertIn("PM_DEFERRAL_REQUEST",actions)
        self.assertIn("PM_DEFERRAL_APPROVE",actions)

    def test_rejection_leaves_pm_schedule_unchanged(self):
        row=self.db.request_pm_deferral(
            self.task.id,
            self.task.original_due_date+timedelta(days=2),
            "No window",
            "Risk present",
            "Extra checks",
            "engineer_a",
            expected_task_version=self.task.version,
        )
        self.db.review_pm_deferral(
            row.id,False,"supervisor_b","Risk not acceptable",expected_version=row.version
        )
        task=self.db.get_pm_task(self.task.id)
        self.assertEqual(task.status,"Scheduled")
        self.assertEqual(task.scheduled_date,self.task.original_due_date)

    def test_second_pending_request_is_blocked(self):
        self.db.request_pm_deferral(
            self.task.id,
            self.task.original_due_date+timedelta(days=2),
            "No window","Risk","Checks","engineer_a",
            expected_task_version=self.task.version,
        )
        with self.assertRaises(ValueError):
            self.db.request_pm_deferral(
                self.task.id,
                self.task.original_due_date+timedelta(days=3),
                "Still no window","Risk","Checks","engineer_c",
                expected_task_version=self.task.version,
            )


if __name__=="__main__":
    unittest.main()
