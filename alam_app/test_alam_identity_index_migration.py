import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "011_index_account_primary_visitor.sql"


class AccountIdentityIndexMigrationTests(unittest.TestCase):
    def test_migration_is_idempotent_and_targets_fk_column(self):
        sql = MIGRATION.read_text(encoding="utf-8").lower()
        self.assertIn("create index if not exists", sql)
        self.assertIn("account_profiles_primary_visitor_id_idx", sql)
        self.assertIn("on public.account_profiles (primary_visitor_id)", sql)

    def test_migration_is_non_destructive(self):
        sql = MIGRATION.read_text(encoding="utf-8").lower()
        for forbidden in ("drop table", "delete from", "truncate", "drop column"):
            self.assertNotIn(forbidden, sql)


if __name__ == "__main__":
    unittest.main()
