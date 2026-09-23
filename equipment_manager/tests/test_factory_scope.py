import os
import unittest

from database import Database


class FactoryHierarchyAndScopeTests(unittest.TestCase):
    def setUp(self):
        self.db=Database("sqlite:///:memory:")
        self.db.create_user("admin","Admin","admin-password-123","Administrator")
        self.db.create_user("etch_ee","Etch Engineer","etch-password-123","Equipment Engineer")
        self.db.save_equipment({
            "equipment_id":"ETCH-A01","name":"Etcher A01","site":"FAB1","building":"MFG","floor":"1F","area":"ETCH","line_cell":"BAY-A"
        },user="admin")
        self.db.save_equipment({
            "equipment_id":"CVD-B01","name":"CVD B01","site":"FAB1","building":"MFG","floor":"1F","area":"CVD","line_cell":"BAY-B"
        },user="admin")
        self.db._bootstrap_factory_hierarchy()

    def test_factory_hierarchy_is_normalized_and_assigned(self):
        nodes=self.db.list_factory_nodes()
        types={x.node_type for x in nodes}
        self.assertTrue({"Site","Building","Floor","Area","Line"}.issubset(types))
        etch_loc=self.db.equipment_location("ETCH-A01")
        self.assertIsNotNone(etch_loc)
        self.assertIn("AREA:ETCH",etch_loc.node_code)

    def test_restricted_node_scope_allows_only_ancestor_branch(self):
        self.db.set_user_access_policy("etch_ee","RESTRICTED")
        etch_loc=self.db.equipment_location("ETCH-A01")
        area_code=next(x for x in self.db._node_ancestors_for_test(etch_loc.node_code) if "AREA:ETCH" in x) if hasattr(self.db,"_node_ancestors_for_test") else None
        if area_code is None:
            nodes=self.db.list_factory_nodes()
            area_code=next(x.node_code for x in nodes if x.node_type=="Area" and x.name=="ETCH")
        self.db.add_user_scope("etch_ee","NODE",area_code,"*")
        self.assertTrue(self.db.equipment_in_scope("etch_ee","ETCH-A01","equipment.transition"))
        self.assertFalse(self.db.equipment_in_scope("etch_ee","CVD-B01","equipment.transition"))

    def test_scoped_transition_is_enforced(self):
        self.db.set_user_access_policy("etch_ee","RESTRICTED")
        nodes=self.db.list_factory_nodes()
        area_code=next(x.node_code for x in nodes if x.node_type=="Area" and x.name=="ETCH")
        self.db.add_user_scope("etch_ee","NODE",area_code,"equipment.transition")

        eq=self.db.get_equipment("ETCH-A01")
        self.db.transition_equipment_state(
            "ETCH-A01","Production",
            reason_code="RELEASED",reason_text="Qualified",
            user="etch_ee",expected_version=eq.version,
        )
        self.assertEqual(self.db.get_equipment("ETCH-A01").status,"Production")

        cvd=self.db.get_equipment("CVD-B01")
        with self.assertRaises(PermissionError):
            self.db.transition_equipment_state(
                "CVD-B01","Production",
                reason_code="RELEASED",reason_text="Qualified",
                user="etch_ee",expected_version=cvd.version,
            )

    def test_strict_authz_rejects_unknown_actor(self):
        old=os.environ.get("EMS_STRICT_AUTHZ")
        os.environ["EMS_STRICT_AUTHZ"]="1"
        try:
            eq=self.db.get_equipment("ETCH-A01")
            with self.assertRaises(PermissionError):
                self.db.transition_equipment_state(
                    "ETCH-A01","Production",
                    reason_code="RELEASED",reason_text="Qualified",
                    user="ghost",expected_version=eq.version,
                )
        finally:
            if old is None:os.environ.pop("EMS_STRICT_AUTHZ",None)
            else:os.environ["EMS_STRICT_AUTHZ"]=old


if __name__=="__main__":
    unittest.main()
