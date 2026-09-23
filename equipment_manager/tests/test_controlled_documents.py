import os
import tempfile
import unittest

from database import Database


class ControlledDocumentTests(unittest.TestCase):
    def setUp(self):
        self.db=Database("sqlite:///:memory:")
        self.files=[]
        self.db.create_controlled_document({
            "document_id":"SOP-ETCH-001",
            "entity_type":"Equipment",
            "entity_key":"ETCH-01",
            "document_type":"SOP",
            "title":"Etcher Chamber PM",
            "owner":"Equipment Engineering",
        },"author","CI")

    def tearDown(self):
        for p in self.files:
            try:os.remove(p)
            except OSError:pass

    def make_file(self,content:bytes):
        fd,path=tempfile.mkstemp(suffix=".txt");os.close(fd)
        with open(path,"wb") as f:f.write(content)
        self.files.append(path);return path

    def test_author_cannot_approve_own_revision(self):
        path=self.make_file(b"revision A")
        row=self.db.add_controlled_revision("SOP-ETCH-001","A",path,"Initial release","author")
        with self.assertRaises(ValueError):
            self.db.approve_controlled_revision(row.id,"author",expected_version=row.version)

    def test_independent_approval_sets_effective_revision(self):
        path=self.make_file(b"revision A")
        row=self.db.add_controlled_revision("SOP-ETCH-001","A",path,"Initial","author")
        approved=self.db.approve_controlled_revision(row.id,"controller",expected_version=row.version)
        self.assertEqual(approved.status,"Effective")
        doc=self.db.list_controlled_documents()[0]
        self.assertEqual(doc.current_revision,"A")
        effective=self.db.effective_controlled_revision("SOP-ETCH-001")
        self.assertEqual(effective.revision,"A")
        ok,_=self.db.verify_controlled_revision_file(effective.id)
        self.assertTrue(ok)

    def test_file_tamper_blocks_approval(self):
        path=self.make_file(b"registered")
        row=self.db.add_controlled_revision("SOP-ETCH-001","A",path,"Initial","author")
        with open(path,"wb") as f:f.write(b"changed after registration")
        with self.assertRaises(ValueError):
            self.db.approve_controlled_revision(row.id,"controller",expected_version=row.version)

    def test_new_effective_revision_supersedes_previous(self):
        p1=self.make_file(b"A")
        r1=self.db.add_controlled_revision("SOP-ETCH-001","A",p1,"Initial","author")
        self.db.approve_controlled_revision(r1.id,"controller",expected_version=r1.version)
        p2=self.make_file(b"B")
        r2=self.db.add_controlled_revision("SOP-ETCH-001","B",p2,"Improved procedure","author")
        self.db.approve_controlled_revision(r2.id,"controller",expected_version=r2.version)
        rows=self.db.list_controlled_revisions("SOP-ETCH-001")
        by_rev={r.revision:r for r in rows}
        self.assertEqual(by_rev["A"].status,"Superseded")
        self.assertEqual(by_rev["B"].status,"Effective")
        self.assertEqual(self.db.list_controlled_documents()[0].current_revision,"B")

    def test_rejected_revision_never_becomes_effective(self):
        path=self.make_file(b"bad revision")
        row=self.db.add_controlled_revision("SOP-ETCH-001","X",path,"Draft","author")
        rejected=self.db.reject_controlled_revision(row.id,"controller","Incorrect limits",expected_version=row.version)
        self.assertEqual(rejected.status,"Rejected")
        self.assertIsNone(self.db.effective_controlled_revision("SOP-ETCH-001"))


if __name__=="__main__":
    unittest.main()
