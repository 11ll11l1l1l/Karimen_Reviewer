import os
import tempfile
import unittest

from sqlalchemy import create_engine, text

from database import Database


class SchemaGuardTests(unittest.TestCase):
    def test_incomplete_existing_table_is_rejected(self):
        fd,path=tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            engine=create_engine(f"sqlite:///{path}")
            with engine.begin() as conn:
                conn.execute(text("CREATE TABLE equipment (id INTEGER PRIMARY KEY, equipment_id VARCHAR(100))"))
            with self.assertRaises(RuntimeError) as ctx:
                Database(f"sqlite:///{path}")
            self.assertIn("DATABASE SCHEMA INCOMPATIBLE",str(ctx.exception))
            self.assertIn("equipment: missing columns",str(ctx.exception))
        finally:
            try: os.remove(path)
            except OSError: pass


if __name__=="__main__":
    unittest.main()
