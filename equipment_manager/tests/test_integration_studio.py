import json
import tempfile
import unittest
from pathlib import Path

from database import Database
from integrations import dispatch_pending
from orchestration import process_pending_rules


class IntegrationStudioTests(unittest.TestCase):
    def setUp(self):
        self.db=Database("sqlite:///:memory:")
        self.db.create_user("ee","Equipment Engineer","engineer-password-123","Equipment Engineer")
        self.db.save_equipment({"equipment_id":"ETCH-INT","name":"Integration Etcher"},user="ee")

    def test_mapped_file_delivery_and_revision(self):
        with tempfile.TemporaryDirectory() as td:
            self.db.save_integration_endpoint({
                "endpoint_id":"MES-DROP","name":"MES drop","adapter_type":"FILE","target":td,
                "topics":"equipment.alarm.active","auth_env":"","enabled":True,
            })
            first=self.db.save_integration_mapping(
                "MES-DROP",
                {"tool":"payload.equipment_id","alarm":"payload.alarm_code","event_type":"topic"},
                {"source":"EMS"},"ee",
            )
            self.assertEqual(first.revision,1)
            second=self.db.save_integration_mapping(
                "MES-DROP",
                {"equipment_id":"payload.equipment_id","code":"payload.alarm_code","event_id":"event_id"},
                {"schema":"alarm-v2"},"ee",
            )
            self.assertEqual(second.revision,2)
            self.assertFalse(self.db.list_integration_mappings("MES-DROP")[1].active)

            self.db.ingest_alarm("ETCH-INT","VAC-01",severity="Critical",message="Vacuum low")
            result=dispatch_pending(self.db,100)
            self.assertGreaterEqual(result["sent"],1)
            files=list(Path(td).glob("*.json"))
            self.assertEqual(len(files),1)
            payload=json.loads(files[0].read_text(encoding="utf-8"))
            self.assertEqual(payload["equipment_id"],"ETCH-INT")
            self.assertEqual(payload["code"],"VAC-01")
            self.assertEqual(payload["schema"],"alarm-v2")
            self.assertIn("event_id",payload)

    def test_dead_letter_after_five_failures_and_manual_replay(self):
        self.db.save_integration_endpoint({
            "endpoint_id":"BROKEN","name":"Broken","adapter_type":"FILE","target":"/tmp",
            "topics":"*","auth_env":"","enabled":True,
        })
        self.db.ingest_alarm("ETCH-INT","A1")
        delivery=self.db.integration_delivery_status(10)[0]
        for n in range(5):
            delivery=self.db.mark_integration_delivery(delivery.id,False,f"failure {n}")
        self.assertEqual(delivery.status,"Dead Letter")
        replayed=self.db.replay_integration_delivery(delivery.id)
        self.assertEqual(replayed.status,"Pending")
        self.assertIsNone(replayed.next_attempt_at)

    def test_inbound_receipt_is_idempotent(self):
        payload={"equipment_id":"ETCH-INT","value":123}
        first,created=self.db.receive_integration_event(
            "FDC","evt-100","fdc.measurement","EQUIPMENT","ETCH-INT",payload
        )
        self.assertTrue(created)
        again,created_again=self.db.receive_integration_event(
            "FDC","evt-100","fdc.measurement","EQUIPMENT","ETCH-INT",payload
        )
        self.assertFalse(created_again)
        self.assertEqual(first.id,again.id)
        self.assertEqual(len(self.db.list_inbound_receipts()),1)

    def test_alarm_incident_can_chain_to_work_order(self):
        self.db.save_orchestration_rule({
            "rule_id":"CRIT-ALARM-INCIDENT-CHAIN","name":"Critical alarm incident",
            "topic_pattern":"equipment.alarm.active",
            "condition_json":{"payload.severity":"Critical"},
            "action_type":"CREATE_INCIDENT_FROM_ALARM",
            "action_json":{"actor":"ee","owner":"ee"},"enabled":True,"priority":10,
        })
        self.db.save_orchestration_rule({
            "rule_id":"ALARM-INCIDENT-WO","name":"Alarm incident work order",
            "topic_pattern":"incident.created.from_alarm","condition_json":{},
            "action_type":"CREATE_WORK_ORDER_FROM_TICKET",
            "action_json":{"actor":"ee"},"enabled":True,"priority":20,
        })
        alarm=self.db.ingest_alarm("ETCH-INT","TEMP-HIGH",severity="Critical",message="Temperature high")
        first=process_pending_rules(self.db,500)
        self.assertEqual(first["executed"],1)
        linked=next(x for x in self.db.list_alarms("ETCH-INT") if x.event_key==alarm.event_key)
        self.assertTrue(linked.related_ticket)
        second=process_pending_rules(self.db,500)
        self.assertEqual(second["executed"],1)
        work_orders=self.db.list_work_orders("ETCH-INT")
        self.assertEqual(len(work_orders),1)
        links=self.db.list_work_order_links(work_orders[0].work_order_no)
        self.assertTrue(any(x.entity_type=="TICKET" and x.entity_key==linked.related_ticket for x in links))
        third=process_pending_rules(self.db,500)
        self.assertEqual(third["executed"],0)

    def test_rule_can_apply_controlled_disposition(self):
        self.db.save_orchestration_rule({
            "rule_id":"CRIT-ALARM-HOLD","name":"Critical alarm hold",
            "topic_pattern":"equipment.alarm.active",
            "condition_json":{"payload.severity":"Critical"},
            "action_type":"SET_DISPOSITION",
            "action_json":{"actor":"ee","state":"Hold","reason":"Critical alarm","release_criteria":"Engineering review"},
            "enabled":True,"priority":5,
        })
        self.db.ingest_alarm("ETCH-INT","VAC-CRIT",severity="Critical")
        result=process_pending_rules(self.db,200)
        self.assertEqual(result["executed"],1)
        self.assertEqual(self.db.get_equipment("ETCH-INT").disposition,"Hold")

    def test_critical_alarm_rule_creates_incident_exactly_once(self):
        self.db.save_orchestration_rule({
            "rule_id":"CRIT-ALARM-INCIDENT","name":"Critical alarm incident",
            "topic_pattern":"equipment.alarm.active",
            "condition_json":{"payload.severity":{"in":["Critical","Fatal"]}},
            "action_type":"CREATE_INCIDENT_FROM_ALARM",
            "action_json":{"actor":"ee","owner":"ee"},
            "enabled":True,"priority":10,
        })
        alarm=self.db.ingest_alarm("ETCH-INT","RF-ARC",severity="Critical",message="Arc detected")
        first=process_pending_rules(self.db,200)
        self.assertEqual(first["executed"],1)
        linked=next(x for x in self.db.list_alarms("ETCH-INT") if x.event_key==alarm.event_key)
        self.assertTrue(linked.related_ticket)
        ticket_no=linked.related_ticket
        second=process_pending_rules(self.db,200)
        self.assertEqual(second["executed"],0)
        tickets=[x for x in self.db.list_tickets() if x.ticket_no==ticket_no]
        self.assertEqual(len(tickets),1)
        executions=[x for x in self.db.list_orchestration_executions() if x.rule_id=="CRIT-ALARM-INCIDENT" and x.status=="EXECUTED"]
        self.assertEqual(len(executions),1)


if __name__=="__main__":
    unittest.main()
