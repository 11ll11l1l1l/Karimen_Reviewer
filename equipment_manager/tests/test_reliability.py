import unittest
from datetime import datetime, timedelta

from sqlalchemy import select

from database import Database, EquipmentStateEvent


class ReliabilityMetricsTests(unittest.TestCase):
    def setUp(self):
        self.db=Database("sqlite:///:memory:")
        self.db.save_equipment({"equipment_id":"ETCH-01","name":"Etcher"},user="seed")
        eq=self.db.get_equipment("ETCH-01")
        self.db.transition_equipment_state(
            "ETCH-01","Production",
            reason_code="RELEASED",reason_text="Qualified",
            user="engineer",expected_version=eq.version,
        )
        eq=self.db.get_equipment("ETCH-01")
        self.db.transition_equipment_state(
            "ETCH-01","Down",
            reason_code="FAILURE",reason_text="RF trip",
            related_ticket="INC-1",owner="EE-A",
            user="engineer",expected_version=eq.version,
        )
        eq=self.db.get_equipment("ETCH-01")
        self.db.transition_equipment_state(
            "ETCH-01","Qualification",
            reason_code="QUALIFICATION",reason_text="Post-repair check",
            owner="EE-A",user="engineer",expected_version=eq.version,
        )
        eq=self.db.get_equipment("ETCH-01")
        self.db.transition_equipment_state(
            "ETCH-01","Production",
            reason_code="RELEASED",reason_text="Verification passed",
            user="engineer",expected_version=eq.version,
        )

        self.t0=datetime(2026,9,20,0,0,0)
        times=[self.t0,self.t0+timedelta(hours=2),self.t0+timedelta(hours=12),self.t0+timedelta(hours=16),self.t0+timedelta(hours=18)]
        with self.db.session() as s:
            events=list(s.scalars(
                select(EquipmentStateEvent)
                .where(EquipmentStateEvent.equipment_id=="ETCH-01")
                .order_by(EquipmentStateEvent.id)
            ))
            self.assertEqual(len(events),5)
            for event,when in zip(events,times):
                event.changed_at=when

    def test_unplanned_downtime_mttr_mtbf_and_availability(self):
        result=self.db.reliability_summary(
            "ETCH-01",self.t0,self.t0+timedelta(hours=48)
        )
        self.assertEqual(result["failure_count"],1)
        self.assertAlmostEqual(result["unplanned_downtime_hours"],4.0,places=3)
        self.assertAlmostEqual(result["planned_downtime_hours"],0.0,places=3)
        self.assertAlmostEqual(result["downtime_hours"],4.0,places=3)
        self.assertAlmostEqual(result["mttr_hours"],4.0,places=3)
        self.assertAlmostEqual(result["mtbf_hours"],44.0,places=3)
        self.assertAlmostEqual(result["availability_pct"],91.6666667,places=3)

    def test_period_starts_at_commissioning_event(self):
        result=self.db.reliability_summary(
            "ETCH-01",self.t0-timedelta(hours=10),self.t0+timedelta(hours=10)
        )
        self.assertAlmostEqual(result["period_hours"],10.0,places=3)

    def test_planned_pm_is_separate_from_unplanned_downtime(self):
        self.db.save_equipment({"equipment_id":"CVD-01","name":"CVD"},user="seed")
        eq=self.db.get_equipment("CVD-01")
        self.db.transition_equipment_state(
            "CVD-01","Production",reason_code="RELEASED",reason_text="Start",
            user="engineer",expected_version=eq.version,
        )
        eq=self.db.get_equipment("CVD-01")
        self.db.transition_equipment_state(
            "CVD-01","PM",reason_code="PM_UNSCHEDULED",reason_text="Service",
            user="tech",expected_version=eq.version,
        )
        eq=self.db.get_equipment("CVD-01")
        self.db.transition_equipment_state(
            "CVD-01","Available",reason_code="RELEASED",reason_text="PM complete",
            user="tech",expected_version=eq.version,
        )

        with self.db.session() as s:
            events=list(s.scalars(
                select(EquipmentStateEvent)
                .where(EquipmentStateEvent.equipment_id=="CVD-01")
                .order_by(EquipmentStateEvent.id)
            ))
            times=[self.t0,self.t0+timedelta(hours=1),self.t0+timedelta(hours=10),self.t0+timedelta(hours=14)]
            for event,when in zip(events,times):
                event.changed_at=when

        result=self.db.reliability_summary("CVD-01",self.t0,self.t0+timedelta(hours=20))
        self.assertAlmostEqual(result["planned_downtime_hours"],4.0,places=3)
        self.assertAlmostEqual(result["unplanned_downtime_hours"],0.0,places=3)
        self.assertEqual(result["failure_count"],0)
        self.assertAlmostEqual(result["availability_pct"],80.0,places=3)


if __name__=="__main__":
    unittest.main()
