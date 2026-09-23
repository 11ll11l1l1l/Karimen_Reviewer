import unittest

from database import Database


class CollaborationTests(unittest.TestCase):
    def setUp(self):
        self.db=Database("sqlite:///:memory:")
        self.db.create_user("alice","Alice Engineer","alice-password-123","Equipment Engineer")
        self.db.create_user("bob","Bob Technician","bob-password-123","Technician")
        self.db.save_equipment({"equipment_id":"ETCH-COLLAB","name":"Collaboration Etcher"},user="alice")

    def test_comment_auto_watches_author_and_mentions_user(self):
        comment=self.db.add_record_comment(
            "EQUIPMENT","ETCH-COLLAB",
            "Pressure trend reviewed. @bob please verify the chamber after the next check.",
            "alice","ETCH-COLLAB",
        )
        rows=self.db.list_record_comments("EQUIPMENT","ETCH-COLLAB")
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0].id,comment.id)
        self.assertTrue(self.db.is_watching_record("EQUIPMENT","ETCH-COLLAB","alice"))

        mentions=self.db.list_user_mentions("bob",True)
        self.assertEqual(len(mentions),1)
        self.assertEqual(mentions[0].entity_type,"EQUIPMENT")
        self.assertEqual(mentions[0].entity_key,"ETCH-COLLAB")
        self.assertEqual(mentions[0].mentioned_by,"alice")

        work=self.db.my_work("bob")
        item=next(x for x in work if x["kind"]=="MENTION")
        self.assertEqual(item["entity_type"],"EQUIPMENT")
        self.assertEqual(item["entity_key"],"ETCH-COLLAB")

    def test_mark_read_removes_unread_mention(self):
        self.db.add_record_comment("EQUIPMENT","ETCH-COLLAB","@bob check this tool","alice","ETCH-COLLAB")
        mention=self.db.list_user_mentions("bob",True)[0]
        self.db.mark_mention_read(mention.id,"bob")
        self.assertEqual(self.db.list_user_mentions("bob",True),[])
        self.assertEqual(len(self.db.list_user_mentions("bob",False)),1)

    def test_watch_and_unwatch_record(self):
        self.db.set_record_watch("EQUIPMENT","ETCH-COLLAB","bob",True)
        self.assertTrue(self.db.is_watching_record("EQUIPMENT","ETCH-COLLAB","bob"))
        watchers={x.username for x in self.db.list_record_watchers("EQUIPMENT","ETCH-COLLAB")}
        self.assertIn("bob",watchers)
        self.db.set_record_watch("EQUIPMENT","ETCH-COLLAB","bob",False)
        self.assertFalse(self.db.is_watching_record("EQUIPMENT","ETCH-COLLAB","bob"))


if __name__=="__main__":
    unittest.main()
