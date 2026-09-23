import os
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor

from database import Database


@unittest.skipUnless(os.getenv("EMS_TEST_POSTGRES_URL"),"PostgreSQL test URL not configured")
class PostgreSQLConcurrencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.url=os.environ["EMS_TEST_POSTGRES_URL"]
        cls.db=Database(cls.url)

    def test_two_state_transitions_cannot_both_commit_from_same_version(self):
        suffix=__import__("datetime").datetime.utcnow().strftime("%H%M%S%f")
        equipment_id=f"RACE-EQ-{suffix}"
        self.db.save_equipment({"equipment_id":equipment_id,"name":"Race Tool"},user="ci")
        version=self.db.get_equipment(equipment_id).version
        barrier=threading.Barrier(2)

        def worker(target,reason):
            db=Database(self.url)
            barrier.wait()
            try:
                db.transition_equipment_state(
                    equipment_id,target,reason_code=reason,reason_text="Concurrency CI",
                    user="ci",expected_version=version,
                )
                return "success"
            except RuntimeError as exc:
                if "CONFLICT" in str(exc):return "conflict"
                raise

        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda args:worker(*args),[
                ("Production","RELEASED"),
                ("PM","PM_UNSCHEDULED"),
            ]))
        self.assertEqual(sorted(results),["conflict","success"])
        events=self.db.list_equipment_state_events(equipment_id)
        # Initial event plus exactly one successful operational transition.
        self.assertEqual(len(events),2)

    def test_inventory_row_lock_prevents_over_reservation(self):
        suffix=__import__("datetime").datetime.utcnow().strftime("%H%M%S%f")
        part=f"RACE-PART-{suffix}"
        location=f"LOC-{suffix}"
        self.db.save_storage_location({"location_code":location,"name":"Concurrency Bin"})
        self.db.save_inventory_item({
            "part_number":part,"description":"Race part","location_code":location,
            "quantity":10.0,"min_quantity":0.0,"condition":"Available",
        })
        barrier=threading.Barrier(2)

        def reserve(actor):
            db=Database(self.url)
            barrier.wait()
            ok,result=db.reserve_inventory(part,7.0,actor,location_code=location)
            return ok

        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(reserve,["ci-a","ci-b"]))
        self.assertEqual(results.count(True),1)
        self.assertEqual(results.count(False),1)
        active=[r for r in self.db.list_reservations(True) if r.part_number==part and r.location_code==location]
        self.assertEqual(sum(r.quantity for r in active),7.0)


if __name__=="__main__":
    unittest.main()
