import unittest

from database import Database
from excel_reconcile import (
    apply_extended_reconciliation, apply_reconciliation, reconcile_endorsements,
    reconcile_equipment, reconcile_inventory, reconcile_qualification_protocols,
    reconcile_tickets,
)


class ExcelReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.db=Database("sqlite:///:memory:")
        self.db.create_user("ee","Equipment Engineer","engineer-password-123","Equipment Engineer")
        self.db.save_equipment({
            "equipment_id":"ETCH-XL","name":"Old Name","equipment_type":"Etch",
            "manufacturer":"Vendor A","model":"Model X","serial_number":"SN-XL",
            "asset_number":"ASSET-1","site":"FAB1","building":"MFG","floor":"1F",
            "area":"ETCH","line_cell":"BAY-A","owner":"ee","criticality":"High",
        },user="ee")
        self.db.save_inventory_item({
            "part_number":"FILTER-XL","description":"Original filter","category":"Consumable",
            "manufacturer":"Vendor B","model":"F-100","compatible_equipment":"ETCH-XL",
            "quantity":5.0,"min_quantity":2.0,"unit":"pcs","condition":"Available",
            "location_code":"STOCK-1","image_path":"original.png","notes":"Preserve me",
        })
        self.ticket=self.db.save_ticket({
            "ticket_no":"INC-XL","equipment_id":"ETCH-XL","title":"Old title",
            "description":"Original problem","severity":"S2","priority":"P2","owner":"ee",
            "root_cause":"Open","corrective_action":"","verification":"","created_by":"ee",
        })
        self.protocol=self.db.save_qualification_protocol(
            protocol_id="QUAL-XL",name="Qualification XL",
            checks=[{"check_id":"Q01","label":"Leak check","acceptance":"PASS"}],
            user="ee",equipment_id="ETCH-XL",
        )
        self.endorsement=self.db.save_endorsement({
            "endorsement_no":"HO-XL","equipment_id":"ETCH-XL","current_condition":"Under observation",
            "work_completed":"Initial check","pending_work":"Trend review","restrictions":"Engineering only",
            "next_action":"Review trend","next_owner":"ee","status":"Open","created_by":"ee",
            "acknowledged_by":"","acknowledged_at":None,
        })

    def test_equipment_partial_mapping_preserves_unmapped_fields(self):
        rows=[{
            "equipment_id":"ETCH-XL","name":"New Name","equipment_type":"","manufacturer":"",
            "model":"","serial_number":"","asset_number":"","site":"","building":"",
            "floor":"","area":"","line_cell":"","owner":"","criticality":"Normal",
        }]
        actions=reconcile_equipment(self.db,rows,{"equipment_id":"ID","name":"Name"})
        action=actions[0]
        self.assertEqual(action["status"],"UPDATE")
        self.assertEqual(action["data"]["name"],"New Name")
        self.assertEqual(action["data"]["manufacturer"],"Vendor A")
        self.assertEqual(action["data"]["model"],"Model X")
        self.assertEqual(action["data"]["owner"],"ee")
        self.assertEqual([x["field"] for x in action["changes"]],["name"])

    def test_inventory_partial_mapping_preserves_unmapped_fields(self):
        rows=[{
            "part_number":"FILTER-XL","location_code":"STOCK-1","description":"",
            "quantity":8.0,"min_quantity":0.0,"unit":"ea","condition":"Available","image_path":"",
        }]
        actions=reconcile_inventory(self.db,rows,{
            "part_number":"Part","location_code":"Location","quantity":"Quantity",
        })
        action=actions[0]
        self.assertEqual(action["status"],"UPDATE")
        self.assertEqual(action["data"]["quantity"],8.0)
        self.assertEqual(action["data"]["description"],"Original filter")
        self.assertEqual(action["data"]["category"],"Consumable")
        self.assertEqual(action["data"]["manufacturer"],"Vendor B")
        self.assertEqual(action["data"]["unit"],"pcs")
        self.assertEqual(action["data"]["notes"],"Preserve me")

    def test_ticket_partial_mapping_preserves_lifecycle_and_unmapped_fields(self):
        rows=[{
            "ticket_no":"INC-XL","equipment_id":"ETCH-XL","title":"Updated title",
            "description":"","severity":"","priority":"","owner":"","root_cause":"",
            "corrective_action":"","verification":"",
        }]
        actions=reconcile_tickets(self.db,rows,{
            "ticket_no":"Ticket","equipment_id":"Equipment","title":"Title",
        })
        action=actions[0]
        self.assertEqual(action["status"],"UPDATE")
        self.assertEqual(action["data"]["title"],"Updated title")
        self.assertEqual(action["data"]["description"],"Original problem")
        self.assertEqual(action["data"]["priority"],"P2")
        self.assertNotIn("status",action["data"])

        result=apply_reconciliation(self.db,actions,entity="ticket",user="ee")
        self.assertEqual(result["applied"],1)
        updated=next(x for x in self.db.list_tickets() if x.ticket_no=="INC-XL")
        self.assertEqual(updated.title,"Updated title")
        self.assertEqual(updated.status,"Open")

    def test_ticket_reconciliation_uses_version_conflict_protection(self):
        rows=[{
            "ticket_no":"INC-XL","equipment_id":"ETCH-XL","title":"Workbook title",
            "description":"","severity":"","priority":"","owner":"","root_cause":"",
            "corrective_action":"","verification":"",
        }]
        actions=reconcile_tickets(self.db,rows,{
            "ticket_no":"Ticket","equipment_id":"Equipment","title":"Title",
        })
        current=next(x for x in self.db.list_tickets() if x.ticket_no=="INC-XL")
        self.db.save_ticket({
            "ticket_no":current.ticket_no,"equipment_id":current.equipment_id,"title":"Concurrent edit",
            "description":current.description,"severity":current.severity,"priority":current.priority,
            "owner":current.owner,"root_cause":current.root_cause,"corrective_action":current.corrective_action,
            "verification":current.verification,"created_by":current.created_by,
        },current.version)
        with self.assertRaises(RuntimeError):
            apply_reconciliation(self.db,actions,entity="ticket",user="ee")

    def test_qualification_reconciliation_creates_controlled_revision(self):
        rows=[
            {"protocol_id":"QUAL-XL","name":"Qualification XL","equipment_id":"ETCH-XL","equipment_type":"","check_id":"Q01","label":"Leak check","acceptance":"PASS"},
            {"protocol_id":"QUAL-XL","name":"Qualification XL","equipment_id":"ETCH-XL","equipment_type":"","check_id":"Q02","label":"Particle check","acceptance":"PASS"},
        ]
        mapping={k:k for k in ["protocol_id","name","equipment_id","equipment_type","check_id","label","acceptance"]}
        actions=reconcile_qualification_protocols(self.db,rows,mapping)
        self.assertEqual(actions[0]["status"],"CREATE_REVISION")
        result=apply_extended_reconciliation(self.db,actions,entity="qualification_protocol",user="ee")
        self.assertEqual(result["applied"],1)
        protocols=[x for x in self.db.list_qualification_protocols(active_only=False) if x.protocol_id=="QUAL-XL"]
        self.assertEqual(len(protocols),2)
        active=next(x for x in protocols if x.active)
        self.assertEqual(active.revision,2)
        self.assertIn('"check_id": "Q02"',active.checks_json)

    def test_qualification_reconciliation_skips_unchanged_protocol(self):
        rows=[{"protocol_id":"QUAL-XL","name":"Qualification XL","equipment_id":"ETCH-XL","equipment_type":"","check_id":"Q01","label":"Leak check","acceptance":"PASS"}]
        mapping={k:k for k in ["protocol_id","name","equipment_id","equipment_type","check_id","label","acceptance"]}
        action=reconcile_qualification_protocols(self.db,rows,mapping)[0]
        self.assertEqual(action["status"],"UNCHANGED")
        self.assertEqual(action["changes"],[])

    def test_handover_reconciliation_preserves_lifecycle_fields(self):
        self.db.acknowledge_endorsement("HO-XL","ee")
        current=next(x for x in self.db.list_endorsements() if x.endorsement_no=="HO-XL")
        rows=[{
            "endorsement_no":"HO-XL","equipment_id":"ETCH-XL","current_condition":"Stable",
            "work_completed":"","pending_work":"Morning verification","restrictions":"",
            "next_action":"Verify","next_owner":"ee",
        }]
        mapping={k:k for k in ["endorsement_no","equipment_id","current_condition","pending_work","next_action","next_owner"]}
        actions=reconcile_endorsements(self.db,rows,mapping)
        self.assertEqual(actions[0]["status"],"UPDATE")
        result=apply_extended_reconciliation(self.db,actions,entity="endorsement",user="ee")
        self.assertEqual(result["applied"],1)
        updated=next(x for x in self.db.list_endorsements() if x.endorsement_no=="HO-XL")
        self.assertEqual(updated.current_condition,"Stable")
        self.assertEqual(updated.pending_work,"Morning verification")
        self.assertEqual(updated.status,current.status)
        self.assertEqual(updated.acknowledged_by,current.acknowledged_by)
        self.assertEqual(updated.acknowledged_at,current.acknowledged_at)

    def test_unchanged_mapped_values_are_skipped(self):
        rows=[{
            "equipment_id":"ETCH-XL","name":"Old Name","equipment_type":"","manufacturer":"",
            "model":"","serial_number":"","asset_number":"","site":"","building":"",
            "floor":"","area":"","line_cell":"","owner":"","criticality":"Normal",
        }]
        action=reconcile_equipment(self.db,rows,{"equipment_id":"ID","name":"Name"})[0]
        self.assertEqual(action["status"],"UNCHANGED")
        self.assertEqual(action["changes"],[])


if __name__=="__main__":
    unittest.main()
