from __future__ import annotations

import os
import time
import unittest
import tempfile
from pathlib import Path

import pandas as pd
from datetime import datetime, timedelta

from database import Database, EquipmentAlarmEvent
from services import auto_mapping, dataframe_to_equipment, read_table


@unittest.skipUnless(os.getenv("EMS_RUN_STRESS","0")=="1","set EMS_RUN_STRESS=1 for 100k timeline stress gate")
class M14StressTests(unittest.TestCase):
    def test_100k_event_timeline_first_page(self):
        db=Database(os.getenv("EMS_TEST_POSTGRES_URL","sqlite:///:memory:"))
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


    def test_20k_row_excel_import_preview(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"equipment_20k.xlsx"
            source=pd.DataFrame({
                "equipment_id":[f"EQ-{i:05d}" for i in range(20_000)],
                "name":[f"Tool {i}" for i in range(20_000)],
                "equipment_type":["Etch"]*20_000,
                "site":["SITE"]*20_000,
                "building":["B1"]*20_000,
                "floor":["1"]*20_000,
                "area":["ETCH"]*20_000,
                "owner":["eng"]*20_000,
            })
            source.to_excel(path,index=False)
            start=time.perf_counter()
            loaded=read_table(str(path))
            mapping=auto_mapping(list(loaded.columns))
            rows,errors=dataframe_to_equipment(loaded,mapping)
            elapsed=time.perf_counter()-start
            self.assertFalse(errors)
            self.assertEqual(len(rows),20_000)
            self.assertLess(elapsed,12.0,f"20k-row Excel preview/normalization took {elapsed:.3f}s")


if __name__=="__main__":
    unittest.main()
