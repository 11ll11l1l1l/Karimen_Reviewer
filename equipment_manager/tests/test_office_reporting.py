import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook
from pptx import Presentation

from database import Database
from reporting import (
    export_equipment_pptx,export_equipment_xlsx,
    export_incident_pptx,export_incident_xlsx,
    export_pm_execution_pptx,export_pm_execution_xlsx,
    export_work_order_pptx,export_work_order_xlsx,
)


class OfficeReportingTests(unittest.TestCase):
    def setUp(self):
        self.db=Database("sqlite:///:memory:")
        self.db.create_user("ee","Equipment Engineer","engineer-password-123","Equipment Engineer")
        self.db.save_equipment({
            "equipment_id":"ETCH-RPT","name":"Etcher Reporting","equipment_type":"Etch",
            "area":"ETCH","model":"RPT-100","serial_number":"SN-RPT","owner":"ee",
        },user="ee")
        self.ticket=self.db.save_ticket({
            "ticket_no":"INC-RPT-1","equipment_id":"ETCH-RPT","title":"Pressure instability",
            "description":"Pressure oscillation during process","severity":"S2","priority":"P2","owner":"ee",
            "root_cause":"Pending","corrective_action":"Inspect pressure loop","verification":"Pending","created_by":"ee",
        })
        self.db.save_ticket_operational_control(
            self.ticket.ticket_no,
            {"containment":"Tool held","production_impact":"Tool unavailable","affected_lots":"LOT-1",
             "safety_quality_risk":"Potential process drift","response_due_at":None,
             "containment_due_at":None,"resolution_due_at":None},
            "ee",
        )
        self.db.save_incident_why(self.ticket.ticket_no,1,"Why did pressure oscillate?","Control response unstable","ee")
        self.db.save_incident_causal_factor(
            self.ticket.ticket_no,
            {"category":"Machine","factor_type":"Suspected","description":"Pressure controller","evidence":"Trend correlation","status":"Open"},
            "ee",
        )
        self.db.save_incident_action(
            self.ticket.ticket_no,
            {"action_type":"Corrective","description":"Inspect controller","owner":"ee","due_at":None,"effectiveness_criteria":"Stable pressure"},
            "ee",
        )
        self.db.save_pm_definition({
            "pm_id":"PM-RPT","name":"Reporting PM","equipment_id":"ETCH-RPT",
            "schedule_type":"Interval","frequency_value":30,"frequency_unit":"days","anchor_mode":"Original Due",
            "early_window_days":2,"grace_days":1,"estimated_hours":1.0,"required_people":1,
            "required_skill":"","required_parts":"","sop_path":"","active":True,"revision":1,
        })
        self.db.upsert_pm_spec({
            "pm_id":"PM-RPT","step_no":1,"activity":"Pressure check","method":"Gauge",
            "input_type":"Numeric","unit":"Pa","target":5.0,"spec_low":4.0,"spec_high":6.0,
            "acceptance_text":"","reaction_plan":"Investigate","sop_path":"","sop_page":"","sop_section":"",
            "revision":1,"active":True,
        })
        self.pm_task=self.db.upsert_pm_task({
            "equipment_id":"ETCH-RPT","pm_id":"PM-RPT","pm_name":"Reporting PM",
            "original_due_date":None,"scheduled_date":None,"status":"Scheduled","assigned_to":"ee",
            "estimated_hours":1.0,"priority":"Normal","sop_path":"",
        })
        self.pm_execution=self.db.start_pm_execution(self.pm_task.id,"ee")
        self.db.save_pm_result(self.pm_execution.id,1,{
            "value_numeric":5.2,"value_text":"5.2","comment":"Stable","result":"PASS",
            "evidence_path":"","entered_by":"ee",
        })
        self.work_order=self.db.create_work_order({
            "equipment_id":"ETCH-RPT","source_type":"TICKET","source_key":self.ticket.ticket_no,
            "title":"Inspect pressure controller","description":"Investigate and repair pressure instability",
            "priority":"High","owner":"ee","team":"Equipment","qualification_required":False,"release_required":False,
        },"ee","TEST")

    def test_incident_pptx_and_xlsx_are_reopenable(self):
        with tempfile.TemporaryDirectory() as td:
            ppt=Path(td)/"incident.pptx";xlsx=Path(td)/"incident.xlsx"
            export_incident_pptx(self.db,self.ticket.ticket_no,str(ppt))
            export_incident_xlsx(self.db,self.ticket.ticket_no,str(xlsx))
            deck=Presentation(str(ppt))
            self.assertGreaterEqual(len(deck.slides),6)
            wb=load_workbook(str(xlsx),read_only=True)
            self.assertIn("Summary",wb.sheetnames)
            self.assertIn("5-Why",wb.sheetnames)
            self.assertIn("CAPA",wb.sheetnames)

    def test_pm_pptx_and_xlsx_are_reopenable(self):
        with tempfile.TemporaryDirectory() as td:
            ppt=Path(td)/"pm.pptx";xlsx=Path(td)/"pm.xlsx"
            export_pm_execution_pptx(self.db,self.pm_task.id,str(ppt))
            export_pm_execution_xlsx(self.db,self.pm_task.id,str(xlsx))
            deck=Presentation(str(ppt))
            self.assertGreaterEqual(len(deck.slides),5)
            wb=load_workbook(str(xlsx),read_only=True)
            self.assertIn("Summary",wb.sheetnames)
            self.assertIn("Checklist",wb.sheetnames)
            self.assertIn("Requirements",wb.sheetnames)

    def test_work_order_pptx_and_xlsx_are_reopenable(self):
        with tempfile.TemporaryDirectory() as td:
            ppt=Path(td)/"work_order.pptx";xlsx=Path(td)/"work_order.xlsx"
            export_work_order_pptx(self.db,self.work_order.work_order_no,str(ppt))
            export_work_order_xlsx(self.db,self.work_order.work_order_no,str(xlsx))
            deck=Presentation(str(ppt))
            self.assertGreaterEqual(len(deck.slides),4)
            wb=load_workbook(str(xlsx),read_only=True)
            self.assertIn("Summary",wb.sheetnames)
            self.assertIn("Lifecycle",wb.sheetnames)
            self.assertIn("Links",wb.sheetnames)

    def test_equipment_pptx_and_xlsx_are_reopenable(self):
        with tempfile.TemporaryDirectory() as td:
            ppt=Path(td)/"equipment.pptx";xlsx=Path(td)/"equipment.xlsx"
            export_equipment_pptx(self.db,"ETCH-RPT",str(ppt))
            export_equipment_xlsx(self.db,"ETCH-RPT",str(xlsx))
            deck=Presentation(str(ppt))
            self.assertGreaterEqual(len(deck.slides),5)
            wb=load_workbook(str(xlsx),read_only=True)
            self.assertIn("Summary",wb.sheetnames)
            self.assertIn("Activity",wb.sheetnames)
            self.assertIn("Incidents",wb.sheetnames)


if __name__=="__main__":
    unittest.main()
