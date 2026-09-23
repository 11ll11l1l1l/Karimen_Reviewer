import unittest
from datetime import datetime, timedelta

from database import AUTH_MAX_FAILURES, Database


class AuthenticationSecurityTests(unittest.TestCase):
    def setUp(self):
        self.db=Database("sqlite:///:memory:")
        self.db.create_user("engineer","Engineer","correct-password","Equipment Engineer")

    def test_repeated_failures_lock_account(self):
        for _ in range(AUTH_MAX_FAILURES):
            self.assertIsNone(self.db.authenticate("engineer","wrong-password",workstation="WS-A"))
        state=self.db.auth_security_status("engineer")
        self.assertIsNotNone(state.locked_until)
        self.assertIsNone(self.db.authenticate("engineer","correct-password",workstation="WS-A"))
        attempts=self.db.list_login_attempts("engineer")
        self.assertEqual(attempts[0].reason,"Locked")

    def test_admin_unlock_allows_valid_login(self):
        for _ in range(AUTH_MAX_FAILURES):
            self.db.authenticate("engineer","bad",workstation="WS-A")
        self.db.unlock_user("engineer","admin","ADMIN-PC")
        user=self.db.authenticate("engineer","correct-password",workstation="WS-A")
        self.assertEqual(user["username"],"engineer")
        state=self.db.auth_security_status("engineer")
        self.assertEqual(state.failed_attempts,0)
        self.assertIsNone(state.locked_until)

    def test_success_resets_failure_counter(self):
        self.db.authenticate("engineer","bad",workstation="WS-A")
        self.db.authenticate("engineer","bad",workstation="WS-A")
        user=self.db.authenticate("engineer","correct-password",workstation="WS-A")
        self.assertIsNotNone(user)
        state=self.db.auth_security_status("engineer")
        self.assertEqual(state.failed_attempts,0)

    def test_expired_lockout_gets_fresh_attempt_window(self):
        for _ in range(AUTH_MAX_FAILURES):
            self.db.authenticate("engineer","bad",workstation="WS-A")
        with self.db.session() as s:
            from database import AuthSecurityState
            from sqlalchemy import select
            state=s.scalar(select(AuthSecurityState).where(AuthSecurityState.username=="engineer"))
            state.locked_until=datetime.utcnow()-timedelta(seconds=1)
        self.db.authenticate("engineer","bad",workstation="WS-A")
        state=self.db.auth_security_status("engineer")
        self.assertEqual(state.failed_attempts,1)
        self.assertIsNone(state.locked_until)

    def test_password_reset_clears_lockout(self):
        for _ in range(AUTH_MAX_FAILURES):
            self.db.authenticate("engineer","bad")
        self.db.update_user("engineer",password="new-correct-password")
        self.assertIsNotNone(self.db.authenticate("engineer","new-correct-password"))


if __name__=="__main__":
    unittest.main()
