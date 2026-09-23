import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook
from pptx import Presentation

from database import Database
from reporting import (
    export_equipment_pptx,export_equipment_xlsx,
    export_incident_pptx,export_incident_xlsx,
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
