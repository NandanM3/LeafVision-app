"""Driver-boundary tests; no network or real database credentials required."""
import os
import ssl
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import feedback_store as store


class PostgresStoreTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://leaf%40user:p%40ss@test.invalid:5433/leaf%20vision?sslmode=require&channel_binding=require",
            "RENDER": "",
        })
        environment.start()
        self.addCleanup(environment.stop)
        self.connection = MagicMock()
        self.cursor = self.connection.cursor.return_value
        driver = patch.object(store.pg8000.dbapi, "connect", return_value=self.connection)
        self.connect = driver.start()
        self.addCleanup(driver.stop)

    def test_missing_render_configuration_fails(self):
        with patch.dict(os.environ, {"DATABASE_URL": "", "RENDER": "true"}):
            with self.assertRaisesRegex(store.StorageError, "Set DATABASE_URL"):
                store.initialize_storage()
        self.connect.assert_not_called()

    def test_local_initialization_does_not_connect(self):
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            store.initialize_storage()
        self.connect.assert_not_called()

    def test_initialization_executes_schema(self):
        store.initialize_storage()
        sql = self.cursor.execute.call_args_list[-1].args[0]
        self.assertIn("CREATE TABLE IF NOT EXISTS feedback", sql)
        self.assertIn("ON CONFLICT (id) DO NOTHING", sql)
        self.connection.commit.assert_called_once_with()
        self.connection.close.assert_called_once_with()

    def test_comment_is_a_parameter_not_sql(self):
        comment = "It's wrong 🌿'; DROP TABLE feedback; --"
        store.save_feedback("Tomato___healthy", True, comment)
        sql, parameters = self.cursor.execute.call_args_list[-1].args
        self.assertNotIn(comment, sql)
        self.assertEqual(parameters, ("Tomato___healthy", True, comment, None))
        settings = self.connect.call_args.kwargs
        self.assertEqual(settings["user"], "leaf@user")
        self.assertEqual(settings["password"], "p@ss")
        self.assertEqual(settings["host"], "test.invalid")
        self.assertEqual(settings["port"], 5433)
        self.assertEqual(settings["database"], "leaf vision")
        self.assertEqual(settings["timeout"], 10)
        self.assertIsInstance(settings["ssl_context"], ssl.SSLContext)
        self.connection.commit.assert_called_once_with()

    def test_atomic_counter_returns_database_value(self):
        self.cursor.fetchone.return_value = (42,)
        self.assertEqual(store.increment_scan_count(), 42)
        self.assertIn("scan_count = scan_count + 1", self.cursor.execute.call_args_list[-1].args[0])
        self.assertEqual(store.get_scan_count(), 42)

    def test_read_records_serializes_timestamp(self):
        self.cursor.fetchone.return_value = (3,)
        self.cursor.description = [("id",), ("created_at",), ("comment",)]
        self.cursor.fetchall.return_value = [
            (1, datetime(2026, 9, 24, tzinfo=timezone.utc), "")
        ]
        data = store.get_all()
        self.assertEqual(data["scan_count"], 3)
        self.assertEqual(data["feedback"][0]["created_at"], "2026-09-24T00:00:00+00:00")

    def test_connection_failure_never_writes_local_file(self):
        self.connect.side_effect = store.pg8000.dbapi.InterfaceError("secret password")
        with patch.object(store, "_write") as write:
            with self.assertRaises(store.StorageError) as caught:
                store.save_feedback("Tomato___healthy", False, "")
        self.assertNotIn("secret", str(caught.exception))
        write.assert_not_called()

    def test_failed_commit_is_not_reported_as_saved(self):
        self.connection.commit.side_effect = store.pg8000.dbapi.InterfaceError("connection lost on commit")
        with self.assertRaises(store.StorageError):
            store.save_feedback("Tomato___healthy", False, "")
        self.connection.rollback.assert_called_once_with()
        self.connection.close.assert_called_once_with()

    def test_query_failure_rolls_back_and_closes(self):
        self.cursor.execute.side_effect = [None, store.pg8000.dbapi.DatabaseError("query failed")]
        with self.assertRaises(store.StorageError):
            store.save_feedback("Tomato___healthy", False, "")
        self.connection.rollback.assert_called_once_with()
        self.connection.close.assert_called_once_with()

    def test_invalid_database_url_is_rejected_without_connecting(self):
        with patch.dict(os.environ, {"DATABASE_URL": "not-a-postgres-url"}):
            with self.assertRaisesRegex(store.StorageError, "valid PostgreSQL URL"):
                store.initialize_storage()
        self.connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
