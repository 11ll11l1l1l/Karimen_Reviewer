import unittest
from datetime import datetime, timedelta

from database import Database


class ApprovalDelegationTests(unittest.TestCase):
    def setUp(self):
        self.db=Database("sqlite:///:memory:")
        self.db.create_user("manager","Manager","manager-password-123","Manager")
        self.db.create_user("delegate","Delegate","delegate-password-123","Read Only")
        self.db.create_user("requester","Requester","requester-password-123","Equipment Engineer")
        self.db.create_user("verifier","Verifier","verifier-password-123","Process Engineer")
        self.db.save_equipment({"equipment_id":"ETCH-01","name":"Etcher"},user="manager")
        self.db.save_equipment({"equipment_id":"CVD-01","name":"CVD"},user="manager")

    def test_scoped_delegation_grants_exact_permission(self):
        row=self.db.create_approval_delegation(
            "manager","delegate","release.approve",
            datetime.utcnow()+timedelta(days=2),
            "Manager on planned leave","manager",
            scope_type="EQUIPMENT",scope_key="ETCH-01",
        )
        self.assertTrue(self.db.delegated_permission("delegate","release.approve","ETCH-01"))
        self.assertFalse(self.db.delegated_permission("delegate","release.approve","CVD-01"))
        self.db.assert_authorized("delegate","release.approve","ETCH-01")
        with self.assertRaises(PermissionError):
            self.db.assert_authorized("delegate","release.approve","CVD-01")

    def test_sensitive_permissions_cannot_be_delegated(self):
        for permission in ["user.admin","workflow.override"]:
            with self.assertRaises(ValueError):
                self.db.create_approval_delegation(
                    "manager","delegate",permission,
                    datetime.utcnow()+timedelta(days=1),"No","manager"
                )

    def test_revocation_removes_grant(self):
        row=self.db.create_approval_delegation(
            "manager","delegate","release.approve",
            datetime.utcnow()+timedelta(days=1),"Coverage","manager"
        )
        self.db.revoke_approval_delegation(row.id,"manager","Returned to duty")
        self.assertFalse(self.db.delegated_permission("delegate","release.approve","ETCH-01"))

    def test_expired_delegation_not_active(self):
        with self.assertRaises(ValueError):
            self.db.create_approval_delegation(
                "manager","delegate","release.approve",
                datetime.utcnow()-timedelta(minutes=1),"Invalid window","manager"
            )

    def test_delegated_release_approval_still_respects_separation_of_duties(self):
        self.db.create_approval_delegation(
            "manager","delegate","release.approve",
            datetime.utcnow()+timedelta(days=1),"Coverage","manager",
            scope_type="EQUIPMENT",scope_key="ETCH-01",
        )
        checks={
            "maintenance_complete":True,"measurements_pass":True,"calibration_valid":True,
            "safety_check":True,"verification_run":True,"critical_tickets_cleared":True,
        }
        req=self.db.create_release_request("ETCH-01","",checks,"Ready","requester")
        verified=self.db.verify_release(req.id,checks,"verifier",req.version)
        approved=self.db.approve_release(verified.id,"delegate",verified.version)
        self.assertEqual(approved.approved_by,"delegate")


if __name__=="__main__":
    unittest.main()
