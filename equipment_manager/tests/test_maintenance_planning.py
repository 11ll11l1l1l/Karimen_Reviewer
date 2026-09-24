import unittest
from datetime import datetime, timedelta

from database import Database


class MaintenancePlanningTests(unittest.TestCase):
    def setUp(self):
        self.db=Database("sqlite:///:memory:")
        self.db.create_user("planner","Planner","planner-password-123","Equipment Engineer")
        self.db.save_equipment({"equipment_id":"ETCH-01","name":"Etcher 01"},user="planner")
        self.db.save_pm_definition({
            "pm_id":"PM-MONTHLY","name":"Monthly chamber PM","equipment_id":"ETCH-01",
            "schedule_type":"Interval","frequency_value":30,"frequency_unit":"days",
            "anchor_mode":"Original Due","early_window_days":2,"grace_days":1,
            "estimated_hours":4.0,"required_people":1,"required_skill":"",
            "required_parts":"","sop_path":"","active":True,"revision":1,
        })
        self.db.save_inventory_item({
            "part_number":"FILTER-A","description":"Chamber filter","category":"Consumable",
            "manufacturer":"","model":"","compatible_equipment":"ETCH-01","quantity":10.0,
            "min_quantity":2.0,"unit":"pcs","condition":"Available","location_code":"STOCK-A",
            "image_path":"","notes":"",
        })
        self.db.upsert_pm_requirement({
            "requirement_id":"REQ-PART-FILTER","pm_id":"PM-MONTHLY","requirement_type":"PART",
            "requirement_key":"FILTER-A","description":"Replacement filter","quantity":2.0,
            "mandatory":True,"active":True,"revision":1,
        })
        self.db.upsert_pm_requirement({
            "requirement_id":"REQ-CERT-ETCH","pm_id":"PM-MONTHLY","requirement_type":"CERTIFICATION",
            "requirement_key":"ETCH-PM","description":"Etch PM certification","quantity":1.0,
            "mandatory":True,"active":True,"revision":1,
        })
        self.db.upsert_pm_spec({
            "pm_id":"PM-MONTHLY","step_no":1,"activity":"Replace chamber filter","method":"Visual",
            "input_type":"Pass / Fail","unit":"","acceptance_text":"PASS","reaction_plan":"Stop and escalate",
            "sop_path":"","sop_page":"","sop_section":"","revision":1,"active":True,
        })
        self.db.save_inventory_item({
            "part_number":"FILTER-A","description":"Chamber filter","category":"Consumable",
            "manufacturer":"","model":"","compatible_equipment":"ETCH-01","quantity":10.0,
            "min_quantity":2.0,"unit":"pcs","condition":"Available","location_code":"STOCK-A",
            "image_path":"","notes":"",
        })
        self.db.upsert_pm_requirement({
            "requirement_id":"REQ-PART-FILTER","pm_id":"PM-MONTHLY","requirement_type":"PART",
            "requirement_key":"FILTER-A","description":"Replacement filter","quantity":2.0,
            "mandatory":True,"active":True,"revision":1,
        })
        self.db.upsert_pm_requirement({
            "requirement_id":"REQ-CERT-ETCH","pm_id":"PM-MONTHLY","requirement_type":"CERTIFICATION",
            "requirement_key":"ETCH-PM","description":"Etch PM certification","quantity":1.0,
            "mandatory":True,"active":True,"revision":1,
        })
        self.db.upsert_pm_spec({
            "pm_id":"PM-MONTHLY","step_no":1,"activity":"Replace chamber filter","method":"Visual",
            "input_type":"Pass / Fail","unit":"","acceptance_text":"PASS","reaction_plan":"Stop and escalate",
            "sop_path":"","sop_page":"","sop_section":"","revision":1,"active":True,
        })
        self.due=datetime(2026,10,10,8,0)
        self.task=self.db.upsert_pm_task({
            "equipment_id":"ETCH-01","pm_id":"PM-MONTHLY","pm_name":"Monthly chamber PM",
            "original_due_date":self.due,"scheduled_date":self.due,"status":"Scheduled",
            "assigned_to":"","estimated_hours":4.0,"priority":"Normal","sop_path":"",
        })

    def test_planner_can_assign_and_reschedule_within_controlled_window(self):
        planned=self.db.plan_pm_task(
            self.task.id,"planner",scheduled_date=self.due-timedelta(days=1),
            assigned_to="planner",expected_version=self.task.version,
        )
        self.assertEqual(planned.assigned_to,"planner")
        self.assertEqual(planned.scheduled_date,self.due-timedelta(days=1))

    def test_planner_cannot_bypass_deferral_by_scheduling_beyond_grace(self):
        with self.assertRaises(ValueError) as ctx:
            self.db.plan_pm_task(
                self.task.id,"planner",scheduled_date=self.due+timedelta(days=3),
                expected_version=self.task.version,
            )
        self.assertIn("deferral",str(ctx.exception).lower())

    def test_readiness_surfaces_parts_and_certification_blocks(self):
        rows=self.db.pm_planning_rows(365,True)
        row=next(x for x in rows if x["id"]==self.task.id)
        self.assertEqual(row["parts_status"],"READY")
        self.assertEqual(row["certification_status"],"UNASSIGNED")
        planned=self.db.plan_pm_task(self.task.id,"planner",assigned_to="planner",expected_version=self.task.version)
        self.db.save_technician_certification({
            "username":"planner","cert_code":"ETCH-PM","issuer":"Training","issued_at":datetime(2026,1,1),
            "expires_at":datetime(2027,1,1),"active":True,"note":"",
        })
        readiness=self.db.pm_task_readiness(planned.id)
        self.assertEqual(readiness["parts_status"],"READY")
        self.assertEqual(readiness["certification_status"],"READY")

    def test_required_parts_reserve_and_consume_inside_pm(self):
        self.db.save_technician_certification({
            "username":"planner","cert_code":"ETCH-PM","issuer":"Training","issued_at":datetime(2026,1,1),
            "expires_at":datetime(2027,1,1),"active":True,"note":"",
        })
        planned=self.db.plan_pm_task(self.task.id,"planner",assigned_to="planner",expected_version=self.task.version)
        reservations=self.db.reserve_pm_required_parts(planned.id,"planner")
        self.assertEqual(len(reservations),1)
        self.assertEqual(reservations[0].part_number,"FILTER-A")
        self.assertEqual(reservations[0].quantity,2.0)
        execution=self.db.start_pm_execution(planned.id,"planner")
        tx=self.db.consume_pm_reserved_parts(execution.id,"planner")
        self.assertEqual(sum(-x.quantity for x in tx),2.0)
        item=next(x for x in self.db.list_inventory("FILTER-A") if x.location_code=="STOCK-A")
        self.assertEqual(item.quantity,8.0)
        active=[x for x in self.db.list_reservations() if x.pm_task_id==planned.id and x.status=="Reserved"]
        self.assertEqual(active,[])

    def test_readiness_surfaces_parts_and_certification_blocks(self):
        rows=self.db.pm_planning_rows(365,True)
        row=next(x for x in rows if x["id"]==self.task.id)
        self.assertEqual(row["parts_status"],"READY")
        self.assertEqual(row["certification_status"],"UNASSIGNED")
        planned=self.db.plan_pm_task(self.task.id,"planner",assigned_to="planner",expected_version=self.task.version)
        self.db.save_technician_certification({
            "username":"planner","cert_code":"ETCH-PM","issuer":"Training","issued_at":datetime(2026,1,1),
            "expires_at":datetime(2027,1,1),"active":True,"note":"",
        })
        readiness=self.db.pm_task_readiness(planned.id)
        self.assertEqual(readiness["parts_status"],"READY")
        self.assertEqual(readiness["certification_status"],"READY")

    def test_required_parts_reserve_and_consume_inside_pm(self):
        self.db.save_technician_certification({
            "username":"planner","cert_code":"ETCH-PM","issuer":"Training","issued_at":datetime(2026,1,1),
            "expires_at":datetime(2027,1,1),"active":True,"note":"",
        })
        planned=self.db.plan_pm_task(self.task.id,"planner",assigned_to="planner",expected_version=self.task.version)
        reservations=self.db.reserve_pm_required_parts(planned.id,"planner")
        self.assertEqual(len(reservations),1)
        self.assertEqual(reservations[0].part_number,"FILTER-A")
        self.assertEqual(reservations[0].quantity,2.0)
        execution=self.db.start_pm_execution(planned.id,"planner")
        tx=self.db.consume_pm_reserved_parts(execution.id,"planner")
        self.assertEqual(sum(-x.quantity for x in tx),2.0)
        item=next(x for x in self.db.list_inventory("FILTER-A") if x.location_code=="STOCK-A")
        self.assertEqual(item.quantity,8.0)
        active=[x for x in self.db.list_reservations() if x.pm_task_id==planned.id and x.status=="Reserved"]
        self.assertEqual(active,[])

    def test_planning_rows_expose_window_and_load_fields(self):
        rows=self.db.pm_planning_rows(365,True)
        row=next(x for x in rows if x["id"]==self.task.id)
        self.assertEqual(row["equipment_id"],"ETCH-01")
        self.assertEqual(row["estimated_hours"],4.0)
        self.assertIn(row["window"],{"IN WINDOW","OVERDUE"})


if __name__=="__main__":
    unittest.main()
