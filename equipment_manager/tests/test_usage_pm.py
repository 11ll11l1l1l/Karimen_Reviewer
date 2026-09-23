import unittest

from sqlalchemy import select

from database import Database, PMTask


class UsageTriggeredPMTests(unittest.TestCase):
    def setUp(self):
        self.db=Database("sqlite:///:memory:")
        self.db.save_equipment({"equipment_id":"ETCH-01","name":"Etcher"},user="seed")
        self.db.save_pm_definition({
            "pm_id":"PM-RF-100H",
            "name":"RF generator 100-hour PM",
            "equipment_id":"ETCH-01",
            "schedule_type":"Event Triggered",
            "frequency_value":100,
            "frequency_unit":"hours",
            "anchor_mode":"Original Due",
            "estimated_hours":2,
            "required_people":1,
            "required_skill":"Equipment",
            "required_parts":"",
            "sop_path":"",
            "active":True,
        })
        self.meter=self.db.save_meter({
            "equipment_id":"ETCH-01",
            "meter_code":"RF_HOURS",
            "name":"RF Generator Hours",
            "unit":"hours",
            "current_value":0.0,
            "active":True,
        })
        self.trigger=self.db.save_pm_usage_trigger({
            "trigger_id":"TRIG-RF-100H",
            "equipment_id":"ETCH-01",
            "pm_id":"PM-RF-100H",
            "meter_code":"RF_HOURS",
            "interval_value":100.0,
            "active":True,
        })

    def test_threshold_creates_exactly_one_pm_task(self):
        _,tasks=self.db.record_meter_reading(
            "ETCH-01","RF_HOURS",50,"tech",expected_version=self.meter.version
        )
        self.assertEqual(tasks,[])
        meter=self.db.list_meters("ETCH-01")[0]
        _,tasks=self.db.record_meter_reading(
            "ETCH-01","RF_HOURS",100,"tech",expected_version=meter.version
        )
        self.assertEqual(len(tasks),1)
        self.assertEqual(tasks[0].pm_id,"PM-RF-100H")
        self.assertEqual(tasks[0].status,"Pending")
        trigger=self.db.list_pm_usage_triggers("ETCH-01")[0]
        self.assertEqual(trigger.last_trigger_value,100.0)
        self.assertEqual(trigger.next_trigger_value,200.0)
        occurrences=self.db.list_pm_usage_occurrences("TRIG-RF-100H")
        self.assertEqual(len(occurrences),1)
        self.assertEqual(occurrences[0].trigger_value,100.0)

    def test_open_pm_prevents_duplicate_usage_task(self):
        meter=self.db.list_meters("ETCH-01")[0]
        self.db.record_meter_reading("ETCH-01","RF_HOURS",100,"tech",expected_version=meter.version)
        meter=self.db.list_meters("ETCH-01")[0]
        _,tasks=self.db.record_meter_reading("ETCH-01","RF_HOURS",250,"tech",expected_version=meter.version)
        self.assertEqual(tasks,[])
        open_tasks=[t for t in self.db.list_pm_tasks() if t.pm_id=="PM-RF-100H" and t.status!="Completed"]
        self.assertEqual(len(open_tasks),1)

    def test_next_threshold_triggers_after_previous_task_closes(self):
        meter=self.db.list_meters("ETCH-01")[0]
        _,tasks=self.db.record_meter_reading("ETCH-01","RF_HOURS",100,"tech",expected_version=meter.version)
        with self.db.session() as s:
            task=s.get(PMTask,tasks[0].id)
            task.status="Completed"
        meter=self.db.list_meters("ETCH-01")[0]
        _,tasks2=self.db.record_meter_reading("ETCH-01","RF_HOURS",205,"tech",expected_version=meter.version)
        self.assertEqual(len(tasks2),1)
        self.assertEqual(self.db.list_pm_usage_triggers("ETCH-01")[0].next_trigger_value,300.0)

    def test_decreasing_reading_requires_explicit_reset(self):
        meter=self.db.list_meters("ETCH-01")[0]
        self.db.record_meter_reading("ETCH-01","RF_HOURS",80,"tech",expected_version=meter.version)
        meter=self.db.list_meters("ETCH-01")[0]
        with self.assertRaises(ValueError):
            self.db.record_meter_reading("ETCH-01","RF_HOURS",10,"tech",expected_version=meter.version)

    def test_reset_rebases_trigger_threshold(self):
        meter=self.db.list_meters("ETCH-01")[0]
        self.db.record_meter_reading("ETCH-01","RF_HOURS",80,"tech",expected_version=meter.version)
        meter=self.db.list_meters("ETCH-01")[0]
        _,tasks=self.db.record_meter_reading(
            "ETCH-01","RF_HOURS",10,"tech",note="RF generator replaced",
            reset=True,expected_version=meter.version
        )
        self.assertEqual(tasks,[])
        trigger=self.db.list_pm_usage_triggers("ETCH-01")[0]
        self.assertEqual(trigger.last_trigger_value,10.0)
        self.assertEqual(trigger.next_trigger_value,110.0)
        readings=self.db.list_meter_readings("ETCH-01","RF_HOURS")
        self.assertEqual(readings[0].reading_type,"Reset")


if __name__=="__main__":
    unittest.main()
