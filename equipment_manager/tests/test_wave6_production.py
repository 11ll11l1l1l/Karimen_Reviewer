import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from database import Database
from inbound_integrations import preview_inbound_file


class Wave6ProductionWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.db=Database("sqlite:///:memory:")
        self.db.create_user("admin","Administrator","admin-password-123","Administrator")
        self.db.create_user("tech","Technician","tech-password-123","Technician")
        self.db.save_equipment({
            "equipment_id":"ETCH-W6","name":"Wave6 Etcher","equipment_type":"Etch",
            "area":"ETCH","owner":"tech",
        },user="admin")

    def test_supplier_order_partial_and_full_receipt(self):
        order=self.db.save_supplier_order({
            "order_no":"PO-W6-001","supplier":"Vendor A","expected_at":datetime.utcnow()+timedelta(days=3),
        },"admin")
        line=self.db.add_supplier_order_line(order.order_no,{
            "part_number":"FILTER-W6","ordered_qty":5.0,"destination_location":"STOCK-W6",
            "unit_cost":1000.0,"currency":"JPY",
        },"admin")
        submitted=self.db.submit_supplier_order(order.order_no,"admin",order.version)
        self.assertEqual(submitted.status,"Submitted")

        line,order,_tx=self.db.receive_supplier_order_line(line.id,2.0,"admin","DEL-1")
        self.assertEqual(line.status,"Partial")
        self.assertEqual(order.status,"Partially Received")
        line,order,_tx=self.db.receive_supplier_order_line(line.id,3.0,"admin","DEL-2")
        self.assertEqual(line.status,"Received")
        self.assertEqual(order.status,"Received")
        stock=next(x for x in self.db.list_inventory("FILTER-W6") if x.location_code=="STOCK-W6")
        self.assertEqual(stock.quantity,5.0)

    def test_rotable_repair_cycle_preserves_history(self):
        asset=self.db.register_rotable({
            "asset_id":"ROT-W6-001","part_number":"PUMP-W6","serial_number":"SN-W6",
            "description":"Vacuum pump","current_location":"STOCK-W6",
        },"admin")
        installed=self.db.transition_rotable(asset.asset_id,"Installed","admin",equipment_id="ETCH-W6",expected_version=asset.version)
        repair=self.db.transition_rotable(installed.asset_id,"In Repair","admin",vendor="Repair Vendor",reference="RMA-001",expected_version=installed.version)
        returned=self.db.transition_rotable(repair.asset_id,"Stock","admin",location_code="STOCK-W6",reference="RETURN-001",expected_version=repair.version)
        self.assertEqual(returned.status,"Stock")
        self.assertEqual(returned.repair_count,1)
        events=self.db.list_rotable_events(asset.asset_id)
        self.assertGreaterEqual(len(events),4)
        self.assertEqual(events[0].to_status,"Stock")

    def test_pm_kit_staging_requires_reserved_ready_parts(self):
        self.db.save_pm_definition({
            "pm_id":"PM-W6","name":"Wave6 PM","equipment_id":"ETCH-W6","schedule_type":"Interval",
            "frequency_value":30,"frequency_unit":"days","anchor_mode":"Original Due","early_window_days":0,
            "grace_days":1,"estimated_hours":1.0,"required_people":1,"required_skill":"",
            "required_parts":"","sop_path":"","active":True,"revision":1,
        })
        task=self.db.upsert_pm_task({
            "equipment_id":"ETCH-W6","pm_id":"PM-W6","pm_name":"Wave6 PM",
            "original_due_date":datetime.utcnow()+timedelta(days=1),"scheduled_date":datetime.utcnow()+timedelta(days=1),
            "status":"Scheduled","assigned_to":"tech","estimated_hours":1.0,"priority":"Normal","sop_path":"",
        })
        self.db.save_inventory_item({
            "part_number":"KIT-W6","description":"PM kit part","category":"Consumable","manufacturer":"","model":"",
            "compatible_equipment":"ETCH-W6","quantity":3.0,"min_quantity":0.0,"unit":"ea",
            "condition":"Available","location_code":"STOCK-W6","image_path":"","notes":"",
        })
        self.db.upsert_pm_requirement({
            "requirement_id":"REQ-W6","pm_id":"PM-W6","requirement_type":"PART","requirement_key":"KIT-W6",
            "description":"Kit part","quantity":2.0,"mandatory":True,"active":True,"revision":1,
        })
        self.db.reserve_pm_required_parts(task.id,"admin")
        stage=self.db.set_pm_kit_stage(task.id,"Staged","admin","STAGE-A")
        self.assertEqual(stage.status,"Staged")
        issued=self.db.set_pm_kit_stage(task.id,"Issued","admin","STAGE-A",expected_version=stage.version)
        self.assertEqual(issued.status,"Issued")

    def test_form_layout_and_v2_configuration_package(self):
        self.db.save_custom_field_definition({
            "field_id":"CF-W6","entity_type":"TICKET","applies_to":"Etch","label":"Chamber Position",
            "field_type":"TEXT","options_json":"[]","required":False,"sort_order":10,"active":True,
        })
        section=self.db.save_form_section({
            "section_id":"SEC-W6","entity_type":"TICKET","applies_to":"Etch","title":"Process Context",
            "description":"Etch-specific context","sort_order":10,"columns":2,"collapsible":True,"active":True,
        })
        layout=self.db.save_custom_field_layout("CF-W6",{
            "section_id":section.section_id,"column_index":1,"width_span":1,
            "placeholder":"e.g. CH-A","help_text":"Physical chamber position",
        })
        self.assertEqual(self.db.custom_field_layouts(["CF-W6"])["CF-W6"].section_id,"SEC-W6")
        bundle=self.db.export_configuration_bundle()
        self.assertEqual(bundle["schema"],"EMS_CONFIGURATION_V2")
        self.assertTrue(any(x["section_id"]=="SEC-W6" for x in bundle["form_sections"]))
        preview=self.db.import_configuration_bundle(bundle,"admin",True)
        self.assertIn("form_sections",preview["counts"])
        self.assertIn("custom_field_layouts",preview["counts"])

    def test_drafts_and_work_order_notifications(self):
        wo=self.db.create_work_order({
            "equipment_id":"ETCH-W6","source_type":"ENGINEERING","title":"Repair chamber",
            "description":"Initial","owner":"tech","team":"Equipment",
        },"admin")
        self.db.save_user_draft("tech","WORK_ORDER",wo.work_order_no,{"description":"Unsaved edit"},"details")
        draft=self.db.get_user_draft("tech","WORK_ORDER",wo.work_order_no,"details")
        self.assertEqual(draft["payload"]["description"],"Unsaved edit")
        updated=self.db.transition_work_order(wo.work_order_no,"Assigned","admin",owner="tech",expected_version=wo.version)
        notices=self.db.list_notifications("tech",True)
        self.assertTrue(any(x.entity_key==wo.work_order_no for x in notices))
        saved=self.db.update_work_order_details(updated.work_order_no,"admin",description="Saved edit",team="Night Shift",expected_version=updated.version)
        self.assertEqual(saved.description,"Saved edit")
        self.assertEqual(saved.team,"Night Shift")
        self.assertTrue(self.db.clear_user_draft("tech","WORK_ORDER",wo.work_order_no,"details"))

    def test_inbound_mapping_preview_is_non_mutating(self):
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/"sample.json"
            source.write_text(json.dumps({"tool":"ETCH-W6","code":"A123","severity":"Warning","message":"Vacuum alarm"}),encoding="utf-8")
            self.db.save_inbound_endpoint({
                "endpoint_id":"IN-W6","name":"FDC Alarm Feed","adapter_type":"FILE_JSON","entity_type":"ALARM",
                "source_path":td,"file_pattern":"*.json",
                "mapping_json":json.dumps({"equipment_id":"tool","alarm_code":"code","severity":"severity","message":"message"}),
                "defaults_json":json.dumps({"state":"ACTIVE","source":"FDC"}),
                "archive_path":str(Path(td)/"archive"),"quarantine_path":str(Path(td)/"quarantine"),"enabled":True,
            })
            before=len(self.db.list_alarms("ETCH-W6",False,100))
            preview=preview_inbound_file(self.db,"IN-W6",str(source),10)
            after=len(self.db.list_alarms("ETCH-W6",False,100))
            self.assertEqual(preview["valid"],1)
            self.assertEqual(preview["invalid"],0)
            self.assertEqual(before,after)


if __name__=="__main__":
    unittest.main()
