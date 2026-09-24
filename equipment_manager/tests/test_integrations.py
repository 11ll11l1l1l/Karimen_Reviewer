import json
import tempfile
import unittest
from pathlib import Path

from database import Database
from integrations import dispatch_pending


class IntegrationOutboxTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=Database("sqlite:///:memory:")
        self.db.create_user("ee","Engineer","engineer-password-123","Equipment Engineer")
        self.db.save_equipment({"equipment_id":"ETCH-01","name":"Etcher"},user="ee")
        self.db.save_integration_endpoint({
            "endpoint_id":"FILE-ALL",
            "name":"Local integration drop",
            "adapter_type":"FILE",
            "target":self.tmp.name,
            "topics":"equipment.state.changed,incident.state.changed",
            "enabled":True,
        })

    def tearDown(self):
        self.tmp.cleanup()

    def test_state_change_commits_outbox_and_dispatches_file(self):
        eq=self.db.get_equipment("ETCH-01")
        self.db.transition_equipment_state(
            "ETCH-01","Production",
            reason_code="RELEASED",reason_text="Qualified",
            user="ee",expected_version=eq.version,
        )
        pending=self.db.pending_integration_deliveries()
        self.assertEqual(len(pending),1)
        delivery,event,endpoint=pending[0]
        self.assertEqual(event.topic,"equipment.state.changed")
        result=dispatch_pending(self.db)
        self.assertEqual(result["sent"],1)
        files=list(Path(self.tmp.name).glob("*.json"))
        self.assertEqual(len(files),1)
        payload=json.loads(files[0].read_text(encoding="utf-8"))
        self.assertEqual(payload["topic"],"equipment.state.changed")
        self.assertEqual(payload["payload"]["equipment_id"],"ETCH-01")
        self.assertEqual(self.db.integration_delivery_status()[0].status,"Sent")

    def test_endpoint_topic_filter_prevents_irrelevant_delivery(self):
        self.db.save_integration_endpoint({
            "endpoint_id":"QUAL-ONLY",
            "name":"Qualification only",
            "adapter_type":"FILE",
            "target":self.tmp.name,
            "topics":"qualification.approved",
            "enabled":True,
        })
        eq=self.db.get_equipment("ETCH-01")
        self.db.transition_equipment_state(
            "ETCH-01","Production",
            reason_code="RELEASED",reason_text="Qualified",
            user="ee",expected_version=eq.version,
        )
        pending=self.db.pending_integration_deliveries()
        self.assertEqual({x[2].endpoint_id for x in pending},{"FILE-ALL"})

    def test_dead_letter_and_replay_controls_preserve_delivery_identity(self):
        blocker=Path(self.tmp.name)/"dead-blocker"
        blocker.write_text("x",encoding="utf-8")
        self.db.save_integration_endpoint({
            "endpoint_id":"DEAD",
            "name":"Dead-letter target",
            "adapter_type":"FILE",
            "target":str(blocker),
            "topics":"equipment.state.changed",
            "enabled":True,
        })
        eq=self.db.get_equipment("ETCH-01")
        self.db.transition_equipment_state(
            "ETCH-01","Production",
            reason_code="RELEASED",reason_text="Qualified",
            user="ee",expected_version=eq.version,
        )
        dispatch_pending(self.db)
        row=next(x for x in self.db.integration_delivery_rows() if x["endpoint_id"]=="DEAD")
        self.assertEqual(row["status"],"Retry")
        delivery_id=row["id"];event_id=row["event_id"]
        self.db.dead_letter_integration_delivery(delivery_id,"Manual quarantine")
        dead=next(x for x in self.db.integration_delivery_rows() if x["id"]==delivery_id)
        self.assertEqual(dead["status"],"DeadLetter")
        self.assertEqual(dead["event_id"],event_id)
        self.assertIn("Manual quarantine",dead["last_error"])
        self.db.requeue_integration_delivery(delivery_id)
        replay=next(x for x in self.db.integration_delivery_rows() if x["id"]==delivery_id)
        self.assertEqual(replay["status"],"Pending")
        self.assertEqual(replay["event_id"],event_id)

    def test_bulk_requeue_dead_letters_can_scope_endpoint(self):
        eq=self.db.get_equipment("ETCH-01")
        self.db.transition_equipment_state(
            "ETCH-01","Production",
            reason_code="RELEASED",reason_text="Qualified",
            user="ee",expected_version=eq.version,
        )
        pending=self.db.pending_integration_deliveries()
        self.assertTrue(pending)
        delivery_id=pending[0][0].id
        endpoint_id=pending[0][0].endpoint_id
        self.db.dead_letter_integration_delivery(delivery_id,"operator quarantine")
        self.assertEqual(self.db.requeue_dead_letters("NOT-THIS-ENDPOINT"),0)
        self.assertEqual(self.db.requeue_dead_letters(endpoint_id),1)
        row=next(x for x in self.db.integration_delivery_rows() if x["id"]==delivery_id)
        self.assertEqual(row["status"],"Pending")

    def test_failed_file_delivery_is_retryable(self):
        # Point a FILE endpoint at a path that is a file, not a directory.
        blocker=Path(self.tmp.name)/"blocker"
        blocker.write_text("x",encoding="utf-8")
        self.db.save_integration_endpoint({
            "endpoint_id":"BROKEN",
            "name":"Broken target",
            "adapter_type":"FILE",
            "target":str(blocker),
            "topics":"equipment.state.changed",
            "enabled":True,
        })
        eq=self.db.get_equipment("ETCH-01")
        self.db.transition_equipment_state(
            "ETCH-01","Production",
            reason_code="RELEASED",reason_text="Qualified",
            user="ee",expected_version=eq.version,
        )
        result=dispatch_pending(self.db)
        self.assertEqual(result["failed"],1)
        statuses={x.endpoint_id:x for x in self.db.integration_delivery_status()}
        self.assertEqual(statuses["BROKEN"].status,"Retry")
        self.assertGreater(statuses["BROKEN"].attempts,0)


if __name__=="__main__":
    unittest.main()
