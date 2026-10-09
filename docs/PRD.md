# ReflexEnglish - Product Requirements Document

| Field | Value |
|---|---|
| Product | ReflexEnglish - Visual-First English Reflex Platform for school students |
| PRD version | 1.1 (first section: web app + guest-first onboarding; amended per `docs/architecture/guest_first_web_app_review.md`) |
| Date | 2026-10-09 |
| Source of truth for the domain | `docs/spec_v1.1.md` (extract of `Product_Specification_ReflexEnglish_v1.1.docx`) |
| Prototype to port | `docs/reflex_app.html` (vanilla JS SPA with mock data) |
| Platform | Mobile-first web app (PWA ready) |
| Persona | Vietnamese school students, assumed age 11-18, CEFR A1-B1 |
| Core goal | Shorten silent-translation latency: see an object, say the English word in seconds, without going through Vietnamese |
| Economic principle | Call the AI exactly once per unique image; store the result; every later reader (any user) reads from the DB |
| UI language | Vietnamese. Learning content: English |

Section index

| # | Section | Status |
|---|---|---|
| 1 | ReflexEnglish Web App (FastAPI + SQLite) with Guest-First Onboarding | Amended after architect review (PASS after amendments); binding resolutions in section 1.16 |

---

## 1. ReflexEnglish Web App (FastAPI + SQLite) with Guest-First Onboarding

### 1.1 Feature description and goal

Turn the clickable prototype (`docs/reflex_app.html`) into a real web application: a FastAPI backend with a SQLite database serving a vanilla-JS static frontend. The data model follows spec v1.1 section 5 (`image_assets` with sha256 dedupe, `card_contents` = shared AI result, `card_labels`, `audio_assets`, `cards`, `attempts`, `review_state` with SM-2), adapted to SQLite. The AI vision call (Gemini behind an `AIProvider` interface, deterministic mock when `GEMINI_API_KEY` is unset) happens once per unique image; the stored result is read from the DB by every later user.

Onboarding is guest-first. A brand-new visitor lands directly on Home with no welcome screen and no sign-up wall. The server silently creates an anonymous guest user and sets a long-lived HttpOnly device cookie so guest progress persists across visits. Registration is requested only at two moments:

- **Camera gate (soft):** the guest taps the camera / "Add photo" action. The registration screen appears with a Back option.
- **Second-visit gate (hard):** the guest opens the app after having completed at least N previous sessions (N configurable, default 1). The registration screen appears and cannot be skipped.

Registering converts the guest row into a registered user (same user id), so all progress is kept. Registered users who log in receive a long-lived server-side session and are logged in automatically on later visits. A login screen (nickname + password) exists for new devices.

**Goal:** minimise friction for first experience (explore, practice, Reflex, auto mode, library with seeded cards) while capturing a registered, consented (for minors) account exactly when the student shows commitment, without losing any progress and without violating Vietnam Decree 13/2023 for users under 16.

### 1.2 User stories

- US-1 (Guest): As a first-time visitor, I want to start practising immediately without registering so that I can judge the app in under a minute.
- US-2 (Returning guest, within a visit): As a guest, I want my progress, unlocked levels, and review queue to persist when I reload or come back later the same day so that I do not lose work before registering.
- US-3 (Returning guest, second visit): As a guest who comes back, I understand that I must now create an account so that my progress is saved permanently and tied to me.
- US-4 (Registering user): As a guest, I want to register with only a nickname, password, avatar, birth year, and CEFR level so that I can add my own photos while keeping everything I already did.
- US-5 (Returning registered user): As a registered student, I want the app to open already logged in on the device I used before so that I can practise in two taps.
- US-6 (User on a new device): As a registered student, I want to log in with my nickname and password on a new phone or browser so that I can continue my progress there.
- US-7 (Student under 16 / guardian): As a student under 16, I want to register with my parent's or guardian's email and a consent confirmation so that my account complies with the law, and as a guardian I want assurance that only minimal personal data is collected.
- US-8 (Privacy-conscious user): As a registered student, I want to log out, log out of all devices, and delete my account so that I stay in control of my data.
- US-9 (Registered uploader): As a registered student, I want to photograph an everyday scene, review and correct the AI result, and save it as my own private card so that I can practise English on things from my life.

### 1.3 Scope summary

In scope: guest bootstrap, device cookie, usage-session counting, camera gate, second-visit gate, registration with guest conversion, minors' consent capture, login/logout/auto-login, login rate limiting, CSRF, SQLite schema, AI-once upload pipeline with mock/Gemini providers, seeded system cards and audio, Home / Explore / Add photo / Review / Practice (3 levels) / Reflex (R1-R4, hide timer, auto mode) / Library / Profile / Login / Register screens, backend and e2e tests.

Out of scope: see section 1.11.

### 1.4 Definitions

- **Guest:** a `users` row with `kind = 'guest'`, no nickname/password, identified only by a device token.
- **Registered user:** a `users` row with `kind = 'registered'`.
- **Device cookie (`re_device`):** HttpOnly, SameSite=Lax cookie carrying a random 256-bit token; only its sha256 is stored server-side. Identifies a guest.
- **Session cookie (`re_session`):** HttpOnly, SameSite=Lax cookie carrying a random 256-bit token of a registered user's login session; only its sha256 is stored server-side.
- **Usage session ("visit"):** a period of app use. A new usage session starts when the server receives any identity call (bootstrap or any other call carrying the identity, the `touch` dependency) for a user and either (a) the user has no usage session yet, or (b) `now - last_activity_at > SESSION_IDLE_MINUTES` (default 30; strictly greater, so exactly 30:00 is still the same session). Page reloads, tab switches, and navigation within the idle window continue the same usage session and never count as a new one.
- **Completed previous sessions (`prior_sessions`):** count of `usage_sessions` rows of this user with `had_write=1` other than the current one, recomputed every time (never stored as a counter). See FR-12.
- **Gate:** the registration screen shown to a guest. `reason` is one of `camera` (uploads, `POST /api/cards`, share; skippable), `account` (PATCH/DELETE `/api/me`, logout-all), `profile` (Profile banner; skippable) or `second_visit` (mandatory). Dependency chain order on a request: identity -> `second_visit` gate -> registered check (camera/account); `second_visit` wins when both apply.

### 1.5 Functional requirements

#### A. Guest identity and device cookie

- **FR-1** On `POST /api/session/bootstrap` with no valid `re_session` and no valid `re_device` cookie, the server creates a guest user (`kind='guest'`), stores the sha256 of a new random 256-bit device token, and sets `re_device` (HttpOnly, SameSite=Lax, `Secure` when not on localhost, Path=/, Max-Age = 400 days, the maximum browsers honour).
- **FR-2** On every later bootstrap with a valid `re_device`, the server returns the same guest user (same id, same progress) and refreshes `last_seen_at` and the cookie Max-Age.
- **FR-3** A guest has the same read/practice capabilities as a registered user for system (seeded) content: Home, Explore, Practice levels 1-3 with unlock rules, Reflex R1-R4, auto mode, Library (saved seeded cards, "needs review"), search, topics, and profile view. Guests write `attempts`, `review_state`, `card_saves`, and progress rows under their guest user id.
- **FR-4** A guest cannot upload photos, create cards from uploads (`POST /api/cards`), or share. Such requests return `403` with body `{"error":"registration_required","reason":"camera"}`. A guest calling `PATCH /api/me`, `DELETE /api/me` or `POST /api/auth/logout-all` gets `403 {"error":"registration_required","reason":"account"}`. The server enforces this regardless of the UI. `PUT /api/me/settings` (`hide_timer`) is allowed for guests.
- **FR-5** The server never exposes the raw device token or any token hash in any response or log.
- **FR-6** Guest rows with no activity for `GUEST_RETENTION_DAYS` (default 180) are eligible for purge by an idempotent maintenance routine, together with their attempts, review_state, saves, and device tokens. Guests that never performed a write (no attempt, save or completed round) are purged after `GUEST_EMPTY_RETENTION_DAYS` (default 7); this accepts that a cookie-less revisit may leave an orphan guest (see FR-62). Registered users are never purged by this routine.

#### B. Usage sessions and gate decisions

- **FR-7** `POST /api/session/bootstrap` returns `{user, is_guest, gate, csrf_token, config}` where `gate` is `null`, `{"reason":"second_visit","mandatory":true}`, or (computed client-side on demand) the camera gate described in FR-9. The bootstrap response is the client's display source for the second-visit gate; `POST /api/session/heartbeat` returns `{gate}` as well. Any identity call may start a usage session (the `touch` dependency) and set the gate server-side; calls other than bootstrap/heartbeat/`GET /api/me` simply receive 403 in that case.
- **FR-8** The server evaluates the second-visit gate at the moment a new usage session starts (see Definitions). The gate is mandatory when `kind='guest'` AND `prior_sessions >= GUEST_FREE_SESSIONS` (default 1, env-configurable, integer >= 0; value 0 means the gate applies from the very first visit, in which case the first screen is the register screen).
- **FR-9** Camera gate: when a guest taps the camera / "Chụp ảnh" / "Thêm ảnh" action (Home, bottom nav, Library), the client navigates to the Register screen with `reason=camera`. This screen shows a Back button returning to the previous screen. Registering from this gate resumes the add-photo flow on success.
- **FR-10** Second-visit gate enforcement is server-side: while a guest has `gate.reason='second_visit'` unresolved, every `/api/*` endpoint except the exempt list returns `403 {"error":"registration_required","reason":"second_visit"}`. Exempt list: `GET /api/health`, `GET /api/config`, `POST /api/session/bootstrap`, `POST /api/session/heartbeat`, `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/logout`, and `GET /api/me`. The client has no Back or dismiss control on this screen; the only exits are Register or Log in. Grace exception: see FR-13.
- **FR-11** The gate state is persisted per user as `users.gate_required_at` (timestamp set when a new usage session triggers the mandatory gate, cleared on conversion or on login (guest discarded)). The gate is re-evaluated at each new usage-session start; if the user no longer meets the threshold, `gate_required_at` is cleared. A reload, a cleared client state, or a second tab does not bypass the gate.
- **FR-12** Counting rules for "session": (a) only usage sessions with `had_write=1` (an attempt, a card save, or a completed Reflex round) count toward `prior_sessions`; a visit where the guest only looked at screens and left does not consume the free session; (b) two identity calls within `SESSION_IDLE_MINUTES` (strictly: `now - last_activity_at <= idle`) belong to the same session; (c) a heartbeat (`POST /api/session/heartbeat`, sent by the client at most once per minute while the app is in the foreground, and implicitly by any authenticated API call) extends the session; the usage-session touch is a conditional UPDATE performed at most once per 60 s per user; (d) the count is derived server-side from `usage_sessions` and cannot be reset by clearing client storage other than by clearing the device cookie (see edge cases).
- **FR-13** Mid-session interruption and grace rule: the second-visit gate is only evaluated when a new usage session starts. If a tab stays open past the idle timeout and the user resumes mid-practice, the server starts a new usage session on the next call; if that triggers the gate, the client defers showing the gate until the current practice round / Reflex round finishes and its result is saved, and then shows the gate before the next navigation. No in-flight round is discarded. Server-side grace: a gated guest may still call `POST /api/attempts` and `POST /api/reflex/sessions/{id}/complete`, only for items/sessions that existed before `gate_required_at` and only within `GATE_GRACE_SECONDS` (default 600) of it, checked against `reflex_sessions.started_at` or the attempted card's existing progress. Every other call from a gated guest returns 403.

#### C. Registration and guest conversion

- **FR-14** `POST /api/auth/register` accepts: `nickname`, `password`, `avatar_key`, `birth_year`, `cefr_level` (A1|A2|B1), and when the computed age is under 16 also `guardian_email` and `guardian_consent` (must be `true`). Unknown fields are rejected (`422`).
- **FR-15** Validation: nickname 3-20 characters after trim, NFKC-normalised, then restricted to ASCII `[A-Za-z0-9_.-]` only (Vietnamese error message on violation), unique case-insensitively among registered users, not in a reserved/profanity denylist, and must not look like an email or phone number (no real names, no contact data); password 8-128 characters, not equal to the nickname, not in a small list of the most common passwords; `avatar_key` must be one of the preset avatars returned by `/api/config`; `birth_year` between (current year - 100) and (current year - 10) (age under 10 is rejected with a Vietnamese message explaining the app is for ages 10+; see open question OQ-3); there is no confirm-password field and no password reset (accepted); `guardian_email` must be a syntactically valid email, 254 characters max.
- **FR-16** Age rule: age = current calendar year in `Asia/Ho_Chi_Minh` - birth_year (legal sufficiency of this rule stays with the PO, see OQ-3). If age < 16, registration requires a valid `guardian_email` and `guardian_consent = true`; otherwise the server returns `422` with field errors and creates nothing. On success the server stores `guardian_email` and `guardian_consent_at = now`. For age >= 16 the guardian fields must be absent or are rejected; no guardian email is stored.
- **FR-17** Conversion: when the request carries a valid `re_device` guest, registration updates that same `users` row in place (`kind='registered'`, nickname, password hash, avatar, birth year, CEFR level, `registered_at`, clears `gate_required_at`). The user id does not change; all `attempts`, `review_state`, `card_saves`, progress rows, and usage sessions stay attached. The whole conversion runs in one transaction and is idempotent: a concurrent or repeated register call for the same guest after success, or any register call carrying a valid `re_session`, returns `409 {"error":"already_registered"}` without side effects. When the register screen was opened from the Profile banner (`reason=profile`) it has a Back button (like camera) and returns to Profile after success.
- **FR-18** If a register request has no valid guest cookie (cookie cleared, direct API call), the server creates a new registered user directly (no guest to convert).
- **FR-19** On successful registration the server creates a login session (FR-22), sets `re_session`, deletes the guest device token row, and expires the `re_device` cookie, so the device is now a registered device.
- **FR-20** Nickname-taken errors return `409 {"error":"nickname_taken"}` and keep the guest untouched; the form retains typed values (except password) and highlights the nickname field. A uniqueness race between two registrations is resolved by a database unique index; the loser gets the same 409. When `nickname_taken` is returned the UI also offers "Đăng nhập".
- **FR-21** Passwords are hashed with `hashlib.scrypt` (per-user random 16-byte salt, parameters stored with the hash, N=2^14, r=8, p=1 minimum). Comparison uses `hmac.compare_digest`. The hash is never returned or logged.

#### D. Sessions, auto-login, logout

- **FR-22** A login session is a row in `sessions` containing the sha256 of a random 256-bit token, user id, `created_at`, `last_seen_at`, `expires_at` (sliding, default 90 days idle), `absolute_expires_at` (default 365 days), `revoked_at`, and `grace_until` and `rotated_from`. The cookie `re_session` is HttpOnly, SameSite=Lax, `Secure` off localhost, Max-Age = 90 days, refreshed on use at most once per day.
- **FR-23** Auto-login: on bootstrap, a valid, non-revoked, non-expired `re_session` returns the registered user and skips every login/register/gate screen. The client goes straight to Home.
- **FR-24** Rotation: every successful login and every registration issues a brand-new session token; any session token previously presented by that browser (the cookie it sent) is revoked in the same transaction. Tokens are also re-issued if older than 30 days at the time of use (rotate-on-use), with the old row getting `grace_until = now + 60 s`: it stays valid until then (to tolerate parallel tabs) but is never rotated again from it.
- **FR-25** `POST /api/auth/logout` is idempotent (204 for anyone, including guests and cookie-less callers), revokes the current session row if any, and clears `re_session` only (never `re_device`). `POST /api/auth/logout-all` (registered only; a guest gets `403 registration_required` reason `account`) revokes all sessions of the user. A revoked or expired session becomes a new guest on the next bootstrap and reveals nothing about the account (this overrides the earlier edge case #1). Home header and Profile show "Đã có tài khoản? Đăng nhập" for guests.
- **FR-26** `POST /api/auth/login` accepts `nickname` and `password`, returns the same generic error `401 {"error":"invalid_credentials"}` for unknown nickname and wrong password (and burns equivalent scrypt time for unknown nicknames to avoid user enumeration by timing).
- **FR-27** Rate limiting (stored in the generic `rate_events(bucket, key_hash, created_at)` table, sliding window; buckets `login_nick`, `login_ip`, `register_ip`): after 5 failed logins for the same normalised nickname within 15 minutes, or 100 failed logins from the same IP within 15 minutes (raised from 20 for school NAT, see D-9), further login attempts return `429` with a `Retry-After` header and Vietnamese message, even if the password would be right, until the window expires. Login counts failures only; a successful login resets the nickname counter but not the IP counter. Registration is limited to 30 requests per IP per hour and counts every request that passed CSRF (422/409 outcomes included). 429 responses and CSRF failures are not counted. A wrong password on `DELETE /api/me` counts in the nickname login-failure bucket and yields the same 429. Limits are configurable.
- **FR-64** Client IP: `TRUSTED_PROXY_HOPS` (default 0 = socket peer address). If > 0, the client IP is the Nth entry from the right of `X-Forwarded-For`; the leftmost entry is never trusted. IPs are stored only as sha256(IP + server secret) in `rate_events.key_hash`.
- **FR-28** Logging in on a device that has a guest cookie: the rule is **discard-with-warning** (see section 1.12, decision D-1). If the device's guest has progress (at least one attempt, save, or completed round), the login screen first shows a warning in Vietnamese: "Tiến trình khách trên thiết bị này sẽ bị xóa khi bạn đăng nhập. Nếu muốn giữ lại, hãy đăng ký tài khoản mới." with buttons "Đăng nhập và xóa tiến trình khách" and "Quay lại". The login request must carry `discard_guest=true` to proceed when progress exists; otherwise the server returns `409 {"error":"guest_progress_exists"}`. When the guest has no progress, login proceeds silently. After success the guest row and its data are deleted in the same transaction and `re_device` is cleared.
- **FR-29** `PATCH /api/me` (registered only) allows changing avatar and CEFR level only; CEFR accepts A1, A2 or B1 (B2 exists for content only). The `hide_timer` setting is changed only through `PUT /api/me/settings` (any identity, guest included). Nickname and birth year are immutable in this release. `DELETE /api/me` (registered only, requires password re-entry) deletes the user and all owned data (attempts, review_state, saves, sessions, upload claims, and all of the user's cards, shared ones included) and clears cookies. After the deletion commit, every `card_contents` that has no remaining `cards` row and is not owned by the seed is garbage-collected: contents row, `image_assets` row and file are deleted; the GC must first verify that NO `cards` row references the content. The same GC runs in maintenance (FR-62).

#### E. CSRF and request security

- **FR-30** Every state-changing request (POST, PUT, PATCH, DELETE) requires (a) an `Origin` (or, if absent, `Referer`) header whose origin equals the configured `APP_ORIGIN`; if both are missing the request is rejected with 403 (except bootstrap, which is idempotent and harmless); if `Origin` is present it must match, and (b) double-submit CSRF protection: a non-HttpOnly cookie `re_csrf` (SameSite=Lax; named `__Host-re_csrf` when Secure) whose value must equal the `X-CSRF-Token` request header. Missing or mismatched values return `403 {"error":"csrf_failed"}`. `/api/session/bootstrap` issues the CSRF cookie and returns the token; bootstrap itself is exempt from the token check but still enforces the Origin check when an Origin header is present. The CSRF token is stable per browser and is NOT rotated on login/register. Client rule: on `csrf_failed`, re-bootstrap once and retry once; the client sends bootstrap as one shared promise per tab.
- **FR-31** Every request body is validated by a pydantic v2 model with `extra='forbid'`; invalid input returns `422` with field-level errors that never echo the password value.
- **FR-32** All SQL is parameterised and lives in repositories. Passwords, tokens, token hashes, and guardian emails are never logged or returned (the guardian email is not returned by any endpoint, including `/api/me`).
- **FR-33** Responses set `Cache-Control: no-store` for all `/api/` JSON that includes user-specific data, and security headers (`X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`, a restrictive `Content-Security-Policy` allowing only same-origin scripts and `blob:`/`data:` images and media).

#### F. AI-once pipeline, uploads, cards

- **FR-34** `POST /api/uploads` (registered only; multipart) accepts JPEG, PNG, or WebP up to `MAX_UPLOAD_BYTES` (default 5 MB, after client-side compression to about 1280 px long edge) and `MAX_PIXELS` (default 25 MP). The type is determined by content sniffing (not by the client-supplied header or extension). Other unsupported types (including animated WebP/APNG) return `415 unsupported_image`; oversize bytes return `413`; exceeding the pixel limit or a decompression bomb returns `413 image_too_large`; corrupt images return `422`.
- **FR-35** The server re-encodes the image with Pillow, which strips all EXIF/GPS metadata, and only the cleaned image is stored (on disk under a configured data directory with a random file name; the DB stores relative `storage_path`). The dedupe key is the sha256 of the **raw uploaded bytes** (`image_assets.source_sha256`, UNIQUE); the cleaned file's sha256 is stored separately as `clean_sha256`. `phash` stays a nullable, unused column.
- **FR-36** Dedupe and AI-once (overrides the earlier text): an upload NEVER creates a `cards` row. It finds or creates `image_assets` + `card_contents` and inserts an `upload_claims(user_id, content_id)` row for the uploader; the claim is the access control for `GET /api/uploads/{content_id}`, `POST /api/cards` and the retry path (no claim -> 404). If `source_sha256` exists and its `card_contents.status='ready'`, the server makes zero AI calls and the response has `dedupe='ready'`; if the user already owns a card for that content the response includes `card_id`. If the content is `processing`, the request attaches to the in-flight job, makes zero provider calls and returns `dedupe='in_flight'` (message "Ảnh này đang được xử lý, vui lòng chờ…"). If no row exists (`dedupe='none'`), the server inserts `image_assets` + `card_contents(status='processing')` in a single `BEGIN IMMEDIATE` transaction guarded by the unique `source_sha256`, then runs the analysis outside the DB transaction as a FastAPI BackgroundTask in the worker that won the insert. The card is created only by `POST /api/cards {content_id, title, label_overrides}` (idempotent via UNIQUE(owner, content)); there are no draft rows, and cancelling the review saves nothing.
- **FR-37** Simultaneous uploads of identical bytes by different users result in exactly one `AIProvider.analyze` call (`card_contents.ai_calls = 1`), both users get an `upload_claims` row for the same `card_contents`, and each ends with their own `cards` row (after `POST /api/cards`) pointing to it.
- **FR-38** The AI result is validated with pydantic (topic, tags, CEFR, 3-5 labels with box, IPA, Vietnamese meaning, accepted answers, descriptions en+vi, story en+vi, safety flags). Retry budget: a timeout or exception counts as a call, and `ai_calls` is incremented in a committed write BEFORE each call. Per processing run: 1 automatic retry (at most 2 calls). Manual retries: 2 per image in total (`manual_retries`), triggered by re-uploading a failed image. Hard cap: 6 calls per image; once exhausted the upload returns `409 analysis_unavailable`. After the budget of a run is spent: `status='failed'`, `error` recorded, Vietnamese retry message. "<= 1.05 calls per image" is an aggregate pilot metric (section 1.14), not a per-image cap.
- **FR-39** Bounding boxes are converted from the provider's `box_2d` (0-1000, `[ymin, xmin, ymax, xmax]`) to normalised 0-1 centre `x,y` plus box corners; labels with coordinates outside 0-1 are dropped.
- **FR-40** Audio: for each label word, description sentence, and story sentence, an `audio_assets` row is found or created by `(text, voice)`; the same text across images maps to one audio asset. In this release, TTS bytes come from the pre-generated mp3 catalogue (file name = slug + djb2 hash) for seeded text. The files are copied from `docs/audio` to `frontend/audio` by a tool step and served statically at `/audio/<file>`; the card payload carries `audio_url`. There is NO `GET /api/audio/{id}` endpoint (removed). For text with no file the frontend falls back to the browser speech voice and `audio_assets.storage_path` may be NULL.
- **FR-41** Review step: after processing, `GET /api/uploads/{content_id}` (upload claim required, else 404) returns status and, when ready, the AI result. The user may drag markers, move/edit/delete existing labels and set a title; adding labels is not allowed. Validation: 1-8 labels; word 1-40 characters; no duplicate words (case-insensitive); title <= 60 characters. `POST /api/cards` (upload claim required) saves the card with the user's edits stored as a per-card revision (`label_overrides` JSON on `cards`); shared `card_contents`/`card_labels` are never overwritten by a user's edits.
- **FR-42** The processing screen shows the number of AI calls made for this image (`ai_calls`) and a message such as "Ảnh này đã có sẵn, không cần gọi AI" when `dedupe='ready'` (this request made 0 calls). The upload response carries `dedupe: none|ready|in_flight`.
- **FR-65** Processing lease: `card_contents.lease_expires_at = now + (2 x provider timeout + 30 s)`. Any poll or upload that sees an expired `processing` row sets it to `failed` (lazy sweep); a startup sweep does the same. The client stops polling after 120 s and shows a retry message.
- **FR-43** Photos are private by default (`cards.visibility='private'`). A card image file is served only to its owner, or to any user if the card is a seeded system card, or if visibility is not private AND `card_contents.moderation_status='approved'`. Another user's private card returns `404` (not `403`) on every card subroute, to avoid revealing existence.
- **FR-44** Sharing (overrides the earlier pending behaviour): there is no reviewer, so there is NO pending state. `POST /api/cards/{id}/share` (registered owner only) checks the safety flags from the single AI call (`has_identifiable_faces=false`, `has_personal_info=false`, `has_nsfw_or_violence=false`, `is_suitable_for_students=true`). Clean -> `moderation_status='approved'` and visibility `public` (`class` stays in the CHECK but is never set). Any unsafe flag -> `moderation_status='rejected'`, visibility stays private and the response is `422 share_not_allowed` with a Vietnamese reason (faces / personal info / unsuitable). No back-office exists in this release (section 1.11).
- **FR-58** Card lifecycle endpoints: `DELETE /api/cards/{id}/share` returns a shared card to private (registered owner); `DELETE /api/cards/{id}` deletes the card (registered owner; the content/image GC of FR-29 applies afterwards).
- **FR-59** Pagination: list endpoints use keyset pagination on `(created_at DESC, id DESC)` with `limit` (default 20, max 50) and an opaque `cursor`.
- **FR-45** Seeding: an idempotent seed on startup inserts the system cards, labels, sentences and audio assets from the prototype's data (owner = a system user, `kind='system'` which never logs in and has no password hash, `moderation_status='approved'`, visibility public) without calling any AI provider. Production seed = the prototype cards; their images ship under `backend/seed_assets/` and are copied into `DATA_DIR` on seed. The 100-card performance dataset (NFR-F1) is a test-only fixture generator.
- **FR-63** Migrations and seed: the migration runner uses `BEGIN EXCLUSIVE`, re-reads `schema_migrations` inside the lock, splits each file with `sqlite3.complete_statement`, executes statements one by one, inserts the version and commits; it never uses `executescript` (auto-commit). The seed runs afterwards in its own `BEGIN IMMEDIATE`. Seed rows are keyed by a stable `seed_key`; IDs are uuid5(seed_key) so label/sentence IDs survive reseeds; the seed is upserted, seed content is never deleted while referenced, and `seed_version` is kept in `app_meta`.
- **FR-46** AIProvider: `AIProvider.analyze(image_bytes) -> AnalysisResult`. `GeminiProvider` is selected only when `GEMINI_API_KEY` is set; otherwise `MockProvider` (deterministic, derived from the sha256) is used. Tests use the mock. The provider is called only from the upload service, with a timeout (default 30 s) and a global concurrency limit (default 2) to bound cost.

#### G. Practice, Reflex, Library

- **FR-47** Practice: three levels per card (Labeling, Describing, Storytelling). Level 1 shows markers and IPA; the Vietnamese meaning is hidden until "Xem nghĩa" is tapped. Level 2 unlocks when the user's Level 1 score for that card is >= 70%; Level 3 unlocks when Level 2 is >= 70%. Scores and unlocks are stored server-side per user and card (`card_progress`). Level score = mean over the level's items of the LATEST score per item; unattempted items count 0. Level 1 = labels, level 2 = description sentences, level 3 = story sentences. `best_score` = maximum of this value ever reached. Unlock threshold >= 70. An attempt on a locked level returns `409 level_locked`.
- **FR-48** `POST /api/attempts` records one attempt (item type, item id, mode `shadow|reflex`, reflex level, optional `reflex_session_id`, transcript, pronunciation, `reflex_ms`, `skipped`, `client_attempt_id`) with server-side range validation, and updates `review_state` (SM-2, FR-56) and progress in the same transaction. The server computes accuracy (FR-55); the client no longer sends it. `client_attempt_id` (UUID) with UNIQUE(user_id, client_attempt_id): a replay returns the original result with 200. There is no offline queue. Response: `AttemptOut{accuracy, score, q, unlocks, xp}`.
- **FR-49** Reflex mode: `POST /api/reflex/sessions` returns up to 10 rounds chosen from the user's due `review_state` items first, then new items (weak words first). Levels R1 (hint, 6 s), R2 (no hint, 5 s), R3 (no hint, 3 s), R4 (describe the highlighted region, 8 s). Reflex score per FR-55. Unlock of the next level requires >= 80% in 2 consecutive sessions of the level, tracked in `reflex_progress` (FR-61). `reflex_ms` must be in 0..limit+2000 ms; above the limit counts as a timeout.
- **FR-50** Hide-timer option: the user can hide the countdown; timing is still measured. The setting is stored in `user_settings.hide_timer` and applies to guests and registered users.
- **FR-51** Auto mode (hands-free): one tap starts countdown, beep, auto-open microphone, scoring, model audio, next round; a Stop button always works. Without microphone permission it runs in listen-and-repeat mode and writes no attempts (does not affect `review_state`).
- **FR-52** Library: tabs "Bài của tôi" (owned cards; for guests: an empty state with a "Chụp ảnh" call to action that triggers the camera gate; saved seeded cards appear only in "Đã lưu", overriding the earlier wording), "Đã lưu", "Cần ôn lại" (cards with due `review_state` items; the badge counts CARDS), search by word (`lower(word)` index), topic list with counts, and filters by topic. Combined score per attempt = `reflex_score` (reflex mode) or accuracy (shadow mode). Card mastery = mean combined score of the last <= 5 attempts on the card; 0 attempts = "Chưa học"; under 60% "Cần ôn", 60-84% "Đang học", 85%+ "Đã thuộc".
- **FR-53** Explore: lists seeded cards and approved shared cards, filterable by topic and CEFR level, with Save and Practice actions; no AI calls on read paths.
- **FR-54** Profile: shows avatar, nickname, streak, XP, level progress (rules in FR-57). For guests, Profile shows a prominent "Đăng ký để lưu tiến trình" banner (reason `profile`, skippable, no gate on viewing), a "Đã có tài khoản? Đăng nhập" link, and no editable fields. For registered users it shows logout, logout-all, and delete-account actions.
- **FR-55** Scoring (server-side, pure function). Matching: NFKC, lowercase, punctuation stripped. Label accuracy: 100 if any accepted answer appears as a whole word in the transcript, otherwise round(100 x difflib ratio) capped at 60. Sentence accuracy: word-level recall via difflib matching blocks. `pronunciation` is clamped to 0-100 and stored only (never used for unlock or SRS). Reflex score = 0.6 x accuracy + 0.4 x speed x [accuracy >= 70] (speed counts only when accuracy >= 70; speed = 100 at <= 1.0 s, linear to 0 at the level limit). R4 is scored against the highlighted label's word and accepted answers (whole-word containment in the transcript). Skip = timeout: transcript null, accuracy 0, q=0, and it counts as an answered round.
- **FR-56** SRS (SM-2, pure function). Score s maps to quality q: s>=90 -> 5, >=80 -> 4, >=70 -> 3, >=50 -> 2, >=20 -> 1, else 0. If q<3: reps=0, interval=1, lapses+1. Otherwise interval = 1 (first), 6 (second), then round(interval x ease), reps+1. ease += 0.1 - (5-q)(0.08 + 0.02(5-q)), floor 1.3 (initial 2.5). `due_at = now + interval days`.
- **FR-57** XP, streak, level (computed on read, no stored counters). XP per attempt (`attempts.xp`): 10 if score >= 70 else 2; listen-only (auto mode without microphone) earns none. Streak = number of consecutive `Asia/Ho_Chi_Minh` calendar days with >= 1 attempt, ending today or yesterday. Level = floor(XP / 500) + 1; level progress = (XP mod 500) / 500.
- **FR-60** `GET /api/me` and `PUT /api/me/settings` are available to guests and registered users; `GET /api/me` returns streak/xp/level and settings and never the guardian email.
- **FR-61** `reflex_progress` rows are created lazily; R1 is unlocked by default. Practice (card_progress) and Reflex unlocks are independent. A Reflex session counts toward unlock only with >= 5 answered rounds (skips count as answered); session score = mean `reflex_score`; `POST /api/reflex/sessions/{id}/complete` is idempotent.
- **FR-62** Maintenance: guest purge (FR-6), empty-guest purge (`GUEST_EMPTY_RETENTION_DAYS`), stale `processing` sweep, orphan content/image GC (FR-29) and `rate_events` older than 1 day are removed by an idempotent maintenance job that runs at startup and then every 24 h as an asyncio task; it is also runnable as `python -m backend.app.maintenance`.
- **FR-66** Foreign keys: every user-owned table has an FK to `users` ON DELETE CASCADE; `card_progress` and `card_saves` also FK to `cards` ON DELETE CASCADE (see 1.9). Seed content (`kind='system'` owner) is never removed by user deletion.

### 1.6 Non-functional requirements

**Security**
- NFR-S1 Tokens: random 256-bit (`secrets.token_urlsafe(32)`), stored as sha256 only; cookies HttpOnly, SameSite=Lax, `Secure` when not on localhost.
- NFR-S2 CSRF as in FR-30; CORS is disabled by default (same-origin only).
- NFR-S3 SQL injection: 100% of queries parameterised (verified by a repository-level test that scans for string-formatted SQL).
- NFR-S4 Uploads: type sniffing, size and pixel limits, decompression-bomb protection (Pillow `MAX_IMAGE_PIXELS` enforced), re-encoding, random server-side filenames, no path traversal.
- NFR-S5 Frontend never uses `innerHTML` with dynamic data (DOM builders / `textContent`); CSP blocks inline scripts.
- NFR-S6 No secrets in git: `.env` is git-ignored; `.env.example` lists `GEMINI_API_KEY`, `APP_ORIGIN`, `DATA_DIR`, `GUEST_FREE_SESSIONS` (default 1), `SESSION_IDLE_MINUTES`, `GATE_GRACE_SECONDS`, `TRUSTED_PROXY_HOPS`, `GUEST_RETENTION_DAYS`, `GUEST_EMPTY_RETENTION_DAYS`, rate-limit and size settings.
- NFR-S7 Login and registration enumeration resistance as in FR-26 and FR-20 (nickname availability is only disclosed on register submit, not via a public lookup endpoint).

**Privacy**
- NFR-P1 Personal data limited to nickname, avatar key, birth year, and guardian email (only if under 16) plus `guardian_consent_at`. No real name, phone, location, or EXIF.
- NFR-P2 Guardian email is write-only at the API level (never returned, never logged, excluded from analytics); no email is sent in this release.
- NFR-P3 Photos private by default (FR-43); safety flags from the single AI call decide approval or rejection for sharing (FR-44); there is no pending state.
- NFR-P4 No public leaderboard; no display of other users' nicknames except on approved shared cards (nickname only).
- NFR-P5 Account deletion removes personal data (FR-29); guest purge per FR-6. A short Vietnamese privacy notice is linked from the Register screen.

**Performance**
- NFR-F1 p95 latency for read endpoints (cards list, card detail, library, search, bootstrap) <= 200 ms server-side at 50 concurrent users on a single small instance (measured with the seeded dataset of at least 100 cards, excluding network).
- NFR-F2 p95 latency for `POST /api/attempts` <= 150 ms.
- NFR-F3 Upload pipeline with MockProvider: p95 <= 3 s from request to `ready`; with Gemini the target is p50 <= 15 s (spec section 8), and the UI shows progress and never blocks navigation.
- NFR-F4 scrypt login/registration takes 50-250 ms CPU and runs off the event loop (thread pool) so that it does not block other requests.
- NFR-F5 Initial JS+CSS payload <= 300 KB uncompressed (no framework); audio is fetched lazily per item.

**SQLite concurrency and availability**
- NFR-A1 SQLite pragmas on every connection: `journal_mode=WAL`, `foreign_keys=ON`, `busy_timeout=5000`, `synchronous=NORMAL`; one short-lived connection per request (or per worker thread); every write uses `BEGIN IMMEDIATE`; write transactions are short and never wrap an AI or network call. The usage-session touch is throttled to once per 60 s per user to limit write contention.
- NFR-A2 Deployment is a single app instance in this release; the pilot runs uvicorn with `--workers 1` because the AI concurrency semaphore and BackgroundTasks are per process (a worker crash loses a job; the lease sweep recovers it). Dedupe uses `BEGIN IMMEDIATE` plus the unique `source_sha256` constraint.
- NFR-A3 Schema migrations are numbered SQL files (`backend/migrations/001_init.sql`...) applied on startup by the runner described in FR-63 and recorded in `schema_migrations`; migrations are forward-only.
- NFR-A4 Backup: the SQLite file and the image directory can be backed up by copying with the SQLite online backup API; documented in the README. Target availability for pilot: 99% during school hours; a crash during an AI job leaves `card_contents.status='processing'` rows that are recovered by the lease rule (FR-65) at startup and lazily on poll.

**Accessibility and mobile**
- NFR-X1 Mobile-first layout tested at 360x640 and 390x844; Safari iOS and Chrome Android supported.
- NFR-X2 Markers are `button` elements with `aria-label`, hit area at least 44x44 px; minimum text size 12 px; contrast meets WCAG AA; every flow is operable without the countdown visible (hide-timer).
- NFR-X3 Registration form fields have labels, inline Vietnamese error messages announced via `aria-live`, and logical focus order; the gate screens trap focus appropriately and the mandatory gate has no close button.
- NFR-X4 Press-and-hold-to-speak uses Pointer Events with `pointercancel` handling and disables the context menu on the button.

### 1.7 Acceptance criteria

- **AC-1** Given a new browser with no cookies, when the user opens `/`, then Home is displayed within 2 s with no welcome or registration screen, a guest user row exists, and an `re_device` cookie with HttpOnly and Max-Age of about 400 days is set.
- **AC-2** Given a guest who completed a Level 1 practice with 80% yesterday, when the guest reloads within the same visit, then the same user id is returned and Level 2 is shown as unlocked.
- **AC-3** Given a guest, when they tap the camera button, then the Register screen opens with reason `camera` and a Back button, and tapping Back returns to the previous screen with state intact and no account created.
- **AC-4** Given a guest calling `POST /api/uploads` directly, then the response is `403` with `registration_required` and reason `camera`, and no file is stored.
- **AC-5** Given `GUEST_FREE_SESSIONS=1` and a guest with one meaningful completed usage session, when the guest opens the app after more than 30 minutes of inactivity, then the Register screen appears with reason `second_visit`, no Back button, and any other non-exempt API call (e.g., `GET /api/cards`) returns `403 registration_required`; `GET /api/me`, heartbeat, login, register and logout still work, and `POST /api/attempts` for an item that existed before `gate_required_at` is still accepted within `GATE_GRACE_SECONDS` (FR-13).
- **AC-6** Given a guest who only viewed screens (no attempt, save, or Reflex round) in their first visit, when they return later, then the second-visit gate does not appear (FR-12a) and the next visit that contained a write action counts.
- **AC-7** Given two page loads 10 minutes apart, then they belong to one usage session (`usage_sessions` row count is 1).
- **AC-8** Given a guest with attempts and a valid registration payload, when they register, then the response is `201`, the user id equals the previous guest id, all previous attempts remain visible under the new account, `re_session` is set, and `re_device` is cleared.
- **AC-9** Given a registered user on the same device, when the browser is closed and reopened a week later, then bootstrap returns the registered user, no login or gate screen is shown, and Home is displayed.
- **AC-10** Given a registered user on a new device (no cookies), when they log in with the correct nickname and password, then a session is created, a previous token from that browser (if any) is revoked, and the user lands on Home with their progress.
- **AC-11** Given an under-16 birth year, when the form is submitted without a guardian email or without the consent checkbox, then the response is `422`, no user is changed or created, and the UI highlights the missing fields in Vietnamese.
- **AC-12** Given an under-16 registration with a valid guardian email and consent, then `guardian_consent_at` is set, and no API response (including `/api/me`) contains the guardian email.
- **AC-13** Given a registered nickname "Minh_An", when another user submits "minh_an", then the response is `409 nickname_taken` and the submitting guest keeps all progress.
- **AC-14** Given 5 failed login attempts for one nickname within 15 minutes, when a sixth attempt is made (even with the correct password), then the response is `429` with a `Retry-After` header.
- **AC-15** Given unknown nickname vs. known nickname with a wrong password, then both return an identical `401` body and status.
- **AC-16** Given a guest with progress who opens Login and logs in, then the warning in FR-28 is shown first; confirming discards the guest data and logs in; the guest row no longer exists; cancelling keeps the guest unchanged.
- **AC-17** Given a POST without the `X-CSRF-Token` header, or with a mismatched token, or with a foreign `Origin`, then the response is `403 csrf_failed` and no state changes.
- **AC-18** Given a registered user clicking logout, then the session row is revoked, `re_session` is cleared, and replaying the old cookie returns a fresh guest (no gate reason or message reveals the account); guest Home/Profile show "Đã có tài khoản? Đăng nhập".
- **AC-19** Given two users uploading the same image bytes at the same time (two threads, MockProvider with a call counter), then the counter equals 1, `card_contents.ai_calls=1`, both users have an `upload_claims` row, no `cards` row exists until each calls `POST /api/cards`, and after that both users have a card referencing one `card_contents` row.
- **AC-20** Given an already-processed image uploaded again by a different user, then no provider call occurs, the response has `dedupe='ready'`, and the processing screen shows the dedupe message. An upload of an image currently `processing` returns `dedupe='in_flight'` with 0 provider calls from that request.
- **AC-21** Given an upload that is a GIF, a 12 MB JPEG, or an HTML file renamed `.jpg`, then the responses are `415`, `413`, and `415` respectively, and nothing is stored. An animated WebP returns `415 unsupported_image`; an image above `MAX_PIXELS` or a decompression bomb returns `413 image_too_large`.
- **AC-22** Given a JPEG with GPS EXIF, after upload the stored file contains no EXIF tags (verified by re-opening the stored file).
- **AC-23** Given a private card owned by user A, when user B requests its image, then the response is `404`.
- **AC-24** Given a card whose safety flags include `has_identifiable_faces=true`, when the owner taps Share, then the response is `422 share_not_allowed` with a Vietnamese reason, `moderation_status='rejected'`, visibility stays private, and no "pending" state or message exists. Given clean flags, Share sets `moderation_status='approved'` and visibility `public`.
- **AC-25** Given a Level 1 score of 69%, then Level 2 is locked; at 70% it unlocks (boundary test).
- **AC-26** Given Reflex at R3 with hide-timer on, then the countdown is not displayed but `reflex_ms` is recorded for each attempt.
- **AC-27** Given a Reflex session in auto mode without microphone permission, then the app runs listen-and-repeat, shows the Vietnamese notice, and no attempts are written.
- **AC-28** Given the Library search for "cup", then results are returned using the `lower(word)` index and include cards whose labels contain "cup" (case-insensitive); response p95 <= 200 ms on the seeded dataset.
- **AC-29** Given the server started twice on the same database, then seed data is not duplicated and migrations are not re-applied.
- **AC-30** Given the Playwright e2e run, then the following flow passes: open `/` as a new visitor, start a Practice level, tap the camera, see the Register screen, press Back and continue, tap the camera again, register (age >= 16), land on the upload screen with previous progress intact, reload the page and remain logged in, close and reopen the browser context with saved cookies and land on Home logged in without a login screen.
- **AC-31** Given the pytest suite, then it contains and passes tests for: guest bootstrap, conversion (same id, data retained), sessions (rotation, revocation, expiry), rate limit, AI-once dedupe (including concurrency), CSRF, uploads (type, size, EXIF), and the cases AC-32 to AC-47.
- **AC-32** Given a gated guest within `GATE_GRACE_SECONDS` of `gate_required_at`, then `POST /api/attempts` for an item/session that pre-existed the gate succeeds; after the grace window, or for a new item, it returns 403; heartbeat returns `{gate}`.
- **AC-33** Given idle of exactly 30:00 vs 30:01 (`SESSION_IDLE_MINUTES=30`), then the first stays in the same usage session and the second starts a new one.
- **AC-34** Given a guest who no longer meets the threshold at a new usage-session start, then `gate_required_at` is cleared; `GUEST_FREE_SESSIONS` defaults to 1.
- **AC-35** Given a guest calling `POST /api/cards`, `PATCH /api/me` or `POST /api/auth/logout-all`, then the responses are 403 with reason `camera`, `account`, `account` respectively; `POST /api/auth/logout` returns 204 for guests and cookie-less callers.
- **AC-36** Given 100 failed logins from one IP in 15 minutes, then the next login returns 429 with `Retry-After`; 99 failures plus a valid login still succeed. Given 30 registration requests from one IP in an hour (422/409 included), the 31st returns 429. 429 responses and CSRF failures add no `rate_events` rows.
- **AC-37** Given `TRUSTED_PROXY_HOPS=0`, a spoofed `X-Forwarded-For` is ignored; with `=1` the last entry is used and the leftmost never.
- **AC-38** Given a state-changing request with neither Origin nor Referer, then 403 (bootstrap excepted); with a non-matching Origin, 403; after a `csrf_failed` the client re-bootstraps and retries once.
- **AC-39** Given a registered user with a shared card who deletes the account (correct password), then all their cards (including the shared one) are deleted, and `card_contents`/`image_assets`/files with no remaining `cards` row and not owned by the seed are removed; content still referenced by another user's card is kept. A wrong password returns 401/429 per the nickname bucket.
- **AC-40** Given an upload by user A, then `GET /api/uploads/{id}` and `POST /api/cards` by user B (no claim) return 404; the retry path likewise requires a claim; two image retries beyond `manual_retries=2` or more than 6 total calls return `409 analysis_unavailable`.
- **AC-41** Given a provider timeout, then `ai_calls` was incremented before the call and persisted; an expired `processing` lease is set to `failed` on the next poll or upload.
- **AC-42** Given label scoring, then "cup" in transcript "a red cup" scores 100; a fuzzy match is capped at 60; `accuracy` supplied by the client is rejected (422); `reflex_ms` above limit+2000 is rejected and above the limit is a timeout.
- **AC-43** Given scores 95/85/75/55/25/10, then SM-2 quality is 5/4/3/2/1/0; q<3 sets reps=0, interval=1, lapses+1; ease never drops below 1.3.
- **AC-44** Given a replayed `client_attempt_id`, then the original result is returned with 200 and no new attempt/XP/review change is recorded; an attempt on a locked level returns `409 level_locked`.
- **AC-45** Given attempts with scores 80 and 50 on the same day, then XP = 12; given activity yesterday and today, streak = 2; XP 1200 gives level 3 with progress 0.4.
- **AC-46** Given a guest, the Library tab "Bài của tôi" shows the empty state with a camera CTA, and a saved seeded card appears only in "Đã lưu"; the "Cần ôn lại" badge counts cards, not items.
- **AC-47** Given a card payload, then `audio_url` points to `/audio/<file>`, the file is served statically, and `GET /api/audio/{id}` does not exist (404). Given the migration runner executed concurrently by two processes, then migrations apply exactly once; the seed is idempotent with stable uuid5 IDs; the maintenance job (also `python -m backend.app.maintenance`) is idempotent.

### 1.8 REST API surface (product level)

Auth level: `public` = no identity needed; `identity` = guest or registered (cookie); `registered` = registered only; `csrf` = state-changing, Origin check + double-submit per FR-30; `gate` = blocked while a `second_visit` gate is set (FR-10), `exempt` = never blocked by the gate, `gate with grace` = FR-13. Unknown request fields are rejected everywhere (`extra='forbid'`). Error body: `{error, reason?, fields?}`.

| Method | Path | Auth / gate | Request -> Response |
|---|---|---|---|
| GET | `/api/health` | public | -> Health |
| GET | `/api/config` | public | -> ConfigOut (avatars, CEFR levels, upload limits, gate settings, birth-year range) |
| POST | `/api/session/bootstrap` | public, Origin check if present | -> BootstrapOut{user, is_guest, gate, csrf_token, config} |
| POST | `/api/session/heartbeat` | identity, csrf, exempt | -> HeartbeatOut{gate} |
| POST | `/api/auth/register` | public, csrf, exempt, rate-limited | RegisterIn -> 201 MeOut |
| POST | `/api/auth/login` | public, csrf, exempt, rate-limited | LoginIn{nickname, password, discard_guest} -> MeOut |
| POST | `/api/auth/logout` | any, csrf, exempt | -> 204 (idempotent) |
| POST | `/api/auth/logout-all` | registered, csrf | -> 204 (guest: 403 reason `account`) |
| GET | `/api/me` | identity, exempt | -> MeOut (streak/xp/level, settings; no guardian email) |
| PATCH | `/api/me` | registered, csrf, gate | MePatchIn{avatar_key?, cefr_level?} -> MeOut |
| PUT | `/api/me/settings` | identity, csrf, gate | SettingsIn -> SettingsOut (`hide_timer`) |
| DELETE | `/api/me` | registered, csrf | DeleteMeIn{password} -> 204 |
| GET | `/api/cards` | identity, gate | `?scope&topic&cefr&q&cursor&limit` -> CardPage (`scope=explore|mine|saved|due`) |
| GET | `/api/cards/{id}` | identity, gate, visibility -> 404 | -> CardDetail (labels, sentences, story, `audio_url`, progress/unlock state) |
| GET | `/api/cards/{id}/image` | identity, gate, visibility -> 404 | -> bytes |
| POST/DELETE | `/api/cards/{id}/save` | identity, csrf, gate, visible | -> SaveOut |
| POST/DELETE | `/api/cards/{id}/share` | registered owner, csrf, gate | -> ShareOut / 422 `share_not_allowed` |
| DELETE | `/api/cards/{id}` | registered owner, csrf, gate | -> 204 |
| GET | `/api/topics` | identity, gate | -> TopicList |
| POST | `/api/uploads` | registered, csrf, gate | multipart -> 202 UploadOut{content_id, status, dedupe, ai_calls, card_id?} |
| GET | `/api/uploads/{content_id}` | registered, upload claim required else 404 | -> UploadStatusOut |
| POST | `/api/cards` | registered, csrf, gate, upload claim | CardCreateIn{content_id, title, label_overrides} -> 201 CardDetail |
| POST | `/api/attempts` | identity, csrf, gate with grace | AttemptIn{client_attempt_id, card_id, item_type, item_id, mode, reflex_level?, reflex_session_id?, transcript?, pronunciation?, reflex_ms?, skipped} -> AttemptOut{accuracy, score, q, unlocks, xp} |
| POST | `/api/reflex/sessions` | identity, csrf, gate | ReflexStartIn{level} -> ReflexSessionOut |
| POST | `/api/reflex/sessions/{id}/complete` | owner, csrf, gate with grace, idempotent | -> ReflexSummaryOut |

Removed from the earlier draft: `GET /api/audio/{id}` (audio is static, FR-40). Settings are changed only via `PUT /api/me/settings` (FR-29). Static assets (`/`, `/js/*`, `/css/*`, `/audio/*`) are public and served by the backend.

### 1.9 SQLite schema changes

Replaced per `docs/architecture/guest_first_web_app_review.md`. Migration `001_init.sql` creates the tables below. TEXT UUID PKs, ISO-8601 UTC TEXT timestamps, JSON in TEXT with `CHECK (json_valid(col))`. Pragmas on every connection: `journal_mode=WAL`, `foreign_keys=ON`, `busy_timeout=5000`, `synchronous=NORMAL`. Every write uses `BEGIN IMMEDIATE`. Every user-owned table has an FK to `users` ON DELETE CASCADE; `card_progress` and `card_saves` also FK to `cards` ON DELETE CASCADE.

| Table | Columns, constraints, indexes |
|---|---|
| `schema_migrations` | version PK, applied_at |
| `app_meta` | key PK, value (holds `seed_version`) |
| `users` | id, kind CHECK(guest/registered/system), nickname, nickname_ci, password_hash, password_params, avatar_key, birth_year, cefr_level, guardian_email, guardian_consent_at, role, gate_required_at, created_at, registered_at, last_seen_at. Partial UNIQUE(nickname_ci) WHERE kind='registered'; idx(kind, last_seen_at) |
| `device_tokens` | token_hash PK, user_id FK CASCADE, created_at, last_seen_at; idx user_id |
| `sessions` | token_hash PK, user_id FK CASCADE, created_at, last_seen_at, expires_at, absolute_expires_at, revoked_at, grace_until, rotated_from; idx user_id, expires_at |
| `usage_sessions` | id, user_id FK CASCADE, started_at, last_activity_at, had_write; idx(user_id, last_activity_at DESC) |
| `rate_events` | id INTEGER PK, bucket CHECK(login_nick/login_ip/register_ip), key_hash, created_at; idx(bucket, key_hash, created_at) (replaces `login_attempts`) |
| `image_assets` | id, source_sha256 UNIQUE NOT NULL, clean_sha256, phash NULL, storage_path NOT NULL, width, height, first_uploaded_by FK users SET NULL, created_at |
| `card_contents` | id, image_asset_id UNIQUE FK CASCADE, seed_key UNIQUE NULL, status CHECK(processing/ready/failed), model, prompt_version, ai_calls, manual_retries, lease_expires_at, topic, topic_tags JSON, cefr_level, safety JSON, moderation_status CHECK(pending/approved/rejected), raw_response JSON, error, created_at; idx topic, idx(status, lease_expires_at) |
| `card_labels` | id, content_id FK CASCADE, position, word, ipa, vi_meaning, accepted_answers JSON, cefr_level, confidence, x, y, box_x1..box_y2 (CHECK 0..1), audio_id FK audio_assets SET NULL; idx lower(word), (content_id, position) |
| `card_sentences` | id, content_id FK CASCADE, kind CHECK(description/story), position, en, vi, audio_id FK SET NULL; idx(content_id, kind, position) (replaces the `descriptions`/`story_*` columns of the earlier draft) |
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

Notes: the `system` user (`kind='system'`) owns all seeded cards, never logs in and has no password hash. `nickname` display uses the original casing; uniqueness uses `nickname_ci`. `card_contents` rows are shared; seed rows carry a `seed_key`. Guardian email is stored plain text (needed for future consent follow-up, D-11) and is never returned by any API.

### 1.10 UI changes per screen

All screens are rebuilt from the prototype as vanilla-JS modules (`frontend/js/screens/*.js`), Vietnamese UI strings, no `innerHTML` with dynamic data.

- **Boot (no Welcome screen):** calls bootstrap, then routes: second-visit gate -> Register (mandatory); otherwise Home. A skeleton is shown for at most 2 s.
- **Home:** greeting by nickname or "Bạn khách"; streak/XP; "Luyện tiếp" and "Cần ôn lại" tiles; a camera button (guest triggers camera gate); a small banner for guests "Đăng ký để lưu tiến trình" that never blocks; a "Đã có tài khoản? Đăng nhập" link for guests in the header.
- **Explore:** seeded and approved shared cards, topic/CEFR filters, Save / Luyện actions.
- **Add photo (registered only):** pick/take photo, client-side compression to about 1280 px, upload; error states for type, size, network.
- **Processing:** shows steps and the AI call count ("Số lần gọi AI: 1" or "0 - ảnh đã có sẵn"); polls status; retry on failure.
- **Review AI result:** photo with draggable markers (>= 44 px), edit/move/delete existing labels (no adding; 1-8 labels, title <= 60), title, Save (`POST /api/cards`), Cancel (nothing saved); edits stored per card. Share / Unshare / Delete actions on the card of a registered owner; a rejected share shows the Vietnamese reason.
- **Practice:** three level tabs with lock states (unlock at 70%), IPA on Level 1, "Xem nghĩa" reveal, hold-to-speak, replay sample and recording, error states for mic permission, silence, noise.
- **Reflex:** levels R1-R4, countdown ring with hide-timer toggle, Skip, feedback ("Phản xạ tốt"), summary screen; auto mode with Stop.
- **Library:** tabs "Bài của tôi" / "Đã lưu" / "Cần ôn lại" with badge (counts cards); search; topics; guest "Bài của tôi" = empty state with CTA to camera gate (saved cards only in "Đã lưu").
- **Profile:** avatar, nickname, streak, XP; guest register banner (opens Register with `reason=profile`, Back returns to Profile, success returns to Profile) and "Đã có tài khoản? Đăng nhập" link; registered: logout, logout everywhere, delete account (password confirmation).
- **Login (new):** nickname + password; shows the FR-28 discard warning when the device guest has progress; generic invalid-credentials message; rate-limit message with remaining wait time; link "Chưa có tài khoản? Đăng ký".
- **Register (new):** fields nickname, password (show/hide), avatar picker (preset set), birth year (select), CEFR level (A1/A2/B1); if age < 16: guardian email + consent checkbox ("Cha mẹ/người giám hộ của em đồng ý cho em sử dụng ReflexEnglish và lưu thông tin tối thiểu"); privacy notice link; Back button for reasons `camera` and `profile` (never for `second_visit`); on `nickname_taken` a "Đăng nhập" action is offered; link "Đã có tài khoản? Đăng nhập". Copy for the second-visit gate explains: "Em đã luyện tập rồi - hãy tạo tài khoản để giữ tiến trình nhé."
- **Navigation:** bottom nav (Home, Explore, Camera, Library, Profile); the Camera item shows the camera gate for guests.

### 1.11 Out of scope (this release)

- Teacher role, classes, class sharing (`visibility='class'` exists in schema but is not exposed).
- Moderation back-office or reviewer UI (there is no pending state: unsafe images are rejected for sharing, FR-44).
- Content reporting ("Báo cáo") flow and community comments, follows, leaderboards.
- Payments, subscriptions, ads.
- Sending email of any kind (guardian email is stored only; no verification email, no consent email).
- Password reset by email, email-based recovery, OAuth/social login, magic links, MFA.
- Changing nickname or birth year after registration; merging two registered accounts.
- Merging guest progress into an existing account at login (see D-1).
- Real server-side STT/pronunciation scoring; Azure TTS generation at runtime (pre-generated mp3 and browser fallback are used).
- PWA install/offline mode (layout is PWA ready only), push notifications.
- Perceptual-hash "similar image" suggestion UI (phash stored only).
- Multi-instance / PostgreSQL deployment.

### 1.12 Decisions on open questions (defaults chosen)

| ID | Question | Decision |
|---|---|---|
| D-1 | Login on a device that has a guest with progress: merge or discard? | Discard with explicit warning and confirmation (FR-28). Merging two different identities' SM-2 state, unlock levels, and saves has no trivially correct rule and risks cross-user data exposure on shared family devices. Guests who want to keep progress are directed to Register. |
| D-2 | What counts as a session / how many free sessions? | `GUEST_FREE_SESSIONS` default 1; a session is a usage session with 30 min idle timeout (`SESSION_IDLE_MINUTES`) containing at least one write action (FR-12). |
| D-3 | Camera gate skippable? | Yes (Back), repeated each time the guest taps the camera. Second-visit gate is not skippable. |
| D-4 | Mid-practice second-visit gate | Gate is evaluated only at new-session start; if the idle timeout elapses mid-practice, the gate waits until the current round is saved (FR-13). |
| D-5 | Registered session lifetime | 90 days sliding idle, 365 days absolute, rotate on login/registration and on use when older than 30 days. |
| D-6 | Guest cookie lifetime and retention | 400-day cookie; guest rows purged after 180 days of inactivity. |
| D-7 | Minimum age | 10 (OQ-3 for legal confirmation); under 16 requires guardian email + consent; no email verification in this release. |
| D-8 | Nickname rules | 3-20 chars, case-insensitive unique, no spaces, no emails/phones, denylist. |
| D-9 | Login rate limit | OVERRIDDEN (school NAT, architect OQ-15): 5 failures / nickname / 15 min (unchanged) and 100 failures / IP / 15 min (was 20); registration 30 / IP / hour (was 5). Generic `rate_events` table; login counts failures only; registration counts every request that passed CSRF. |
| D-10 | Guest uploads | Disabled; guests use seeded content only, which bounds AI cost and abuse by anonymous users. |
| D-11 | Guardian email storage | Stored plain, write-only through API; encryption at rest deferred. |
| D-12 | Image storage | Local disk under `DATA_DIR` with random names; DB stores relative paths. |

Other decisions changed or fixed by the architect review: D-7 stays at minimum age 10 (persona text "11-18" is descriptive only); D-10 unchanged (guest uploads disabled, now also `POST /api/cards` and share); D-4 now includes the explicit grace rule of FR-13; D-6 gains the 7-day empty-guest purge.

Open questions (status after the architect review):
- OQ-1 RESOLVED: `GUEST_FREE_SESSIONS=1` for the pilot, configurable.
- OQ-2 RESOLVED for the build (default kept): logout is available, no PIN lock; shared-device risk is accepted for the pilot.
- OQ-3 OPEN (PO/legal): minimum age 10 and sufficiency of an unverified guardian email under Decree 13/2023. Release-blocking for under-16 sign-ups in production, not for the build.
- OQ-4 OPEN (PO): monthly AI budget; default concurrency 2 and `--workers 1`, no monthly cap.
- OQ-5 RESOLVED: no consent-upgrade flow in this release; documented as out of scope.

### 1.13 Edge cases for the BA to expand into use cases

1. **Cookie cleared (guest):** guest progress is orphaned and a new guest starts with a fresh session counter (the second-visit gate is thereby bypassable by clearing cookies; accepted risk, mitigated by guests having no upload ability). Orphans are purged by FR-6/FR-62 (empty guests after 7 days). Cookie cleared (registered), or session revoked/expired: the browser becomes a NEW guest and nothing about the account is revealed (architect override, FR-25); Home and Profile show "Đã có tài khoản? Đăng nhập". Sessions on the server remain valid until expiry or revocation.
2. **Guest on two devices:** two independent guests; each counts sessions separately; registering the same nickname on the second device returns `nickname_taken`; no merging.
3. **Simultaneous uploads of identical image** by two users, or by one user in two tabs: one AI call, one `image_assets` row, `UNIQUE(owner_id, content_id)` returns the existing card for the same user.
4. **Registering while an upload is processing:** guests cannot upload, but the camera-gate flow can be interrupted; registration in tab 2 while tab 1 is still a guest: tab 1's next request carries the old `re_device` which has been deleted, so it must fall back to bootstrap (new guest or the registered session via `re_session` shared cookie) without errors. An upload started by the converted user and still processing continues; its result is attached to the same user id.
5. **Double-submit registration** (double click, retry after timeout): exactly one conversion, second call `409 already_registered`.
6. **Under-16 without consent / without guardian email / with invalid guardian email**; birth year boundary (user turns 16 this calendar year: age = year difference, documented), birth year in the future, under minimum age.
7. **Nickname taken** with different case, Unicode look-alikes, leading/trailing spaces, reserved words; race between two registrations.
8. **Brute force:** distributed attempts across IPs against one nickname (per-nickname limit), one IP against many nicknames (per-IP limit), lock-out timing and user messaging, attempts after expiry, effect of successful login on counters, attempt during CSRF failure (not counted).
9. **Guest threshold counting:** reload, two tabs, background tab heartbeat, idle exactly at 30 minutes, view-only visit, visit that begins and ends within seconds, `GUEST_FREE_SESSIONS=0`, `=3`, clock skew, bootstrap failure mid-way.
10. **Second-visit gate mid-practice:** resumed tab after idle, in-flight Reflex round or auto mode, microphone recording in progress, pending attempt write after the gate flips; the user must never lose the current result or be stuck in a loop.
11. **Login with discard:** guest with and without progress, cancelling the warning, failed login (guest must not be deleted on failure), login in tab 1 while tab 2 is still the guest, two accounts logging in on one device in sequence.
12. **Session lifecycle:** expired session, revoked session, rotation overlap with two tabs, logout in one tab while another tab is mid-request, `logout-all`, session cookie present but user deleted.
13. **Upload failures:** AI invalid JSON twice, AI timeout, server restart during processing, disk full, concurrent re-upload of a failed image, safety flags unsuitable for students (card is saved private but cannot be shared).
14. **Offline / network loss** mid-attempt save (retry queue or user message), and cookies blocked by the browser (show a Vietnamese notice because guest persistence is impossible).
15. **CSRF edge cases:** missing Origin (older browsers), Origin with a different port, token cookie missing after bootstrap failure.
16. **Account deletion** with owned cards that are shared and approved: all of the user's cards are deleted, shared ones included (architect override, FR-29); orphaned `card_contents`/images are garbage-collected after the commit, but only if no `cards` row references them.

### 1.14 Success metrics

| Metric | Target (pilot) | Measurement |
|---|---|---|
| Guest-to-registered conversion at the gates | >= 40% of guests who hit a gate register within the same visit | gate shown vs. conversions (`registered_at`), by reason |
| Time to first practice for a new visitor | <= 30 s from landing to the first answered item, median | first bootstrap vs. first attempt |
| Registration form completion | >= 80% of started registrations succeed | form opens vs. 201 responses |
| Progress retention after conversion | 100% of guest attempts retained | automated check in tests and a nightly consistency query |
| D7 return rate (registered) | >= 35% (spec 1.3) | logins/auto-logins plus >= 1 practice session |
| Auto-login success | >= 95% of registered returning visits without a login screen | bootstrap results by session validity |
| AI cost control | AI calls per unique image <= 1.05 on average (aggregate pilot metric, including retries; not a per-image cap, see FR-38); zero duplicate calls for identical raw bytes | `SUM(ai_calls)/COUNT(card_contents)` |
| Login abuse | 0 successful logins after the rate limit trips (tests); 429 rate below 1% of login attempts in the pilot (monitor school-NAT lockouts) | `rate_events` + access logs |
| Read latency | p95 <= 200 ms (NFR-F1) | server access logs |
| Reflex median response time (Level 1) | -25% after 3 weeks (spec 1.3) | `attempts.reflex_ms` by week |

### 1.15 Related documents and cross-references

- Domain and prompt contract: `docs/spec_v1.1.md` sections 3 (modules), 4 (AI-once pipeline), 5 (schema, adapted here from PostgreSQL/Supabase to SQLite; the Supabase RLS policies of section 5.1 are replaced by application-level authorisation in FR-4, FR-10, FR-43), 2.2 (minors' constraints, implemented by FR-14 to FR-16). This section supersedes the spec's "Welcome and registration" first-screen flow shown in the prototype (spec section 7), which is replaced by the guest-first flow.
- Stack and hard rules: `.claude/CLAUDE.md`.
- Use cases (BA): `docs/use-cases/guest_first_web_app_use_cases.md`. Architecture review (binding): `docs/architecture/guest_first_web_app_review.md`. Next document: `docs/qa/guest_first_web_app_test_cases.md` (QA).

### 1.16 Architecture decisions

The architect review `docs/architecture/guest_first_web_app_review.md` (verdict FAIL -> PASS after amendments) is the binding resolution of PRD/UC contradictions and open questions OQ-1..OQ-63 of the review; where it conflicts with other PRD text, the review wins. Stack, layering and decisions D-1..D-8, D-10..D-12 stand; D-9 is changed. Summary of overrides and additions:

- **FR-36 (override):** an upload never creates a `cards` row; `upload_claims(user_id, content_id)` is the access control; `POST /api/cards` creates the card; dedupe key is the sha256 of raw bytes; response carries `dedupe none|ready|in_flight`.
- **FR-38 (override):** retry budget with pre-call `ai_calls` commit: 1 automatic retry per run, 2 manual retries per image, hard cap 6 calls, then `409 analysis_unavailable`; "<= 1.05 calls/image" is an aggregate metric.
- **FR-44 / AC-24 (override):** no pending state; unsafe images are `rejected` and share returns `422 share_not_allowed`; clean images become `public`. Unshare and delete endpoints added (FR-58).
- **FR-52 (override):** guest "Bài của tôi" is an empty state with camera CTA; saved cards appear only in "Đã lưu"; the "Cần ôn lại" badge counts cards.
- **Edge #1 (override):** a revoked/expired session becomes a new guest; guests get a "Đăng nhập" link. **Edge #16 (override):** account deletion removes all the user's cards and GCs orphan content and images.
- **FR-10 / FR-13:** exempt list now includes heartbeat and `GET /api/me`; grace rule (`GATE_GRACE_SECONDS=600`).
- **D-9:** login 100 failures/IP/15 min, registration 30/IP/hour, nickname limit unchanged.
- **FR-29 / API:** settings only via `PUT /api/me/settings`; `PATCH /api/me` = avatar and CEFR (A1/A2/B1).
- **FR-40:** audio served from `frontend/audio` at `/audio/<file>`; `GET /api/audio/{id}` removed.
- **New rules:** scoring (FR-55), SM-2 (FR-56), XP/streak/level (FR-57), pagination (FR-59), reflex progress (FR-61), maintenance (FR-62), migrations and seed (FR-63), client IP (FR-64), processing lease (FR-65), FK/cascade rules (FR-66), CSRF/Origin details (FR-30).
- **Schema (1.9) and API (1.8)** are replaced by the review's tables. Slices needing security or architect pre-review are listed in the review file and must be honoured by the planner.
- **OQ status:** OQ-1, OQ-2, OQ-5 resolved; OQ-3 (legal) and OQ-4 (AI budget) remain with the PO (see 1.12).
