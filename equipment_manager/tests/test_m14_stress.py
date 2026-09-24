from __future__ import annotations

import os
import time
import unittest
from datetime import datetime, timedelta

from database import Database, EquipmentAlarmEvent


@unittest.skipUnless(os.getenv("EMS_RUN_STRESS","0")=="1","set EMS_RUN_STRESS=1 for 100k timeline stress gate")
class M14StressTests(unittest.TestCase):
    def test_100k_event_timeline_first_page(self):
        db=Database("sqlite:///:memory:")
        db.save_equipment({
            "equipment_id":"STRESS-01","name":"Stress Tool","equipment_type":"Etch",
            "site":"SITE","building":"B1","floor":"1","area":"ETCH","owner":"eng",
        },user="admin")
        base=datetime.utcnow()
        batch=[]
        with db.session() as s:
            for i in range(100_000):
                batch.append(EquipmentAlarmEvent(
                    event_key=f"STRESS-{i:06d}",equipment_id="STRESS-01",
                    alarm_code=f"A{i%100:03d}",severity="Warning",message="stress",
                    source="STRESS",state="CLEARED",occurred_at=base-timedelta(seconds=i),
                ))
                if len(batch)==5000:
                    s.add_all(batch);s.flush();batch=[]
            if batch:s.add_all(batch)
        start=time.perf_counter()
        rows=db.equipment_activity_timeline("STRESS-01",700)
        elapsed=time.perf_counter()-start
        self.assertEqual(len(rows),700)
        self.assertLess(elapsed,1.5,f"timeline first page took {elapsed:.3f}s")


if __name__=="__main__":
    unittest.main()
