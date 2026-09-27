"""PostgreSQL persistence when DATABASE_URL is set; JSON for local development.

Database failures never fall back to a temporary local file. JSON mode is
single-process only; PostgreSQL handles concurrent counter updates itself.
"""

import json
import os
import threading
from datetime import datetime, timezone
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

_lock = threading.Lock()
_STORE_PATH = Path(os.environ.get("LEAFVISION_STORE_PATH", str(Path(__file__).resolve().parent / "data" / "store.json")))


class StorageError(OSError):
    """A storage failure safe for callers to report without connection details."""


def _database_url():
    url = os.environ.get("DATABASE_URL", "").strip()
    # Refuse a deployment that would appear to save data on ephemeral storage.
    if not url and os.environ.get("RENDER") == "true":
        raise StorageError("Set DATABASE_URL in Render before deploying.")
    return url


@contextmanager
def _connection():
    try:
        # Each operation gets a short-lived connection. A successful block
        # commits; an exception rolls back; either way the connection closes.
        with psycopg.connect(_database_url(), connect_timeout=10, row_factory=dict_row) as conn:
            conn.execute("SET LOCAL statement_timeout = '10s'")
            yield conn
    except psycopg.Error:
        # Driver errors can include private connection details or submitted text.
        raise StorageError("Database operation failed.") from None


def initialize_storage():
    """Create missing tables at startup without clearing existing records."""
    if _database_url():
        schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
        with _connection() as conn:
            conn.execute(schema)


def _read():
    if not _STORE_PATH.exists():
        return {"scan_count": 0, "feedback": []}
    with open(_STORE_PATH, encoding="utf-8") as f:
        return json.load(f)


def _write(data):
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = _STORE_PATH.with_suffix(".tmp")
    with open(temporary_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    temporary_path.replace(_STORE_PATH)


def get_all():
    """Everything collected so far -- for the admin view."""
    if _database_url():
        with _connection() as conn:
            count = conn.execute("SELECT scan_count FROM app_stats WHERE id = 1").fetchone()
            records = conn.execute("SELECT * FROM feedback ORDER BY id").fetchall()
        for record in records:
            record["created_at"] = record["created_at"].astimezone(timezone.utc).isoformat()
        return {"scan_count": count["scan_count"], "feedback": records}
    with _lock:
        return _read()


def increment_scan_count():
    """Call once per successful prediction. Returns the new count."""
    if _database_url():
        with _connection() as conn:
            row = conn.execute(
                "UPDATE app_stats SET scan_count = scan_count + 1 WHERE id = 1 RETURNING scan_count"
            ).fetchone()
        return row["scan_count"]
    with _lock:
        data = _read()
        data["scan_count"] += 1
        _write(data)
        return data["scan_count"]


def get_scan_count():
    if _database_url():
        with _connection() as conn:
            row = conn.execute("SELECT scan_count FROM app_stats WHERE id = 1").fetchone()
        return row["scan_count"]
    with _lock:
        return _read()["scan_count"]


def save_feedback(predicted_label, looked_wrong, comment, blur_score=None):
    """
    predicted_label: what the model said (str)
    looked_wrong: bool -- did the user flag this as wrong
    comment: free text -- what they actually photographed / what it should
             have said. Optional, may be empty.
    blur_score: the variance-of-Laplacian score for this image, if
                available -- lets failure reports later be correlated with
                how blurred the source photo was.
    """
    if _database_url():
        with _connection() as conn:
            conn.execute(
                """INSERT INTO feedback (predicted_label, looked_wrong, comment, blur_score)
                   VALUES (%s, %s, %s, %s)""",
                (predicted_label, looked_wrong, comment.strip()[:500], blur_score),
            )
        return
    with _lock:
        data = _read()
        data["feedback"].append({
            "created_at": datetime.now(timezone.utc).isoformat(),
            "predicted_label": predicted_label,
            "looked_wrong": looked_wrong,
            "comment": comment.strip()[:500],  # cap length, basic sanity
            "blur_score": blur_score,
        })
        _write(data)
