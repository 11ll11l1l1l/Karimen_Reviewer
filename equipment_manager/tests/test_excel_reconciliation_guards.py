import unittest

from database import Database
from excel_reconcile import apply_reconciliation, reconcile_equipment


class ExcelReconciliationGuardTests(unittest.TestCase):
    def test_duplicate_keys_are_rejected_before_apply(self):
        db = Database("sqlite:///:memory:")
        with self.assertRaisesRegex(ValueError, "Duplicate equipment key"):
            reconcile_equipment(
                db,
                [{"equipment_id": "EQ-1"}, {"equipment_id": "EQ-1"}],
                {"name": "Name"},
            )

    def test_deletion_is_refused_by_default(self):
        db = Database("sqlite:///:memory:")
        with self.assertRaisesRegex(ValueError, "explicit delete approval"):
            apply_reconciliation(
                db,
                [{"status": "DELETE", "data": {}}],
                entity="equipment",
                user="engineer",
            )


if __name__ == "__main__":
    unittest.main()
