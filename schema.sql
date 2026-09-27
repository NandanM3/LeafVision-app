-- Safe to run again: existing tables, feedback, and counts are preserved.
CREATE TABLE IF NOT EXISTS feedback (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    predicted_label TEXT NOT NULL CHECK (length(predicted_label) > 0),
    looked_wrong BOOLEAN NOT NULL,
    comment VARCHAR(500) NOT NULL DEFAULT '',
    blur_score DOUBLE PRECISION
);

-- The id constraint makes this a single-row counter table.
CREATE TABLE IF NOT EXISTS app_stats (
    id SMALLINT PRIMARY KEY CHECK (id = 1),
    scan_count BIGINT NOT NULL DEFAULT 0 CHECK (scan_count >= 0)
);

INSERT INTO app_stats (id, scan_count) VALUES (1, 0)
ON CONFLICT (id) DO NOTHING;
