from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from database import Database
from production_validation import REQUIRED_UAT_SCENARIOS, evaluate_uat, generate_uat_template


class M14M15ReadinessTests(unittest.TestCase):
    def test_uat_template_contains_every_required_role_scenario(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"uat.json"
            payload=generate_uat_template(path)
            self.assertEqual(payload["schema"],"EMS_UAT_EVIDENCE_V1")
            self.assertEqual({x["id"] for x in payload["scenarios"]},{x[0] for x in REQUIRED_UAT_SCENARIOS})
            self.assertTrue(path.is_file())

    def test_incomplete_site_evidence_blocks_release(self):
        with tempfile.TemporaryDirectory() as td:
            payload=generate_uat_template(Path(td)/"uat.json")
            checks=evaluate_uat(payload)
            self.assertTrue(any(x.status=="FAIL" for x in checks))
            self.assertTrue(any(x.name=="uat_signoff" and x.status=="FAIL" for x in checks))

    def test_complete_uat_evidence_can_pass_gate(self):
        with tempfile.TemporaryDirectory() as td:
            payload=generate_uat_template(Path(td)/"uat.json")
            for row in payload["scenarios"]:
                row.update(status="PASS",tester="CI",evidence="test evidence")
            payload["restore_drill"]={"passed":True,"evidence":"restore log"}
            payload["upgrade_rollback"]={"passed":True,"evidence":"rollback log"}
            payload["site_integrations"]={"passed":True,"evidence":"integration certification"}
            payload["training"]={"complete":True,"evidence":"training roster"}
            payload["support_owner"]="EMS Support"
            payload["signoff"]={"approved":True,"approved_by":["Site Owner"],"date":"2026-09-25","notes":""}
            checks=evaluate_uat(payload,max_open_p2=0)
            self.assertTrue(checks)
            self.assertTrue(all(x.status=="PASS" for x in checks))

    def test_timeline_limit_is_bounded(self):
        db=Database("sqlite:///:memory:")
        db.save_equipment({
            "equipment_id":"PERF-01","name":"Performance Tool","equipment_type":"Etch",
            "site":"SITE","building":"B1","floor":"1","area":"ETCH","owner":"eng",
        },user="admin")
        rows=db.equipment_activity_timeline("PERF-01",700)
        self.assertLessEqual(len(rows),700)


if __name__=="__main__":
    unittest.main()
