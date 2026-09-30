import tempfile
import unittest
from pathlib import Path

from database import Database


class EquipmentBatchTests(unittest.TestCase):
    def test_batch_create_and_update_are_atomic(self):
        with tempfile.TemporaryDirectory() as root:
            db=Database(f"sqlite:///{Path(root)/'ems.db'}")
            first=db.save_equipment({"equipment_id":"ETCH-01","name":"Etcher A"})
            rows=db.save_equipment_batch([
                {
                    "data":{"equipment_id":"ETCH-01","name":"Etcher B"},
                    "expected_version":first.version,
                },
                {
                    "data":{"equipment_id":"CMP-01","name":"Polisher"},
                    "expected_version":None,
                },
            ],user="planner",workstation="TEST-PC")
            self.assertEqual(len(rows),2)
            self.assertEqual(db.get_equipment("ETCH-01").name,"Etcher B")
            self.assertEqual(db.get_equipment("CMP-01").name,"Polisher")

            stale_version=first.version
            with self.assertRaises(RuntimeError):
                db.save_equipment_batch([
                    {
                        "data":{"equipment_id":"ETCH-01","name":"Should Roll Back"},
                        "expected_version":stale_version,
                    },
                    {
                        "data":{"equipment_id":"CVD-01","name":"Should Not Exist"},
                        "expected_version":None,
                    },
                ],user="planner",workstation="TEST-PC")
            self.assertEqual(db.get_equipment("ETCH-01").name,"Etcher B")
            self.assertIsNone(db.get_equipment("CVD-01"))


if __name__=="__main__":
    unittest.main()
