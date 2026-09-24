import json
import unittest
from datetime import datetime

from database import Database


class WorkflowAutomationTests(unittest.TestCase):
    def setUp(self):
        self.db=Database("sqlite:///:memory:")
        self.db.create_user("ee","Equipment Engineer","engineer-password-123","Equipment Engineer")
        self.db.save_equipment({"equipment_id":"ETCH-01","name":"Etcher 01","owner":"ee"},user="ee")

    def test_critical_alarm_rule_creates_connected_work_once(self):
        self.db.save_workflow_rule({
            "rule_id":"ALARM-CRITICAL",
            "name":"Critical alarm response",
            "trigger":"ALARM_ACTIVE",
            "priority":10,
            "enabled":True,
            "match_json":json.dumps({"severity":["Critical","Fatal"]}),
            "actions_json":json.dumps([
                {"type":"CREATE_INCIDENT","priority":"P1","severity":"S1","title":"Critical tool alarm","owner":"ee"},
                {"type":"SET_DISPOSITION","state":"Hold","reason":"Critical alarm automation"},
                {"type":"CREATE_HANDOVER","pending_work":"Critical alarm follow-up","next_owner":"ee"},
            ]),
        },"ee")
        alarm=self.db.ingest_alarm(
            "ETCH-01","E999",severity="Critical",message="Vacuum protection trip",
            source="FDC",event_key="alarm-fixed-key",
        )
        tickets=[x for x in self.db.list_tickets() if x.equipment_id=="ETCH-01"]
        self.assertEqual(len(tickets),1)
        self.assertEqual(tickets[0].priority,"P1")
        equipment=self.db.get_equipment("ETCH-01")
        self.assertEqual(equipment.disposition,"Hold")
        handovers=[x for x in self.db.list_endorsements() if x.equipment_id=="ETCH-01"]
        self.assertEqual(len(handovers),1)
        executions=self.db.list_workflow_automation_executions()
        self.assertEqual(len(executions),1)
        self.assertEqual(executions[0].status,"Completed")

        # Re-ingesting the same external event is idempotent.
        self.db.ingest_alarm(
            "ETCH-01","E999",severity="Critical",message="Vacuum protection trip",
            source="FDC",event_key="alarm-fixed-key",
        )
        self.assertEqual(len([x for x in self.db.list_tickets() if x.equipment_id=="ETCH-01"]),1)
        self.assertEqual(len(self.db.list_workflow_automation_executions()),1)

    def test_abnormal_pm_result_creates_work_order_once(self):
        self.db.save_workflow_rule({
            "rule_id":"PM-FAILURE-WORK",
            "name":"PM failure follow-up",
            "trigger":"PM_ABNORMAL_RESULT",
            "priority":20,
            "enabled":True,
            "match_json":"{}",
            "actions_json":json.dumps([
                {"type":"CREATE_WORK_ORDER","priority":"High","title":"Investigate PM abnormal result","qualification_required":True,"release_required":True}
            ]),
        },"ee")
        self.db.save_pm_definition({
            "pm_id":"PM-01","name":"Monthly PM","equipment_id":"ETCH-01",
            "schedule_type":"Interval","frequency_value":30,"frequency_unit":"days",
            "anchor_mode":"Original Due","early_window_days":2,"grace_days":1,
            "estimated_hours":1.0,"required_people":1,"required_skill":"",
            "required_parts":"","sop_path":"","active":True,"revision":1,
        })
        self.db.upsert_pm_spec({
            "pm_id":"PM-01","step_no":1,"activity":"Pressure check","method":"Gauge",
            "input_type":"Numeric","unit":"Pa","target":5.0,
            "spec_low":4.0,"spec_high":6.0,"acceptance_text":"",
            "reaction_plan":"Stop and investigate","sop_path":"","sop_page":"","sop_section":"",
            "revision":1,"active":True,
        })
        task=self.db.upsert_pm_task({
            "equipment_id":"ETCH-01","pm_id":"PM-01","pm_name":"Monthly PM",
            "original_due_date":datetime(2026,9,24,8,0),"scheduled_date":datetime(2026,9,24,8,0),
            "status":"Scheduled","assigned_to":"ee","estimated_hours":1.0,"priority":"Normal","sop_path":"",
        })
        execution=self.db.start_pm_execution(task.id,"ee")
        result=self.db.save_pm_result(execution.id,1,{
            "value_numeric":9.0,"value_text":"","result":"PASS","comment":"Out of specification",
            "evidence_path":"","entered_by":"ee",
        })
        self.assertIn(result.result,{"SPECIFICATION FAILURE","CONTROL FAILURE","FAIL","INVALID"})
        work=self.db.list_work_orders(equipment_id="ETCH-01")
        self.assertEqual(len(work),1)
        self.assertTrue(work[0].qualification_required)
        self.assertTrue(work[0].release_required)

        current=self.db.get_pm_result(execution.id,1)
        self.db.save_pm_result(execution.id,1,{
            "value_numeric":9.0,"value_text":"","result":"PASS","comment":"Still out",
            "evidence_path":"","entered_by":"ee",
        },current.version)
        self.assertEqual(len(self.db.list_work_orders(equipment_id="ETCH-01")),1)
        self.assertEqual(len(self.db.list_workflow_automation_executions()),1)


if __name__=="__main__":
    unittest.main()
