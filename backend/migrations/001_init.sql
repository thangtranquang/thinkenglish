-- ReflexEnglish schema v1 (lean). TEXT UUID keys, ISO-UTC TEXT timestamps, JSON in TEXT.

CREATE TABLE IF NOT EXISTS schema_migrations (
  version TEXT PRIMARY KEY,
  applied_at TEXT NOT NULL
);

CREATE TABLE app_meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE users (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL CHECK (kind IN ('guest', 'registered', 'system')),
  nickname TEXT,
  nickname_ci TEXT,
  password_hash TEXT,
  password_params TEXT,
  avatar_key TEXT,
  birth_year INTEGER,
  cefr_level TEXT CHECK (cefr_level IS NULL OR cefr_level IN ('A1', 'A2', 'B1')),
  guardian_email TEXT,
  guardian_consent_at TEXT,
  role TEXT NOT NULL DEFAULT 'student',
  gate_required_at TEXT,
  hide_timer INTEGER NOT NULL DEFAULT 0,
  reflex_level_unlocked INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  registered_at TEXT,
  last_seen_at TEXT NOT NULL
);
CREATE UNIQUE INDEX ux_users_nickname_ci ON users (nickname_ci) WHERE kind = 'registered';
CREATE INDEX ix_users_kind_seen ON users (kind, last_seen_at);

CREATE TABLE device_tokens (
  token_hash TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  created_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL
);
CREATE INDEX ix_device_tokens_user ON device_tokens (user_id);

CREATE TABLE sessions (
  token_hash TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  created_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  absolute_expires_at TEXT NOT NULL,
  revoked_at TEXT
);
CREATE INDEX ix_sessions_user ON sessions (user_id);
CREATE INDEX ix_sessions_expires ON sessions (expires_at);

CREATE TABLE usage_sessions (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  started_at TEXT NOT NULL,
  last_activity_at TEXT NOT NULL,
  had_write INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX ix_usage_user_activity ON usage_sessions (user_id, last_activity_at DESC);

CREATE TABLE rate_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  bucket TEXT NOT NULL CHECK (bucket IN ('login_nick', 'login_ip', 'register_ip', 'guest_ip')),
  key_hash TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX ix_rate_events ON rate_events (bucket, key_hash, created_at);

CREATE TABLE image_assets (
  id TEXT PRIMARY KEY,
  source_sha256 TEXT NOT NULL UNIQUE,
  clean_sha256 TEXT,
  phash TEXT,
  storage_path TEXT NOT NULL,
  width INTEGER,
  height INTEGER,
  first_uploaded_by TEXT REFERENCES users (id) ON DELETE SET NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE card_contents (
  id TEXT PRIMARY KEY,
  image_asset_id TEXT NOT NULL UNIQUE REFERENCES image_assets (id) ON DELETE CASCADE,
  seed_key TEXT UNIQUE,
  status TEXT NOT NULL CHECK (status IN ('processing', 'ready', 'failed')),
  model TEXT,
  prompt_version TEXT,
  ai_calls INTEGER NOT NULL DEFAULT 0,
  processing_started_at TEXT,
  topic TEXT,
  topic_tags TEXT CHECK (topic_tags IS NULL OR json_valid(topic_tags)),
  cefr_level TEXT,
  safety TEXT CHECK (safety IS NULL OR json_valid(safety)),
  moderation_status TEXT NOT NULL DEFAULT 'pending'
    CHECK (moderation_status IN ('pending', 'approved', 'rejected')),
  raw_response TEXT CHECK (raw_response IS NULL OR json_valid(raw_response)),
  error TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX ix_contents_topic ON card_contents (topic);
CREATE INDEX ix_contents_status ON card_contents (status);

CREATE TABLE card_labels (
  id TEXT PRIMARY KEY,
  content_id TEXT NOT NULL REFERENCES card_contents (id) ON DELETE CASCADE,
  position INTEGER NOT NULL,
  word TEXT NOT NULL,
  ipa TEXT,
  vi_meaning TEXT,
  accepted_answers TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(accepted_answers)),
  cefr_level TEXT,
  confidence REAL,
  x REAL CHECK (x IS NULL OR (x BETWEEN 0 AND 1)),
  y REAL CHECK (y IS NULL OR (y BETWEEN 0 AND 1)),
  box_x1 REAL CHECK (box_x1 IS NULL OR (box_x1 BETWEEN 0 AND 1)),
  box_y1 REAL CHECK (box_y1 IS NULL OR (box_y1 BETWEEN 0 AND 1)),
  box_x2 REAL CHECK (box_x2 IS NULL OR (box_x2 BETWEEN 0 AND 1)),
  box_y2 REAL CHECK (box_y2 IS NULL OR (box_y2 BETWEEN 0 AND 1)),
  audio_file TEXT
);
CREATE INDEX ix_labels_word ON card_labels (lower(word));
CREATE INDEX ix_labels_content_pos ON card_labels (content_id, position);

CREATE TABLE card_sentences (
  id TEXT PRIMARY KEY,
  content_id TEXT NOT NULL REFERENCES card_contents (id) ON DELETE CASCADE,
  kind TEXT NOT NULL CHECK (kind IN ('description', 'story')),
  position INTEGER NOT NULL,
  en TEXT NOT NULL,
  vi TEXT,
  audio_file TEXT
);
CREATE INDEX ix_sentences_content ON card_sentences (content_id, kind, position);

CREATE TABLE upload_claims (
  user_id TEXT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  content_id TEXT NOT NULL REFERENCES card_contents (id) ON DELETE CASCADE,
  created_at TEXT NOT NULL,
  PRIMARY KEY (user_id, content_id)
);

CREATE TABLE cards (
  id TEXT PRIMARY KEY,
  owner_id TEXT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  content_id TEXT NOT NULL REFERENCES card_contents (id) ON DELETE RESTRICT,
  title TEXT NOT NULL,
  visibility TEXT NOT NULL DEFAULT 'private' CHECK (visibility IN ('private', 'class', 'public')),
  published_at TEXT,
  label_overrides TEXT CHECK (label_overrides IS NULL OR json_valid(label_overrides)),
  created_at TEXT NOT NULL,
  UNIQUE (owner_id, content_id)
);
CREATE INDEX ix_cards_owner ON cards (owner_id, created_at DESC);
CREATE INDEX ix_cards_visibility ON cards (visibility, created_at DESC);

CREATE TABLE card_saves (
  user_id TEXT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  card_id TEXT NOT NULL REFERENCES cards (id) ON DELETE CASCADE,
  saved_at TEXT NOT NULL,
  PRIMARY KEY (user_id, card_id)
);
CREATE INDEX ix_saves_user ON card_saves (user_id, saved_at DESC);

CREATE TABLE card_progress (
  user_id TEXT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  card_id TEXT NOT NULL REFERENCES cards (id) ON DELETE CASCADE,
  level INTEGER NOT NULL CHECK (level BETWEEN 1 AND 3),
  best_score INTEGER NOT NULL DEFAULT 0,
  unlocked INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (user_id, card_id, level)
);

CREATE TABLE reflex_sessions (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  level INTEGER NOT NULL CHECK (level BETWEEN 1 AND 4),
  rounds TEXT CHECK (rounds IS NULL OR json_valid(rounds)),
  started_at TEXT NOT NULL,
  completed_at TEXT,
  score INTEGER
);
CREATE INDEX ix_reflex_user ON reflex_sessions (user_id, started_at);

CREATE TABLE attempts (
  id TEXT PRIMARY KEY,
  client_attempt_id TEXT NOT NULL,
  user_id TEXT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  card_id TEXT NOT NULL REFERENCES cards (id) ON DELETE CASCADE,
  item_type TEXT NOT NULL CHECK (item_type IN ('label', 'sentence', 'story')),
  item_id TEXT NOT NULL,
  mode TEXT NOT NULL,
  reflex_level INTEGER,
  reflex_session_id TEXT REFERENCES reflex_sessions (id) ON DELETE SET NULL,
  transcript TEXT,
  accuracy INTEGER,
  pronunciation INTEGER,
  reflex_ms INTEGER,
  reflex_score INTEGER,
  xp INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  UNIQUE (user_id, client_attempt_id)
);
CREATE INDEX ix_attempts_user_time ON attempts (user_id, created_at DESC);
CREATE INDEX ix_attempts_user_card ON attempts (user_id, card_id, created_at DESC);

CREATE TABLE review_state (
  user_id TEXT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  item_type TEXT NOT NULL,
  item_id TEXT NOT NULL,
  card_id TEXT NOT NULL REFERENCES cards (id) ON DELETE CASCADE,
  ease REAL NOT NULL DEFAULT 2.5,
  interval_days INTEGER NOT NULL DEFAULT 0,
  reps INTEGER NOT NULL DEFAULT 0,
  lapses INTEGER NOT NULL DEFAULT 0,
  due_at TEXT NOT NULL,
  last_reviewed_at TEXT,
  PRIMARY KEY (user_id, item_type, item_id)
);
CREATE INDEX ix_review_due ON review_state (user_id, due_at);
