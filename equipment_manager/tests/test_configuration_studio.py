import unittest

from database import Database


class ConfigurationStudioTests(unittest.TestCase):
    def setUp(self):
        self.db=Database("sqlite:///:memory:")
        self.db.create_user("admin","Admin","admin-password-123","Administrator")
        self.db.save_equipment({
            "equipment_id":"ETCH-CFG","name":"Config Etcher","equipment_type":"Plasma Etcher"
        },user="admin")

    def test_custom_fields_validate_scope_and_types(self):
        self.db.save_custom_field_definition({
            "entity_type":"EQUIPMENT","field_key":"chamber_count","applies_to":"Plasma Etcher",
            "label":"Chamber Count","data_type":"NUMBER","choices_json":[],"required":True,
            "active":True,"sort_order":10,
        })
        self.db.save_custom_field_definition({
            "entity_type":"EQUIPMENT","field_key":"platform","applies_to":"",
            "label":"Platform","data_type":"CHOICE","choices_json":["A","B"],"required":False,
            "active":True,"sort_order":20,
        })
        self.db.set_custom_field_value("EQUIPMENT","ETCH-CFG","chamber_count","4","admin","Plasma Etcher")
        self.db.set_custom_field_value("EQUIPMENT","ETCH-CFG","platform","A","admin","Plasma Etcher")
        rows={x["field_key"]:x for x in self.db.custom_field_values("EQUIPMENT","ETCH-CFG","Plasma Etcher")}
        self.assertEqual(rows["chamber_count"]["value"],4.0)
        self.assertEqual(rows["platform"]["value"],"A")
        with self.assertRaises(ValueError):
            self.db.set_custom_field_value("EQUIPMENT","ETCH-CFG","platform","C","admin","Plasma Etcher")

    def test_scope_specific_definition_overrides_global(self):
        self.db.save_custom_field_definition({
            "entity_type":"EQUIPMENT","field_key":"local_owner_code","applies_to":"",
            "label":"Global Owner Code","data_type":"TEXT","choices_json":[],"required":False,
            "active":True,"sort_order":20,
        })
        self.db.save_custom_field_definition({
            "entity_type":"EQUIPMENT","field_key":"local_owner_code","applies_to":"Plasma Etcher",
            "label":"Etch Owner Code","data_type":"TEXT","choices_json":[],"required":True,
            "active":True,"sort_order":10,
        })
        rows=[x for x in self.db.custom_field_values("EQUIPMENT","ETCH-CFG","Plasma Etcher") if x["field_key"]=="local_owner_code"]
        self.assertEqual(len(rows),2)
        scoped=next(x for x in rows if x["applies_to"]=="Plasma Etcher")
        self.assertEqual(scoped["label"],"Etch Owner Code")

    def test_record_template_round_trip_and_scope(self):
        row=self.db.save_record_template({
            "template_id":"WO-ETCH-CHAMBER","entity_type":"WORK_ORDER","name":"Etch Chamber Work",
            "applies_to":"Plasma Etcher",
            "payload_json":{"priority":"High","qualification_required":True,"release_required":True},
            "active":True,"created_by":"admin",
        })
        self.assertEqual(row.version,1)
        rows=self.db.list_record_templates("WORK_ORDER","Plasma Etcher",True)
        self.assertEqual(len(rows),1)
        self.assertIn('"qualification_required": true',rows[0].payload_json)
        updated=self.db.save_record_template({
            "template_id":"WO-ETCH-CHAMBER","entity_type":"WORK_ORDER","name":"Etch Chamber Work",
            "applies_to":"Plasma Etcher",
            "payload_json":{"priority":"Critical","qualification_required":True,"release_required":True},
            "active":True,"created_by":"admin",
        },row.version)
        self.assertEqual(updated.version,2)


if __name__=="__main__":
    unittest.main()
