import json
import unittest

from database import Database


CHECKS = {
    "maintenance_complete": True,
    "measurements_pass": True,
    "calibration_valid": True,
    "safety_check": True,
    "verification_run": True,
    "critical_tickets_cleared": True,
}


class ReleaseControlTests(unittest.TestCase):
    def setUp(self):
        self.db = Database("sqlite:///:memory:")
        self.db.save_equipment(
            {"equipment_id": "ETCH-01", "name": "Etcher", "owner": "EE-A"},
            user="creator",
            workstation="CI",
        )

    def test_release_requires_independent_approver(self):
        request = self.db.create_release_request(
            "ETCH-01",
            "",
            CHECKS,
            "Post-maintenance release",
            "engineer_a",
            workstation="CI",
        )
        verified = self.db.verify_release(
            request.id,
            CHECKS,
            "engineer_a",
            expected_version=request.version,
            workstation="CI",
        )
        self.assertEqual(verified.status, "Verified")

        with self.assertRaises(ValueError):
            self.db.approve_release(
                verified.id,
                "engineer_a",
                expected_version=verified.version,
                workstation="CI",
            )

        approved = self.db.approve_release(
            verified.id,
            "manager_b",
            expected_version=verified.version,
            workstation="CI",
        )
        self.assertEqual(approved.status, "Approved / Released")
        self.assertEqual(approved.approved_by, "manager_b")
        eq = self.db.get_equipment("ETCH-01")
        self.assertEqual(eq.disposition, "Released")

    def test_incomplete_verification_cannot_be_approved(self):
        request = self.db.create_release_request(
            "ETCH-01", "", CHECKS, "", "engineer_a", workstation="CI"
        )
        failed = dict(CHECKS)
        failed["verification_run"] = False
        verified = self.db.verify_release(
            request.id,
            failed,
            "engineer_a",
            expected_version=request.version,
            workstation="CI",
        )
        self.assertEqual(verified.status, "Verification Failed")
        with self.assertRaises(ValueError):
            self.db.approve_release(
                verified.id,
                "manager_b",
                expected_version=verified.version,
                workstation="CI",
            )

    def test_release_actions_are_audited(self):
        request = self.db.create_release_request(
            "ETCH-01", "", CHECKS, "release", "engineer_a", workstation="WS-1"
        )
        verified = self.db.verify_release(
            request.id, CHECKS, "engineer_a", request.version, workstation="WS-2"
        )
        self.db.approve_release(
            verified.id, "manager_b", verified.version, workstation="WS-3"
        )
        audit = self.db.list_audit(20)
        actions = {row.action for row in audit}
        self.assertTrue({"RELEASE_REQUEST", "RELEASE_VERIFY", "RELEASE_APPROVE"}.issubset(actions))


if __name__ == "__main__":
    unittest.main()
