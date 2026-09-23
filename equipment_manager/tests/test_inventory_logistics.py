import unittest

from database import Database


class InventoryLogisticsTests(unittest.TestCase):
    def setUp(self):
        self.db=Database("sqlite:///:memory:")
        self.db.create_user("manager","Manager","manager-password-123","Manager")
        self.db.save_part_catalog({
            "part_number":"FILTER-A","description":"Chamber filter","category":"Consumable",
            "manufacturer":"Vendor A","supplier":"Supplier A","supplier_part_number":"SUP-F-A",
            "barcode":"BC-FILTER-A","lead_time_days":14,"reorder_qty":20.0,"notes":"","active":True,
        })
        self.db.save_part_catalog({
            "part_number":"FILTER-B","description":"Approved alternate filter","category":"Consumable",
            "manufacturer":"Vendor B","supplier":"Supplier B","supplier_part_number":"SUP-F-B",
            "barcode":"BC-FILTER-B","lead_time_days":10,"reorder_qty":10.0,"notes":"","active":True,
        })

    def test_barcode_receive_transfer_and_cycle_count(self):
        self.assertEqual(self.db.resolve_part_scan("BC-FILTER-A"),"FILTER-A")
        item,tx=self.db.receive_inventory("FILTER-A","STOCK-A",10,"manager","PO-100")
        self.assertEqual(item.quantity,10.0)
        item,_=self.db.receive_inventory("FILTER-A","STOCK-A",5,"manager","PO-101")
        self.assertEqual(item.quantity,15.0)

        source,dest=self.db.transfer_inventory("FILTER-A","STOCK-A","STOCK-B",4,"manager")
        self.assertEqual(source.quantity,11.0)
        self.assertEqual(dest.quantity,4.0)
        self.assertEqual(sum(x.quantity for x in self.db.list_inventory("FILTER-A")),15.0)

        counted,adjustment=self.db.cycle_count_inventory("FILTER-A","STOCK-A",9,"manager","Physical count")
        self.assertEqual(counted.quantity,9.0)
        self.assertEqual(adjustment.quantity,-2.0)
        types=[x.transaction_type for x in self.db.list_inventory_transactions(20)]
        self.assertIn("Receive",types)
        self.assertIn("Transfer Out",types)
        self.assertIn("Transfer In",types)
        self.assertIn("Cycle Count",types)

    def test_reorder_queue_uses_available_after_reservations(self):
        item=self.db.save_inventory_item({
            "part_number":"FILTER-A","description":"Chamber filter","category":"Consumable",
            "manufacturer":"Vendor A","model":"","compatible_equipment":"","quantity":8.0,
            "min_quantity":5.0,"unit":"pcs","condition":"Available","location_code":"STOCK-A",
            "image_path":"","notes":"",
        })
        success,res_id=self.db.reserve_inventory("FILTER-A",4,"manager",location_code="STOCK-A")
        self.assertTrue(success)
        queue=self.db.inventory_reorder_queue()
        row=next(x for x in queue if x["part_number"]=="FILTER-A" and x["location_code"]=="STOCK-A")
        self.assertEqual(row["on_hand"],8.0)
        self.assertEqual(row["reserved"],4.0)
        self.assertEqual(row["available"],4.0)
        self.assertEqual(row["shortage_to_min"],1.0)
        self.assertEqual(row["suggested_order_qty"],20.0)
        self.assertEqual(row["supplier"],"Supplier A")

    def test_approved_alternate_is_exposed_to_pm_kit(self):
        self.db.save_part_alternate("FILTER-A","FILTER-B","manager",True,"Engineering approved")
        self.db.save_equipment({"equipment_id":"ETCH-KIT","name":"Kit Etcher"},user="manager")
        self.db.save_pm_definition({
            "pm_id":"PM-KIT","name":"Filter PM","equipment_id":"ETCH-KIT",
            "schedule_type":"Interval","frequency_value":30,"frequency_unit":"days",
            "anchor_mode":"Original Due","early_window_days":1,"grace_days":1,
            "estimated_hours":1.0,"required_people":1,"required_skill":"",
            "required_parts":"","sop_path":"","active":True,"revision":1,
        })
        self.db.upsert_pm_requirement({
            "requirement_id":"KIT-PART","pm_id":"PM-KIT","requirement_type":"PART",
            "requirement_key":"FILTER-A","description":"Primary filter","quantity":2.0,
            "mandatory":True,"active":True,"revision":1,
        })
        task=self.db.upsert_pm_task({
            "equipment_id":"ETCH-KIT","pm_id":"PM-KIT","pm_name":"Filter PM",
            "status":"Scheduled","assigned_to":"manager","estimated_hours":1.0,"priority":"Normal",
        })
        kit=self.db.pm_kit_status(task.id)
        part=next(x for x in kit["parts"] if x["part_number"]=="FILTER-A")
        self.assertIn("FILTER-B",part["alternates"])


if __name__=="__main__":
    unittest.main()
