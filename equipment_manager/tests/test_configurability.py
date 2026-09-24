import json
import unittest

from database import Database


class ConfigurabilityTests(unittest.TestCase):
    def setUp(self):
        self.db=Database("sqlite:///:memory:")
        self.db.create_user("admin","Administrator","admin-password-123","Administrator")
        self.db.save_equipment({
            "equipment_id":"ETCH-CFG","name":"Etcher Config","equipment_type":"Etch",
            "area":"ETCH","criticality":"High",
        },user="admin")
        self.db.save_equipment({
            "equipment_id":"CVD-CFG","name":"CVD Config","equipment_type":"CVD",
            "area":"CVD","criticality":"Normal",
        },user="admin")

    def test_default_reference_catalog_is_seeded_and_editable_safely(self):
        severities=self.db.list_config_options("TICKET_SEVERITY")
        self.assertEqual([x.code for x in severities],["S1","S2","S3","S4"])
        row=severities[0]
        updated=self.db.save_config_option({
            "category":"TICKET_SEVERITY","code":"S1","label":"S1 — Critical",
            "sort_order":row.sort_order,"active":True,"metadata_json":"{}",
        },row.version)
        self.assertEqual(updated.code,"S1")
        self.assertEqual(updated.label,"S1 — Critical")
        self.assertTrue(updated.system_locked)

    def test_canonical_reason_code_can_be_relabelled_but_not_deactivated(self):
        row=next(x for x in self.db.list_config_options("TICKET_REASON_LABEL") if x.code=="WAIT_PARTS")
        updated=self.db.save_config_option({
            "category":"TICKET_REASON_LABEL","code":"WAIT_PARTS",
            "label":"Awaiting spare-part arrival","sort_order":row.sort_order,
            "active":False,"metadata_json":"{}",
        },row.version)
        self.assertEqual(updated.code,"WAIT_PARTS")
        self.assertEqual(updated.label,"Awaiting spare-part arrival")
        self.assertTrue(updated.active)

    def test_site_can_add_reference_option_without_code_change(self):
        row=self.db.save_config_option({
            "category":"WORK_TYPE","code":"Vendor Calibration","label":"Vendor Calibration",
            "sort_order":75,"active":True,"system_locked":False,"metadata_json":"{}",
        })
        self.assertEqual(row.code,"Vendor Calibration")
        values=[x.code for x in self.db.list_config_options("WORK_TYPE")]
        self.assertIn("Vendor Calibration",values)

    def test_equipment_template_applies_defaults_but_user_values_win(self):
        self.db.save_entity_template({
            "template_id":"ETCH-STANDARD","entity_type":"EQUIPMENT","name":"Standard Etch Tool",
            "applies_to":"Etch","defaults_json":json.dumps({
                "equipment_type":"Etch","site":"FAB1","area":"ETCH","criticality":"High",
                "manufacturer":"Vendor A",
            }),"active":True,
        },"admin")
        data=self.db.apply_entity_template("ETCH-STANDARD",{"equipment_id":"ETCH-NEW","name":"Etcher New","area":"ETCH-A"})
        self.assertEqual(data["equipment_type"],"Etch")
        self.assertEqual(data["site"],"FAB1")
        self.assertEqual(data["area"],"ETCH-A")
        self.assertEqual(data["equipment_id"],"ETCH-NEW")

    def test_custom_fields_are_typed_and_scoped_by_equipment_type(self):
        self.db.save_custom_field_definition({
            "field_id":"etch_chamber_count","entity_type":"EQUIPMENT","applies_to":"Etch",
            "label":"Chamber Count","field_type":"NUMBER","options_json":"[]",
            "required":True,"sort_order":10,"active":True,
        })
        self.db.save_custom_field_definition({
            "field_id":"process_family","entity_type":"EQUIPMENT","applies_to":"",
            "label":"Process Family","field_type":"CHOICE","options_json":json.dumps(["Dry","Wet"]),
            "required":False,"sort_order":20,"active":True,
        })
        self.db.save_custom_field_definition({
            "field_id":"cvd_gas_box","entity_type":"EQUIPMENT","applies_to":"CVD",
            "label":"Gas Box","field_type":"TEXT","options_json":"[]",
            "required":True,"sort_order":30,"active":True,
        })

        self.db.save_custom_field_values(
            "EQUIPMENT","ETCH-CFG",
            {"etch_chamber_count":4,"process_family":"Dry"},
            "admin","Etch",
        )
        values=self.db.custom_field_values("EQUIPMENT","ETCH-CFG")
        self.assertEqual(values["etch_chamber_count"],4.0)
        self.assertEqual(values["process_family"],"Dry")
        self.assertNotIn("cvd_gas_box",values)

        with self.assertRaises(ValueError):
            self.db.save_custom_field_values(
                "EQUIPMENT","CVD-CFG",{"process_family":"Dry"},"admin","CVD"
            )
        with self.assertRaises(ValueError):
            self.db.save_custom_field_values(
                "EQUIPMENT","ETCH-CFG",{"etch_chamber_count":"not-a-number"},"admin","Etch"
            )
        with self.assertRaises(ValueError):
            self.db.save_custom_field_values(
                "EQUIPMENT","ETCH-CFG",{"process_family":"Unknown"},"admin","Etch"
            )

    def test_inactive_custom_fields_disappear_from_active_definition_list(self):
        row=self.db.save_custom_field_definition({
            "field_id":"legacy_note","entity_type":"TICKET","applies_to":"",
            "label":"Legacy note","field_type":"TEXT","options_json":"[]",
            "required":False,"sort_order":10,"active":True,
        })
        updated=self.db.save_custom_field_definition({
            "field_id":"legacy_note","entity_type":"TICKET","applies_to":"",
            "label":"Legacy note","field_type":"TEXT","options_json":"[]",
            "required":False,"sort_order":10,"active":False,
        },row.version)
        self.assertFalse(updated.active)
        self.assertEqual(self.db.list_custom_field_definitions("TICKET"),[])


if __name__=="__main__":
    unittest.main()
