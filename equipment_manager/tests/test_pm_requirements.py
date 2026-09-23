import unittest
from datetime import datetime, timedelta

from database import Database


class PMRequirementTests(unittest.TestCase):
    def setUp(self):
        self.db=Database("sqlite:///:memory:")
        self.db.create_user("tech","Maintenance Tech","maintenance-password-123","Maintenance")
        self.db.save_equipment({"equipment_id":"ETCH-01","name":"Etcher"},user="tech")
        self.db.upsert_pm_spec({
            "pm_id":"PM-001","step_no":1,"activity":"Visual inspection","input_type":"Pass / Fail","revision":1,"active":True,
        })
        self.db.upsert_pm_requirement({
            "requirement_id":"PM001-CERT","pm_id":"PM-001","requirement_type":"CERTIFICATION",
            "requirement_key":"LOTO-ETCH","description":"Current LOTO qualification","mandatory":True,"active":True,
        })
        self.db.upsert_pm_requirement({
            "requirement_id":"PM001-LOTO","pm_id":"PM-001","requirement_type":"LOTO",
            "requirement_key":"LOCKOUT","description":"Apply lockout/tagout before chamber access","mandatory":True,"active":True,
        })
        self.db.upsert_pm_requirement({
            "requirement_id":"PM001-TOOL","pm_id":"PM-001","requirement_type":"TOOL",
            "requirement_key":"TORQUE-WRENCH","description":"Calibrated torque wrench available","mandatory":True,"active":True,
        })
        due=datetime(2026,9,23)
        self.task=self.db.upsert_pm_task({
            "equipment_id":"ETCH-01","pm_id":"PM-001","pm_name":"Chamber PM",
            "original_due_date":due,"scheduled_date":due,"status":"Scheduled",
        })

    def test_missing_certification_blocks_pm_start(self):
        with self.assertRaises(PermissionError):
            self.db.start_pm_execution(self.task.id,"tech")

    def test_valid_certification_allows_start_and_freezes_requirements(self):
        self.db.save_technician_certification({
            "username":"tech","cert_code":"LOTO-ETCH","issuer":"EHS",
            "issued_at":datetime.utcnow()-timedelta(days=30),
            "expires_at":datetime.utcnow()+timedelta(days=335),"active":True,
        })
        ex=self.db.start_pm_execution(self.task.id,"tech")
        reqs=self.db.list_pm_execution_requirements(ex.id)
        self.assertEqual({r.requirement_id for r in reqs},{"PM001-CERT","PM001-LOTO","PM001-TOOL"})

        self.db.upsert_pm_requirement({
            "requirement_id":"PM001-TOOL","pm_id":"PM-001","requirement_type":"TOOL",
            "requirement_key":"NEW-TOOL","description":"Newer requirement","mandatory":True,"active":True,
        },create_revision=True)
        frozen=self.db.list_pm_execution_requirements(ex.id)
        tool=next(r for r in frozen if r.requirement_id=="PM001-TOOL")
        self.assertEqual(tool.requirement_key,"TORQUE-WRENCH")

    def test_completion_requires_mandatory_acknowledgements(self):
        self.db.save_technician_certification({
            "username":"tech","cert_code":"LOTO-ETCH","issuer":"EHS",
            "expires_at":datetime.utcnow()+timedelta(days=30),"active":True,
        })
        ex=self.db.start_pm_execution(self.task.id,"tech")
        self.db.save_pm_result(ex.id,1,{
            "value_text":"Pass","value_numeric":None,"entered_by":"tech",
        })
        with self.assertRaises(ValueError):
            self.db.complete_pm_execution(ex.id,"tech")
        self.db.acknowledge_pm_requirement(ex.id,"PM001-LOTO","tech","Locks verified")
        self.db.acknowledge_pm_requirement(ex.id,"PM001-TOOL","tech","Calibration sticker valid")
        completed=self.db.complete_pm_execution(ex.id,"tech")
        self.assertEqual(completed.status,"Completed")

    def test_expired_certification_is_rejected(self):
        self.db.save_technician_certification({
            "username":"tech","cert_code":"LOTO-ETCH","issuer":"EHS",
            "expires_at":datetime.utcnow()-timedelta(days=1),"active":True,
        })
        with self.assertRaises(PermissionError):
            self.db.start_pm_execution(self.task.id,"tech")


if __name__=="__main__":
    unittest.main()
