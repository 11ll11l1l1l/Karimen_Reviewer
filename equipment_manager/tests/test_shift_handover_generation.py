import unittest

from database import Database


class ShiftHandoverGenerationTests(unittest.TestCase):
    def setUp(self):
        self.db=Database("sqlite:///:memory:")
        self.db.create_user("ee","Equipment Engineer","engineer-password-123","Equipment Engineer")
        self.db.save_equipment({"equipment_id":"ETCH-HO","name":"Etcher Handover","owner":"ee"},user="ee")
        self.db.save_equipment({"equipment_id":"CVD-NORMAL","name":"Normal CVD","owner":"ee"},user="ee")

    def test_active_alarm_creates_live_handover_candidate(self):
        self.db.ingest_alarm("ETCH-HO","VAC-HO",severity="Critical",message="Vacuum trip",source="Tool")
        rows=self.db.shift_handover_candidates()
        row=next(x for x in rows if x["equipment_id"]=="ETCH-HO")
        self.assertEqual(row["severity"],"CRITICAL")
        self.assertEqual(row["active_alarms"],1)
        self.assertIn("VAC-HO",row["pending_work"])
        self.assertFalse(any(x["equipment_id"]=="CVD-NORMAL" for x in rows))

    def test_publish_candidate_creates_operational_handover(self):
        self.db.ingest_alarm("ETCH-HO","TEMP-HO",severity="Warning",message="Temperature warning",source="Tool")
        row=self.db.publish_shift_handover("ETCH-HO","ee")
        self.assertEqual(row.equipment_id,"ETCH-HO")
        self.assertEqual(row.status,"Open")
        self.assertIn("Alarm TEMP-HO",row.pending_work)
        self.assertEqual(row.next_owner,"ee")

    def test_open_p1_incident_is_included_in_candidate(self):
        self.db.save_ticket({
            "ticket_no":"INC-HO-P1","equipment_id":"ETCH-HO","title":"Critical process issue",
            "description":"Tool held for investigation","severity":"S1","priority":"P1","owner":"ee",
            "root_cause":"","corrective_action":"","verification":"","created_by":"ee",
        })
        rows=self.db.shift_handover_candidates()
        row=next(x for x in rows if x["equipment_id"]=="ETCH-HO")
        self.assertEqual(row["severity"],"CRITICAL")
        self.assertIn("INC-HO-P1",row["pending_work"])


if __name__=="__main__":
    unittest.main()
