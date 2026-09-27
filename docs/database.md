# Database setup and code walkthrough

## Connect Neon to Render

1. Create a free Neon project for LeafVision, preferably near the Render region.
2. In Neon, open **Connect** and copy the PostgreSQL connection string. The pooled
   connection string is suitable. Keep the supplied TLS parameters, including
   `sslmode=require` (or a stricter mode) and any `channel_binding` setting.
3. In the existing Render web service's **Environment** settings, add
   `DATABASE_URL` with that complete string as its value. Do not include shell
   commands or surrounding quotation marks. Never put the real value in Git.
4. Push this code, then deploy the updated service. The existing Dockerfile
   installs requirements and starts `app.py`; no start-command change is needed.
5. At startup, the app creates the tables if they do not exist. The supplied
   database role therefore needs permission to create tables in its schema.
6. Upload a photo on the actual deployed site and submit feedback. In Neon's SQL
   editor, run the read-only query below to verify it arrived.

```sql
SELECT id, created_at, predicted_label, looked_wrong, comment
FROM feedback
ORDER BY id DESC
LIMIT 50;
```

`SELECT` chooses the columns to view. `FROM feedback` selects the table.
`ORDER BY id DESC` puts newer submissions first; `LIMIT 50` limits the output.
These records are visible through your authenticated database account, not through
a public feedback-list endpoint in the app.

Restart the Render service and run the query again to confirm the rows remain.
The separate UI preview in `scripts/preview.py` deliberately does not save data,
so it cannot verify a real database connection.

Render's free service can still sleep: external storage preserves the records but
does not eliminate model startup time. Monitor the database provider's free usage
limits and export collected feedback periodically. Both the application and the
database run remotely; your computer does not need to stay on.

## What changed and why

### requirements.txt: the database driver

`psycopg[binary]>=3.2,<4` installs Psycopg version 3, the Python PostgreSQL driver.
The binary extra provides compiled dependencies so the Docker build does not need
a compiler or PostgreSQL development tools. The version range excludes a future
major version with potentially incompatible behavior.

### schema.sql: the structure of the stored data

A schema is the definition of tables and their columns. The `feedback` table has:

| Column | Meaning |
| --- | --- |
| `id` | A database-generated integer identifying each row; it is the primary key. |
| `created_at` | A timezone-aware timestamp assigned by the database when inserting. |
| `predicted_label` | The model's predicted class; blank values are rejected. |
| `looked_wrong` | A required boolean: true for thumbs down, false for thumbs up. |
| `comment` | Optional text represented by an empty string, limited to 500 characters. |
| `blur_score` | An existing optional field retained for compatibility; currently null. |

`NOT NULL` prevents a required value from being absent. `DEFAULT` supplies a value
when an insert omits it. `CHECK` enforces a condition inside the database itself.
`TIMESTAMPTZ` represents a point in time; database tools may display it in their
session timezone, while the Python reader converts it to UTC.

The `app_stats` table holds one row whose `id` must be 1 and whose `scan_count`
cannot be negative. The startup insert creates this row with zero scans.
`ON CONFLICT (id) DO NOTHING` preserves an existing count on subsequent starts.
`CREATE TABLE IF NOT EXISTS` preserves existing tables; it does not automatically
change their definitions if a future release needs new columns.

### feedback_store.py: choosing storage and performing operations

`_database_url()` reads `DATABASE_URL` from the server environment. On Render,
missing configuration raises `StorageError` so the app cannot accidentally save
real feedback to temporary disk. Outside Render, an absent URL selects the
existing local JSON implementation. A configured but broken URL never falls back
to JSON. `LEAFVISION_STORE_PATH` only affects local JSON mode.

`StorageError` inherits from `OSError`, letting route handlers catch both local
file failures and database failures with the same exception handler.

`_connection()` is a context manager, used with Python's `with` statement. It opens
a short-lived connection with a 10-second connection timeout and sets a 10-second
SQL statement timeout for the transaction. `row_factory=dict_row` makes results
accessible by column names such as `row['scan_count']` instead of numeric positions.

The `yield` temporarily hands the connection to the caller. When the caller's
block finishes, Psycopg commits successful changes, or rolls them back if an
exception occurred, then closes the connection. A commit failure also raises an
error: the route does not claim a successful save before commit completes.
The timeouts bound connection attempts and individual queries; they are not a
single end-to-end request deadline.

Driver errors become generic `StorageError` messages. Raw errors can contain
connection details or submitted text, so the application avoids logging them.

`initialize_storage()` reads `schema.sql` and executes it in a transaction at app
startup. If setup fails, startup fails visibly rather than accepting submissions
against an uninitialized database. Restarting after fixing configuration retries
setup. An outage after startup is handled by the routes below.

`save_feedback()` inserts a row using `%s` placeholders and a separate tuple of
values. These are Psycopg parameters, not Python string interpolation. A comment
containing quotes or SQL-looking text remains plain data and cannot become a SQL
command. The existing trimming and 500-character cap are preserved; the HTTP
route also rejects oversized input before it reaches this function.

`increment_scan_count()` uses `UPDATE ... SET scan_count = scan_count + 1` and
`RETURNING scan_count`. PostgreSQL increments the stored value atomically and
returns the result, preventing simultaneous requests from overwriting each
other's increments. There is no separate read-then-write race.

`get_scan_count()` reads the counter. `get_all()` reads the counter and feedback
rows, converts timestamps to UTC strings, and returns the existing dictionary
shape. It is a Python helper, not a public HTTP endpoint.

The JSON helpers remain for offline local development. Their lock protects only
threads in one process, so deployed multi-process use should select PostgreSQL.

### app.py: startup and failure handling

The app calls `initialize_storage()` before loading the model, making database
setup errors appear early. The model path now matches the checked-in file,
`model/leafvision_efficientnet_v1.keras`; the old filename did not exist.

`/feedback` keeps its existing validation and returns success only after the
storage call completes. Storage failures return HTTP 503 so the existing browser
form keeps the user's choices and allows retrying.

`/predict` still returns a successful prediction if updating the scan counter
fails. It returns `scan_count: null`, meaning unavailable, rather than inventing
a number or discarding the model result. Failed counter increments are not queued
for later recovery; this is an activity indicator, not an exact audit log.

`/stats` returns HTTP 503 when its count cannot be read. Logs contain a generic
message for feedback/counter failures without credentials or raw comments.

### .gitignore and tests

`.env` and `.env.*` are excluded from Git to reduce accidental credential commits.
The app does not automatically load those files; Render injects environment
variables itself. Existing collected JSON data remains excluded as well.

Run `python -m unittest discover -s tests -v` after installing Flask and Psycopg.
The tests replace the expensive classifier with a mock, and driver-boundary tests
replace the database connection. They cover parameterized inserts, transaction
failures, startup configuration, counter errors, and the HTTP feedback behavior.
They do not prove that your Neon credentials or deployed network connection work;
the deployed submission and read-back check above verifies that final connection.

## Existing data and interpretation

Switching to PostgreSQL starts a new store; it does not import `data/store.json`.
Back up that file if it contains real responses and import them deliberately
rather than re-importing on every deployment. Uploaded photos are not stored.

Votes are opinions, not verified accuracy measurements or unique tester counts.
Submission retries after an ambiguous network failure may create duplicates;
this version does not implement server-side submission deduplication.
