import unittest

from database import Database
from excel_reconcile import reconcile_equipment, reconcile_inventory


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
