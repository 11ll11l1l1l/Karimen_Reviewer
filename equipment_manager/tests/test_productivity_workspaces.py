import os
import tempfile
import unittest
from datetime import datetime

from database import Database


class ProductivityWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.db=Database("sqlite:///:memory:")
        self.db.create_user("ee","Equipment Engineer","engineer-password-123","Equipment Engineer")
        self.db.save_equipment({
            "equipment_id":"ETCH-A01","name":"Etcher A01","equipment_type":"Etch",
            "area":"ETCH","model":"X1000","serial_number":"SN-001","owner":"ee",
        },user="ee")
        self.db.save_ticket({
            "ticket_no":"INC-9001","equipment_id":"ETCH-A01","title":"Vacuum instability",
            "description":"Pressure oscillation during process","severity":"S2","priority":"P2",
            "owner":"ee","root_cause":"","corrective_action":"","verification":"","created_by":"ee",
        })

    def test_global_search_spans_operational_entities(self):
        equipment=self.db.global_search("SN-001")
        self.assertTrue(any(x["entity_type"]=="EQUIPMENT" and x["entity_key"]=="ETCH-A01" for x in equipment))
        ticket=self.db.global_search("Vacuum instability")
        self.assertTrue(any(x["entity_type"]=="TICKET" and x["entity_key"]=="INC-9001" for x in ticket))

    def test_recent_and_favorite_round_trip(self):
        self.db.record_recent_item("ee","EQUIPMENT","ETCH-A01","ETCH-A01 — Etcher A01","ETCH-A01")
        recent=self.db.list_recent_items("ee")
        self.assertEqual(recent[0].entity_key,"ETCH-A01")
        self.db.set_favorite("ee","EQUIPMENT","ETCH-A01",True,"ETCH-A01 — Etcher A01","ETCH-A01")
        self.assertTrue(self.db.is_favorite("ee","EQUIPMENT","ETCH-A01"))
        self.assertEqual(self.db.list_favorites("ee")[0].entity_key,"ETCH-A01")
        self.db.set_favorite("ee","EQUIPMENT","ETCH-A01",False)
        self.assertFalse(self.db.is_favorite("ee","EQUIPMENT","ETCH-A01"))

    def test_universal_attachment_tracks_integrity_and_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            path=os.path.join(td,"evidence.txt")
            with open(path,"w",encoding="utf-8") as handle:handle.write("pressure trace evidence")
            row=self.db.add_attachment(
                "TICKET","INC-9001",path,original_name="evidence.txt",
                media_type="text/plain",category="Log",caption="Vacuum trace",
                tags="vacuum,pressure",equipment_id="ETCH-A01",created_by="ee",
            )
            self.assertEqual(len(row.file_sha256),64)
            listed=self.db.list_attachments("TICKET","INC-9001")
            self.assertEqual(len(listed),1)
            self.assertEqual(listed[0].caption,"Vacuum trace")
            self.db.update_attachment_metadata(row.id,"Updated","trace,reviewed","Evidence","ee")
            updated=self.db.get_attachment(row.id)
            self.assertEqual(updated.caption,"Updated")
            self.db.remove_attachment(row.id,"ee")
            self.assertEqual(self.db.list_attachments("TICKET","INC-9001"),[])

    def test_my_work_includes_owned_incident(self):
        rows=self.db.my_work("ee")
        self.assertTrue(any(x["kind"]=="INCIDENT" and x["key"]=="INC-9001" for x in rows))

    def test_productivity_migration_is_recorded(self):
        revisions={x.revision for x in self.db.list_schema_migrations()}
        self.assertIn("20260923_003",revisions)


if __name__=="__main__":
    unittest.main()
