import os
import unittest

from database import Database
from demo_data import DEMO_FIXTURE_CODE, seed_demo_data


class FullDemoFixtureTests(unittest.TestCase):
    def setUp(self):
        self.db=Database("sqlite:///:memory:")
        self.db.create_user("demo_admin","Demo Admin","demo-admin-password-123","Administrator")
        self.old_allow=os.environ.get("EMS_ALLOW_DEMO_SEED")
        os.environ["EMS_ALLOW_DEMO_SEED"]="1"

    def tearDown(self):
        if self.old_allow is None:
            os.environ.pop("EMS_ALLOW_DEMO_SEED",None)
        else:
            os.environ["EMS_ALLOW_DEMO_SEED"]=self.old_allow

    def test_full_fixture_populates_cross_domain_demo_and_is_idempotent(self):
        result=seed_demo_data(self.db,"demo_admin")
        self.assertEqual(result["errors"],[],result)
        self.assertTrue(result["changed"])
        self.assertGreaterEqual(len(self.db.list_equipment()),28)
        self.assertGreaterEqual(len(self.db.list_tickets()),5)
        self.assertGreaterEqual(len(self.db.list_work_orders()),3)
        self.assertTrue(self.db.list_pm_tasks())
        self.assertTrue(self.db.list_pm_usage_triggers())
        self.assertTrue(self.db.list_pm_condition_triggers())
        self.assertTrue(self.db.list_reservations())
        self.assertTrue(self.db.list_supplier_orders())
        self.assertTrue(self.db.list_rotables())
        self.assertTrue(self.db.list_qualification_runs())
        verified=next(x for x in self.db.list_qualification_runs("FAB-MET-07") if x.run_no=="DEMO-QUAL-RUN-VERIFIED")
        self.assertEqual(verified.status,"Verified")
        releases=self.db.list_release_requests("FAB-WET-06")
        self.assertTrue(releases)
        self.assertEqual(releases[0].status,"Verified")
        self.assertTrue(self.db.list_endorsements())
        self.assertTrue(self.db.list_controlled_documents())
        effective=self.db.effective_controlled_revision("DEMO-SOP-PM-001")
        self.assertIsNotNone(effective)
        self.assertEqual(effective.status,"Effective")
        self.assertTrue(self.db.list_attachments("TICKET","DEMO-ISSUE-001"))
        self.assertIsNotNone(self.db.get_user_draft("demo_admin","TICKET","DEMO-ISSUE-001","summary"))
        self.assertEqual(self.db.equipment_dependency_snapshot("FAB-PVD-04")["location_status"],"OK")
        marker=[x for x in self.db.list_config_options("DEMO_FIXTURE",active_only=False) if x.code==DEMO_FIXTURE_CODE]
        self.assertEqual(len(marker),1)

        second=seed_demo_data(self.db,"demo_admin")
        self.assertFalse(second["changed"])
        self.assertEqual(second["errors"],[])


if __name__=="__main__":
    unittest.main()
