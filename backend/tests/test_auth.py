from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.app.auth import hash_session_token
from backend.app.storage import DraftStore


class AdminAuthTest(unittest.TestCase):
    def test_admin_login_session_and_password_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = DraftStore(Path(tmp) / "auth.sqlite3")
            store.initialize()
            admin = store.ensure_admin_user("teacher", "initial-password")

            self.assertIsNone(store.authenticate_admin("teacher", "wrong-password"))
            authenticated = store.authenticate_admin("teacher", "initial-password")
            self.assertEqual(authenticated, admin)

            token_hash = hash_session_token("first-session")
            store.create_admin_session(admin["id"], token_hash, 7)
            self.assertEqual(store.get_admin_by_session(token_hash)["username"], "teacher")

            store.change_admin_password(admin["id"], "initial-password", "new-password-123")
            self.assertIsNone(store.get_admin_by_session(token_hash))
            self.assertIsNone(store.authenticate_admin("teacher", "initial-password"))
            self.assertIsNotNone(store.authenticate_admin("teacher", "new-password-123"))


if __name__ == "__main__":
    unittest.main()
