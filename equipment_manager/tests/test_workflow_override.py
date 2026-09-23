import unittest

from database import Database


class WorkflowOverrideTests(unittest.TestCase):
    def setUp(self):
        self.db=Database("sqlite:///:memory:")
        self.db.create_user("manager","Manager","manager-password-123","Manager")
        self.db.create_user("engineer","Engineer","engineer-password-123","Equipment Engineer")
        self.db.save_equipment({"equipment_id":"ETCH-01","name":"Etcher","owner":"engineer"},user="manager")

    def test_normal_user_cannot_use_override(self):
        eq=self.db.get_equipment("ETCH-01")
        with self.assertRaises(PermissionError):
            self.db.transition_equipment_state(
                "ETCH-01","Decommissioned",
                reason_code="DECOMMISSION",
                reason_text="Exceptional test",
                user="engineer",expected_version=eq.version,
                override=True,override_reason="Emergency disposition",
            )

    def test_override_requires_reason(self):
        eq=self.db.get_equipment("ETCH-01")
        with self.assertRaises(ValueError):
            self.db.transition_equipment_state(
                "ETCH-01","Decommissioned",
                reason_code="DECOMMISSION",
                reason_text="Exceptional test",
                user="manager",expected_version=eq.version,
                override=True,
            )

    def test_manager_override_is_audited(self):
        eq=self.db.get_equipment("ETCH-01")
        self.db.transition_equipment_state(
            "ETCH-01","Decommissioned",
            reason_code="DECOMMISSION",
            reason_text="Equipment retired outside normal sequence",
            user="manager",expected_version=eq.version,
            override=True,override_reason="Approved emergency retirement",
        )
        audit=self.db.list_audit(20)
        hit=next(x for x in audit if x.action=="STATE_TRANSITION_OVERRIDE")
        self.assertIn("Approved emergency retirement",hit.detail)


if __name__=="__main__":
    unittest.main()
