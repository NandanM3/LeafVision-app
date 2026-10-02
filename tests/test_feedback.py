"""Feedback tests run without loading TensorFlow or the classifier."""
import importlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import feedback_store


class FeedbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        inference = Mock()
        inference.load_class_map.return_value = {0: "Tomato___healthy"}
        with patch.dict(os.environ, {"DATABASE_URL": "", "RENDER": ""}), patch.dict(sys.modules, {
            "numpy": Mock(), "cv2": Mock(), "inference.predict": inference,
        }):
            cls.module = importlib.import_module("app")
            cls.application = cls.module.app
        cls.application.config["TESTING"] = True

    def setUp(self):
        environment = patch.dict(os.environ, {"DATABASE_URL": "", "RENDER": ""})
        environment.start()
        self.addCleanup(environment.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = patch.object(feedback_store, "_STORE_PATH", Path(self.temp.name) / "store.json")
        self.store.start()
        self.addCleanup(self.store.stop)
        self.client = self.application.test_client()

    def payload(self, **changes):
        return dict(predicted_label="Tomato___healthy", looked_wrong=False, comment="") | changes

    def test_both_votes_persist_with_optional_comment_and_timestamp(self):
        for vote, comment in [(False, ""), (True, "  Expected blight 🌿  ")]:
            response = self.client.post("/feedback", json=self.payload(looked_wrong=vote, comment=comment))
            self.assertEqual(response.status_code, 200)
        records = feedback_store.get_all()["feedback"]
        self.assertEqual([r["looked_wrong"] for r in records], [False, True])
        self.assertEqual(records[1]["comment"], "Expected blight 🌿")
        self.assertIn("+00:00", records[0]["created_at"])
        self.assertEqual(feedback_store.increment_scan_count(), 1)
        self.assertEqual(len(feedback_store.get_all()["feedback"]), 2)

    def test_invalid_submissions_do_not_write(self):
        for payload in [[], None, {}, self.payload(looked_wrong="false"),
                        self.payload(looked_wrong=None), self.payload(predicted_label="unknown"),
                        self.payload(comment=[]), self.payload(comment="x" * 501)]:
            with self.subTest(payload=payload):
                self.assertEqual(self.client.post("/feedback", json=payload).status_code, 400)
        self.assertEqual(feedback_store.get_all()["feedback"], [])

    def test_storage_failure_does_not_claim_success(self):
        with patch.object(feedback_store, "save_feedback", side_effect=OSError("disk unavailable")):
            response = self.client.post("/feedback", json=self.payload())
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("ok", response.json)

    def test_page_has_feedback_form(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'id="feedbackForm"', response.data)

    def test_database_failure_does_not_claim_success(self):
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@unused/db"}), patch.object(
            feedback_store.pg8000.dbapi, "connect",
            side_effect=feedback_store.pg8000.dbapi.InterfaceError("private details")
        ):
            response = self.client.post("/feedback", json=self.payload())
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(b"private details", response.data)
        self.assertEqual(feedback_store.get_all()["feedback"], [])

    def test_stats_failure_is_reported(self):
        with patch.object(feedback_store, "get_scan_count", side_effect=feedback_store.StorageError()):
            self.assertEqual(self.client.get("/stats").status_code, 503)

    def test_counter_failure_does_not_lose_prediction(self):
        result = [{"label": "Tomato___healthy", "confidence": 95}]
        with patch.object(self.module, "predict", return_value=result), patch.object(
            feedback_store, "increment_scan_count", side_effect=feedback_store.StorageError()
        ):
            response = self.client.post("/predict", data={"image": (io.BytesIO(b"mock image"), "leaf.jpg")})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["top"], result[0])
        self.assertIsNone(response.json["scan_count"])


if __name__ == "__main__":
    unittest.main()
