"""Driver-boundary tests; no network or real database credentials required."""
import os
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import feedback_store as store


class PostgresStoreTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {"DATABASE_URL": "postgresql://test.invalid/leafvision", "RENDER": ""})
        environment.start()
        self.addCleanup(environment.stop)
        self.connection = MagicMock()
        self.connection.__enter__.return_value = self.connection
        driver = patch.object(store.psycopg, "connect", return_value=self.connection)
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
        sql = self.connection.execute.call_args.args[0]
        self.assertIn("CREATE TABLE IF NOT EXISTS feedback", sql)
        self.assertIn("ON CONFLICT (id) DO NOTHING", sql)

    def test_comment_is_a_parameter_not_sql(self):
        comment = "It's wrong 🌿'; DROP TABLE feedback; --"
        store.save_feedback("Tomato___healthy", True, comment)
        sql, parameters = self.connection.execute.call_args.args
        self.assertNotIn(comment, sql)
        self.assertEqual(parameters, ("Tomato___healthy", True, comment, None))
        self.connection.__exit__.assert_called_once_with(None, None, None)
        self.assertEqual(self.connect.call_args.kwargs["connect_timeout"], 10)

    def test_atomic_counter_returns_database_value(self):
        self.connection.execute.return_value.fetchone.return_value = {"scan_count": 42}
        self.assertEqual(store.increment_scan_count(), 42)
        self.assertIn("scan_count = scan_count + 1", self.connection.execute.call_args.args[0])
        self.assertEqual(store.get_scan_count(), 42)

    def test_read_records_serializes_timestamp(self):
        self.connection.execute.return_value.fetchone.return_value = {"scan_count": 3}
        self.connection.execute.return_value.fetchall.return_value = [
            {"id": 1, "created_at": datetime(2026, 9, 24, tzinfo=timezone.utc), "comment": ""}
        ]
        data = store.get_all()
        self.assertEqual(data["scan_count"], 3)
        self.assertEqual(data["feedback"][0]["created_at"], "2026-09-24T00:00:00+00:00")

    def test_connection_failure_never_writes_local_file(self):
        self.connect.side_effect = store.psycopg.OperationalError("secret password")
        with patch.object(store, "_write") as write:
            with self.assertRaises(store.StorageError) as caught:
                store.save_feedback("Tomato___healthy", False, "")
        self.assertNotIn("secret", str(caught.exception))
        write.assert_not_called()

    def test_failed_commit_is_not_reported_as_saved(self):
        self.connection.__exit__.side_effect = store.psycopg.OperationalError("connection lost on commit")
        with self.assertRaises(store.StorageError):
            store.save_feedback("Tomato___healthy", False, "")

    def test_query_failure_exits_transaction_with_exception(self):
        self.connection.execute.side_effect = [None, store.psycopg.OperationalError("query failed")]
        self.connection.__exit__.return_value = False
        with self.assertRaises(store.StorageError):
            store.save_feedback("Tomato___healthy", False, "")
        self.assertIs(self.connection.__exit__.call_args.args[0], store.psycopg.OperationalError)


if __name__ == "__main__":
    unittest.main()
