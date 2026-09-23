import unittest
from datetime import datetime, timedelta

from database import Database


class AlarmDomainTests(unittest.TestCase):
    def setUp(self):
        self.db=Database("sqlite:///:memory:")
        self.db.create_user("ee","Engineer","engineer-password-123","Equipment Engineer")
        self.db.save_equipment({"equipment_id":"ETCH-01","name":"Etcher"},user="ee")

    def test_idempotent_ingest_and_clear(self):
        first=self.db.ingest_alarm(
            "ETCH-01","E1421",severity="Critical",message="Vacuum interlock",
            source="SECS/GEM",event_key="SRC-1",
        )
        duplicate=self.db.ingest_alarm(
            "ETCH-01","E1421",severity="Critical",message="Vacuum interlock",
            source="SECS/GEM",event_key="SRC-1",
        )
        self.assertEqual(first.id,duplicate.id)
        self.assertEqual(len(self.db.list_alarms("ETCH-01",True)),1)

        cleared=self.db.ingest_alarm(
            "ETCH-01","E1421",state="CLEARED",source="SECS/GEM",
            event_key="SRC-2",
        )
        self.assertEqual(cleared.state,"CLEARED")
        self.assertEqual(len(self.db.list_alarms("ETCH-01",True)),0)

    def test_acknowledgement_and_command_center(self):
        alarm=self.db.ingest_alarm("ETCH-01","RF-01",severity="Critical",message="RF trip")
        self.db.acknowledge_alarm(alarm.event_key,"ee")
        row=self.db.list_alarms("ETCH-01")[0]
        self.assertEqual(row.acknowledged_by,"ee")
        # cleared alarms no longer appear as active command-center exceptions
        queue=self.db.operations_attention_queue()
        self.assertTrue(any(x["kind"]=="ALARM" and x["key"]==alarm.event_key for x in queue))

    def test_pareto_counts_repeat_alarm_occurrences(self):
        self.db.ingest_alarm("ETCH-01","A1",message="Repeat",event_key="A1-1")
        self.db.ingest_alarm("ETCH-01","A1",state="CLEARED",event_key="A1-C1")
        self.db.ingest_alarm("ETCH-01","A1",message="Repeat",event_key="A1-2")
        rows=self.db.alarm_pareto(30,"ETCH-01")
        hit=next(x for x in rows if x["alarm_code"]=="A1" and x["message"]=="Repeat")
        self.assertEqual(hit["count"],2)

    def test_alarm_ingest_emits_transactional_integration_event(self):
        self.db.save_integration_endpoint({
            "endpoint_id":"ALL","name":"All events","adapter_type":"FILE",
            "target":".","topics":"equipment.alarm.active","enabled":True,
        })
        alarm=self.db.ingest_alarm("ETCH-01","A2",message="Alarm",event_key="A2-1")
        pending=self.db.pending_integration_deliveries()
        self.assertEqual(len(pending),1)
        self.assertEqual(pending[0][1].topic,"equipment.alarm.active")


if __name__=="__main__":
    unittest.main()
