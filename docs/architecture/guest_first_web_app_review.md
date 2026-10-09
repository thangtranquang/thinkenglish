# Architecture review – ReflexEnglish web app (guest-first, FastAPI + SQLite)

Source: architect review of `docs/PRD.md` §1 and `docs/use-cases/guest_first_web_app_use_cases.md`. This file is the binding resolution of the PRD/UC contradictions and gaps (OQ-1..OQ-63). Where it conflicts with the PRD/UC text, **this file wins** until the PRD is amended; the PRD/UC amendments must then reference it.

## Verdict
FAIL → **PASS after amendments**. The approach is sound; no redesign. Stack, CLAUDE.md layering and PRD decisions D-1..D-8, D-10..D-12 stay. D-9 is changed (school NAT). FR-36, FR-38, FR-44, FR-52 and PRD edge #1/#16 are overridden as noted below.

Required document changes:
1. FR-29 + API table: settings only via `PUT /api/me/settings` (OQ-22).
2. FR-29 + edge #16: account deletion removes the user's cards (shared included) and garbage-collects orphan images (OQ-26/27).
3. FR-36 + FR-41: an upload never creates a `cards` row; `upload_claims` handles access control (OQ-29/38).
4. FR-38: retry budget (OQ-33/34/36).
5. FR-44 + AC-24: no "pending forever"; unsafe images are rejected for sharing (OQ-40).
6. FR-10 + FR-13: exempt list and grace rule (OQ-3/5/9).
7. D-9 IP limits (OQ-15).
8. Edge #1: an expired/revoked session becomes a new guest; guests get a login link (OQ-19).
9. Add scoring, SRS, streak and XP rules (OQ-23, OQ-45..56).
10. FR-52: guest "Bài của tôi" tab (OQ-53).
11. PRD §1.9 schema replaced by the schema below.
12. FR-40: audio served from `frontend/audio` (OQ-61).

## Decisions
| ID | Decision |
|---|---|
| OQ-1 | Rename PRD 1.15 link to `guest_first_web_app_use_cases.md`. |
| OQ-2 | Default `GUEST_FREE_SESSIONS=1` for the pilot. |
| OQ-3/9 | `/api/session/heartbeat` and `GET /api/me` join the exempt list (heartbeat returns `{gate}`). Grace: a gated guest may still call `POST /api/attempts` and `POST /api/reflex/sessions/{id}/complete`, only for items/sessions that existed before `gate_required_at`, only within `GATE_GRACE_SECONDS=600` (checked against `reflex_sessions.started_at` or the attempted card's existing progress). Every other call gets 403. |
| OQ-4 | A new usage session starts only if `now - last_activity_at > idle`. Exactly 30:00 is still the same session. |
| OQ-5 | Dependency chain order: identity → `second_visit` gate → registered check (camera/account). `second_visit` wins. |
| OQ-6 | Gate is re-evaluated at each new usage-session start; if the user no longer meets the threshold `gate_required_at` is cleared. |
| OQ-7 | `logout` is idempotent 204 for anyone and clears `re_session` only. `logout-all` for a guest → 403 `registration_required`/`account`. |
| OQ-8 | Gate reasons: `camera` (uploads, `POST /api/cards`, share), `account` (PATCH/DELETE `/api/me`, logout-all), `profile` (banner, skippable), `second_visit`. |
| OQ-10 | Age uses the calendar year in `Asia/Ho_Chi_Minh`. Legal sufficiency stays with the PO (PRD OQ-3). |
| OQ-11 | Nickname: ASCII `[A-Za-z0-9_.-]` only, applied after NFKC; Vietnamese error message. |
| OQ-12 | Accepted: no confirm-password field, no reset. |
| OQ-13 | CSRF token is stable per browser, **not** rotated on login/register. Client rule: on `csrf_failed`, re-bootstrap once and retry once. |
| OQ-14 | Register with a valid `re_session` → 409 `already_registered`. Otherwise `nickname_taken` is accepted and the UI offers "Đăng nhập". |
| OQ-15/18 | One generic `rate_events(bucket, key_hash, created_at)` table, sliding window. Login counts failures only. Registration counts every request that passed CSRF (422/409 included). 429 responses are not counted. **Override D-9 for school NAT:** login 100 failures/IP/15 min, registration 30/IP/hour. Per-nickname login limit stays 5/15 min. |
| OQ-16 | `TRUSTED_PROXY_HOPS` (default 0 = socket peer). If >0, take the Nth entry from the right of X-Forwarded-For. Never trust the leftmost entry. |
| OQ-17 | Every user-owned table has an FK to `users` ON DELETE CASCADE; `card_progress` and `card_saves` also FK to `cards` ON DELETE CASCADE. |
| OQ-19 | **Override edge #1:** a revoked/expired session becomes a new guest and reveals nothing about the account. Home header and Profile show "Đã có tài khoản? Đăng nhập" for guests. |
| OQ-20 | Accept a possible orphan guest. Client sends bootstrap as one shared promise per tab. Guests with no writes are purged after `GUEST_EMPTY_RETENTION_DAYS=7`. |
| OQ-21 | The Profile banner opens Register with `reason=profile`; it has Back (like camera) and returns to Profile after success. |
| OQ-22 | `PATCH /api/me` = avatar and CEFR (registered). `PUT /api/me/settings` = `hide_timer` (any identity). |
| OQ-23 (FR-54) | XP per attempt (`attempts.xp`): 10 if score ≥70 else 2; listen-only earns none. Streak = consecutive `Asia/Ho_Chi_Minh` days with ≥1 attempt ending today or yesterday. Level = floor(XP/500)+1; progress = (XP mod 500)/500. Computed on read. |
| OQ-24 | PATCH CEFR accepts only A1, A2, B1 (B2 kept for content only). |
| OQ-25 | Wrong password on DELETE `/api/me` counts in the nickname login-failure bucket; same 429. |
| OQ-26 | **Override edge #16:** deletion removes all of the user's cards, shared ones included. |
| OQ-27 | After the deletion commit, GC every `card_contents` with no remaining `cards` and not owned by the seed: delete contents row, asset row and file. Same GC runs in maintenance. GC must verify NO `cards` row references the content. |
| OQ-28 | Origin and Referer both missing on a state-changing request → 403, except bootstrap (idempotent, harmless). If Origin is present it must match `APP_ORIGIN`. When Secure, CSRF cookie name is `__Host-re_csrf`. |
| OQ-29 | **Override FR-36:** an upload never creates `cards`; it inserts `upload_claims(user_id, content_id)`. `POST /api/cards {content_id, title, label_overrides}` creates the card (idempotent via UNIQUE(owner, content)). No draft rows; cancel = nothing saved. If the user already owns the content the upload response includes `card_id`. |
| OQ-30 | Pixel limit exceeded / decompression bomb → 413 `image_too_large`. Animated WebP/APNG → 415 `unsupported_image`. Corrupt → 422. |
| OQ-31 | Upload response has `dedupe: none|ready|in_flight`. For `in_flight` the message is "Ảnh này đang được xử lý, vui lòng chờ…" and this request made 0 provider calls. |
| OQ-32 | Dedupe key = sha256 of the **raw uploaded bytes** (`source_sha256` UNIQUE). Cleaned file and its sha stored separately. `phash` stays a nullable unused column. |
| OQ-33 | A timeout or exception counts as a call. `ai_calls` is incremented in a committed write **before** each call. |
| OQ-34/36 | Per run: 1 automatic retry (≤2 calls). Manual retries: 2 per image in total (`manual_retries`), triggered by re-uploading a failed image. Hard cap 6 calls per image; exhausted → 409 `analysis_unavailable`. "≤1.05 calls/image" is an aggregate pilot metric, not a per-image cap. |
| OQ-35 | `card_contents.lease_expires_at = now + (2×timeout + 30s)`. Any poll/upload seeing an expired `processing` row sets it to `failed` (lazy sweep); startup sweep does the same. Client stops polling after 120 s. |
| OQ-37 | Review: 1–8 labels; word 1–40 chars; no duplicate words (case-insensitive); title ≤60 chars. Overrides may only edit, move or delete existing labels; adding labels is not allowed. |
| OQ-38 | `GET /api/uploads/{id}`, `POST /api/cards` and the retry path require an `upload_claims` row for (user, content); otherwise 404. |
| OQ-39 | Approved share → `public`. `class` stays in the CHECK but is never set. |
| OQ-40 | **Override FR-44/AC-24:** no reviewer, so no pending state. Any unsafe flag → `moderation_status='rejected'` and share returns 422 `share_not_allowed` with a Vietnamese reason (faces / personal info / unsuitable). Clean → approved and public. |
| OQ-41 | Another user's private card → 404 on every card subroute. |
| OQ-42 | Add `DELETE /api/cards/{id}/share` (back to private) and `DELETE /api/cards/{id}` (owner). |
| OQ-43 | Keyset pagination on `(created_at DESC, id DESC)`, `limit` default 20 max 50, opaque `cursor`. |
| OQ-44 | Attempt on a locked level → 409 `level_locked`. |
| OQ-45 | Level score = mean over the level's items of the **latest** score per item; unattempted items count 0. Level 1 = labels, 2 = description sentences, 3 = story sentences. `best_score` = max of this value ever. Unlock at ≥70. |
| OQ-46 | `client_attempt_id` (UUID), UNIQUE(user_id, client_attempt_id). A replay returns the original result with 200. No offline queue. |
| OQ-47 | Score s → SM-2 quality q: ≥90→5, ≥80→4, ≥70→3, ≥50→2, ≥20→1, else 0. q<3: reps=0, interval=1, lapses+1. Otherwise interval = 1, then 6, then round(interval×ease), reps+1. ease += 0.1−(5−q)(0.08+0.02(5−q)), floor 1.3. due_at = now + interval days. |
| OQ-48 | **Server computes accuracy**; the client field is removed. Matching: NFKC-lowercase, punctuation stripped. Label: 100 if any accepted answer appears as a whole word, else round(100×difflib ratio) capped at 60. Sentence: word-level recall via difflib matching blocks. `pronunciation` clamped 0–100, stored only (never used for unlock/SRS). `reflex_ms` must be 0..limit+2000; above the limit = timeout. |
| OQ-49 | Skip = timeout: transcript null, accuracy 0, q=0, counted. |
| OQ-50 | R4 is scored against the highlighted label's word and accepted answers (whole-word containment in the transcript). |
| OQ-51 | Speed counts only when accuracy ≥70: score = 0.6·acc + 0.4·speed·[acc≥70]. |
| OQ-52 | `reflex_progress` rows created lazily; R1 unlocked by default; Practice and Reflex unlocks independent. A session counts toward unlock only with ≥5 answered rounds; session score = mean `reflex_score`. |
| OQ-53 | Guest "Bài của tôi" = empty state + camera CTA. Saved cards appear only in "Đã lưu". |
| OQ-54/55/56 | Combined score per attempt = `reflex_score` (reflex) or accuracy (shadow). Mastery = mean of last ≤5 attempts on the card; 0 attempts = "Chưa học". The "Cần ôn lại" badge counts **cards**. |
| OQ-57 | Maintenance (guest purge, empty-guest purge, stale processing, orphan GC, `rate_events` older than 1 day) runs at startup then every 24 h as an asyncio task; idempotent; also `python -m backend.app.maintenance`. |
| OQ-58 | Migration runner: `BEGIN EXCLUSIVE`, re-read `schema_migrations` inside the lock, split each file with `sqlite3.complete_statement`, execute statements one by one, insert version, commit. Never `executescript` (auto-commits). Seed runs afterwards in its own `BEGIN IMMEDIATE`. |
| OQ-59 | Production seed = the prototype cards; images shipped under `backend/seed_assets/`, copied into `DATA_DIR` on seed. The 100-card performance dataset is a test-only fixture generator. |
| OQ-60 | Seed keyed by stable `seed_key`; IDs are uuid5(seed_key) so label/sentence IDs survive. Upserted; seed content never deleted while referenced; `seed_version` in `app_meta`. |
| OQ-61 | Audio copied from `docs/audio` to `frontend/audio` by a tool step, served at `/audio/<file>`. Card payload carries `audio_url`. **Remove `GET /api/audio/{id}`**. |
| OQ-62 | Moot: `prior_sessions` = count of `usage_sessions` with `had_write=1` other than the current one, recomputed every time. |
| OQ-63 | Stays with the PO (legal); release-blocking for under-16 sign-ups in production, not for the build. |
| FR-11 | Gate is cleared "on conversion or on login (guest discarded)". |
| FR-7 vs FR-13 | Any identity call may start a usage session (the `touch` dependency) and set the gate. Bootstrap is the client's display source; other calls just 403. |
| FR-12c | Usage-session touch is a conditional UPDATE at most once per 60 s per user. |
| Persona vs D-7 | Keep minimum age 10; persona text is descriptive only. |
| Session rotate-on-use | Old row gets `grace_until = now+60s`; valid until then, no further rotation from it. |
| System user | `kind='system'` never logs in; no password hash. |

## Schema (`001_init.sql`; TEXT UUID PKs, ISO-UTC TEXT timestamps, JSON in TEXT with `CHECK json_valid`)
Pragmas on every connection: `journal_mode=WAL`, `foreign_keys=ON`, `busy_timeout=5000`, `synchronous=NORMAL`. Every write uses `BEGIN IMMEDIATE`.

| Table | Columns, constraints, indexes |
|---|---|
| `schema_migrations` | version PK, applied_at |
| `app_meta` | key PK, value (holds `seed_version`) |
| `users` | id, kind CHECK(guest/registered/system), nickname, nickname_ci, password_hash, password_params, avatar_key, birth_year, cefr_level, guardian_email, guardian_consent_at, role, gate_required_at, created_at, registered_at, last_seen_at. Partial UNIQUE(nickname_ci) WHERE kind='registered'; idx(kind, last_seen_at) |
| `device_tokens` | token_hash PK, user_id FK CASCADE, created_at, last_seen_at; idx user_id |
| `sessions` | token_hash PK, user_id FK CASCADE, created_at, last_seen_at, expires_at, absolute_expires_at, revoked_at, grace_until, rotated_from; idx user_id, expires_at |
| `usage_sessions` | id, user_id FK CASCADE, started_at, last_activity_at, had_write; idx(user_id, last_activity_at DESC) |
| `rate_events` | id INTEGER PK, bucket CHECK(login_nick/login_ip/register_ip), key_hash, created_at; idx(bucket, key_hash, created_at) |
| `image_assets` | id, source_sha256 UNIQUE NOT NULL, clean_sha256, phash NULL, storage_path NOT NULL, width, height, first_uploaded_by FK users SET NULL, created_at |
| `card_contents` | id, image_asset_id UNIQUE FK CASCADE, seed_key UNIQUE NULL, status CHECK(processing/ready/failed), model, prompt_version, ai_calls, manual_retries, lease_expires_at, topic, topic_tags JSON, cefr_level, safety JSON, moderation_status CHECK(pending/approved/rejected), raw_response JSON, error, created_at; idx topic, idx(status, lease_expires_at) |
| `card_labels` | id, content_id FK CASCADE, position, word, ipa, vi_meaning, accepted_answers JSON, cefr_level, confidence, x, y, box_x1..box_y2 (CHECK 0..1), audio_id FK audio_assets SET NULL; idx lower(word), (content_id, position) |
| `card_sentences` | id, content_id FK CASCADE, kind CHECK(description/story), position, en, vi, audio_id FK SET NULL; idx(content_id, kind, position) |
| `audio_assets` | id, text, voice, storage_path NULL, duration_ms, UNIQUE(text, voice) |
| `upload_claims` | user_id FK CASCADE, content_id FK card_contents CASCADE, created_at, PK(user_id, content_id) |
| `cards` | id, owner_id FK users CASCADE, content_id FK RESTRICT, title, visibility CHECK(private/class/public), published_at, label_overrides JSON, created_at, UNIQUE(owner_id, content_id); idx(owner_id, created_at DESC), idx(visibility, created_at DESC) |
| `card_saves` | user_id FK CASCADE, card_id FK CASCADE, saved_at, PK(user_id, card_id); idx(user_id, saved_at DESC) |
| `card_progress` | user_id FK CASCADE, card_id FK cards CASCADE, level CHECK 1..3, best_score, unlocked, updated_at, PK(user_id, card_id, level) |
| `reflex_sessions` | id, user_id FK CASCADE, level CHECK 1..4, rounds JSON, started_at, completed_at, score; idx(user_id, started_at) |
| `attempts` | id, client_attempt_id, user_id FK CASCADE, card_id FK CASCADE, item_type CHECK(label/sentence/story), item_id, mode, reflex_level, reflex_session_id FK SET NULL, transcript, accuracy, pronunciation, reflex_ms, reflex_score, xp, created_at; UNIQUE(user_id, client_attempt_id); idx(user_id, created_at DESC), idx(user_id, card_id, created_at DESC) |
| `review_state` | user_id FK CASCADE, item_type, item_id, card_id FK CASCADE, ease, interval_days, reps, lapses, due_at, last_reviewed_at, PK(user_id, item_type, item_id); idx(user_id, due_at) |
| `reflex_progress` | user_id FK CASCADE, level, streak_over_80, unlocked, PK(user_id, level) |
| `user_settings` | user_id PK FK CASCADE, hide_timer, updated_at |

## API (gate = blocked when a `second_visit` gate is set; csrf = Origin check + double-submit)
| Method | Path | Auth / gate | Request → Response |
|---|---|---|---|
| GET | /api/health | public | → Health |
| GET | /api/config | public | → ConfigOut |
| POST | /api/session/bootstrap | public, Origin check if present | → BootstrapOut{user, is_guest, gate, csrf_token, config} |
| POST | /api/session/heartbeat | identity, csrf, exempt | → HeartbeatOut{gate} |
| POST | /api/auth/register | public, csrf, exempt, rate-limited | RegisterIn → 201 MeOut |
| POST | /api/auth/login | public, csrf, exempt, rate-limited | LoginIn{nickname, password, discard_guest} → MeOut |
| POST | /api/auth/logout | any, csrf, exempt | → 204 |
| POST | /api/auth/logout-all | registered, csrf | → 204 |
| GET | /api/me | identity, exempt | → MeOut (streak/xp/level, settings) |
| PATCH | /api/me | registered, csrf, gate | MePatchIn{avatar_key?, cefr_level?} → MeOut |
| PUT | /api/me/settings | identity, csrf, gate | SettingsIn → SettingsOut |
| DELETE | /api/me | registered, csrf | DeleteMeIn{password} → 204 |
| GET | /api/cards | identity, gate | ?scope&topic&cefr&q&cursor&limit → CardPage |
| GET | /api/cards/{id} | identity, gate, visibility→404 | → CardDetail |
| GET | /api/cards/{id}/image | identity, gate, visibility→404 | → bytes |
| POST/DELETE | /api/cards/{id}/save | identity, csrf, gate, visible | → SaveOut |
| POST/DELETE | /api/cards/{id}/share | registered owner, csrf, gate | → ShareOut / 422 share_not_allowed |
| DELETE | /api/cards/{id} | registered owner, csrf, gate | → 204 |
| GET | /api/topics | identity, gate | → TopicList |
| POST | /api/uploads | registered, csrf, gate | multipart → 202 UploadOut{content_id, status, dedupe, ai_calls, card_id?} |
| GET | /api/uploads/{content_id} | registered, upload claim required else 404 | → UploadStatusOut |
| POST | /api/cards | registered, csrf, gate, upload claim | CardCreateIn{content_id, title, label_overrides} → 201 CardDetail |
| POST | /api/attempts | identity, csrf, gate with grace | AttemptIn{client_attempt_id, card_id, item_type, item_id, mode, reflex_level?, reflex_session_id?, transcript?, pronunciation?, reflex_ms?, skipped} → AttemptOut{accuracy, score, q, unlocks, xp} |
| POST | /api/reflex/sessions | identity, csrf, gate | ReflexStartIn{level} → ReflexSessionOut |
| POST | /api/reflex/sessions/{id}/complete | owner, csrf, gate with grace, idempotent | → ReflexSummaryOut |

Unknown fields rejected everywhere (`extra='forbid'`). Error body `{error, reason?, fields?}`.

## Module breakdown (`backend/app/`)
- Top level: `main.py` (app factory; lifespan = migrate → seed → sweep → maintenance task), `config.py`, `db.py` (connection factory, `transaction(immediate=True)`, migration runner), `security.py` (scrypt, token generation/hashing, IP hashing, CSRF compare), `deps.py` (chain: `identity`, `touch_usage`, `csrf`, `not_gated(grace=False)`, `registered(reason)`, `client_ip`), `errors.py` (envelope), `middleware.py` (security headers, no-store), `seed.py`, `maintenance.py`.
- `routers/`: `health_config.py`, `session.py`, `auth.py`, `me.py`, `cards.py`, `uploads.py`, `practice.py` (attempts), `reflex.py`, `topics.py`.
- `schemas/`: pydantic in/out models per router.
- `services/`: identity/auth: `guest.py`, `usage.py` (session + gate logic), `auth.py` (register, login, discard, sessions, rotation), `ratelimit.py`, `account.py` (delete + GC). Content/practice: `cards.py` (visibility policy), `upload.py` (only importer of `ai/`; claim, lease, background job), `imaging.py` (Pillow sniff + re-encode), `storage.py` (DATA_DIR paths, no traversal), `scoring.py` (pure), `srs.py` (pure SM-2), `practice.py`, `reflex.py`, `stats.py` (XP, streak, mastery).
- `repositories/`: one per aggregate (`users`, `tokens`, `sessions`, `usage`, `rate_events`, `images`, `contents`, `cards`, `saves`, `attempts`, `review`, `progress`, `reflex`, `audio`, `meta`).
- `ai/`: `provider.py`, `mock.py`, `gemini.py`, `schema.py` (AnalysisResult with box conversion).
Dependency direction holds; `scoring.py` and `srs.py` are pure (no imports from the app). Upload processing runs as a FastAPI BackgroundTask in the worker that won the insert. The AI concurrency semaphore is per process → pilot runs `--workers 1`.

## Slices needing security pre-review
Cookies/device token/bootstrap; register + conversion (age, guardian, nickname normalisation); login + discard, sessions + rotation, logout; CSRF + Origin middleware; rate limiting + client IP; gate dependency, grace and exempt list; upload (sniffing, size/pixel limits, bomb, animation, EXIF strip, storage paths); upload claims + card visibility (IDOR, 404 policy); account deletion + orphan GC; guest purge; security headers + CSP.

## Slices needing architect pre-review
`001_init.sql`, migration runner (exclusive lock, statement split) and idempotent seed with uuid5 keys; AI-once pipeline (BEGIN IMMEDIATE insert on `source_sha256`, pre-call `ai_calls` increment, lease + lazy sweep, retry budget, BackgroundTask ownership, AC-19 concurrency test with two threads and a MockProvider counter); scoring, SRS, unlocks and reflex session completion; usage-session + gate state machine; stats (XP, streak, mastery) query cost vs NFR-F1.

## Risks
- Multiple uvicorn workers multiply the AI semaphore and BackgroundTasks; a worker crash loses a job (lease sweep recovers). Pilot: 1 worker.
- Touching the usage session on every request causes SQLite write contention; the 60 s throttle is required.
- School NAT can still lock out a class during group login; monitor 429s.
- Raw-bytes dedupe misses re-compressed duplicates, so cost may exceed 1.05 calls per *visual* image (accepted).
- Computed accuracy depends on browser STT quality; the fuzzy cap of 60 may block unlocks for accented speech; tune after the pilot.
- Guardian consent legally unverified (OQ-63); plaintext guardian email (D-11) is a breach liability.
- Account deletion + GC remove the dedupe cache for other users' unshared copies; GC must check no `cards` row references the content before deleting files.
- Seed ID stability: changing a `seed_key` orphans users' SRS history.

## Addendum – decisions on the BA's remaining gaps (tech-lead/orchestrator, binding like the rest of this file)
| # | Gap | Decision |
|---|---|---|
| 1 | Does a successful login clear earlier failures? | No. Buckets are pure sliding windows; success does not reset them. |
| 2 | Re-entering Review for an abandoned, ready upload | Re-uploading the same file returns `dedupe: ready` + the existing claim (0 AI calls) and the client opens Review. No draft rows. |
| 3 | `upload_claims` and orphan GC | A content is an orphan only if it has no `cards` rows AND no `upload_claims` newer than 7 days. Maintenance deletes claims older than 7 days that have no card. Claims cascade on user deletion. |
| 4 | Resume Add-photo after register/login from the camera gate | Yes: after successful register from reason=camera the client navigates to the Add-photo screen. |
| 5 | Replayed `client_attempt_id` with a different payload | Return the original stored result with 200; the new payload is ignored. |
| 6 | `analysis_unavailable` check order | Check the 6-call cap before inserting the claim; a provider call is allowed iff `ai_calls < 6` at the moment of the committed pre-call increment. |
| 7 | Cursor/filter mismatch | 422 `invalid_cursor`. |
| 8 | Effect of unsharing on others | Unshare deletes other users' `card_saves` for that card; their progress rows remain but the card is no longer visible to them. |
| 9 | Remaining `[ASSUMED]` minor items | Accepted as written in the use-case file unless QA finds a conflict. |
