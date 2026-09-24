import unittest

from database import Database


class CollaborationTests(unittest.TestCase):
    def setUp(self):
        self.db=Database("sqlite:///:memory:")
        self.db.create_user("alice","Alice Engineer","alice-password-123","Equipment Engineer")
        self.db.create_user("bob","Bob Technician","bob-password-123","Technician")
        self.db.create_user("cara","Cara Engineer","cara-password-123","Equipment Engineer")
        self.db.save_equipment({"equipment_id":"ETCH-COLLAB","name":"Collaboration Etcher"},user="alice")

    def test_comment_auto_watches_author_mentions_user_and_notifies_watchers(self):
        self.db.set_record_watch("EQUIPMENT","ETCH-COLLAB","cara",True)
        comment=self.db.add_record_comment(
            "EQUIPMENT","ETCH-COLLAB",
            "Pressure trend reviewed. @bob please verify the chamber after the next check.",
            "alice","ETCH-COLLAB",
        )
        rows=self.db.list_record_comments("EQUIPMENT","ETCH-COLLAB")
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0].id,comment.id)
        self.assertTrue(self.db.is_watching_record("EQUIPMENT","ETCH-COLLAB","alice"))

        bob=self.db.list_user_record_notifications("bob",True)
        self.assertEqual(len(bob),1)
        self.assertEqual(bob[0].notification_type,"MENTION")
        self.assertEqual(bob[0].entity_type,"EQUIPMENT")
        self.assertEqual(bob[0].entity_key,"ETCH-COLLAB")

        cara=self.db.list_user_record_notifications("cara",True)
        self.assertEqual(len(cara),1)
        self.assertEqual(cara[0].notification_type,"WATCH")

        work=self.db.my_work("bob")
        item=next(x for x in work if x["kind"]=="COLLAB")
        self.assertEqual(item["entity_type"],"EQUIPMENT")
        self.assertEqual(item["entity_key"],"ETCH-COLLAB")
        self.assertIn("Mention from alice",item["summary"])

    def test_mark_read_removes_notification_from_my_work(self):
        self.db.add_record_comment("EQUIPMENT","ETCH-COLLAB","@bob check this tool","alice","ETCH-COLLAB")
        note=self.db.list_user_record_notifications("bob",True)[0]
        self.db.mark_record_notification_read(note.id,"bob")
        self.assertEqual(self.db.list_user_record_notifications("bob",True),[])
        self.assertFalse(any(x["kind"]=="COLLAB" for x in self.db.my_work("bob")))

    def test_watch_unwatch_and_no_self_notification(self):
        self.db.set_record_watch("EQUIPMENT","ETCH-COLLAB","bob",True)
        self.assertTrue(self.db.is_watching_record("EQUIPMENT","ETCH-COLLAB","bob"))
        self.db.add_record_comment("EQUIPMENT","ETCH-COLLAB","Routine note","bob","ETCH-COLLAB")
        self.assertEqual(self.db.list_user_record_notifications("bob",True),[])
        self.db.set_record_watch("EQUIPMENT","ETCH-COLLAB","bob",False)
        self.assertFalse(self.db.is_watching_record("EQUIPMENT","ETCH-COLLAB","bob"))


if __name__=="__main__":
    unittest.main()
