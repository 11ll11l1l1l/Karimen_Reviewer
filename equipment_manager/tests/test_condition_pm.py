import unittest
from datetime import datetime

from database import Database, PMTask


class ConditionPMTriggerTests(unittest.TestCase):
    def setUp(self):
        self.db=Database("sqlite:///:memory:")
        self.db.create_user("tech","Tech","tech-password-123","Maintenance")
        self.db.save_equipment({"equipment_id":"ETCH-01","name":"Etcher"},user="tech")
        self.db.save_pm_definition({
            "pm_id":"PM-VAC","name":"Vacuum investigation","equipment_id":"ETCH-01",
            "schedule_type":"Event Triggered","frequency_value":0,"frequency_unit":"hours",
            "anchor_mode":"Original Due","estimated_hours":1,"required_people":1,
            "required_skill":"","required_parts":"","sop_path":"","active":True,
        })
        self.meter=self.db.save_meter({
            "equipment_id":"ETCH-01","meter_code":"BASE_PRESSURE","name":"Base Pressure",
            "unit":"Pa","meter_mode":"GAUGE","current_value":0.0,"active":True,
        })
        self.trigger=self.db.save_pm_condition_trigger({
            "trigger_id":"VAC-HIGH","equipment_id":"ETCH-01","pm_id":"PM-VAC",
            "meter_code":"BASE_PRESSURE","comparator":">","threshold":10.0,
            "reset_threshold":8.0,"active":True,
        })

    def test_threshold_triggers_once_and_latches(self):
        _,tasks=self.db.record_meter_reading("ETCH-01","BASE_PRESSURE",11.0,"tech",expected_version=self.meter.version)
        self.assertEqual(len(tasks),1)
        trig=self.db.list_pm_condition_triggers()[0]
        self.assertTrue(trig.latched)

        meter=self.db.list_meters("ETCH-01")[0]
        _,again=self.db.record_meter_reading("ETCH-01","BASE_PRESSURE",12.0,"tech",expected_version=meter.version)
        self.assertEqual(again,[])
        occurrences=self.db.list_pm_condition_occurrences("VAC-HIGH")
        self.assertEqual(len([x for x in occurrences if x.event_type=="TRIGGERED"]),1)

    def test_hysteresis_reset_rearms_trigger(self):
        _,tasks=self.db.record_meter_reading("ETCH-01","BASE_PRESSURE",11.0,"tech",expected_version=self.meter.version)
        with self.db.session() as s:
            task=s.get(PMTask,tasks[0].id)
            task.status="Completed"

        meter=self.db.list_meters("ETCH-01")[0]
        self.db.record_meter_reading("ETCH-01","BASE_PRESSURE",9.0,"tech",expected_version=meter.version)
        self.assertTrue(self.db.list_pm_condition_triggers()[0].latched)

        meter=self.db.list_meters("ETCH-01")[0]
        self.db.record_meter_reading("ETCH-01","BASE_PRESSURE",8.0,"tech",expected_version=meter.version)
        self.assertFalse(self.db.list_pm_condition_triggers()[0].latched)

        meter=self.db.list_meters("ETCH-01")[0]
        _,tasks2=self.db.record_meter_reading("ETCH-01","BASE_PRESSURE",11.0,"tech",expected_version=meter.version)
        self.assertEqual(len(tasks2),1)

    def test_below_threshold_does_not_trigger(self):
        _,tasks=self.db.record_meter_reading("ETCH-01","BASE_PRESSURE",7.5,"tech",expected_version=self.meter.version)
        self.assertEqual(tasks,[])


if __name__=="__main__":
    unittest.main()
