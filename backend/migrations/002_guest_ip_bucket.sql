-- Allow the 'guest_ip' rate-limit bucket (guest creation limit). SQLite cannot alter a CHECK
-- constraint, so rebuild the table; existing events are kept.
CREATE TABLE rate_events_new (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  bucket TEXT NOT NULL CHECK (bucket IN ('login_nick', 'login_ip', 'register_ip', 'guest_ip')),
  key_hash TEXT NOT NULL,
  created_at TEXT NOT NULL
);
INSERT INTO rate_events_new (id, bucket, key_hash, created_at)
  SELECT id, bucket, key_hash, created_at FROM rate_events;
DROP TABLE rate_events;
ALTER TABLE rate_events_new RENAME TO rate_events;
CREATE INDEX ix_rate_events ON rate_events (bucket, key_hash, created_at);
