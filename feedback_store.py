"""PostgreSQL persistence when DATABASE_URL is set; JSON for local development.

Database failures never fall back to a temporary local file. JSON mode is
single-process only; PostgreSQL handles concurrent counter updates itself.
"""

import json
import os
import ssl
import threading
from datetime import datetime, timezone
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import unquote, urlparse

import pg8000.dbapi

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
    conn = None
    try:
        parsed = urlparse(_database_url())
        if parsed.scheme not in {"postgres", "postgresql"} or not all(
            (parsed.hostname, parsed.username, parsed.path.lstrip("/"))
        ):
            raise StorageError("DATABASE_URL is not a valid PostgreSQL URL.")

        # pg8000 implements PostgreSQL's network protocol in Python. A verified
        # TLS context encrypts the connection and checks Neon's certificate.
        conn = pg8000.dbapi.connect(
            user=unquote(parsed.username),
            password=unquote(parsed.password or ""),
            host=parsed.hostname,
            port=parsed.port or 5432,
            database=unquote(parsed.path.lstrip("/")),
            ssl_context=ssl.create_default_context(),
            timeout=10,
            application_name="leafvision",
        )
        cursor = conn.cursor()
        cursor.execute("SET LOCAL statement_timeout = '10s'")
        yield cursor
        conn.commit()
    except (pg8000.dbapi.Error, ValueError):
        if conn is not None:
            try:
                conn.rollback()
            except pg8000.dbapi.Error:
                pass
        # Driver errors can include private connection details or submitted text.
        raise StorageError("Database operation failed.") from None
    finally:
        if conn is not None:
            try:
                conn.close()
            except pg8000.dbapi.Error:
                pass


def initialize_storage():
    """Create missing tables at startup without clearing existing records."""
    if _database_url():
        print("Preparing PostgreSQL schema with the pure-Python pg8000 driver...")
        schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
        with _connection() as cursor:
            print("PostgreSQL connection opened.")
            cursor.execute(schema)
        print("PostgreSQL schema ready.")


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
        with _connection() as cursor:
            cursor.execute("SELECT scan_count FROM app_stats WHERE id = 1")
            count = cursor.fetchone()[0]
            cursor.execute("SELECT * FROM feedback ORDER BY id")
            columns = [column[0] for column in cursor.description]
            records = [dict(zip(columns, row)) for row in cursor.fetchall()]
        for record in records:
            record["created_at"] = record["created_at"].astimezone(timezone.utc).isoformat()
        return {"scan_count": count, "feedback": records}
    with _lock:
        return _read()


def increment_scan_count():
    """Call once per successful prediction. Returns the new count."""
    if _database_url():
        with _connection() as cursor:
            cursor.execute(
                "UPDATE app_stats SET scan_count = scan_count + 1 WHERE id = 1 RETURNING scan_count"
            )
            row = cursor.fetchone()
        return row[0]
    with _lock:
        data = _read()
        data["scan_count"] += 1
        _write(data)
        return data["scan_count"]


def get_scan_count():
    if _database_url():
        with _connection() as cursor:
            cursor.execute("SELECT scan_count FROM app_stats WHERE id = 1")
            row = cursor.fetchone()
        return row[0]
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
        with _connection() as cursor:
            cursor.execute(
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
