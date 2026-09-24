import unittest

from database import Database


class CollaborationTests(unittest.TestCase):
    def setUp(self):
        self.db=Database("sqlite:///:memory:")
        self.db.create_user("ee","Equipment Engineer","engineer-password-123","Equipment Engineer")
        self.db.create_user("lead","Shift Lead","leader-password-123","Supervisor")
        self.db.save_equipment({"equipment_id":"ETCH-01","name":"Etcher 01","owner":"ee"},user="ee")

    def test_comment_mentions_and_watchers_flow_into_my_work(self):
        comment=self.db.add_record_comment(
            "EQUIPMENT","ETCH-01",
            "Vacuum recovery is stable. @lead please verify on next shift.",
            "ee","ETCH-01",
        )
        self.assertEqual(comment.created_by,"ee")
        self.assertTrue(self.db.is_record_watching("EQUIPMENT","ETCH-01","ee"))
        comments=self.db.list_record_comments("EQUIPMENT","ETCH-01")
        self.assertEqual(len(comments),1)

        mentions=self.db.list_unacknowledged_mentions("lead")
        self.assertEqual(len(mentions),1)
        mention,linked_comment=mentions[0]
        self.assertEqual(linked_comment.id,comment.id)
        self.assertEqual(linked_comment.entity_key,"ETCH-01")

        work=self.db.my_work("lead")
        hit=next(x for x in work if x["kind"]=="MENTION")
        self.assertEqual(hit["entity_type"],"EQUIPMENT")
        self.assertEqual(hit["entity_key"],"ETCH-01")

        self.db.acknowledge_mention(mention.id,"lead")
        self.assertEqual(self.db.list_unacknowledged_mentions("lead"),[])

    def test_watch_toggle_and_author_only_comment_edit(self):
        self.db.set_record_watch("EQUIPMENT","ETCH-01","lead",True)
        self.assertTrue(self.db.is_record_watching("EQUIPMENT","ETCH-01","lead"))
        watchers={x.username for x in self.db.list_record_watchers("EQUIPMENT","ETCH-01")}
        self.assertIn("lead",watchers)

        comment=self.db.add_record_comment("EQUIPMENT","ETCH-01","Initial note","ee","ETCH-01")
        with self.assertRaises(PermissionError):
            self.db.edit_record_comment(comment.id,"Unauthorized edit","lead",comment.version)
        updated=self.db.edit_record_comment(comment.id,"Updated note","ee",comment.version)
        self.assertEqual(updated.body,"Updated note")

        self.db.set_record_watch("EQUIPMENT","ETCH-01","lead",False)
        self.assertFalse(self.db.is_record_watching("EQUIPMENT","ETCH-01","lead"))


if __name__=="__main__":
    unittest.main()
