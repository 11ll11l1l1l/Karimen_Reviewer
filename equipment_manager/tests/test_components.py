import unittest

from database import Database


class EquipmentComponentTests(unittest.TestCase):
    def setUp(self):
        self.db=Database("sqlite:///:memory:")
        self.db.save_equipment({"equipment_id":"ETCH-01","name":"Etcher"},user="seed")

    def test_component_install_and_history(self):
        row=self.db.save_component({
            "component_id":"ETCH01-RFGEN-001",
            "equipment_id":"ETCH-01",
            "parent_component_id":"",
            "name":"RF Generator",
            "component_type":"Generator",
            "manufacturer":"Demo",
            "model":"RF-1",
            "serial_number":"SN1001",
            "part_number":"PN-RF",
            "life_limit_value":10000,
            "life_limit_unit":"hours",
            "usage_value":125,
            "notes":"",
        },user="engineer",workstation="CI")
        self.assertEqual(row.status,"Installed")
        events=self.db.list_component_events(component_id=row.component_id)
        self.assertEqual(len(events),1)
        self.assertEqual(events[0].event_type,"INSTALLED")

    def test_child_component_must_share_same_equipment(self):
        self.db.save_equipment({"equipment_id":"CVD-01","name":"CVD"},user="seed")
        self.db.save_component({
            "component_id":"CVD-MODULE",
            "equipment_id":"CVD-01",
            "parent_component_id":"",
            "name":"Module",
        },user="engineer")
        with self.assertRaises(ValueError):
            self.db.save_component({
                "component_id":"ETCH-CHILD",
                "equipment_id":"ETCH-01",
                "parent_component_id":"CVD-MODULE",
                "name":"Invalid Child",
            },user="engineer")

    def test_parent_cannot_be_removed_before_installed_child(self):
        parent=self.db.save_component({
            "component_id":"CHAMBER-01",
            "equipment_id":"ETCH-01",
            "parent_component_id":"",
            "name":"Process Chamber",
        },user="engineer")
        child=self.db.save_component({
            "component_id":"ESC-01",
            "equipment_id":"ETCH-01",
            "parent_component_id":"CHAMBER-01",
            "name":"Electrostatic Chuck",
        },user="engineer")
        with self.assertRaises(ValueError):
            self.db.remove_component(parent.component_id,"Replace chamber","engineer",expected_version=parent.version)

        child=self.db.list_components("ETCH-01")[1]
        self.db.remove_component(
            child.component_id,
            "ESC replacement",
            "engineer",
            related_ticket="INC-100",
            expected_version=child.version,
        )
        parent=next(c for c in self.db.list_components("ETCH-01") if c.component_id=="CHAMBER-01")
        removed=self.db.remove_component(
            parent.component_id,
            "Chamber replacement",
            "engineer",
            related_ticket="INC-100",
            expected_version=parent.version,
        )
        self.assertEqual(removed.status,"Removed")
        events=self.db.list_component_events(component_id=removed.component_id)
        self.assertEqual(events[0].event_type,"REMOVED")

    def test_master_edit_cannot_move_or_reinstall_component(self):
        row=self.db.save_component({
            "component_id":"PUMP-01",
            "equipment_id":"ETCH-01",
            "parent_component_id":"",
            "name":"Turbo Pump",
        },user="engineer")
        self.db.save_component({
            "component_id":"PUMP-01",
            "equipment_id":"OTHER",
            "parent_component_id":"SOMEWHERE",
            "name":"Turbo Pump Updated",
            "status":"Removed",
        },expected_version=row.version,user="engineer")
        updated=next(c for c in self.db.list_components("ETCH-01") if c.component_id=="PUMP-01")
        self.assertEqual(updated.equipment_id,"ETCH-01")
        self.assertEqual(updated.parent_component_id,"")
        self.assertEqual(updated.status,"Installed")
        self.assertEqual(updated.name,"Turbo Pump Updated")


if __name__=="__main__":
    unittest.main()
