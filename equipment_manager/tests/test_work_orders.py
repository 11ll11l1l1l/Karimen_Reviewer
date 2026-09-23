import unittest

from database import Database


class WorkOrderLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.db=Database("sqlite:///:memory:")
        self.db.create_user("ee","Equipment Engineer","engineer-password-123","Equipment Engineer")
        self.db.save_equipment({"equipment_id":"ETCH-01","name":"Etcher 01"},user="ee")
        self.ticket=self.db.save_ticket({
            "ticket_no":"INC-WO-1","equipment_id":"ETCH-01","title":"Vacuum instability",
            "description":"Investigate vacuum instability","severity":"S2","priority":"P2","owner":"ee",
            "root_cause":"","corrective_action":"","verification":"","created_by":"ee",
        })
        self.db.save_pm_definition({
            "pm_id":"PM-WO","name":"Work-order PM","equipment_id":"ETCH-01",
            "schedule_type":"Interval","frequency_value":30,"frequency_unit":"days",
            "anchor_mode":"Original Due","early_window_days":1,"grace_days":1,
            "estimated_hours":2.0,"required_people":1,"required_skill":"",
            "required_parts":"","sop_path":"","active":True,"revision":1,
        })
        self.pm=self.db.upsert_pm_task({
            "equipment_id":"ETCH-01","pm_id":"PM-WO","pm_name":"Work-order PM",
            "status":"Scheduled","assigned_to":"ee","estimated_hours":2.0,"priority":"Normal",
        })

    def test_ticket_creates_single_open_work_order_with_source_link(self):
        first=self.db.create_work_order_from_ticket(self.ticket.ticket_no,"ee")
        second=self.db.create_work_order_from_ticket(self.ticket.ticket_no,"ee")
        self.assertEqual(first.work_order_no,second.work_order_no)
        links=self.db.list_work_order_links(first.work_order_no)
        self.assertTrue(any(x.entity_type=="TICKET" and x.entity_key==self.ticket.ticket_no and x.relation=="SOURCE" for x in links))
        self.assertTrue(first.qualification_required)
        self.assertTrue(first.release_required)

    def test_pm_creates_linked_work_order(self):
        row=self.db.create_work_order_from_pm(self.pm.id,"ee")
        self.assertEqual(row.equipment_id,"ETCH-01")
        links=self.db.list_work_order_links(row.work_order_no)
        self.assertTrue(any(x.entity_type=="PM_TASK" and x.entity_key==str(self.pm.id) for x in links))

    def test_work_order_lifecycle_is_evented_and_version_checked(self):
        row=self.db.create_work_order_from_ticket(self.ticket.ticket_no,"ee")
        started=self.db.transition_work_order(row.work_order_no,"In Progress","ee",expected_version=row.version)
        self.assertEqual(started.status,"In Progress")
        with self.assertRaises(RuntimeError):
            self.db.transition_work_order(row.work_order_no,"Completed","ee",expected_version=row.version)
        completed=self.db.transition_work_order(started.work_order_no,"Ready for Qualification","ee",expected_version=started.version)
        final=self.db.transition_work_order(completed.work_order_no,"Completed","ee",expected_version=completed.version)
        self.assertEqual(final.status,"Completed")
        events=self.db.list_work_order_events(row.work_order_no)
        self.assertEqual([x.to_state for x in events],["Open","In Progress","Ready for Qualification","Completed"])

    def test_waiting_parts_requires_reason(self):
        row=self.db.create_work_order_from_ticket(self.ticket.ticket_no,"ee")
        started=self.db.transition_work_order(row.work_order_no,"In Progress","ee",expected_version=row.version)
        with self.assertRaises(ValueError):
            self.db.transition_work_order(started.work_order_no,"Waiting Parts","ee",expected_version=started.version)


if __name__=="__main__":
    unittest.main()
