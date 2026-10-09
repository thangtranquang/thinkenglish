# Test Cases: ReflexEnglish Web App with Guest-First Onboarding

> Based on [PRD](../PRD.md) and [Use Cases](../use-cases/guest_first_web_app_use_cases.md). Binding decisions: [architecture review + Addendum](../architecture/guest_first_web_app_review.md) (the review wins over the PRD where they differ).
>
> Created 2026-10-09. Specification only: no test code is written here; the `test-writer` agent implements these cases (TDD) from this document.

---

## 0. Conventions

### 0.1 ID scheme (stable)

- `TC-<n>.<m>`: `n` = the use-case number (UC-n), `m` = sequence inside that use case. TC IDs never get renumbered; new cases are appended with the next `m`.
- The **Flow** column names the exact use-case scenario covered: `UC-n` primary, `UC-n-Am` alternative, `UC-n-Em` error, `UC-n-Xm` edge case. A TC may cover several flows (comma separated). Every flow ID in the use-case file appears in at least one Flow cell (see section 55 coverage matrix).
- **Type**: `unit` (pure logic or single module, no HTTP), `API` (backend integration through httpx `TestClient`, real SQLite temp DB), `e2e` (Playwright Python, real uvicorn on a free port, MockProvider), `manual` (cannot be automated reliably, executed per release).
- **Priority**: `P0` = release blocker (security, gating, data integrity, AI-once, core happy path); `P1` = must pass before merge, lower blast radius; `P2` = edge or polish, may be deferred one iteration.
- **Module** column = the pytest module under `backend/tests/unit/` (type unit) or `backend/tests/api/` (type API), or the Playwright spec under `e2e/` (type e2e). Folder prefix is implied by Type. See section 51.
- **Covers** = FR / AC / NFR / OQ references.
- Cells never contain a pipe character, so rows can be counted mechanically.

### 0.2 Shorthand used in Pre / Steps

| Term | Meaning |
|---|---|
| default env | Fresh temp SQLite DB (migrated + production seed), temp `DATA_DIR`, `FakeClock` at 2026-03-02T03:00:00Z, `MockProvider`, `APP_ORIGIN=http://localhost:8000`, defaults of the use-case file (`GUEST_FREE_SESSIONS=1`, idle 30 min, grace 600 s, `TRUSTED_PROXY_HOPS=0`, 5 MB, 25 MP) |
| `guest` | fixture: TestClient after `POST /api/session/bootstrap`; cookie jar holds `re_device`, `re_csrf`; helper methods add `X-CSRF-Token` and `Origin` automatically |
| `raw` | the same client but helper does NOT add CSRF/Origin (used to test CSRF failures) |
| `reg` | fixture: registered user (nickname `Minh_An`, age >= 16) with `re_session`; helper adds CSRF/Origin |
| `gated` | fixture: guest with one write session, clock advanced 31 min, bootstrap returned `gate=second_visit` (`gate_required_at` set) |
| `clock` | `FakeClock` (`advance(seconds)`, `set(datetime)`) injected into the app |
| `provider` | `MockProvider` (call counter, delay, scripted failures) injected into the app |
| csrf headers | `X-CSRF-Token` equal to the `re_csrf` cookie plus `Origin: http://localhost:8000` |
| DB | direct read-only `sqlite3` connection to the temp DB used for assertions |
| ICT | `Asia/Ho_Chi_Minh` (UTC+7) |

### 0.3 Global invariants asserted in every API test (via the shared `assert_clean_response` helper)

- No response body, header or captured log line contains: a raw cookie token, any `token_hash`, `password_hash`, `scrypt` params, the password just submitted, or any `guardian_email` (FR-5, FR-32, NFR-S2, NFR-P2).
- Error bodies follow `{"error": code, ...}`; no stack trace or SQL text (UC-39-X1).
- User-specific JSON under `/api/` carries `Cache-Control: no-store`.

---

## 1. UC-1 First visit as a brand-new guest

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-1.1 | UC-1 | Bootstrap creates a guest | API | P0 | test_bootstrap | default env, no cookies | `POST /api/session/bootstrap` (no body, no CSRF) | 200 `{user{kind guest, nickname null, cefr A1}, is_guest true, gate null, csrf_token, config}`; DB: 1 users(kind guest), 1 device_tokens (only 64-hex sha256 stored), 1 usage_sessions(had_write 0); Set-Cookie `re_device` HttpOnly SameSite=Lax Path=/ Max-Age about 400 d and `re_csrf` non-HttpOnly SameSite=Lax; `Cache-Control: no-store` | FR-1 FR-3 FR-5 FR-7 AC-1 OQ-2 |
| TC-1.2 | UC-1 | Home paints for a new visitor with no wall | e2e | P0 | test_guest_home | real server, new browser context | open `/` | Skeleton at most 2 s then Home: greeting "Bạn khách", streak/XP, "Luyện tiếp", camera button, banner "Đăng ký để lưu tiến trình", link "Đã có tài khoản? Đăng nhập"; no welcome screen, no register wall; `re_device` cookie present and HttpOnly | AC-1 NFR-F1 FR-9 |
| TC-1.3 | UC-1 | Seeded cards visible with zero AI calls | API | P1 | test_bootstrap | guest | `GET /api/cards?scope=explore` | seeded system cards listed; `provider.call_count == 0` | FR-45 |
| TC-1.4 | UC-1-A1 | Cookie flags on localhost vs HTTPS host | API | P0 | test_bootstrap | two app instances: `APP_ORIGIN=http://localhost:8000` and `https://app.example.vn` | bootstrap on each | localhost: no `Secure`, csrf cookie `re_csrf`; https: `Secure` on `re_device`, csrf cookie named `__Host-re_csrf` (Path=/, no Domain) | FR-5 OQ-28 NFR-S1 |
| TC-1.5 | UC-1-A2 | GUEST_FREE_SESSIONS=0 gates immediately | API | P1 | test_gate | app with `GUEST_FREE_SESSIONS=0` | bootstrap new visitor, then `GET /api/cards` | bootstrap `gate={reason second_visit, mandatory true}`; `GET /api/cards` 403 second_visit | FR-7 AC-34 OQ-2 |
| TC-1.6 | UC-1-A3 | First write sets had_write | API | P1 | test_bootstrap | guest | `POST /api/attempts` (valid label attempt) | 201; `usage_sessions.had_write == 1` | FR-12 |
| TC-1.7 | UC-1-E1 | Bootstrap 5xx shows retry state | e2e | P1 | test_network_offline | route intercept makes `/api/session/bootstrap` fail once | open `/`, then restore and click retry | Vietnamese retry text "Không kết nối được, thử lại", no Home content, second attempt reaches Home | NFR-F4 PRD#14 |
| TC-1.8 | UC-1-E1 | Cookie lost after commit leaves a purgeable orphan | API | P2 | test_bootstrap | default env | bootstrap, discard cookies, bootstrap again; advance clock 8 d; run maintenance | 2 guest rows after second bootstrap; after maintenance the no-write orphan rows are purged | OQ-20 FR-6 |
| TC-1.9 | UC-1-E2 | Cookies blocked notice | e2e | P2 | test_guest_home | browser context blocking cookies (route strips Set-Cookie) | open `/` | Vietnamese notice that progress cannot be saved without cookies; non-writing screens still render (assumed behaviour) | PRD#14 |
| TC-1.10 | UC-1-E3 | Foreign Origin on bootstrap rejected | API | P0 | test_csrf | no cookies | `POST /api/session/bootstrap` with `Origin: https://evil.example` | 403 `csrf_failed`; users table unchanged | FR-30 OQ-28 AC-38 |
| TC-1.11 | UC-1-E3 | Bootstrap accepted without Origin and Referer | API | P1 | test_csrf | no cookies | `POST /api/session/bootstrap` with neither header | 200, guest created | OQ-28 AC-38 |
| TC-1.12 | UC-1-X1 | Forged re_device is ignored | API | P0 | test_bootstrap | cookie `re_device=garbage` and a 64-char random value | bootstrap | 200, NEW guest, `Set-Cookie re_device` overwrites the forged one; no 4xx | FR-1 |
| TC-1.13 | UC-1-X2 | re_device hashing to a registered user never honoured | API | P1 | test_bootstrap | DB row inserted: device_tokens hash pointing to a registered user | send that token | treated as invalid: new guest, registered user untouched | FR-19 |
| TC-1.14 | UC-1-X3 | Two tabs without cookies | e2e | P2 | test_guest_home | one context, two pages opened concurrently | open `/` in both, reload one | each tab sent exactly ONE bootstrap (request count); at most two guests exist; after reload both tabs show the same identity | OQ-20 |
| TC-1.15 | UC-1-X4 | Home paint latency with 100+ seeded cards | e2e | P2 | test_perf_ui | test-only 100-card fixture loaded | open `/`, measure time to Home | <= 2 s | NFR-F1 |
| TC-1.16 | UC-1-X5 | Bootstrap body hygiene | API | P0 | test_security_hygiene | default env | bootstrap; scan body, headers, logs | no `token`, `token_hash`, `password_hash`, `guardian_email` keys or values | FR-5 FR-32 NFR-S2 |
| TC-1.17 | UC-1 | Token randomness and hashing at rest | unit | P0 | test_security_tokens | none | generate 1000 device tokens; hash with the project helper | each token is 256-bit (43+ url-safe chars), unique; stored value equals sha256 hex of the token; token itself never persisted | FR-5 NFR-S1 |

## 2. UC-2 Returning guest within the free sessions

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-2.1 | UC-2 | Same guest id and progress after reload | API | P0 | test_bootstrap | guest completed Level 1 at 80 (attempts via API) | clock +1 day, bootstrap with same cookie | same `user.id`; `last_seen_at` updated; `re_device` re-issued; `GET /api/cards/{id}` shows Level 2 unlocked; no duplicate rows | FR-2 AC-2 |
| TC-2.2 | UC-2 | Level 2 still unlocked after page reload | e2e | P0 | test_practice_reflex | guest with Level 1 = 80 | reload page | Level 2 tab unlocked, Library shows saved cards and "Cần ôn lại" badge | AC-2 |
| TC-2.3 | UC-2-A1 | Second tab shares identity and usage session | API | P1 | test_usage_sessions | guest | second TestClient with copied cookies bootstraps within idle window | same user id; usage_sessions count 1 | FR-12 |
| TC-2.4 | UC-2-A2 | Guest save and hide-timer persist under guest id | API | P1 | test_bootstrap | guest | `POST /api/cards/{seed}/save`; `PUT /api/me/settings {hide_timer true}`; re-bootstrap | `card_saves.user_id` and `user_settings` rows belong to the guest; values survive | FR-3 FR-50 |
| TC-2.5 | UC-2-E1 | Cookie valid but guest row purged | API | P1 | test_maintenance | guest older than 180 d, maintenance ran | bootstrap with old cookie | new guest, empty progress, cookie replaced | FR-6 UC-34 |
| TC-2.6 | UC-2-X1 | Return after 399 days (past purge) | API | P2 | test_maintenance | clock +399 d, maintenance run at +181 d | bootstrap | new guest silently replaces cookie, no error | FR-6 |
| TC-2.7 | UC-2-X2 | Clock regression never lowers last_seen_at | unit | P2 | test_usage_gate_logic | stored last_seen = T | touch with now = T minus 1 h | stored value stays T; session math uses server time only | assumed |

## 3. UC-3 Usage-session counting

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-3.1 | UC-3 | New session after idle, write flag, prior_sessions | API | P0 | test_usage_sessions | guest with one write session | clock +31 min, bootstrap; one attempt | 2 usage_sessions rows; new row `had_write` 0 then 1 after the attempt; `prior_sessions` derived, no stored column | FR-12 OQ-62 |
| TC-3.2 | UC-3-A1 | Loads 10 minutes apart are one session | API | P0 | test_usage_sessions | guest | bootstrap, clock +10 min, bootstrap | exactly 1 usage_sessions row; `last_activity_at` updated | AC-7 |
| TC-3.3 | UC-3-A2 | View-only first visit does not count | API | P0 | test_usage_sessions | guest, GET calls only | clock +31 min, bootstrap (visit 2); do a write; clock +31 min, bootstrap (visit 3) | visit 2: gate null (prior=0); visit 3: gate second_visit | AC-6 FR-12a |
| TC-3.4 | UC-3-A3 | GUEST_FREE_SESSIONS=3 | API | P1 | test_usage_sessions | app with FREE=3 | three write sessions separated by 31 min; fourth bootstrap | gate absent at sessions 2 and 3; present at start of session 4 | FR-8 |
| TC-3.5 | UC-3-A4 | Hidden tab sends no heartbeat; resume after 30 min starts a session | e2e | P2 | test_gates | page with fake timers and clock API | hide tab (visibilitychange), wait heartbeat period | no heartbeat request while hidden; after clock +31 min and resume the next call begins a new session | FR-12c |
| TC-3.6 | UC-3-E1 | Heartbeat while gated returns gate not 403 | API | P0 | test_gate | `gated` | `POST /api/session/heartbeat` with csrf | 200 `{gate{reason second_visit, mandatory true}}` | OQ-3 AC-32 |
| TC-3.7 | UC-3-E2 | Heartbeat without CSRF | API | P0 | test_csrf | guest | `raw.post(heartbeat)` | 403 `csrf_failed`; `last_activity_at` unchanged | FR-30 |
| TC-3.8 | UC-3-X1 | Idle boundary 30:00 vs 30:01 | API | P0 | test_usage_sessions | guest with activity at T | call at T+1800 s then (fresh user) at T+1801 s | at exactly 1800 s same session (1 row); at 1801 s a second row | AC-33 OQ-4 |
| TC-3.9 | UC-3-X1 | Idle rule is strictly greater-than (pure) | unit | P0 | test_usage_gate_logic | none | `is_new_session(last, now, idle=30)` for deltas 1799 s, 1800 s, 1801 s | False, False, True | AC-33 |
| TC-3.10 | UC-3-X9 | Touch throttled to once per 60 s | API | P1 | test_usage_sessions | guest | two calls 59 s apart, one at 61 s; count UPDATEs via sqlite trace or `last_activity_at` | second call does not write; call at 61 s does | FR-12c |
| TC-3.11 | UC-3-X10 | Gate cleared when threshold no longer met | API | P0 | test_gate | `gated`, then setting raised to `GUEST_FREE_SESSIONS=3` (restart app on same DB) | clock +31 min, bootstrap | `gate_required_at` NULL, `gate null`; non-exempt calls 200 | AC-34 OQ-6 |
| TC-3.12 | UC-3-X2 | Seconds-long no-write visit is not counted | API | P1 | test_usage_sessions | guest with no writes | bootstrap twice (+31 min) then check `prior_sessions` | prior 0, no gate | FR-12a |
| TC-3.13 | UC-3-X3 | Two tabs writing share one session | API | P1 | test_usage_sessions | two clients, same guest | both post attempts | 1 session, `had_write` 1 | FR-12 |
| TC-3.14 | UC-3-X4 | Bootstrap is atomic (no half-created session) | API | P2 | test_bootstrap | fault injection making the usage_sessions INSERT raise once | bootstrap; retry | first call 5xx with no user/device rows left; retry creates exactly 1 user and 1 session | assumed |
| TC-3.15 | UC-3-X5 | Client clock skew ignored | API | P1 | test_usage_sessions | guest | send `Date: Mon, 01 Jan 2035 ...` and a future `X-Client-Time` header; verify DB times | all timestamps equal server clock | FR-12 |
| TC-3.16 | UC-3-X6 | Auto mode without mic sets no had_write | e2e | P1 | test_auto_mode | guest, mic permission denied | run auto mode for 2 rounds | no `POST /api/attempts`; `had_write` stays 0 | FR-51 |
| TC-3.17 | UC-3-X7 | Hide-timer change and profile view are not writes | API | P1 | test_usage_sessions | guest | `PUT /api/me/settings`, `GET /api/me` | `had_write` stays 0 | FR-12 |
| TC-3.18 | UC-3-X8 | Only grace writes possible in a gated session | API | P1 | test_gate_grace | `gated` | attempt (in grace) vs `POST /api/cards/{id}/save` | attempt 201 (sets had_write); save 403 | OQ-3 |
| TC-3.19 | UC-3 | prior_sessions table | unit | P0 | test_usage_gate_logic | none | table DT-10 rows | matches table | FR-12 OQ-62 |

## 4. UC-4 Second-visit mandatory gate

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-4.1 | UC-4 | Bootstrap on second visit returns gate and sets flag | API | P0 | test_gate | guest with 1 write session | clock +31 min, bootstrap | `gate={second_visit, mandatory true}`; `users.gate_required_at == now` | FR-7 FR-8 AC-5 |
| TC-4.2 | UC-4 | Mandatory register screen has no escape | e2e | P0 | test_gates | guest with one write visit; clock +31 min | reload | Register shown with copy "Em đã luyện tập rồi - hãy tạo tài khoản để giữ tiến trình nhé."; no Back, no close, link "Đã có tài khoản? Đăng nhập" only; Escape and browser Back keep Register | AC-5 NFR-X3 |
| TC-4.3 | UC-4 | Every non-exempt endpoint blocked for gated guest | API | P0 | test_gate | `gated` | parametrized over `GET /api/cards`, `GET /api/cards/{id}`, `GET /api/topics`, `PUT /api/me/settings`, `POST /api/cards/{id}/save`, `POST /api/reflex/sessions`, `GET /api/uploads/x` | each 403 `{"error":"registration_required","reason":"second_visit"}` | FR-10 |
| TC-4.4 | UC-4 | Exempt endpoints work while gated | API | P0 | test_gate | `gated` | `/api/health`, `/api/config`, bootstrap, heartbeat, `GET /api/me`, register (invalid body -> 422 not 403), login (bad creds -> 401), logout (204) | none returns 403 registration_required | OQ-3 OQ-9 |
| TC-4.5 | UC-4 | Registering clears the gate | API | P0 | test_register | `gated` | register valid | 201; `gate_required_at` NULL; `GET /api/cards` 200 afterwards | FR-11 |
| TC-4.6 | UC-4 | Login clears the gate (guest discarded) | API | P0 | test_login_discard | `gated` with progress and an existing account | login with `discard_guest true` | 200; guest row gone; `GET /api/cards` 200 as registered | FR-11 FR-28 |
| TC-4.7 | UC-4-A1 | FREE=0 first screen is Register | e2e | P1 | test_gates | app with FREE=0 | open `/` | Register without Back is first screen; Home never rendered | FR-7 |
| TC-4.8 | UC-4-A2 | Gate survives reload, new tab, cleared storage | e2e | P0 | test_gates | gated guest | reload; open second tab; clear local/sessionStorage; reload | Register mandatory each time | FR-11 |
| TC-4.9 | UC-4-A3 | Return within 30 min does not gate | API | P1 | test_gate | guest with write | clock +29 min, bootstrap | gate null | FR-8 |
| TC-4.10 | UC-4-E1 | Direct API bypass attempts report second_visit | API | P0 | test_gate | `gated` | parametrized: `POST /api/uploads`, `POST /api/cards`, `POST /api/cards/{id}/share`, `DELETE /api/cards/{id}/share`, `DELETE /api/cards/{id}`, `PATCH /api/me`, `DELETE /api/me`, `POST /api/auth/logout-all` | all 403 reason `second_visit`, never `camera` or `account` | OQ-5 AC-35 |
| TC-4.11 | UC-4-E2 | Back/Escape does not reveal app | e2e | P1 | test_gates | gated guest on Register | press Escape; `history.back()`; deep link `/#explore` | router re-checks gate and re-renders Register | NFR-X3 |
| TC-4.12 | UC-4-E3 | Cleared cookie bypass is accepted and documented | API | P2 | test_gate | `gated` | drop cookies, bootstrap | new guest with gate null (documented accepted risk); guest cannot upload (403 camera) | PRD#1 |
| TC-4.13 | UC-4-X1 | GET /api/me for gated guest is minimal | API | P1 | test_gate | `gated` | `GET /api/me` | 200 guest summary, no progress detail beyond needed, no guardian email | FR-60 |
| TC-4.14 | UC-4-X2 | Static audio stays reachable | API | P2 | test_audio_static | `gated` | `GET /audio/<known file>` | 200 audio/mpeg | NFR-F5 |
| TC-4.15 | UC-4-X3 | Raised setting keeps flag within session, clears at next | API | P1 | test_gate | `gated`, setting raised to 3 | call within same session; then +31 min bootstrap | within session still 403; next session gate cleared | OQ-6 |
| TC-4.16 | UC-4-X4 | Gate triggers even when the new session has no write | API | P1 | test_gate | guest with prior write, new session no write | bootstrap | gate present and mandatory | FR-8 |
| TC-4.17 | UC-4-X5 | Logout by a gated guest is idempotent 204 | API | P1 | test_logout | `gated` | `POST /api/auth/logout` | 204; `re_session` cleared only; `re_device` untouched; gate remains | OQ-7 |
| TC-4.18 | UC-4-X6 | Gated PATCH/DELETE me/logout-all reason precedence | API | P0 | test_gate | gated guest and non-gated guest | `PATCH /api/me`, `DELETE /api/me`, `logout-all` for each | gated: reason second_visit; non-gated: reason account | OQ-5 OQ-8 AC-35 |
| TC-4.19 | UC-4 | Gate state machine truth table | unit | P0 | test_usage_gate_logic | none | table DT-10 gate rows (kind, prior, FREE, flag) | matches table | FR-7 FR-8 |

## 5. UC-5 Gate mid-practice (grace)

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-5.1 | UC-5 | In-flight attempt accepted after gate flips | API | P0 | test_gate_grace | guest with 1 write session and an open Reflex session started pre-gate; clock +31 min | `POST /api/attempts` for that session | 201 AttemptOut; `gate_required_at` set; next heartbeat returns gate | FR-13 AC-32 |
| TC-5.2 | UC-5 | Round finishes then mandatory Register | e2e | P0 | test_gates | guest mid-round, clock +31 min via test hook | answer the round; finish summary | attempt saved; summary shown; Register mandatory before next navigation; after register lands on Home (not the dead round) | FR-13 D-4 |
| TC-5.3 | UC-5-A1 | Remaining rounds of a pre-gate session within 600 s | API | P0 | test_gate_grace | pre-gate Reflex session with 5 rounds; gate set at T | post attempts at T+100 s for rounds 2..5, then complete at T+300 s | all 201; complete 200 | OQ-9 |
| TC-5.4 | UC-5-A1 | After 600 s every attempt is 403 | API | P0 | test_gate_grace | as above | attempt at T+601 s | 403 second_visit; no row written | OQ-9 AC-32 |
| TC-5.5 | UC-5-A1 | Session cannot start after the gate | API | P1 | test_gate_grace | `gated` | `POST /api/reflex/sessions {level 1}` | 403 second_visit | OQ-9 |
| TC-5.6 | UC-5-A2 | Auto mode finishes the round then gate | e2e | P1 | test_auto_mode | gated mid auto-run | gate flips during run | client stops after current round, saves it, calls complete, shows gate | FR-51 UC-5-A2 |
| TC-5.7 | UC-5-A3 | Recording finished after grace expired | e2e | P1 | test_gates | clock beyond grace | submit recorded answer | 403 handled: gate shown once; no replay after registration | OQ-46 |
| TC-5.8 | UC-5-E1 | Grace boundary 600 s allowed, 601 s denied | API | P0 | test_gate_grace | `gated` at T | attempt at exactly T+600 s; separate case at T+601 s | 201 and 403 respectively | AC-32 |
| TC-5.9 | UC-5-E1 | Attempt for a new item (not pre-existing) denied | API | P0 | test_gate_grace | `gated`, item with no progress and no session pre-gate | `POST /api/attempts` | 403 second_visit; client shows gate exactly once (e2e assertion in TC-5.2) | OQ-3 |
| TC-5.10 | UC-5-E3 | Complete on foreign session is 404 even in grace | API | P0 | test_gate_grace | gated guest A; session owned by user B | `POST /api/reflex/sessions/{B}/complete` | 404 | OQ-9 |
| TC-5.11 | UC-5-E2 | Network down at the grace write | e2e | P2 | test_network_offline | gated mid-round, route abort on attempts | answer | message "Chưa lưu được kết quả" then gate; no crash | PRD#14 |
| TC-5.12 | UC-5-X1 | Review/Processing screens unreachable for guests | API | P2 | test_gate | guest | `GET /api/uploads/{any}`, `POST /api/uploads` | 403 camera (so gate flip there is not applicable) | UC-6 |
| TC-5.13 | UC-5-X2 | Resumed tab non-attempt call gets 403, UI defers gate | e2e | P1 | test_gates | guest mid-round, clock +31 min | `GET /api/cards` happens first | 403 second_visit; UI keeps the round, shows gate only after the round | FR-13 |
| TC-5.14 | UC-5-X3 | Two tabs: A mid-round defers, B shows gate | e2e | P2 | test_gates | one context, two pages | flip gate | A finishes round then gate; B shows gate immediately | FR-13 |
| TC-5.15 | UC-5 | Grace window is evaluated from server time | unit | P1 | test_usage_gate_logic | none | `grace_allows(gate_at, now, started_at)` boundary table (599, 600, 601 s; started_at after gate) | True, True, False; session started after gate False | AC-32 |

## 6. UC-6 Camera / Add-photo gate

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-6.1 | UC-6 | Camera tap opens Register(camera); Back restores state | e2e | P0 | test_gates | guest on Practice level 1 with a selected card and scroll | tap camera; tap Back | Register with Back shown (no API call besides none); on Back the previous screen with scroll/level/card intact; no account created (DB users count unchanged) | AC-3 FR-4 FR-9 |
| TC-6.2 | UC-6 | Gate repeats on every camera tap | e2e | P1 | test_gates | guest | tap camera, Back, tap camera | Register appears each time | D-3 |
| TC-6.3 | UC-6 | Register from camera gate resumes Add-photo | e2e | P0 | test_guest_to_registered | guest with an attempt | camera -> register (age 17) | after 201 upload screen opens with previous progress intact | AC-30 Addendum#4 |
| TC-6.4 | UC-6-A1 | Library empty-state CTA triggers same gate | e2e | P1 | test_library_explore | guest | Library > "Bài của tôi" > "Chụp ảnh" | Register(camera) with Back | AC-46 |
| TC-6.5 | UC-6-A2 | Login from the gate lands on Home, no resume | e2e | P2 | test_login | existing account; guest on camera gate | tap login link, log in | Home as registered account; Add-photo not auto-opened | Addendum#4 |
| TC-6.6 | UC-6-E1 | Guest cannot call camera-level endpoints | API | P0 | test_camera_gate | `guest` | parametrized: `POST /api/uploads` (valid JPEG), `POST /api/cards`, `POST /api/cards/{id}/share`, `DELETE /api/cards/{id}/share`, `DELETE /api/cards/{id}`, `GET /api/uploads/{id}` | 403 `registration_required` reason `camera`; no file/rows stored | AC-4 AC-35 |
| TC-6.7 | UC-6-E1 | Guest account-level endpoints give reason account | API | P0 | test_camera_gate | `guest` | `PATCH /api/me`, `DELETE /api/me`, `POST /api/auth/logout-all` | 403 reason `account` | AC-35 OQ-8 |
| TC-6.8 | UC-6-E2 | second_visit wins when both apply | API | P0 | test_gate | `gated` | `POST /api/uploads` | reason `second_visit` | OQ-5 |
| TC-6.9 | UC-6-X1 | Browser Back from Register(camera) | e2e | P2 | test_gates | guest | tap camera; `history.back()` | same as Back button | FR-9 |
| TC-6.10 | UC-6-X2 | Deep link to add-photo | e2e | P1 | test_gates | guest | navigate to `/#add` | redirected to camera gate | FR-4 |
| TC-6.11 | UC-6-X3 | Expired registered session sees camera gate | e2e | P1 | test_gates | registered user whose session expired (clock) | open app, tap camera | camera gate (not an error) and "Đã có tài khoản? Đăng nhập" visible | OQ-19 UC-44 |

## 7. UC-7 Registration with guest conversion

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-7.1 | UC-7 | Conversion keeps id and all progress | API | P0 | test_register | `guest` with 3 attempts, 1 save, review_state, card_progress, reflex_progress, settings | `POST /api/auth/register {nickname Minh_An, password, avatar_key, birth_year 2000, cefr_level A2}` | 201 `{user}`; `users.id` unchanged; kind registered; nickname/nickname_ci/params/registered_at set; gate_required_at NULL; one new sessions row; device_tokens row deleted; Set-Cookie `re_session` HttpOnly SameSite=Lax Max-Age 90 d and `re_device` expiring; every attempts/review_state/card_saves/card_progress/reflex_progress/usage_sessions row still owned by the same id; body has no hash/guardian email | FR-14 FR-17 FR-19 FR-21 AC-8 |
| TC-7.2 | UC-7 | Registration form happy path in browser | e2e | P0 | test_register_form | guest | fill nickname, password (toggle show/hide), avatar, birth year, CEFR; submit | 201; guardian fields hidden (age >= 16); privacy notice link present; password field cleared after submit | FR-14 FR-16 NFR-P1 |
| TC-7.3 | UC-7, UC-7-E5 | Conversion is one transaction | API | P0 | test_register | fault injection after the users UPDATE | register | rollback: user still guest, device token still present, no session row, cookie jar unchanged; retry succeeds | UC-7-E5 NFR-A2 |
| TC-7.4 | UC-7 | Password stored only as per-user scrypt hash | unit | P0 | test_security_tokens | none | hash same password twice; verify right/wrong; inspect params | salts (16 bytes) differ so hashes differ; N >= 16384, r 8, p 1 stored; verify uses `hmac.compare_digest`; wrong password False | FR-21 NFR-S7 |
| TC-7.5 | UC-7-A1 | Under-16 registration stores consent | API | P0 | test_register | `guest` | register with birth_year = current ICT year - 12, `guardian_email`, `guardian_consent true` | 201; `guardian_email` and `guardian_consent_at` stored; no response (register, `/api/me`, bootstrap, login) contains the email | FR-16 AC-12 NFR-P2 |
| TC-7.6 | UC-7-A2 | Age exactly 16 rejects guardian fields | API | P1 | test_register | current ICT year 2026 | register birth_year 2010 with `guardian_email` | 422 on guardian field; without it 201 | FR-16 |
| TC-7.7 | UC-7-A3 | Registering from second-visit gate unlocks app | e2e | P0 | test_gates | gated guest, Register mandatory | register | Home shown; `GET /api/cards` works immediately | FR-11 |
| TC-7.8 | UC-7-A4 | Registering from camera gate opens upload | e2e | P0 | test_guest_to_registered | guest with progress on camera gate | register | upload screen shown, progress intact | AC-30 |
| TC-7.9 | UC-7-A5 | Register from profile returns to Profile | e2e | P1 | test_register_form | see TC-45.1 | see TC-45.1 | see TC-45.1 | FR-54 |
| TC-7.10 | UC-7-E1 | Validation failure leaves guest untouched | API | P0 | test_register | `guest` | register with invalid nickname | 422 with `fields[]`; users row unchanged; no `re_session`; no sessions row | AC-11 NFR-X3 |
| TC-7.11 | UC-7-E2 | Nickname taken | API | P0 | test_register | account `Minh_An` exists | guest registers `Minh_An` | 409 `nickname_taken`; guest keeps progress and cookies | AC-13 |
| TC-7.12 | UC-7-E2 | Nickname taken UI focus and aria-live | e2e | P1 | test_register_form | account exists | submit duplicate | nickname field highlighted and focused; message in aria-live region | NFR-X3 |
| TC-7.13 | UC-7-E3 | Rate limited register returns 429 | API | P1 | test_register_ratelimit | limit set to 2 | 3 calls | third 429 with Retry-After; see TC-10.3 for the 30/hour numbers | FR-18 |
| TC-7.14 | UC-7-E4 | Register without CSRF | API | P0 | test_csrf | `raw` guest | register without header | 403 `csrf_failed`; no state change | AC-17 |
| TC-7.15 | UC-7-E6 | already_registered only with a valid session | API | P0 | test_register | registered `reg` | register again with `re_session`; then without any cookie using the same nickname | 409 `already_registered`; second case 409 `nickname_taken` | OQ-14 |
| TC-7.16 | UC-7-X1 | usage_sessions retained after gated registration | API | P2 | test_register | `gated` | register | usage_sessions rows kept (count unchanged) | FR-17 |
| TC-7.17 | UC-7-X2 | Password never echoed or logged | API | P0 | test_security_hygiene | log capture enabled | register with good and with bad data | password string absent from bodies, headers and logs; DOM check in TC-8.9 | NFR-S7 FR-32 |
| TC-7.18 | UC-7-X3 | scrypt does not block the event loop | API | P1 | test_register_concurrency | uvicorn thread or ASGI test with async client | launch 10 registrations concurrently and poll `/api/health` | every health response within 200 ms while registrations run | NFR-F4 |
| TC-7.19 | UC-7-X4 | Unknown avatar_key | API | P1 | test_register_validation | `guest` | register avatar_key not in config | 422 field avatar_key | FR-14 |
| TC-7.20 | UC-7-X5 | cefr_level B2 rejected, A1/A2/B1 accepted | API | P1 | test_register_validation | `guest` | register with B2, then each valid level | 422 then 201 | OQ-24 |
| TC-7.21 | UC-7-X6 | Birth year uses ICT calendar year | API | P1 | test_register_validation | clock 2026-12-31T18:00:00Z (= 2027-01-01 ICT) | register birth_year 2017 (age 10) and 2018 | 2017 accepted (guardian required), 2018 422 | OQ-10 |
| TC-7.22 | UC-7 | Unique partial index on nickname_ci | API | P0 | test_db_migrations_seed | DB | insert two registered rows `A_b` and `a_B` directly | second INSERT raises IntegrityError; two guests with NULL nickname allowed | FR-20 UC-8 |

## 8. UC-8 Registration validation

Rows reference DT-8 (nickname), DT-9 (age/birth year). Every matrix row of the use case is one parametrized case in the unit module, and each category has an API test proving a 422 changes nothing.

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-8.1 | UC-8 (rows 1-8) | Nickname rules table | unit | P0 | test_nickname_validation | none | run DT-8 rows 1-14 through `validate_nickname` | each row yields the listed accept/reject and normalised value | FR-15 OQ-11 |
| TC-8.2 | UC-8 (rows 9-11) | Password rules table | unit | P0 | test_nickname_validation | none | 7/8/128/129 chars; equals nickname; common list | 7 no, 8 yes, 128 yes, 129 no; equal-to-nickname no; "12345678" and "password" no | FR-15 |
| TC-8.3 | UC-8 (rows 13-17) | Birth-year bounds | unit | P0 | test_age_rules | year 2026 ICT | DT-9 rows | current-10 ok (guardian needed), current-9 rejected with message "ReflexEnglish dành cho học sinh từ 10 tuổi", +1 future no, current-100 ok, current-101 no, "abc" no | FR-16 |
| TC-8.4 | UC-8 (rows 18-22) | Guardian rules | unit | P0 | test_age_rules | none | under-16 without email; email without consent; consent false; malformed emails; 254 vs 255 chars; age >= 16 with guardian fields | 422 on guardian_email / guardian_consent / email format; 254 ok, 255 no; guardian fields rejected at >= 16 | AC-11 FR-16 |
| TC-8.5 | UC-8 (row 12) | Avatar must be a preset | API | P1 | test_register_validation | `guest` | register avatar_key "hacker" | 422 | FR-14 |
| TC-8.6 | UC-8 (row 23) | Unknown fields rejected | API | P0 | test_register_validation | `guest` | add `role`, `kind`, `is_admin` one at a time | 422 each; user stays guest | NFR-S7 FR-31 |
| TC-8.7 | UC-8 (row 24) | Missing required field | API | P1 | test_register_validation | `guest` | omit each required field in turn | 422 naming the field | FR-14 |
| TC-8.8 | UC-8 | All failing fields reported together, nothing persisted | API | P0 | test_register_validation | `guest` | register with bad nickname + bad password + bad year | 422 `validation_error` with one entry per field `{field, code, message_vi}`; DB unchanged; password not in body | FR-31 |
| TC-8.9 | UC-8 | Browser shows errors accessibly | e2e | P1 | test_register_form | guest | submit invalid form | each failing field highlighted, messages in `aria-live`, typed values kept except password, focus on first invalid field | NFR-X3 |
| TC-8.10 | UC-8-A1 | Case-insensitive nickname conflict | API | P0 | test_register | `Minh_An` registered | guest registers `minh_an` | 409 `nickname_taken`; guest keeps progress | AC-13 |
| TC-8.11 | UC-8-A2 | Nickname free again after the owner deletes account | API | P1 | test_register | `Minh_An` registered then deleted | new guest registers `Minh_An` | 201 | FR-20 |
| TC-8.12 | UC-8-A3 | Client omits guardian fields after year change | e2e | P1 | test_register_form | guest | enter age 12 with guardian data, switch year to age 20, submit | request body contains no guardian fields; 201 | FR-16 |
| TC-8.13 | UC-8-E1 | Fullwidth folds to conflict, Cyrillic rejected | API | P1 | test_register | `Minh_An` registered | register `Ｍinh_An`; register nickname with Cyrillic "а" | first 409 `nickname_taken`; second 422 charset error | OQ-11 |
| TC-8.14 | UC-8-E2 | Guests have no nickname conflict | API | P2 | test_register | two guests | both register different nicknames; verify NULL nickname rows do not collide | both 201 | FR-20 |
| TC-8.15 | UC-8-E3 | No confirm-password field and no reset | e2e | P2 | test_register_form | guest | inspect form and routes | only one password field; no reset link | OQ-12 |
| TC-8.16 | UC-8-X1 | 422 body and logs exclude password | API | P0 | test_security_hygiene | log capture | submit invalid with password `Sup3rSecret!` | string absent from body and logs | FR-32 |
| TC-8.17 | UC-8-X2 | Guardian email never returned anywhere | API | P0 | test_security_hygiene | under-16 registered | call bootstrap, register, login, `GET /api/me`, cards, upload status | no `guardian_email` key or value in any body | FR-32 NFR-P2 AC-12 |
| TC-8.18 | UC-8-X3 | Whitespace and NBSP nickname | unit | P2 | test_nickname_validation | none | " abc ", "abc" with NBSP, tab | trimmed " abc " -> "abc"; NBSP/tab inside -> rejected | FR-15 |
| TC-8.19 | UC-8-X4 | Diacritics rejected with Vietnamese hint | API | P1 | test_register_validation | `guest` | nickname "Nguyễn" | 422 message_vi mentions letters, digits and `_ . -` without diacritics | OQ-11 |
| TC-8.20 | UC-8-X5 | guardian_consent must be strict boolean | API | P2 | test_register_validation | age 12 | `guardian_consent: "true"` | 422 | FR-16 |
| TC-8.21 | UC-8-X6 | Turning-16 uses year difference | unit | P1 | test_age_rules | clock 2026-01-15 ICT | birth_year 2010 (born Dec 2010) | age 16 -> no guardian required (documented behaviour) | OQ-10 OQ-63 |
| TC-8.22 | UC-8-X6 | Legal sign-off of the under-16 consent flow | manual | P0 | manual | PO and legal reviewer, staging | review consent text, year-difference age rule and guardian-email retention | written sign-off recorded; release-blocking for production under-16 sign-ups only (not for the build) | OQ-63 |

## 9. UC-9 Registration concurrency

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-9.1 | UC-9 | Double submit yields one conversion | API | P0 | test_register_concurrency | `guest` | two threads POST register simultaneously with the same cookies | exactly one 201 and one 409 `already_registered`; one sessions row for the user; password hash from the first request | AC-8 FR-17 |
| TC-9.2 | UC-9 | Submit button disabled after first click | e2e | P2 | test_register_form | guest | double click Submit | one request sent | FR-17 |
| TC-9.3 | UC-9-A1 | Two guests race for one nickname | API | P0 | test_register_concurrency | two guests with progress | two threads register `Nam_01` | one 201; other 409 `nickname_taken` and remains a guest with progress intact | FR-20 AC-13 |
| TC-9.4 | UC-9-A2 | Tab 1 continues as registered after tab 2 registers | API | P0 | test_register_concurrency | two clients sharing one cookie jar | client B registers; client A (stale header, same jar) posts an attempt | attempt 201 under the registered user id; CSRF header still valid (token stable) | OQ-13 |
| TC-9.5 | UC-9-A2 | csrf_failed safety net re-bootstraps once | e2e | P1 | test_gates | tab with deleted csrf cookie | trigger POST | client re-bootstraps once, retries once, no loop; no extra guest created | OQ-13 AC-38 |
| TC-9.6 | UC-9-A3 | Registered user's in-flight upload unaffected | API | P2 | test_upload_pipeline | registered user with job processing | second login in another client | job completes; claim attached to the same user id | FR-17 |
| TC-9.7 | UC-9-E1 | Retry after lost 201 | API | P1 | test_register_concurrency | register succeeded, cookies discarded, old `re_device` replayed | retry same payload | 409 `nickname_taken`; UI (TC-9.8) offers Login | OQ-14 |
| TC-9.8 | UC-9-E1 | UI offers Đăng nhập after nickname_taken | e2e | P2 | test_register_form | as above | submit | "Nickname đã được dùng" plus "Đăng nhập" button | OQ-14 |
| TC-9.9 | UC-9-E2 | Retry with valid re_session | API | P1 | test_register | `reg` | register again | 409 `already_registered` | OQ-14 |
| TC-9.10 | UC-9-E3 | Second tab after success navigates Home | e2e | P2 | test_register_form | two pages, one register | submit in page 2 | `already_registered` handled: bootstrap then Home | FR-17 |
| TC-9.11 | UC-9-X1 | Ten parallel registers | API | P0 | test_register_concurrency | `guest` | 10 threads | one 201, nine 409; users count unchanged except conversion; one sessions row | FR-17 |
| TC-9.12 | UC-9-X2 | Stale re_device-only attempt falls back to bootstrap | e2e | P2 | test_register_form | cookie jar split | send attempt with stale device cookie | client calls bootstrap, no error screen | FR-17 |
| TC-9.13 | UC-9-X3 | Crash between commit and token delete leaves no half state | API | P1 | test_register_concurrency | fault injection (kill after users UPDATE before device delete) | register | either fully converted or fully guest (assert via DB); never registered with live device token | NFR-A2 |

## 10. UC-10 Registration without guest cookie and rate limit

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-10.1 | UC-10 | Register with no valid guest cookie | API | P0 | test_register | client has `re_csrf` but `re_device` removed | register | 201 new registered user, empty progress, no device row deleted (none existed), `re_session` set | FR-18 |
| TC-10.2 | UC-10-A1 | Cleared cookies then register converts fresh guest | API | P1 | test_register | guest with progress; drop all cookies; bootstrap again | register | converts the NEW guest; old guest orphaned and untouched | FR-18 |
| TC-10.3 | UC-10-E1 | 31st registration in an hour returns 429 | API | P0 | test_register_ratelimit | same client IP | 30 requests (mix of 201, 422, 409), then the 31st | 31st 429 with integer `Retry-After >= 1` and Vietnamese message; `rate_events(bucket register_ip)` has 30 rows with sha256 `key_hash`, no raw IP | AC-36 OQ-15 |
| TC-10.4 | UC-10-E2 | What counts toward the limit | API | P0 | test_register_ratelimit | limit 3 | send one 201, one 422, one 409; one CSRF-failed; hit 429 twice | only the first three counted; CSRF 403 and 429 add no rows | AC-36 OQ-18 |
| TC-10.5 | UC-10-X1 | School NAT: 30 students pass | API | P1 | test_register_ratelimit | 30 guests behind one IP | each registers once | all 30 return 201; 31st 429 | OQ-15 |
| TC-10.6 | UC-10-X2 | Client IP resolution | unit | P0 | test_client_ip | none | DT-12 rows (hops 0 ignore XFF; hops 1 take last; hops 2 take second from right; leftmost never used; malformed XFF) | match table | AC-37 FR-64 OQ-16 |
| TC-10.7 | UC-10-X2 | Spoofed X-Forwarded-For cannot evade limit | API | P0 | test_register_ratelimit | hops 0, limit 2 | rotate XFF values | still limited after the same peer IP hits the limit | AC-37 |
| TC-10.8 | UC-10-X3 | CSRF-failed requests are not counted | API | P1 | test_register_ratelimit | limit 1 | 5 CSRF failures then one valid | valid request 201 | OQ-18 |
| TC-10.9 | UC-10-X4 | Window expiry and purge of old events | API | P1 | test_register_ratelimit | limit 30 filled at T | at T+3599 s 429 (Retry-After 1); at T+3601 s success; maintenance after 1 day | oldest event leaves window; rows older than 1 day purged, newer kept | FR-27 UC-34-X9 |

## 11. UC-11 Login on a new device

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-11.1 | UC-11 | Login with correct credentials | API | P0 | test_login | account `Minh_An` with progress; fresh empty `guest` | `POST /api/auth/login {nickname, password}` | 200 `{user}`; old browser token revoked; empty guest row + device token deleted; new sessions row; `re_session` set; `re_device` cleared; no hash/token in body | FR-22 FR-24 AC-10 |
| TC-11.2 | UC-11 | Login lands on Home with progress | e2e | P0 | test_login | account with streak, XP, due items | new context, Login | Home shows progress, streak, "Cần ôn lại" badge | AC-10 |
| TC-11.3 | UC-11-A1 | Nickname case-insensitive | API | P1 | test_login | account `Minh_An` | login as `MINH_AN` | 200 | FR-22 |
| TC-11.4 | UC-11-A2 | Old session cookie revoked on login | API | P0 | test_login | client holds session S1 | login again | S1 row `revoked_at` set; new S2 works | AC-10 |
| TC-11.5 | UC-11-A3 | Two accounts in sequence leak nothing | e2e | P1 | test_login | accounts A and B | A logs out, B logs in | no A nickname/progress visible; client state reset | NFR-P3 |
| TC-11.6 | UC-11-E1 | Wrong password | API | P0 | test_login | account exists | login with wrong password | 401 `invalid_credentials`; failure event recorded; guest untouched | FR-26 |
| TC-11.7 | UC-11-E2 | Unknown vs wrong password indistinguishable | API | P0 | test_login | account exists | login unknown nickname and known nickname with wrong pw | identical status 401, identical body bytes and identical headers except Date | AC-15 |
| TC-11.8 | UC-11-E3 | Login validation | API | P1 | test_login | none | missing password; extra field | 422 each; not counted as a failure | FR-31 |
| TC-11.9 | UC-11-E4 | Rate limited login | API | P1 | test_login_ratelimit | see TC-13.1 | see TC-13.1 | 429 | FR-27 |
| TC-11.10 | UC-11-E5 | CSRF failure on login | API | P0 | test_csrf | `raw` | login without CSRF | 403; no failure recorded | UC-18-E8 |
| TC-11.11 | UC-11-X1 | Timing equalisation | API | P1 | test_login | account exists; scrypt cost real | 30 samples each: unknown nickname vs wrong password | median difference below 30 ms (marked slow; skip in fast CI) | AC-15 |
| TC-11.12 | UC-11-X2 | Password spaces not trimmed | API | P2 | test_login | account password " pass word " | login with trimmed vs exact | trimmed 401, exact 200 | FR-22 |
| TC-11.13 | UC-11-X3 | Login response hygiene | API | P0 | test_security_hygiene | account under 16 | login | no hash, token, guardian email | FR-32 |
| TC-11.14 | UC-11-X4 | Login while logged in | API | P1 | test_login | `reg` A; account B | login A again; then login B on same jar | A: new token, old revoked, 200; B: A's session on this browser revoked, A's other devices unaffected | FR-24 |
| TC-11.15 | UC-11-X5 | Three devices, each own session | API | P1 | test_login | account | login from 3 clients; 4th login | 4 live sessions, none revoked by the others | FR-24 |
| TC-11.16 | UC-11-E2 | Unknown nickname burns a dummy scrypt | unit | P1 | test_security_tokens | none | `verify_login(None_user, pw)` with a spy on scrypt | scrypt called once with dummy hash; returns False | AC-15 |

## 12. UC-12 Login with guest discard

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-12.1 | UC-12 | Login with discard_guest deletes guest | API | P0 | test_login_discard | guest with attempts/saves/progress and a registered account | login with `discard_guest true` | 200; guest users row gone and all FK children gone; `re_device` cleared; `re_session` set | FR-28 AC-16 OQ-17 |
| TC-12.2 | UC-12 | Warning dialog flow | e2e | P0 | test_login | guest with progress | open Login | text "Tiến trình khách trên thiết bị này sẽ bị xóa..." with buttons "Đăng nhập và xóa tiến trình khách" and "Quay lại"; confirm logs in | AC-16 |
| TC-12.3 | UC-12-A1 | Guest without progress logs in silently | API | P1 | test_login_discard | view-only guest | login without `discard_guest` | 200; guest removed | FR-28 |
| TC-12.4 | UC-12-A2 | Cancel makes no request | e2e | P1 | test_login | guest with progress | click "Quay lại" | no POST sent; guest unchanged; previous screen (or Register for mandatory gate) | AC-16 |
| TC-12.5 | UC-12-A3 | Mandatory gate + login | e2e | P1 | test_gates | `gated` guest with progress | login with warning confirm | registered Home; gate gone | FR-11 |
| TC-12.6 | UC-12-E1 | Missing discard_guest with progress | API | P0 | test_login_discard | guest with progress | login without flag | 409 `guest_progress_exists`; nothing deleted; no session created | AC-16 |
| TC-12.7 | UC-12-E2 | Wrong credentials with discard keeps guest | API | P0 | test_login_discard | guest with progress | login wrong password with `discard_guest true` | 401; guest row and all its data intact; `re_device` still valid | PRD#11 |
| TC-12.8 | UC-12-E3 | Rate limited with discard keeps guest | API | P0 | test_login_discard | bucket full | login with discard | 429; guest intact | PRD#11 |
| TC-12.9 | UC-12-X1 | Tab 2 after login in tab 1 | e2e | P1 | test_login | two pages one context, guest | login in tab 1; act in tab 2 | tab 2 becomes registered identity, CSRF still valid; at most one re-bootstrap | OQ-13 |
| TC-12.10 | UC-12-X2 | What counts as guest progress | API | P1 | test_login_discard | parametrize: view-only, 1 attempt, 1 save, completed round, only settings change | login without discard flag | view-only and settings-only: silent 200; attempt/save/completed round: 409 | FR-28 |
| TC-12.11 | UC-12-X3 | discard_guest without cookie ignored | API | P2 | test_login_discard | no guest cookie | login with flag | normal 200 | FR-28 |
| TC-12.12 | UC-12-X4 | Failed login does not clear re_device | API | P1 | test_login_discard | guest | wrong password | no Set-Cookie clearing `re_device` | FR-28 |
| TC-12.13 | UC-12-X5 | Discard removes guest usage_sessions only | API | P1 | test_login_discard | account has 2 usage sessions; guest has 3 | login with discard | account keeps its 2; guest's 3 gone | FR-28 |
| TC-12.14 | UC-12-X6 | No merge: guest progress absent from account | API | P1 | test_login_discard | guest attempts on card X | login with discard | account attempts count unchanged; XP unchanged | D-1 |
| TC-12.15 | UC-12 | Cascade leaves no orphan rows | API | P0 | test_login_discard | guest with rows in every owned table | login with discard; run `PRAGMA foreign_key_check` and per-table counts for the guest id | 0 rows in attempts, review_state, card_saves, card_progress, reflex_sessions, reflex_progress, user_settings, device_tokens, usage_sessions, upload_claims; foreign_key_check empty | OQ-17 FR-66 |

## 13. UC-13 Login rate limiting

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-13.1 | UC-13 | Five failures lock the nickname | API | P0 | test_login_ratelimit | account `minh_an` | 5 wrong passwords; then correct password | first 5 are 401; the 6th (correct) is 429 with integer `Retry-After`, Vietnamese message with wait time | AC-14 FR-27 |
| TC-13.2 | UC-13 | Window expiry restores access | API | P0 | test_login_ratelimit | after TC-13.1 | clock +15 min + 1 s, correct password | 200; success adds no rate event | FR-27 |
| TC-13.3 | UC-13-A1 | Distributed attack against one nickname | API | P1 | test_login_ratelimit | 6 distinct client IPs (peer addr override) | 5 failures from 5 IPs; 6th from IP 6 | 429 per-nickname | AC-36 |
| TC-13.4 | UC-13-A2 | 100 failures per IP | API | P0 | test_login_ratelimit | one IP, 100 different nicknames | 100 failures; then 101st; separate run: 99 failures + valid login | 101st 429 regardless of nickname; 99 + valid still 200 | AC-36 OQ-15 |
| TC-13.5 | UC-13-A4 | DELETE /api/me wrong password counts | API | P0 | test_login_ratelimit | `reg` | 5 wrong passwords on `DELETE /api/me`, then a login attempt | 6th delete and a login for the same nickname return 429 | OQ-25 |
| TC-13.6 | UC-13-A3 | Unknown nickname counted like known | API | P1 | test_login_ratelimit | none | 5 failures on unknown nick then 6th | 429 (does not reveal existence) | FR-27 |
| TC-13.7 | UC-13-E1 | CSRF failure not counted | API | P1 | test_login_ratelimit | limit 2 | 5 CSRF-failed logins then 2 wrong | still under limit after the CSRF ones | OQ-18 |
| TC-13.8 | UC-13-E2 | 422 not counted | API | P1 | test_login_ratelimit | limit 2 | 5 empty-password logins then wrong password | not locked | OQ-18 |
| TC-13.9 | UC-13-X1 | 4 failures + correct succeeds; 5 + correct 429 | API | P0 | test_login_ratelimit | account | both scenarios on separate nicknames | 200 and 429 respectively | AC-14 |
| TC-13.10 | UC-13-X2 | 429 responses are not counted | API | P1 | test_login_ratelimit | locked | hammer 20 more attempts; check `rate_events` count and the reset time | count stays 5; Retry-After does not grow | OQ-18 |
| TC-13.11 | UC-13-X3 | Retry-After = oldest failure leaves window | unit | P1 | test_ratelimit_window | none | DT-11 rows | integer >= 1 matching table | FR-27 |
| TC-13.12 | UC-13-X4 | Success writes no event and no IP reset | API | P1 | test_login_ratelimit | 3 failures on nick A, success on nick B same IP | check events and then 2 more failures on A | login_ip count unchanged by success; A still locks at 5 total | Addendum#1 |
| TC-13.13 | UC-13-X5 | Case/Unicode variants share one bucket | API | P2 | test_login_ratelimit | none | fail with `Minh_An`, `MINH_AN`, `Ｍinh_An` (fullwidth) | one bucket key (5 total => 429) | FR-27 |
| TC-13.14 | UC-13-X6 | Limits are configurable | API | P2 | test_login_ratelimit | env `LOGIN_NICK_LIMIT=2` | 2 failures then third | 429 | FR-27 |
| TC-13.15 | UC-13-X7 | Classroom behind one IP stays under limit | API | P1 | test_login_ratelimit | 30 students each mistyping 3 times from one IP | 90 failures on 30 distinct nicknames | no 429 (90 < 100) | OQ-15 |
| TC-13.16 | UC-13 | Raw IP and nickname never stored | API | P0 | test_login_ratelimit | after failures | read `rate_events` | `key_hash` values are sha256 hex; no row contains the IP string or nickname | FR-27 NFR-S2 |
| TC-13.17 | UC-13 | Sliding window math | unit | P0 | test_ratelimit_window | none | DT-11 rows (events at t0..t4, query at 899 s / 900 s / 901 s) | per table | FR-27 |

## 14. UC-14 Auto-login and session lifecycle

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-14.1 | UC-14 | Bootstrap a week later returns the registered user | API | P0 | test_session_lifecycle | `reg`; clock +7 d | bootstrap with `re_session` | 200 `is_guest false`, `gate null`, same user; `last_seen_at` and `expires_at` extended (sliding 90 d) | AC-9 FR-23 |
| TC-14.2 | UC-14 | Browser reopen with saved cookies lands on Home | e2e | P0 | test_guest_to_registered | registered context | save storage state, close, reopen new context with state | Home shown, no login/gate screen | AC-9 AC-30 |
| TC-14.3 | UC-14-A1 | Rotate on use when token older than 30 d | API | P0 | test_session_lifecycle | session created at T | use at T+31 d | new token row with `rotated_from` = old hash; new Set-Cookie; old row `grace_until = now + 60 s` | FR-23 |
| TC-14.4 | UC-14-A2 | Sliding extension capped by absolute | API | P1 | test_session_lifecycle | session | use on day 80 | `expires_at` = day 170 but never beyond `absolute_expires_at` (365 d) | FR-23 |
| TC-14.5 | UC-14-A3 | Parallel tab during rotation overlap | API | P0 | test_session_lifecycle | rotated at T | request with old token at T+30 s; at T+61 s | works at 30 s (no second rotation); 401-equivalent (new guest) after 61 s | AC-31 |
| TC-14.6 | UC-14-E1 | Expired session becomes a new guest | API | P0 | test_session_lifecycle | idle 91 d; separately age 366 d | bootstrap | `is_guest true`, new user id, empty progress, no hint of the account | OQ-19 FR-25 |
| TC-14.7 | UC-14-E2 | Revoked token becomes a new guest | API | P0 | test_session_lifecycle | revoke session row | bootstrap | new guest; body identical in shape to a first visit | AC-18 |
| TC-14.8 | UC-14-E3 | Session of a deleted user | API | P1 | test_session_lifecycle | delete the user (DB) | bootstrap with old cookie | no 500; new guest | OQ-17 |
| TC-14.9 | UC-14-E4 | Tampered or unknown token | API | P0 | test_session_lifecycle | none | bootstrap with random and with truncated token | new guest each time | NFR-S1 |
| TC-14.10 | UC-14-X1 | Day 364 capped, day 366 expired | API | P1 | test_session_lifecycle | session aged 364 d with frequent use | use at day 364; at day 366 | expires_at capped at day 365; day 366 treated as expired | FR-23 |
| TC-14.11 | UC-14-X2 | Cookie refresh at most once per 24 h | API | P1 | test_session_lifecycle | session | 5 calls within 24 h, then one after | Set-Cookie on the first of them only; again after 24 h | FR-23 |
| TC-14.12 | UC-14-X3 | Concurrent rotation does not mint competing tokens | API | P0 | test_session_lifecycle | token older than 30 d | two threads use it at once | both succeed; at most one new live token (plus grace row) | AC-31 |
| TC-14.13 | UC-14-X4 | re_session beats re_device | API | P1 | test_session_lifecycle | both cookies present | bootstrap | registered identity | FR-22 |
| TC-14.14 | UC-14-X5 | Grace validity exactly 60 s and no re-rotation | API | P1 | test_session_lifecycle | rotated old token | use at +59 s and +61 s | 59 s valid with no new rotation; 61 s invalid | FR-23 |
| TC-14.15 | UC-14-X6 | Refreshed cookie Max-Age 90 days | API | P2 | test_session_lifecycle | session needing refresh | inspect Set-Cookie | `Max-Age=7776000` (90 d), HttpOnly, SameSite=Lax | FR-23 |
| TC-14.16 | UC-14 | Session expiry/rotation arithmetic | unit | P0 | test_security_tokens | none | DT-13 rows (idle 89/90/91 d; absolute 364/365/366; rotation age 29/30/31 d) | per table | FR-23 |
| TC-14.17 | UC-14 | Session token stored as sha256 only | API | P0 | test_security_hygiene | `reg` | read `sessions` table | no raw token anywhere; `token_hash` equals sha256 of the cookie value | NFR-S1 |

## 15. UC-15 Logout and logout-all

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-15.1 | UC-15 | Logout revokes the session | API | P0 | test_logout | `reg` | `POST /api/auth/logout` | 204; session `revoked_at` set; `re_session` expired; `re_device`, `re_csrf` untouched; other devices unaffected | FR-25 AC-18 |
| TC-15.2 | UC-15 | UI returns to guest Home with login link | e2e | P0 | test_login | registered | Profile > Đăng xuất | state reset; new empty guest; Home shows "Đã có tài khoản? Đăng nhập" | AC-18 |
| TC-15.3 | UC-15 | Replaying the old cookie gives a fresh guest | API | P0 | test_logout | after logout | bootstrap with the old `re_session` | new guest, no account hints | AC-18 |
| TC-15.4 | UC-15-A1 | logout-all revokes every session | API | P0 | test_logout | `reg` logged in on 3 clients | `POST /api/auth/logout-all` from one | all 3 sessions revoked; others get a new guest at next bootstrap | FR-25 |
| TC-15.5 | UC-15-A2 | Logout then login keeps progress | API | P1 | test_logout | `reg` with progress | logout, login | same user; progress intact | FR-25 |
| TC-15.6 | UC-15-E1 | Guest logout 204; guest logout-all 403 account | API | P0 | test_logout | `guest` and a cookie-less client | logout x2; logout-all | 204 for both; logout-all 403 reason `account` (second_visit if gated) | AC-35 OQ-7 |
| TC-15.7 | UC-15-E2 | Logout without CSRF | API | P0 | test_csrf | `reg`, `raw` | logout | 403; session still valid | FR-30 |
| TC-15.8 | UC-15-E3 | Logout with expired or revoked session | API | P2 | test_logout | revoked session cookie | logout | 204 | OQ-7 |
| TC-15.9 | UC-15-X1 | Tab 2 request after logout in tab 1 | e2e | P1 | test_login | two pages registered | logout in tab 1; create-card action in tab 2 | 403 `registration_required` handled: client re-bootstraps, no crash loop, nothing written under wrong user | FR-25 |
| TC-15.10 | UC-15-X2 | Double logout harmless | API | P2 | test_logout | `reg` | two logouts | 204 twice | OQ-7 |
| TC-15.11 | UC-15-X3 | New guest after logout has fresh free session | API | P2 | test_logout | `reg` logout | bootstrap | prior_sessions 0, gate null | D-5 |
| TC-15.12 | UC-15-X4 | logout-all during rotation overlap revokes both tokens | API | P1 | test_logout | rotated session in grace | logout-all | old and new token rows both revoked | FR-25 |

## 16. UC-16 Profile, settings, account fields

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-16.1 | UC-16 | GET /api/me shape for registered | API | P0 | test_profile_settings | `reg` with attempts | `GET /api/me` | 200 `{user, settings, streak, xp, level, level_progress}`; no guardian_email, no hashes; no-store | FR-60 OQ-23 |
| TC-16.2 | UC-16 | Profile screen actions | e2e | P1 | test_login | registered | open Profile | avatar, nickname, streak, XP, level progress; actions logout, logout-all, delete | FR-54 |
| TC-16.3 | UC-16 | PATCH avatar | API | P1 | test_profile_settings | `reg` | `PATCH /api/me {avatar_key}` | 200 updated | FR-29 |
| TC-16.4 | UC-16 | PATCH cefr A1/A2/B1 | API | P1 | test_profile_settings | `reg` | PATCH each | 200 each | OQ-24 |
| TC-16.5 | UC-16 | PUT settings hide_timer | API | P1 | test_profile_settings | `reg` | `PUT /api/me/settings {hide_timer true}`; GET me | 200; persisted | FR-50 |
| TC-16.6 | UC-16-A1 | Guest Profile view | e2e | P1 | test_guest_home | guest | open Profile | card "Đăng ký để lưu tiến trình", login link, "Bạn khách", streak, XP; no edit fields, no logout-all/delete | FR-54 |
| TC-16.7 | UC-16-A2 | Guest hide_timer persisted | API | P1 | test_profile_settings | `guest` | PUT settings; re-bootstrap; GET me | stored under guest id | FR-50 |
| TC-16.8 | UC-16-E1 | Guest PATCH/DELETE/logout-all reason account | API | P0 | test_camera_gate | `guest` | the three calls | 403 reason `account`; gated: `second_visit` | OQ-8 AC-35 |
| TC-16.9 | UC-16-E2 | PATCH with nickname or birth_year | API | P0 | test_profile_settings | `reg` | PATCH `{nickname}`, `{birth_year}` | 422 each; values unchanged | FR-29 |
| TC-16.10 | UC-16-E3 | Invalid avatar/CEFR | API | P1 | test_profile_settings | `reg` | avatar "zzz", cefr "C1" | 422 | FR-29 |
| TC-16.11 | UC-16-E4 | Gated guest PUT settings | API | P1 | test_gate | `gated` | PUT settings | 403 second_visit | OQ-3 |
| TC-16.12 | UC-16-X1 | hide_timer via PATCH rejected | API | P1 | test_profile_settings | `reg` | `PATCH /api/me {hide_timer true}` | 422 unknown field | OQ-22 |
| TC-16.13 | UC-16-X2 | XP, streak, level via API | API | P0 | test_profile_settings | clock fixed; attempts with scores 80 and 50 same ICT day; then yesterday's attempt | `GET /api/me` | xp 12; streak 2; level 1; level_progress 12/500 | AC-45 OQ-23 |
| TC-16.14 | UC-16-X2 | XP, streak, level pure tables | unit | P0 | test_stats | none | DT-5 rows | per table | AC-45 FR-57 |
| TC-16.15 | UC-16-X2 | Streak ICT midnight with clock | API | P1 | test_profile_settings | attempts at 2026-03-01T16:59:59Z and 2026-03-01T17:00:01Z | `GET /api/me` at 2026-03-02 ICT | streak 2 (23:59 ICT and 00:01 ICT are two days) | OQ-23 |
| TC-16.16 | UC-16-X3 | No guardian_email key even for under-16 | API | P0 | test_security_hygiene | under-16 registered | `GET /api/me` | key absent | AC-12 |
| TC-16.17 | UC-16-X4 | B2 rejected on PATCH | API | P1 | test_profile_settings | `reg` | PATCH cefr B2 | 422 | OQ-24 |

## 17. UC-17 Account deletion

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-17.1 | UC-17 | Delete account with correct password | API | P0 | test_account_delete | `reg` with attempts, saves, cards, sessions, claims | `DELETE /api/me {password}` | 204; cookies cleared; all owned rows gone; `image_assets.first_uploaded_by` NULL | FR-29 NFR-P5 |
| TC-17.2 | UC-17 | Deletion UI flow | e2e | P1 | test_login | registered | Profile > Xóa tài khoản, enter password, confirm | irreversible warning shown; afterwards guest state (new guest) | FR-29 |
| TC-17.3 | UC-17-A1 | Owner of a shared approved card | API | P0 | test_account_delete | user shares a card (public) | delete account | card gone from Explore; contents/asset/file GC'd if unreferenced | OQ-26 AC-39 |
| TC-17.4 | UC-17-A2 | Content also held by another user's card | API | P0 | test_account_delete | A and B own cards on the same content | delete A | B's card, `card_contents`, `image_assets` and file kept | OQ-27 AC-39 |
| TC-17.5 | UC-17-A3 | Others' saves of deleted user's card vanish | API | P1 | test_account_delete | B saved A's public card | delete A | B `card_saves` row gone; B library no longer lists it | OQ-26 |
| TC-17.6 | UC-17-E1 | Wrong password | API | P0 | test_account_delete | `reg` | DELETE with wrong password x5 then 6th | 401 `invalid_credentials`, nothing deleted; counts in nickname bucket; 6th 429 | OQ-25 AC-39 |
| TC-17.7 | UC-17-E2 | Missing password | API | P1 | test_account_delete | `reg` | DELETE without body | 422 | FR-29 |
| TC-17.8 | UC-17-E3 | Guest delete | API | P0 | test_camera_gate | `guest` and `gated` | DELETE /api/me | 403 account; gated: second_visit | AC-35 |
| TC-17.9 | UC-17-E4 | Delete during upload processing | API | P1 | test_account_delete | upload `processing` with delayed provider | delete account; let job finish; run maintenance | content has no card/claim: GC removes content, asset and file; another user's attached claim keeps content alive | OQ-27 Addendum#3 |
| TC-17.10 | UC-17-X1 | GC removes DB rows and file; crash repaired later | API | P0 | test_account_delete | private image with one holder | delete; verify file path absent; second scenario: kill GC after commit, run maintenance | file and rows removed in both; seed contents never removed | OQ-27 |
| TC-17.11 | UC-17-X2 | Replayed cookies after deletion | API | P1 | test_account_delete | deleted user's old cookies | bootstrap | new guest, no error | FR-29 |
| TC-17.12 | UC-17-X3 | Second delete from another tab | API | P2 | test_account_delete | two clients | both DELETE | second gets 403 (guest) or no identity handled; no 500 | FR-29 |
| TC-17.13 | UC-17-X4 | RESTRICT FK on cards.content_id does not block | API | P0 | test_account_delete | user with card | delete account | success; cards cascade first, content survives if referenced | OQ-17 |
| TC-17.14 | UC-17-X5 | Nickname reusable immediately | API | P1 | test_account_delete | deleted `Lan_95` | register `Lan_95` | 201 | FR-20 |
| TC-17.15 | UC-17 | No personal data remains | API | P0 | test_account_delete | user under 16 with guardian email | delete; search all tables and files for nickname, birth year, email string | zero hits | NFR-P5 |

## 18. UC-18 CSRF and request security

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-18.1 | UC-18 | Protected request accepted | API | P0 | test_csrf | `guest` | POST with matching token and same Origin | 2xx | FR-30 |
| TC-18.2 | UC-18 | All state-changing methods are protected | API | P0 | test_csrf | `reg` | parametrized POST/PUT/PATCH/DELETE on every route in the OpenAPI schema except exempt list | each without CSRF returns 403 `csrf_failed`; with CSRF not 403 csrf | FR-30 |
| TC-18.3 | UC-18-A1 | Bootstrap exemption | API | P0 | test_csrf | no cookies | bootstrap without token, with and without Origin/Referer; with foreign Origin | accepted, accepted, 403 | OQ-28 AC-38 |
| TC-18.4 | UC-18-A2 | Referer fallback and exact Origin | API | P1 | test_csrf | `guest` | no Origin but same-origin Referer; Origin present but different | 200; 403 | OQ-28 |
| TC-18.5 | UC-18-A3 | Cookie name follows scheme | e2e | P2 | test_guest_home | https test config (self-signed) or API config check | read cookies / `config` | `__Host-re_csrf` under HTTPS, `re_csrf` on localhost; client reads whichever configured | OQ-28 |
| TC-18.6 | UC-18-A4 | CSRF token stable across login/register | API | P0 | test_csrf | `guest` | note token; register; login | cookie/token value identical | OQ-13 |
| TC-18.7 | UC-18-E1 | Missing X-CSRF-Token | API | P0 | test_csrf | `raw` | POST attempts without header | 403 `csrf_failed`; no state change | AC-17 |
| TC-18.8 | UC-18-E2 | Token mismatch | API | P0 | test_csrf | `raw` | header differs from cookie | 403 | AC-17 |
| TC-18.9 | UC-18-E3 | Foreign Origin | API | P0 | test_csrf | `raw` | Origin `https://evil.example` | 403 | AC-17 |
| TC-18.10 | UC-18-E4 | Different port or scheme | API | P1 | test_csrf | `raw` | Origin `http://localhost:9999`, `https://localhost:8000` | 403 | OQ-28 |
| TC-18.11 | UC-18-E5 | re_csrf missing: re-bootstrap once, retry once | e2e | P1 | test_gates | delete `re_csrf` cookie in browser | perform a POST action | client re-bootstraps once and retries once; success; if second csrf_failed shown (forced) no loop | OQ-13 AC-38 |
| TC-18.12 | UC-18-E6 | Neither Origin nor Referer on state change | API | P0 | test_csrf | `raw` | POST attempts with valid token, no Origin/Referer | 403 | AC-38 |
| TC-18.13 | UC-18-E7 | Unknown field or wrong type | API | P1 | test_csrf | `guest` | attempts with extra field; type mismatch | 422 with field errors; no password echo | FR-31 |
| TC-18.14 | UC-18-E8 | Cross-site login is 403 and not counted | API | P0 | test_login_ratelimit | none | login with foreign Origin x10 then valid | 403 each; valid not limited | OQ-18 |
| TC-18.15 | UC-18-X1 | GETs need no CSRF | API | P2 | test_csrf | `guest` | GET cards, image, `/audio/x` | 200/404 without CSRF header | FR-30 |
| TC-18.16 | UC-18-X2 | Origin comparison rules | unit | P1 | test_origin_check | none | DT-12b rows: scheme, host case, port, trailing slash, `null` | exact scheme+host+port match; host case-insensitive | OQ-28 |
| TC-18.17 | UC-18-X3 | No CORS | API | P1 | test_security_hygiene | none | OPTIONS preflight from `Origin: https://evil.example` | no `Access-Control-Allow-Origin` header | NFR-S2 |
| TC-18.18 | UC-18-X4 | SQL injection strings inert | API | P0 | test_security_hygiene | `reg` | nickname `' OR 1=1 --`, `q=%27;DROP TABLE users;--`, cursor `'; --` | 422 or empty results; tables intact; no 500 | NFR-S3 |
| TC-18.19 | UC-18-X4 | No string-formatted SQL in repositories | unit | P0 | test_sql_scan | none | AST/regex scan of `backend/app/repositories/*.py` for f-strings, `%` or `.format` feeding `execute` | zero violations; `routers/` contain no `execute` | NFR-S3 |
| TC-18.20 | UC-18-X5 | Hostile content rendered as text | e2e | P0 | test_upload_review | registered; card title `<img src=x onerror=alert(1)>`; label word similar | open Review, Library, Explore | text shown literally; no dialog/script executed; CSP forbids inline script (console CSP violation on injected inline) | NFR-S5 |
| TC-18.21 | UC-18-X6 | Logs contain no secrets | API | P0 | test_security_hygiene | log capture at DEBUG | register, login, fail login, upload, delete account | no password, token, hash, guardian email, raw IP in logs | FR-32 |
| TC-18.22 | UC-18-X7 | Security headers | API | P0 | test_security_hygiene | `guest` | GET `/`, `/api/me`, cards | `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`, restrictive CSP (no unsafe-inline script, allows blob:/data: img+media); `Cache-Control: no-store` on user JSON | FR-33 |

## 19. UC-19 Cookie-cleared, blocked, multi-device guests

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-19.1 | UC-19 | Guest clears cookies | API | P1 | test_guest_cookie_scenarios | guest with progress | drop cookies; bootstrap | new guest, fresh usage counter, empty progress; old rows orphaned | FR-1 FR-6 |
| TC-19.2 | UC-19 | Login link visible after cookie clear | e2e | P1 | test_guest_home | context cookies cleared | reload | Home with "Đã có tài khoản? Đăng nhập" | UC-44 |
| TC-19.3 | UC-19-A1 | Registered user clears cookies | API | P1 | test_guest_cookie_scenarios | `reg` | drop cookies; bootstrap; then login | new guest reveals nothing; login restores account | OQ-19 |
| TC-19.4 | UC-19-A2 | Two devices independent guests | API | P1 | test_guest_cookie_scenarios | two clients | each writes; one hits the gate | separate ids, counters; the other not gated | FR-1 |
| TC-19.5 | UC-19-A3 | Same nickname on device B | API | P1 | test_guest_cookie_scenarios | `Lan_95` registered on A | B guest registers `Lan_95` | 409 `nickname_taken`; no merge | AC-13 |
| TC-19.6 | UC-19-A4 | Incognito behaves as new device | e2e | P2 | test_guest_home | second context | open app | brand-new guest; nothing persists after context close | FR-1 |
| TC-19.7 | UC-19-E1 | Cookies blocked: register/login cannot persist | e2e | P2 | test_guest_home | context where Set-Cookie dropped | open and try register | Vietnamese notice; no infinite bootstrap loop (bounded requests) | PRD#14 |
| TC-19.8 | UC-19-E2 | Cross-site POST carries no cookies | API | P1 | test_csrf | cookies parsed | verify Set-Cookie attributes SameSite=Lax; cross-origin request lacks cookie and Origin matches nothing | 403 | NFR-S1 |
| TC-19.9 | UC-19-X1 | Orphans only purged, never merged | API | P1 | test_maintenance | two guests (one orphan) | register new; run maintenance +8 d | orphan removed only if no write; no data moved to the new account | OQ-20 |
| TC-19.10 | UC-19-X2 | B registering unaffected by A | API | P2 | test_guest_cookie_scenarios | two guests | A registers | B row unchanged | FR-17 |
| TC-19.11 | UC-19-X3 | Only re_csrf cleared | API | P2 | test_guest_cookie_scenarios | guest | drop `re_csrf`; bootstrap with `re_device` | same user; `re_csrf` re-issued | FR-5 |
| TC-19.12 | UC-19-X4 | Storage cleared, cookies kept | e2e | P2 | test_guest_home | guest with progress | clear localStorage/sessionStorage; reload | same identity and progress | FR-12 |

## 20. UC-20 Upload a new image (AI called once)

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-20.1 | UC-20 | Upload a new JPEG end to end | API | P0 | test_upload_pipeline | `reg`; `jpeg_bytes()`; provider counter 0 | `POST /api/uploads` multipart; poll `GET /api/uploads/{content_id}` until ready | 202 `{content_id, status processing, dedupe none, ai_calls 0}`; final `status ready`, `ai_calls 1`; DB: 1 image_assets (`source_sha256` = sha256 of RAW bytes, `clean_sha256` stored separately, relative path random name), 1 card_contents (lease_expires_at = now+90 s while processing), 3-5 card_labels, sentences, audio_assets, 1 upload_claims; NO cards row; `provider.call_count == 1` | FR-34 FR-35 FR-36 OQ-29 OQ-32 |
| TC-20.2 | UC-20 | Processing screen then Review | e2e | P0 | test_upload_review | registered, mock provider delay 1 s | pick photo | steps shown with "Số lần gọi AI: 1"; navigation not blocked; Review opens when ready | FR-39 NFR-F3 |
| TC-20.3 | UC-20 | ai_calls committed before the provider call | API | P0 | test_upload_pipeline | provider hook reads the DB from a second connection when `analyze` is entered | upload | at entry `card_contents.ai_calls == 1` is already committed and visible | AC-41 OQ-33 |
| TC-20.4 | UC-20 | AI result validated and box_2d converted | unit | P1 | test_upload_result | none | feed `AnalysisResult` with box_2d [200,100,400,300]; box out of range (1200); 2 labels only | centre x=0.2, y=0.3 (normalised), corners kept; out-of-range label dropped; fewer than 3 labels after dropping -> invalid result | FR-39 FR-41 |
| TC-20.5 | UC-20-A1 | Provider selection by environment | unit | P1 | test_provider_selection | env without and with `GEMINI_API_KEY` | `get_provider(settings)` | MockProvider vs GeminiProvider (instantiate only, no network); tests never use Gemini | FR-34 |
| TC-20.6 | UC-20-A2 | Leaving during processing; resume by re-upload | e2e | P2 | test_upload_review | registered | start upload, navigate to Library, re-upload the same file | job continued; second upload returns `dedupe ready` with existing claim; Review opens; no card in "Bài của tôi" before saving | Addendum#2 |
| TC-20.7 | UC-20-A3 | Mock upload to ready within 3 s | API | P2 | test_perf | 100-card fixture, 50 concurrent users optional | measure upload -> ready | p95 <= 3 s | NFR-F3 |
| TC-20.8 | UC-20-E1 | Guest upload blocked | API | P0 | test_camera_gate | `guest`; `gated` | upload | 403 reason camera; gated: second_visit; no file on disk | AC-4 |
| TC-20.9 | UC-20-E2 | Network loss mid upload is retryable | e2e | P1 | test_network_offline | route abort during POST | upload then retry | retry message, no partial rows (`image_assets` count 0 after abort) | PRD#13 |
| TC-20.10 | UC-20-E6 | Budget exhausted returns analysis_unavailable | API | P0 | test_ai_failure_retry | content failed with budget spent | re-upload | 409 `analysis_unavailable`; 0 calls; see TC-48.1 | OQ-36 |
| TC-20.11 | UC-20-E3 | Disk write failure | API | P1 | test_upload_pipeline | monkeypatch storage write to raise OSError(ENOSPC) | upload | 500 or 507 with generic Vietnamese error; no image_assets/claims row; partial file removed | PRD#13 |
| TC-20.12 | UC-20-E4 | Missing CSRF | API | P0 | test_csrf | `reg`, `raw` | upload without header | 403 `csrf_failed`; nothing stored | AC-17 |
| TC-20.13 | UC-20-E5 | Too few valid labels counts as failed call | API | P1 | test_ai_failure_retry | provider returns 4 labels of which 2 out of range | upload | treated as invalid: automatic retry (call 2); after second invalid `failed` | FR-38 |
| TC-20.14 | UC-20-X1 | Provider concurrency limit 2 | API | P0 | test_upload_pipeline | provider records max simultaneous `analyze` entries; delay 0.5 s | 5 uploads of different images | max concurrency 2; all 5 finish ready; none dropped | FR-35 NFR-A1 |
| TC-20.15 | UC-20-X2 | Same word across images shares one audio asset | API | P1 | test_upload_pipeline | two images both labelled "cup" (scripted) uploaded concurrently | upload both | exactly one `audio_assets` row for (text cup, voice) | FR-40 |
| TC-20.16 | UC-20-X3 | audio_url null when no pre-generated file | API | P1 | test_upload_pipeline | label word not in catalogue | `GET /api/cards/{id}` | label `audio_url` null (client falls back to speech) | FR-40 OQ-61 |
| TC-20.17 | UC-20-X4 | Random file names, traversal ignored | API | P0 | test_upload_validation | filename `../../etc/passwd.jpg` | upload | stored under random name inside `DATA_DIR`; no path component of user input; resolved path inside DATA_DIR | NFR-S4 |
| TC-20.18 | UC-20-X5 | DB not locked during the AI call | API | P0 | test_upload_pipeline | provider blocks on an Event (5 s) | while blocked, other user posts attempts and registers | all other writes succeed within 500 ms; no `database is locked` | NFR-A1 |
| TC-20.19 | UC-20-X6 | Pixel limit returns 413 image_too_large | API | P0 | test_upload_validation | 5001x5000 PNG | upload | 413 `image_too_large`; see TC-22.14 | OQ-30 |
| TC-20.20 | UC-20-X7 | Failure after file stored, before DB insert | API | P1 | test_upload_pipeline | fault injection at the DB insert | upload | request fails; no stray file left in DATA_DIR | PRD#13 |
| TC-20.21 | UC-20-A1 | Real Gemini smoke test | manual | P2 | manual | staging with real `GEMINI_API_KEY` | upload 3 real photos incl. one with a face | valid labels/boxes, safety flags populated, `ai_calls 1` each; never run in CI | FR-34 FR-39 |

## 21. UC-21 Dedupe and concurrent identical uploads

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-21.1 | UC-21 | Already processed image by another user | API | P0 | test_upload_dedupe | user A image ready (`ai_calls 1`) | user B uploads identical bytes | 202 `{dedupe ready, status ready, ai_calls 0}`; counter stays 1; new upload_claims(B); NO cards row | AC-20 FR-36 FR-37 |
| TC-21.2 | UC-21 | Dedupe message in UI | e2e | P1 | test_upload_review | A processed; B in second context | B uploads same file | texts "Ảnh này đã có sẵn, không cần gọi AI" and "Số lần gọi AI: 0 - ảnh đã có sẵn"; Review opens at once | AC-20 |
| TC-21.3 | UC-21-A1 | Simultaneous uploads by A and B | API | P0 | test_upload_dedupe | two registered users; provider delay 0.3 s; barrier | two threads upload identical bytes together | one response `dedupe none`, other `dedupe in_flight`; `provider.call_count == 1`; `card_contents.ai_calls == 1`; 2 upload_claims; 0 cards until each calls `POST /api/cards`; then 2 cards referencing 1 content | AC-19 AC-31 |
| TC-21.4 | UC-21-A2 | Same user, two tabs | API | P1 | test_upload_dedupe | one user | two threads upload same bytes; then two `POST /api/cards` | single claim row (PK user+content); one card (UNIQUE owner+content, second returns the existing card); one AI call | FR-42 |
| TC-21.5 | UC-21-A3 | User re-uploads own ready image | API | P1 | test_upload_dedupe | user already has a card | upload same bytes | `dedupe ready`, `card_id` of the existing card included, 0 calls | FR-42 |
| TC-21.6 | UC-21-A4 | in_flight attach message and polling | API | P1 | test_upload_dedupe | job processing | second upload | `status processing`, `dedupe in_flight`, message "Ảnh này đang được xử lý, vui lòng chờ…", 0 provider calls from this request; both pollers see ready | OQ-31 |
| TC-21.7 | UC-21-E1 | In-flight job fails for both | API | P1 | test_upload_dedupe | provider scripted to fail twice | A and B attached | both polls `failed`; retry budget shared | FR-38 |
| TC-21.8 | UC-21-E2 | Unique race loser reads winner, no 500 | API | P0 | test_upload_dedupe | test hook inserts the winner row between the loser's SELECT and INSERT | upload | loser returns 202 attached to winner; never 500 | NFR-A1 |
| TC-21.9 | UC-21-X1 | Ten simultaneous identical uploads | API | P0 | test_upload_dedupe | 10 users, barrier | 10 threads | provider counter 1; 1 image_assets; 1 card_contents; 10 claims; after each saves, 10 cards | AC-19 |
| TC-21.10 | UC-21-X2 | Re-compressed copy is not deduped | API | P1 | test_upload_dedupe | same picture saved at quality 90 and 70 | upload both | two different `source_sha256`, two contents, 2 calls (documented) | OQ-32 |
| TC-21.11 | UC-21-X3 | Different raw bytes with equal cleaned pixels | API | P2 | test_upload_dedupe | JPEG with and without EXIF over identical pixels | upload both | not deduped (raw-byte key) | OQ-32 |
| TC-21.12 | UC-21-X4 | Aggregate calls per image metric | API | P2 | test_upload_dedupe | 20 unique images, 20 duplicates | upload all | `SUM(ai_calls) / unique images` <= 1.05 | OQ-34 OQ-36 |
| TC-21.13 | UC-21-X5 | Dedupe does not expose A's private card to B | API | P0 | test_upload_dedupe | A has private card of the image | B uploads same bytes, then `GET /api/cards/{A_card}` and `/image` | B gets claim and 0 AI calls; A's card is 404 for B | OQ-41 |

## 22. UC-22 Upload validation and privacy cleaning

Fixtures are generated in code (section 52). After every error case the shared assertion `nothing_stored()` checks: no image_assets, no card_contents, no upload_claims, no new file in DATA_DIR.

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-22.1 | UC-22 | EXIF/GPS stripped from stored JPEG | API | P0 | test_upload_validation | JPEG with GPS EXIF (lat/long, make/model, thumbnail) | upload; reopen the stored file with Pillow and scan raw bytes | `getexif()` empty, no GPSInfo, no `Exif\0\0` marker bytes; original bytes not retained; image still valid | AC-22 NFR-S4 |
| TC-22.2 | UC-22-A1 | PNG and WebP metadata dropped | API | P1 | test_upload_validation | PNG with tEXt/iTXt/eXIf chunks; WebP with EXIF and XMP | upload each | stored files have no ancillary metadata chunks | AC-22 |
| TC-22.3 | UC-22-A2 | EXIF orientation applied before strip | unit | P2 | test_imaging | JPEG 40x20 with orientation 6 | `clean_image` | output 20x40 (rotated) and no orientation tag | assumed |
| TC-22.4 | UC-22-E1 | GIF rejected | API | P0 | test_upload_validation | GIF bytes | upload | 415; nothing stored | AC-21 |
| TC-22.5 | UC-22-E2 | 12 MB JPEG rejected | API | P0 | test_upload_validation | 12 MB JPEG | upload | 413; nothing stored | AC-21 |
| TC-22.6 | UC-22-E3 | HTML renamed .jpg and with image/jpeg content type | API | P0 | test_upload_validation | `<html><script>` bytes | upload with filename `x.jpg` and part Content-Type image/jpeg | 415 by sniffing; nothing stored | AC-21 |
| TC-22.7 | UC-22-E4 | Truncated or corrupt JPEG | API | P1 | test_upload_validation | JPEG cut at 60% | upload | 422; nothing stored | OQ-30 |
| TC-22.8 | UC-22-E5 | Decompression bomb | API | P0 | test_upload_validation | PNG header 30000x30000 with tiny zlib payload (generated by streaming zeros, < 200 KB) | upload while measuring `tracemalloc` peak and time | 413 `image_too_large`; rejected before full decode; peak memory < 150 MB; < 2 s | OQ-30 NFR-S4 |
| TC-22.9 | UC-22-E9 | Animated WebP, APNG, animated GIF | API | P0 | test_upload_validation | 2-frame animated WebP; 2-frame APNG | upload | 415 `unsupported_image`; never first-frame-only | OQ-30 |
| TC-22.10 | UC-22-E6 | SVG, PDF, polyglot | API | P0 | test_upload_validation | SVG with script; `%PDF-` bytes; JPEG header + trailing `<script>alert(1)</script>` | upload each | SVG and PDF 415; polyglot accepted only if decodable and re-encoded: stored file has no `<script` bytes | NFR-S4 |
| TC-22.11 | UC-22-E7 | Missing, multiple, empty file part | API | P1 | test_upload_validation | none | upload with no file part; two files; zero-byte file | 422 each | FR-34 |
| TC-22.12 | UC-22-E8 | Aborted upload stores nothing | API | P2 | test_upload_validation | ASGI client that disconnects mid-body | send half the body | nothing stored | FR-34 |
| TC-22.13 | UC-22-X1 | Exactly MAX_UPLOAD_BYTES vs +1 | API | P0 | test_upload_validation | valid JPEG padded (comment segment) to exactly 5 242 880 bytes and +1 | upload both | first accepted 202; second 413 | AC-21 |
| TC-22.14 | UC-22-X2 | Exactly 25 MP vs 25 MP + 1 px | API | P0 | test_upload_validation | PNG 5000x5000 and 5001x5000 (solid colour) | upload both | first 202; second 413 `image_too_large` | OQ-30 |
| TC-22.15 | UC-22-X3 | Path traversal filename | API | P0 | test_upload_validation | filename `../../etc/passwd.jpg`, `..\\..\\x.jpg`, NUL byte | upload | stored under random name inside DATA_DIR; response and DB never echo user filename | NFR-S4 |
| TC-22.16 | UC-22-X4 | Zero-dimension image | API | P2 | test_upload_validation | PNG with width 0 header | upload | 422 | OQ-30 |
| TC-22.17 | UC-22-X5 | Extension lies, sniff wins | API | P1 | test_upload_validation | JPEG bytes named `a.png` | upload | 202; stored as JPEG | FR-34 |
| TC-22.18 | UC-22 | Content sniffing table | unit | P0 | test_imaging | magic-byte samples for JPEG, PNG, WebP, GIF, BMP, TIFF, HTML, SVG, PDF, empty | `sniff(bytes)` | JPEG/PNG/WebP accepted; all others rejected | FR-34 |
| TC-22.19 | UC-22 | Nothing stored after any rejection | API | P0 | test_upload_validation | parametrize over TC-22.4-22.12 inputs | run each, then `nothing_stored()` | no rows and no files | AC-21 |

## 23. UC-23 AI failure, retry rules, crash recovery

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-23.1 | UC-23 | Invalid output twice ends failed | API | P0 | test_ai_failure_retry | provider scripted: invalid JSON, invalid schema | upload; poll | `provider.call_count == 2`; `ai_calls 2`; status failed with `error`; no `card_labels` rows | FR-38 NFR-A4 |
| TC-23.2 | UC-23 | ai_calls increments before each call | API | P0 | test_ai_failure_retry | hook per call reads DB | upload with provider raising exception | counter in DB was already +1 at each entry; exception still counts | OQ-33 AC-41 |
| TC-23.3 | UC-23 | Manual retry is a fresh run | API | P0 | test_ai_failure_retry | failed content | re-upload same bytes | status back to processing; `manual_retries 1`; at most 2 new provider calls | OQ-34 |
| TC-23.4 | UC-23 | Hard cap: 2 manual retries, 6 calls | API | P0 | test_ai_failure_retry | provider always fails | initial run, retry 1, retry 2, then retry 3 | `ai_calls` 2, 4, 6; third re-upload 409 `analysis_unavailable`, calls stay 6 | OQ-36 AC-40 |
| TC-23.5 | UC-23-A1 | Retry succeeds with cumulative counters | API | P1 | test_ai_failure_retry | provider fails run 1, succeeds first call of run 2 | upload twice | status ready; `ai_calls 3`; `manual_retries 1` | OQ-34 |
| TC-23.6 | UC-23-A2 | Provider timeout counts as call and failure | API | P0 | test_ai_failure_retry | `PROVIDER_TIMEOUT=0.2` and provider sleeping 1 s | upload | timeout recorded; automatic retry follows; counts 2 calls; status failed | FR-38 AC-41 |
| TC-23.7 | UC-23-A3 | Other user's re-upload of failed image | API | P1 | test_ai_failure_retry | A failed; B uploads same bytes | B upload | B gets claim; consumes shared budget (`manual_retries` +1) | OQ-34 |
| TC-23.8 | UC-23-A4 | Lease lazily swept on poll and on upload | API | P0 | test_ai_failure_retry | processing row; clock beyond `lease_expires_at` (90 s) | `GET /api/uploads/{id}`; second scenario via upload of same bytes | status flips to failed; at lease+0 s still processing, lease+1 s failed (boundary assumed) | OQ-35 AC-41 FR-65 |
| TC-23.9 | UC-23-A4 | Client stops polling after 120 s | e2e | P2 | test_upload_review | provider blocked forever; fake timers | wait 121 s virtual | polling stops; retry state shown | OQ-35 |
| TC-23.10 | UC-23-E1 | Budget exhausted | API | P0 | test_ai_failure_retry | manual_retries 2 | re-upload | 409 `analysis_unavailable`; status stays failed | OQ-36 |
| TC-23.11 | UC-23-E2 | Concurrent re-upload of failed image | API | P0 | test_ai_failure_retry | failed content, two threads, barrier | both re-upload | exactly one flips failed -> processing (`manual_retries` +1); other `in_flight`; no duplicate provider calls | OQ-34 |
| TC-23.12 | UC-23-E3 | Restart sweep and live lease | API | P0 | test_ai_failure_retry | row processing with expired lease; another with live lease; app restarted | startup | expired -> failed (retryable); live stays processing until expiry | FR-65 NFR-A4 |
| TC-23.13 | UC-23-E4 | Provider quota/5xx never blocks navigation | e2e | P2 | test_upload_review | provider raising 503 | upload then browse | Vietnamese message and Retry; other screens usable | NFR-A4 |
| TC-23.14 | UC-23-X1 | Persistent failure totals | API | P1 | test_ai_failure_retry | always-failing provider | run to the cap | first run 2 calls; end 6 calls; permanently failed | OQ-36 |
| TC-23.15 | UC-23-X2 | Polling never calls the provider | API | P0 | test_ai_failure_retry | processing and failed contents | poll 20 times each | `provider.call_count` unchanged | FR-38 |
| TC-23.16 | UC-23-X3 | raw_response never returned | API | P0 | test_security_hygiene | ready and failed contents | `GET /api/uploads/{id}`, card detail | no `raw_response` key/value in any body | NFR-S2 |
| TC-23.17 | UC-23-X4 | Failed image stays failed after cap; GC only when unheld | API | P2 | test_maintenance | failed content with claim older than 7 d and no card | run maintenance | removed only when no card and no claim younger than 7 d | Addendum#3 |
| TC-23.18 | UC-23-X5 | Lease boundary inclusivity | unit | P2 | test_retry_budget | none | `lease_expired(lease, now)` at lease+0 s and +1 s | False, True | assumed |
| TC-23.19 | UC-23-X6 | Crash after pre-call increment counts the call | API | P1 | test_ai_failure_retry | fault injection between increment and provider call | upload; restart; sweep | `ai_calls` stays incremented; budget conservative | OQ-33 |
| TC-23.20 | UC-23 | Retry budget state table | unit | P0 | test_retry_budget | none | DT-14 rows (ai_calls, manual_retries, status) -> allowed? | per table; call allowed iff `ai_calls < 6` and `manual_retries < 2` | OQ-36 Addendum#6 |

## 24. UC-24 Review AI result and save the card

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-24.1 | UC-24 | GET upload result with claim | API | P0 | test_review_save_card | `reg` with ready upload | `GET /api/uploads/{content_id}` | 200 topic, labels (with boxes), descriptions, story, safety summary; no raw_response | FR-41 |
| TC-24.2 | UC-24 | Save creates private card with overrides on card only | API | P0 | test_review_save_card | ready content | `POST /api/cards {content_id, title, label_overrides}` | 201 CardDetail; `visibility private`; `cards.label_overrides` JSON set; shared `card_labels` rows unchanged | FR-41 FR-43 OQ-29 |
| TC-24.3 | UC-24 | Review UI drag, edit, delete, save | e2e | P0 | test_upload_review | ready upload | drag marker, edit word/IPA/meaning, delete a label, set title, Save | markers are buttons with aria-label and >= 44x44 hit area; card appears in "Bài của tôi" | US-9 NFR-X2 |
| TC-24.4 | UC-24-A1 | Cancel saves nothing | e2e | P1 | test_upload_review | ready upload | tap Cancel; re-upload same file | no cards row; claim and content remain; Review reopens via same content_id | OQ-29 |
| TC-24.5 | UC-24-A2 | Duplicate label word | API | P1 | test_review_save_card | labels "cup" and "plate" | overrides rename plate to "Cup" | 422 field error (case-insensitive); card not created | OQ-37 |
| TC-24.6 | UC-24-A3 | Keyboard nudges marker | e2e | P2 | test_a11y_mobile | Review open | focus marker; press arrow keys | marker position changes in steps; focus visible | NFR-X2 |
| TC-24.7 | UC-24-E1 | Guest save | API | P0 | test_camera_gate | `guest`, `gated` | POST /api/cards | 403 camera / second_visit | AC-35 |
| TC-24.8 | UC-24-E2 | IDOR on upload and card creation | API | P0 | test_review_save_card | A has content; B authenticated without claim | B: `GET /api/uploads/{id}`, `POST /api/cards`, re-upload path check; also non-existent id | all 404 with byte-identical body to the non-existent case | AC-40 OQ-38 |
| TC-24.9 | UC-24-E3 | Invalid overrides | API | P0 | test_review_save_card | ready content | parametrize: marker x=1.2, y=-0.1; title 61 chars; word 41 chars; 9 labels; 0 labels; foreign label id; new added label | 422 each; nothing created | OQ-37 |
| TC-24.10 | UC-24-E4 | Content not ready | API | P1 | test_review_save_card | content processing | POST /api/cards | 409 | FR-41 |
| TC-24.11 | UC-24-E5 | Save twice | API | P0 | test_review_save_card | ready content | two sequential and two concurrent saves | same card id each time; one cards row; no 500 | FR-42 |
| TC-24.12 | UC-24-X1 | Cannot delete every label | API | P1 | test_review_save_card | ready content | overrides deleting all labels | 422 (min 1) | OQ-37 |
| TC-24.13 | UC-24-X2 | A's edits invisible to B | API | P1 | test_review_save_card | A and B each have a card on one content | A renames a label | B's card detail shows the original word | FR-42 |
| TC-24.14 | UC-24-X3 | HTML title rendered as text | e2e | P1 | test_upload_review | title with tags | save and view | literal text | NFR-S5 |
| TC-24.15 | UC-24-X4 | Markers at edge keep 44 px inside viewport | e2e | P2 | test_a11y_mobile | viewport 360x640; label at x=0.99 | measure bounding boxes | hit area >= 44x44 and fully inside viewport | NFR-X2 |
| TC-24.16 | UC-24-X5 | Refresh restores from server | e2e | P2 | test_upload_review | Review with unsaved edits | reload | Review rebuilt from `GET /api/uploads/{id}`; unsaved edits lost with a message | FR-41 |
| TC-24.17 | UC-24 | Override validation rules table | unit | P1 | test_card_overrides | none | DT-15 rows | per table | OQ-37 |

## 25. UC-25 Card visibility, sharing, moderation

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-25.1 | UC-25 | Private image: owner 200, others 404 | API | P0 | test_card_visibility_share | A owns private card C; B registered; guest; seed card | `GET /api/cards/{C}/image` as A, B, guest; seed card image as each | A 200 bytes; B 404; guest 404; seed 200 for all | AC-23 FR-43 |
| TC-25.2 | UC-25 | All card subroutes 404 for non-owner | API | P0 | test_card_visibility_share | as above | parametrize `GET /api/cards/{C}`, `/image`, `POST /save`, `POST /share`, `DELETE /share`, `DELETE` (B) and `GET`/`POST save` (guest) | 404 (guest write routes 403 camera where applicable, reads 404) | OQ-41 |
| TC-25.3 | UC-25-A1 | Share a clean card | API | P0 | test_card_visibility_share | content safety all clean | `POST /api/cards/{id}/share` | 200 `ShareOut`; `moderation_status approved`, `visibility public`; Explore lists it with owner nickname only; image 200 for all identities | FR-43 AC-24 OQ-39 |
| TC-25.4 | UC-25-A2 | Share card with identifiable faces | API | P0 | test_card_visibility_share | provider override `has_identifiable_faces=true` | share | 422 `{"error":"share_not_allowed","reason":"faces"}` with Vietnamese message; `moderation_status rejected`; visibility private; no `pending` anywhere | AC-24 OQ-40 |
| TC-25.5 | UC-25-A3 | Personal info, NSFW, not suitable | API | P0 | test_card_visibility_share | flags personal_info; nsfw_or_violence; `is_suitable_for_students=false` | share each | 422 reason `personal_info` / `unsuitable` / `unsuitable`; card stays private and usable | AC-24 |
| TC-25.6 | UC-25-A4 | Re-share after rejection | API | P1 | test_card_visibility_share | rejected content | share again | same 422; rejection permanent | OQ-40 |
| TC-25.7 | UC-25-A5 | Share twice | API | P1 | test_card_visibility_share | public card | share again | 200 idempotent | FR-44 |
| TC-25.8 | UC-25-A6 | Unshare and delete defined elsewhere | API | P2 | test_unshare_delete_card | n/a | see TC-42.1 and TC-43.1 | pass | OQ-42 |
| TC-25.9 | UC-25-E1 | Non-owner share | API | P0 | test_card_visibility_share | B | `POST /share` on A's card | 404 | OQ-41 |
| TC-25.10 | UC-25-E2 | Guest share | API | P0 | test_camera_gate | `guest`, `gated` | share | 403 camera / second_visit | AC-35 |
| TC-25.11 | UC-25-E3 | Share while content unusable | API | P2 | test_card_visibility_share | card whose content set to failed in DB | share | 409 | FR-44 |
| TC-25.12 | UC-25-E4 | Private card detail by non-owner | API | P0 | test_card_visibility_share | as TC-25.1 | `GET /api/cards/{C}` as B | 404 | OQ-41 |
| TC-25.13 | UC-25-X1 | Image access rule matrix | unit | P0 | test_card_visibility_policy | none | DT-16 rows (owner, system, public+approved, public+pending/rejected, private) | per table | FR-43 |
| TC-25.14 | UC-25-X2 | Moderation is per content | API | P1 | test_card_visibility_share | A shared (approved); B has own card on same content | B reads own card; B image requested by C | B card stays private (C gets 404) until B shares | OQ-41 |
| TC-25.15 | UC-25-X3 | Unshare/delete defined | API | P2 | test_unshare_delete_card | n/a | see UC-42/43 TCs | pass | OQ-42 |
| TC-25.16 | UC-25-X4 | 404 bodies identical | API | P1 | test_card_visibility_share | existing foreign id vs random uuid | request both | identical status, body, relevant headers | AC-23 |
| TC-25.17 | UC-25-X5 | Nicknames only on approved shared cards | API | P1 | test_card_visibility_share | public card by A; private card by A | Explore and library of B | A's nickname only on the public card payload; none for seeded cards (no owner nickname) or private ones | NFR-P4 |
| TC-25.18 | UC-25 | Share UI never says pending | e2e | P1 | test_upload_review | card with faces flag | tap Share | Vietnamese rejection reason; no text "chờ kiểm duyệt" in DOM | AC-24 |
| TC-25.19 | UC-25-A2 | Share decision table | unit | P0 | test_card_visibility_policy | none | DT-16b rows (flag combinations) | decision and reason per table (priority faces > personal_info > unsuitable) | AC-24 |

## 26. UC-26 Explore, search, topic filter

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-26.1 | UC-26 | Explore list with topic and CEFR filters | API | P0 | test_explore_search | production seed + 1 public approved user card | `GET /api/topics`; `GET /api/cards?scope=explore&topic=food&cefr=A1&limit=20` | topic counts correct; `CardPage {items, next_cursor}` only seeded + approved public cards matching filters, ordered `(created_at DESC, id DESC)` | FR-53 FR-52 |
| TC-26.2 | UC-26 | Search is case-insensitive and uses the lower(word) index | API | P0 | test_explore_search | seed with "cup" | `GET /api/cards?q=cup`; `EXPLAIN QUERY PLAN` | cards with label containing "cup"; plan mentions the `lower(word)` index | AC-28 |
| TC-26.3 | UC-26 | Save and unsave | API | P1 | test_explore_search | `guest` or `reg` | `POST /api/cards/{id}/save`; `DELETE` | 200 both; card_saves row appears/disappears | FR-53 |
| TC-26.4 | UC-26 | Explore UI flow | e2e | P1 | test_library_explore | guest | open Explore, filter topic, search "cup", save, tap Practice | filters apply, saved badge, Practice opens | FR-53 |
| TC-26.5 | UC-26 | Read paths make zero AI calls | API | P0 | test_explore_search | provider counter 0 | call topics, cards, search, card detail, library scopes | `provider.call_count == 0` | FR-36 NFR-A1 |
| TC-26.6 | UC-26-A1 | Guest saved seeded card survives and converts | API | P1 | test_explore_search | `guest` saved seed card | reload; register | saved card still present under same user id | FR-3 |
| TC-26.7 | UC-26-A2 | Filters AND-combine | API | P1 | test_explore_search | seed | topic + cefr + q together | intersection only | FR-52 |
| TC-26.8 | UC-26-A3 | Empty result state | e2e | P2 | test_library_explore | guest | search "zzzzzz" | Vietnamese empty state | FR-52 |
| TC-26.9 | UC-26-E1 | Invalid scope or cefr | API | P1 | test_explore_search | `guest` | `scope=foo`, `cefr=C2` | 422 | FR-52 |
| TC-26.10 | UC-26-E2 | Save someone else's private card | API | P0 | test_card_visibility_share | B | `POST /api/cards/{A_private}/save` | 404 | OQ-41 |
| TC-26.11 | UC-26-E5 | Malformed cursor or limit | API | P1 | test_pagination | `guest` | `limit=0`, `limit=51`, cursor `abc`, tampered base64 | 422 each; no 500 | OQ-43 |
| TC-26.12 | UC-26-E3 | Idempotent save and unsave | API | P2 | test_explore_search | `guest` | save twice; unsave twice | 200 each; one row max | FR-53 |
| TC-26.13 | UC-26-E4 | Gated guest | API | P1 | test_gate | `gated` | explore | 403 second_visit | FR-10 |
| TC-26.14 | UC-26-X1 | Wildcards and quotes literal; long q | API | P0 | test_explore_search | seed | `q=%`, `q=_`, `q=c'up`, `q=""`, `q` of 101 and 500 chars | `%` and `_` match literally (no mass match); quote safe; empty q = no filter; long q trimmed or 422, never 500 | NFR-S3 |
| TC-26.15 | UC-26-X2 | CUP equals cup | API | P1 | test_explore_search | seed | `q=CUP` vs `q=cup` | identical result lists | AC-28 |
| TC-26.16 | UC-26-X3 | Never lists other users' private, pending or rejected | API | P0 | test_explore_search | private, rejected and public cards from A | B explores | only public approved visible | FR-43 |
| TC-26.17 | UC-26-X4 | Default and max page size | API | P1 | test_pagination | 60 cards | no limit; `limit=50` | 20 items; 50 items | OQ-43 |
| TC-26.18 | UC-26-X5 | Diacritic query tolerated | API | P2 | test_explore_search | seed | `q=cốc` | 200 empty list (not an error) | UC-26-X5 |

## 27. UC-27 Practice levels and unlock rules

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-27.1 | UC-27 | Card payload with progress | API | P0 | test_practice_levels | `guest`, seed card | `GET /api/cards/{id}` | labels, sentences, story, `audio_url`s, `progress` (Level 1 unlocked by default, others locked) | FR-47 |
| TC-27.2 | UC-27 | Level 1 labeling flow | e2e | P0 | test_practice_reflex | guest, injected transcript via test hook for SpeechRecognition | open card, tap "Xem nghĩa", hold button, release | meaning hidden until tapped; attempt posted; score and unlock state shown | FR-47 |
| TC-27.3 | UC-27 | Level score and unlock logic | unit | P0 | test_unlock_rules | none | DT-6 rows | level score = mean of latest per item, unattempted 0; best_score max; unlock at >= 70 | OQ-45 FR-47 |
| TC-27.4 | UC-27-A1 | Boundary 69 vs 70 | API | P0 | test_practice_levels | attempts producing level-1 score 69, then 70 | read progress | 69: Level 2 locked; 70: unlocked | AC-25 |
| TC-27.5 | UC-27-A2 | best_score never decreases | API | P0 | test_practice_levels | level 2 unlocked at 90 | later attempts average 50 | best_score 90, still unlocked | OQ-45 |
| TC-27.6 | UC-27-A3 | Replay uses no network | e2e | P2 | test_practice_reflex | recording made | replay model audio and own recording | no request carries the recording (no upload endpoint call) | FR-47 |
| TC-27.7 | UC-27-A4 | Guest practice same as registered | API | P1 | test_practice_levels | `guest` | complete level 1 on seed card | progress stored under guest id | FR-3 |
| TC-27.8 | UC-27-E1 | Mic denied | e2e | P1 | test_practice_reflex | permission denied | try recording | Vietnamese guidance; listen-only usable; no attempt rows | NFR-X4 |
| TC-27.9 | UC-27-E2 | Silence creates no attempt | e2e | P2 | test_practice_reflex | empty transcript | hold and release in silence | retry message; no POST | assumed |
| TC-27.10 | UC-27-E3 | Attempt on locked level | API | P0 | test_level_locked | Level 2 locked | `POST /api/attempts` for a description sentence | 409 `level_locked`; no attempts/review_state/progress rows; `had_write` unchanged | OQ-44 AC-44 |
| TC-27.11 | UC-27-E4 | Invalid card id | API | P1 | test_practice_levels | none | `GET /api/cards/{random uuid}` | 404 | FR-47 |
| TC-27.12 | UC-27-X1 | Level 3 needs Level 2 >= 70 | API | P1 | test_practice_levels | L1 95, L2 60 | attempt on a story sentence | 409 `level_locked` | FR-47 |
| TC-27.13 | UC-27-X2 | Independent progress per user | API | P1 | test_practice_levels | two users on same seed card | user 1 unlocks | user 2 still locked | FR-3 |
| TC-27.14 | UC-27-X3 | Unlock survives reload and conversion | API | P0 | test_register | guest L2 unlocked | register; GET card | still unlocked | AC-2 AC-8 |
| TC-27.15 | UC-27-X4 | Press-and-hold uses Pointer Events | e2e | P1 | test_practice_reflex | mobile viewport | pointerdown, then pointercancel; long press context menu | recording stops, nothing submitted; contextmenu default prevented | NFR-X4 |
| TC-27.16 | UC-27-X5 | Worked example | API | P0 | test_practice_levels | 4-label card; scripted transcripts | scores 100, 80, 60, none -> 60 locked; then 4th = 100 and redo 60-item = 80 -> 90; later 50 | locked, unlocked at (100+80+80+100)/4 = 90; best_score stays 90 | OQ-45 |

## 28. UC-28 Attempts and SM-2

Calculations are specified in section 50 (DT-1..DT-4). Rounding rule used throughout: Python `round()` half-to-even is NOT assumed; the implementation must document its rule and the unit tests pin it (inputs chosen to avoid exact .5 except where stated).

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-28.1 | UC-28 | Valid attempt end to end | API | P0 | test_attempts | `guest`, seed label with accepted answers `["cup"]` | `POST /api/attempts {client_attempt_id uuid, card_id, item_type label, item_id, mode shadow, transcript "a red cup"}` | 201 `{accuracy 100, score 100, q 5, unlocks, xp 10}` p95 <= 150 ms; one attempts row (xp stored), review_state created, card_progress updated, `had_write 1` in one transaction | FR-48 FR-55 AC-42 |
| TC-28.2 | UC-28 | Accuracy matching table | unit | P0 | test_scoring | none | DT-1 rows | per table (whole-word 100; fuzzy capped 60; sentence recall) | AC-42 FR-55 |
| TC-28.3 | UC-28 | Reflex score table | unit | P0 | test_scoring | none | DT-4 rows | per table | OQ-51 FR-55 |
| TC-28.4 | UC-28 | Quality mapping table | unit | P0 | test_srs | none | DT-2 rows (95/85/75/55/25/10 and every boundary) | 5/4/3/2/1/0 per table | AC-43 OQ-47 |
| TC-28.5 | UC-28 | SM-2 transitions table | unit | P0 | test_srs | none | DT-3 rows | per table; ease floor 1.3 | AC-43 FR-56 |
| TC-28.6 | UC-28-A1 | Good answers: intervals 1, 6, then multiplied | API | P0 | test_attempts | new item; three q=5 attempts with distinct ids | post three attempts, read review_state after each | reps 1,2,3; intervals 1, 6, round(6 x ease) (ease rule pinned in DT-3); ease +0.1 per q5; `due_at = now + interval` days | OQ-47 |
| TC-28.7 | UC-28-A2 | Wrong answer resets | API | P0 | test_attempts | item with reps 3, interval 15 | attempt score 10 (q 0); another with score 55 (q 2) | reps 0, interval 1, lapses +1 each, ease -0.8 (floor 1.3) and -0.32 respectively | AC-43 |
| TC-28.8 | UC-28-A3 | Accepted answer variants | API | P1 | test_attempts | label "cup" | transcripts "cup", "a cup", "Cup!", "CUP", "cupboard" | first four accuracy 100; "cupboard" below 100 and <= 60 | OQ-48 |
| TC-28.9 | UC-28-A4 | First attempt creates default review state | API | P1 | test_attempts | no review_state | attempt q 4 | row created with ease 2.5 base, reps 0 -> 1 | FR-56 |
| TC-28.10 | UC-28-A5 | Skip is a timeout attempt | API | P0 | test_attempts | `guest` | attempt `skipped true` | accuracy 0, q 0, lapses +1, xp 2, transcript null stored, attempt counted | OQ-49 |
| TC-28.11 | UC-28-A6 | Boundary qualities through the API | API | P1 | test_attempts | scripted accuracy giving score 90, 89, 80, 79, 70, 69, 50, 49, 20, 19 | post each | q 5,4,4,3,3,2,2,1,1,0 | AC-43 |
| TC-28.12 | UC-28-E1 | Out-of-range values | API | P0 | test_attempts | `guest` | `reflex_ms -5`, `reflex_ms limit+2001`, `reflex_level 5`, `item_type "x"`, `mode "x"`; `pronunciation 150` | first five 422 and nothing written; pronunciation clamped to 100, request accepted | AC-42 |
| TC-28.13 | UC-28-E2 | Unknown item or invisible card | API | P1 | test_attempts | `guest` | random item_id; item of another card; private card of B | 404 (or 422 for mismatched item); nothing written | FR-48 |
| TC-28.14 | UC-28-E3 | Client-supplied accuracy rejected | API | P0 | test_attempts | `guest` | add `accuracy 100` or `score 100` or unknown field | 422 | AC-42 OQ-48 |
| TC-28.15 | UC-28-E4 | Network loss: retry with same id | e2e | P1 | test_network_offline | route abort once on attempts | answer, click Retry | "Chưa lưu được" then success; DB has exactly one attempt | OQ-46 |
| TC-28.16 | UC-28-E5 | CSRF on attempts | API | P0 | test_csrf | `raw` | post attempt without header | 403 | AC-17 |
| TC-28.17 | UC-28-E6 | Locked level | API | P0 | test_level_locked | see TC-27.10 | see TC-27.10 | 409 | OQ-44 |
| TC-28.18 | UC-28-E7 | Gated guest attempt | API | P0 | test_gate_grace | `gated` | attempt for a new item (no grace) | 403 second_visit (grace cases in section 5) | FR-13 |
| TC-28.19 | UC-28-X1 | Atomic transaction | API | P0 | test_attempts | fault injection in the review_state UPDATE | post attempt | 500; attempts row rolled back; card_progress unchanged; client may retry the same id | NFR-A2 |
| TC-28.20 | UC-28-X2 | Duplicate POST returns original | API | P0 | test_attempt_replay | see TC-46.1 | see TC-46.1 | 200 original; one row | OQ-46 |
| TC-28.21 | UC-28-X3 | SM-2 worked examples | unit | P0 | test_srs | none | ease 2.5, reps 2, interval 6, q 4; q 3 sequences of 20 | q4 -> interval 15 and ease 2.5; q3 -> ease 2.36; repeated q3 never below 1.3 | AC-43 |
| TC-28.22 | UC-28-X4 | Server recomputes score from transcript | API | P0 | test_attempts | `guest` | transcript "dog" for label "cup"; reflex_ms 500 | accuracy 0 and score from server; no client route to set higher | OQ-48 |
| TC-28.23 | UC-28-X5 | Concurrent attempts same item, two tabs | API | P0 | test_attempts | two threads, distinct ids | post simultaneously | both 201; two attempts rows; review_state reflects both sequentially (reps +2); no lost update | NFR-A1 |
| TC-28.24 | UC-28-X6 | Transcript length cap | API | P2 | test_attempts | `guest` | transcript of 500 and 501 chars | 201; 422 (cap value to be confirmed with Dev, assumed 500) | assumed |
| TC-28.25 | UC-28 | Attempt does not write for listen-only | API | P1 | test_attempts | none | verify no endpoint exists for listen-only results | attempts count unchanged after fallback flow (see TC-31.4) | AC-27 |

## 29. UC-29 Reflex mode R1-R4

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-29.1 | UC-29 | Start session returns up to 10 rounds | API | P0 | test_reflex | `guest` with due review_state on 3 items and many new items | `POST /api/reflex/sessions {level 1}` | 201 `{session_id, rounds <= 10}`; due items come first; then new items, weak words first; no duplicates | FR-49 |
| TC-29.2 | UC-29 | Level rules table | unit | P0 | test_scoring | none | DT-4b: R1 hint 6 s, R2 5 s, R3 3 s, R4 8 s | config values match | FR-49 |
| TC-29.3 | UC-29 | Round attempt scored server-side | API | P0 | test_reflex | session open | post attempt mode reflex, `reflex_ms 3000`, R2, transcript correct | score 80 (accuracy 100, speed 50: 60+20) | OQ-51 FR-55 |
| TC-29.4 | UC-29 | Complete session summary | API | P0 | test_reflex | 10 attempts posted | `POST /api/reflex/sessions/{id}/complete` | 200 summary: score = mean reflex_score; `completed_at` set; `reflex_progress` updated | FR-49 |
| TC-29.5 | UC-29 | Reflex session in browser | e2e | P0 | test_practice_reflex | guest, stub recognition | start R1, answer 3 rounds | hint visible, countdown ring, feedback "Phản xạ tốt" on fast answers, summary at the end | FR-49 US-1 |
| TC-29.6 | UC-29-A1 | Unlock after two consecutive sessions >= 80 | API | P0 | test_reflex | R1 sessions with 5+ answered rounds | session A at 80.0, session B at 85.0 | R2 unlocked after B; Practice unlocks unchanged | FR-61 OQ-52 |
| TC-29.7 | UC-29-A1 | Streak reset and non-counting sessions | API | P0 | test_reflex | streak_over_80 = 1 | next counted session 79.9; then a 4-answered-round session at 100 | 79.9 resets to 0; 4 rounds neither advance nor reset | OQ-52 |
| TC-29.8 | UC-29-A2 | Skip counts as answered round | API | P1 | test_reflex | session | 5 skipped attempts then complete | counts toward the 5-round minimum with score 0 | OQ-49 |
| TC-29.9 | UC-29-A3 | Fewer than 10 items | API | P1 | test_reflex | account with only 3 eligible items; and zero | start session twice | 3 rounds (never counts toward unlock); zero items returns empty-state response | FR-49 |
| TC-29.10 | UC-29-A4 | R4 scoring by highlighted label | API | P1 | test_reflex | R4 unlocked | transcript containing the label word among others | accuracy 100 via whole-word containment | OQ-50 |
| TC-29.11 | UC-29-E1 | Timeout round | API | P0 | test_reflex | R2 | attempt `reflex_ms 5000` and `6500` (limit+1500); and 7001 | first two: accuracy 0, speed 0, score 0, q 0, lapses +1; 7001 -> 422 | AC-42 |
| TC-29.12 | UC-29-E2 | Wrong but fast | API | P0 | test_reflex | R1 | transcript "dog" for "cup" at 500 ms | score <= 0.6 x accuracy (< 42 when accuracy < 70) | OQ-51 |
| TC-29.13 | UC-29-E3 | No mic falls back | e2e | P1 | test_auto_mode | mic denied | start Reflex | listen-and-repeat mode; no attempts | AC-27 |
| TC-29.14 | UC-29-E4 | Foreign session complete | API | P0 | test_reflex | A's session | B completes | 404 | FR-49 |
| TC-29.15 | UC-29-E5 | Complete twice idempotent | API | P0 | test_reflex | completed session | call complete twice | same summary; `reflex_progress` counted once | FR-49 |
| TC-29.16 | UC-29-E6 | Locked reflex level | API | P0 | test_level_locked | R1 only unlocked | `POST /api/reflex/sessions {level 3}` and an attempt tied to R3 | 409 `level_locked` | OQ-44 |
| TC-29.17 | UC-29-E7 | Gated guest start and grace | API | P0 | test_gate_grace | `gated` | start session -> 403; complete a pre-gate session in grace -> 200 | per UC-5 | FR-13 |
| TC-29.18 | UC-29-X1 | Speed boundaries | unit | P0 | test_scoring | none | DT-4 speed rows | 1000 ms -> 100; limit -> 0; above limit -> 0 | OQ-51 |
| TC-29.19 | UC-29-X2 | Exactly 80 counts | unit | P0 | test_unlock_rules | none | DT-6b rows | 80.0 counted success; 79.9 not | FR-61 |
| TC-29.20 | UC-29-X3 | Abandoned session never completed | API | P1 | test_reflex | start, post 3 attempts, no complete | read reflex_progress | unchanged; `completed_at` NULL | FR-61 |
| TC-29.21 | UC-29-X4 | Guest reflex writes under guest id | API | P1 | test_reflex | `guest` | session and attempts | rows owned by guest id | FR-3 |
| TC-29.22 | UC-29-X5 | Gate mid-session | API | P1 | test_gate_grace | see TC-5.3 | see TC-5.3 | pass | FR-13 |
| TC-29.23 | UC-29-X6 | No duplicate item; due first | API | P1 | test_reflex | seeded review_state | start 20 sessions | no duplicates within a session; due items always at the front | FR-49 |
| TC-29.24 | UC-29-X7 | R1 default unlocked, rows lazy | API | P1 | test_reflex | new user | start R1; inspect DB | allowed; `reflex_progress` row created on first completion only | OQ-52 |
| TC-29.25 | UC-29-X8 | Completed round sets had_write | API | P1 | test_usage_sessions | `guest` | post reflex attempt | `had_write 1` | FR-12 |
| TC-29.26 | UC-29-X9 | Unlock sequences table | unit | P0 | test_unlock_rules | none | DT-6b rows | per table | OQ-52 |

## 30. UC-30 Hide-timer option

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-30.1 | UC-30 | PUT settings persists | API | P0 | test_settings_hide_timer | `guest`; `reg` | `PUT /api/me/settings {hide_timer true}`; GET me | 200 and persisted | FR-50 |
| TC-30.2 | UC-30 | Ring hidden at R3, reflex_ms still recorded | e2e | P0 | test_practice_reflex | hide_timer true, R3 unlocked (DB seed) | run one round | no countdown ring element visible; attempt request body has numeric `reflex_ms` | AC-26 |
| TC-30.3 | UC-30 | Persists across reload and device login | e2e | P1 | test_practice_reflex | registered | set; reload; login on second context | setting retained both times (guest: across reload) | FR-50 |
| TC-30.4 | UC-30-A1 | Toggle off | e2e | P2 | test_practice_reflex | on | turn off | ring reappears | FR-50 |
| TC-30.5 | UC-30-A2 | Auto mode with hidden timer enforces limits | e2e | P1 | test_auto_mode | hide on | let a round time out | round ends at limit | FR-60 |
| TC-30.6 | UC-30-E1 | Non-boolean value | API | P1 | test_settings_hide_timer | `guest` | `{hide_timer "yes"}`, `{hide_timer 1}`, extra field | 422 | FR-50 |
| TC-30.7 | UC-30-E2 | Gated guest and PATCH route | API | P1 | test_settings_hide_timer | `gated`; `reg` | PUT settings; `PATCH /api/me {hide_timer}` | 403 second_visit; 422 | OQ-22 |
| TC-30.8 | UC-30-X1 | Accessible timeout without ring | e2e | P1 | test_a11y_mobile | hide on | round times out | text "hết giờ" announced in an aria-live region | NFR-X2 |
| TC-30.9 | UC-30-X2 | Setting carried over by registration | API | P1 | test_register | guest hide_timer true | register | same user_settings row, value true | FR-17 |
| TC-30.10 | UC-30-X3 | Setting deleted on login discard | API | P1 | test_login_discard | guest hide_timer true with progress | login discard | guest settings row gone; account's own setting unchanged | FR-28 |

## 31. UC-31 Hands-free auto mode and fallbacks

Browser speech recognition and TTS are replaced by a deterministic stub (section 52). Real microphone behaviour is covered by manual cases.

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-31.1 | UC-31 | One tap runs the loop | e2e | P0 | test_auto_mode | stub mic granted | tap "Tự động" | countdown, beep, mic opens, scoring, model audio plays, next round without further taps | FR-51 |
| TC-31.2 | UC-31 | Auto rounds post attempts as reflex | e2e | P1 | test_auto_mode | intercept requests | run 3 rounds | 3 attempts with mode reflex, `client_attempt_id` each | FR-51 UC-28 |
| TC-31.3 | UC-31 | Stop works at every phase | e2e | P0 | test_auto_mode | auto running | click "Dừng" in countdown, listening, scoring, audio phases (4 runs) | mic released, timers cleared, results so far saved, summary shown | FR-51 |
| TC-31.4 | UC-31-A1 | No mic: listen-and-repeat | e2e | P0 | test_auto_mode | permission denied | run auto | notice "Chưa bật micro: chế độ nghe và nhắc lại"; DB: no attempts, no review_state changes, `had_write` 0 | AC-27 |
| TC-31.5 | UC-31-A2 | Permission revoked mid-run | e2e | P2 | test_auto_mode | grant then revoke | revoke at round 2 | remaining rounds listen-and-repeat | FR-51 |
| TC-31.6 | UC-31-A3 | TTS file missing falls back | e2e | P1 | test_auto_mode | `/audio/x.mp3` returns 404 | run round | `speechSynthesis.speak` invoked (stub spy) | FR-40 UC-36-A1 |
| TC-31.7 | UC-31-E1 | No SpeechRecognition support | e2e | P1 | test_auto_mode | stub removes API | open Reflex | no-mic fallback with notice | FR-51 |
| TC-31.8 | UC-31-E2 | Autoplay blocked | e2e | P2 | test_auto_mode | stub audio.play rejects | start | "Chạm để nghe" shown; tap plays | FR-51 |
| TC-31.9 | UC-31-E3 | Gate flips during auto | e2e | P1 | test_auto_mode | see TC-5.6 | see TC-5.6 | pass | FR-13 |
| TC-31.10 | UC-31-X1 | Stop during beep or in-flight POST | e2e | P0 | test_auto_mode | delay attempts response 1 s | Stop during beep; Stop while POST pending | in-flight POST completes; no new round; no attempt after Stop; no timers (assert no requests for 3 s) | FR-51 |
| TC-31.11 | UC-31-X2 | Navigating away stops auto mode | e2e | P1 | test_auto_mode | auto running | tap Home | mic track stopped, no further requests | FR-51 |
| TC-31.12 | UC-31-X3 | Hidden tab pauses or stops | e2e | P2 | test_auto_mode | auto running | emit visibilitychange hidden | no recording while hidden (assumed behaviour; Dev to confirm) | assumed |
| TC-31.13 | UC-31-X4 | Auto with hide-timer | e2e | P2 | test_auto_mode | hide on | run 2 rounds | identical behaviour | FR-50 |
| TC-31.14 | UC-31-X5 | Listen-only earns no XP | API | P1 | test_profile_settings | account after TC-31.4 flow | `GET /api/me` | xp unchanged | OQ-23 |
| TC-31.15 | UC-31 | Real microphone and speech recognition on devices | manual | P1 | manual | iOS Safari and Android Chrome, real mic | run Practice L1 and auto mode with 5 real words | words recognised, permission prompts and denial paths behave per UC-31, no recording continues after Stop | FR-51 NFR-X4 |

## 32. UC-32 Library tabs, review queue, mastery

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-32.1 | UC-32 | Scopes mine / saved / due | API | P0 | test_library | `reg` with 2 own cards, 1 saved seed, 2 due | `GET /api/cards?scope=mine|saved|due` | mine = owned cards newest first; saved = saved; due = cards with at least one `due_at <= now` | FR-52 |
| TC-32.2 | UC-32 | Library UI with badge | e2e | P1 | test_library_explore | registered with due cards | open Library | three tabs; badge equals due CARD count | FR-52 AC-46 |
| TC-32.3 | UC-32 | Mastery per card | API | P0 | test_library | attempts of mixed modes | read card list | mastery = mean of last <= 5 combined scores (reflex_score or accuracy); labels "Chưa học", "Cần ôn", "Đang học", "Đã thuộc" | OQ-54 OQ-55 |
| TC-32.4 | UC-32-A1 | Guest Bài của tôi empty; saved seeded only in Đã lưu | API | P0 | test_library | `guest` with saved seed card | `scope=mine`, `scope=saved` | mine empty; saved contains the seed card | AC-46 OQ-53 |
| TC-32.5 | UC-32-A1 | Guest empty state UI and CTA | e2e | P1 | test_library_explore | guest | open Bài của tôi | empty state; CTA "Chụp ảnh" opens camera gate | AC-46 |
| TC-32.6 | UC-32-A2 | Registered no uploads | e2e | P2 | test_library_explore | registered new | open mine | empty state with Add-photo CTA | FR-52 |
| TC-32.7 | UC-32-A3 | Empty due list | e2e | P2 | test_library_explore | none due | open "Cần ôn lại" | "Không có bài cần ôn", badge hidden or 0 | FR-52 |
| TC-32.8 | UC-32-E1 | Invalid scope | API | P1 | test_library | `guest` | `scope=bogus` | 422 | FR-52 |
| TC-32.9 | UC-32-E2 | Gated guest | API | P1 | test_gate | `gated` | library | 403 second_visit | FR-10 |
| TC-32.10 | UC-32-X1 | Mastery boundaries | unit | P0 | test_stats | none | DT-7 rows | 59.99 Cần ôn; 60 Đang học; 84.99 Đang học; 85 Đã thuộc | OQ-54 |
| TC-32.11 | UC-32-X2 | Fewer than 5 attempts, zero attempts | unit | P1 | test_stats | none | DT-7 rows | mean of available; zero -> "Chưa học" | OQ-54 OQ-55 |
| TC-32.12 | UC-32-X3 | due_at == now is due | API | P2 | test_library | review_state due exactly at clock now | `scope=due` | included (assumed inclusive) | assumed |
| TC-32.13 | UC-32-X4 | Badge counts cards | API | P0 | test_library | one card with 3 due items | count in due scope/badge | 1 | OQ-56 AC-46 |
| TC-32.14 | UC-32-X5 | Lists after conversion | API | P1 | test_register | guest with saves and attempts | register; scopes | identical content | FR-3 |
| TC-32.15 | UC-32-X6 | Library latency | API | P2 | test_perf | 100-card fixture | 200 calls | p95 <= 200 ms | NFR-F1 |
| TC-32.16 | UC-32 | Processing or failed uploads not listed | API | P1 | test_library | upload processing/failed, no card | `scope=mine` | not listed | OQ-29 |

## 33. UC-33 Home and navigation

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-33.1 | UC-33 | Home content for guest | e2e | P0 | test_guest_home | guest | open Home | greeting "Bạn khách", streak/XP, tiles "Luyện tiếp" and "Cần ôn lại", camera button | FR-9 |
| TC-33.2 | UC-33 | Bottom nav and camera gate | e2e | P0 | test_guest_home | guest | tap each nav item; Camera item | Home, Explore, Library, Profile routes; Camera opens camera gate | FR-9 |
| TC-33.3 | UC-33 | Banner opens Register(profile), never blocks | e2e | P1 | test_guest_home | guest | tap banner; Back | Register with Back; returns to originating screen; header link "Đã có tài khoản? Đăng nhập" present | OQ-21 |
| TC-33.4 | UC-33-A1 | Registered Home | e2e | P1 | test_login | registered | open Home | no banner; camera opens Add photo | FR-54 |
| TC-33.5 | UC-33-A2 | New guest tile starts first seeded card | e2e | P2 | test_guest_home | new guest | tap "Luyện tiếp" | first seeded card Practice | FR-57 |
| TC-33.6 | UC-33-E1 | Router intercepts gate errors | e2e | P0 | test_gates | API stub returns 403 camera then 403 second_visit | trigger each | camera gate with Back; mandatory gate without Back | FR-9 |
| TC-33.7 | UC-33-E2 | Unknown route | e2e | P2 | test_guest_home | guest | open `/#/nope` | redirected to Home | FR-9 |
| TC-33.8 | UC-33-X1 | Expired session: guest Home with login entry | e2e | P1 | test_guest_home | expired registered session | open `/` | guest Home with visible login link; no error | OQ-19 |
| TC-33.9 | UC-33-X2 | Back from Home | e2e | P2 | test_guest_home | any | history.back() from Home | no blank page | FR-9 |
| TC-33.10 | UC-33-X3 | Deep link to invisible card | e2e | P1 | test_guest_home | other user's private card id | open practice URL | 404 screen with Home link | OQ-41 |

## 34. UC-34 Guest data purge and maintenance

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-34.1 | UC-34 | Purge guests idle > 180 days | API | P0 | test_maintenance | guests last seen 181 d and 10 d ago, each with data; a registered user; the system user | `run_maintenance()` | 181-d guest and all owned rows gone; 10-d guest, registered, system untouched; log lines contain counts only | FR-6 FR-62 AC-47 |
| TC-34.2 | UC-34 | Purge no-write guests after 7 days | API | P0 | test_maintenance | guest `had_write=0` for all sessions last seen 8 d ago | run | purged | OQ-20 |
| TC-34.3 | UC-34 | Same run also sweeps leases, orphan content, rate events | API | P1 | test_maintenance | expired processing row; orphan content+file; old rate_events | run | row failed; orphan rows+file deleted; events older than 1 day deleted | FR-62 OQ-57 |
| TC-34.4 | UC-34 | Idempotent re-run | API | P0 | test_maintenance | after TC-34.1 | run again; compare row counts | no change, no error | AC-47 |
| TC-34.5 | UC-34-A1 | Orphans from cookie clears purged | API | P1 | test_maintenance | 5 empty orphans 8 d old | run | all purged | OQ-20 |
| TC-34.6 | UC-34-A2 | Custom retention days | API | P2 | test_maintenance | `GUEST_RETENTION_DAYS=1` | guest idle 2 d | purged | FR-62 |
| TC-34.7 | UC-34-E1 | Mid-run failure rolls back only that user | API | P1 | test_maintenance | fault injection on the 2nd deletion | run; then run again | first user purged, second intact after failure; re-run completes | NFR-A2 |
| TC-34.8 | UC-34-E2 | Locked DB uses busy_timeout | API | P2 | test_maintenance | another connection holds a write lock 1 s | run | retries and finishes; no partial deletes | UC-35 |
| TC-34.9 | UC-34-X1 | Exactly 180 days idle | unit | P1 | test_usage_gate_logic | none | `is_stale_guest(last_seen, now, 180)` at 179 d 23 h, 180 d, 180 d + 1 s | False, False, True (strict) | assumed |
| TC-34.10 | UC-34-X2 | Day 181 guest before purge continues | API | P2 | test_maintenance | guest at 181 d, purge not run | bootstrap | same guest continues | FR-6 |
| TC-34.11 | UC-34-X3 | Registered never purged | API | P0 | test_maintenance | registered idle 5 years | run | kept | FR-6 |
| TC-34.12 | UC-34-X4 | Gated guest still purged | API | P2 | test_maintenance | `gate_required_at` set, idle 181 d | run | purged | FR-6 |
| TC-34.13 | UC-34-X5 | System user never purged | API | P0 | test_maintenance | seed present, clock +10 years | run | system user and seed cards remain | FR-45 |
| TC-34.14 | UC-34-X6 | FK cascade leaves no orphan rows | API | P0 | test_maintenance | guest with rows in every owned table | run; `PRAGMA foreign_key_check`; per-table counts | no rows for deleted id; foreign_key_check empty | FR-66 OQ-17 |
| TC-34.15 | UC-34-X7 | Empty-guest boundary 6 d vs 8 d; writer kept at 7 d | API | P0 | test_maintenance | guests: no-write 6 d, no-write 8 d, with-write 8 d | run | 6 d kept; 8 d no-write purged; with-write kept | OQ-20 |
| TC-34.16 | UC-34-X8 | GC never removes referenced or seed content | API | P0 | test_maintenance | content with card; seed content; orphan with file; file with no DB row | run | referenced and seed kept; orphan removed with file; stray file reported/removed per design (no leftover for rows that were deleted) | OQ-27 |
| TC-34.17 | UC-34-X9 | rate_events purge | API | P1 | test_maintenance | events 25 h old and 1 h old | run | old deleted, new kept | OQ-15 |
| TC-34.18 | UC-34 | CLI entry point | API | P1 | test_maintenance | temp DB | `python -m backend.app.maintenance` via subprocess twice | exit 0 both; second run no changes | FR-62 AC-47 |
| TC-34.19 | UC-34 | Scheduled at startup and every 24 h | unit | P2 | test_maintenance_schedule | fake sleep | start scheduler | runs once immediately, then after 24 h virtual, errors do not kill the loop | FR-62 |
| TC-34.20 | UC-34 | Orphan claim rule | API | P1 | test_maintenance | claim 6 d old without card; claim 8 d old without card | run | content with the 6-d claim is kept; claim and content of the 8-d case removed | Addendum#3 |

## 35. UC-35 Database concurrency, migration, seed

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-35.1 | UC-35 | Connection pragmas | API | P0 | test_db_migrations_seed | new connections from the factory (3 consecutive) | `PRAGMA journal_mode/foreign_keys/busy_timeout/synchronous` | wal, 1, 5000, 1 (NORMAL) on every connection | NFR-A1 |
| TC-35.2 | UC-35 | Two processes migrate concurrently | API | P0 | test_db_migrations_seed | empty DB file; two subprocesses starting `init_db` with a barrier file | run both | `schema_migrations` has each version once; no error; schema valid | OQ-58 AC-47 |
| TC-35.3 | UC-35 | Seed counts and stable IDs | API | P0 | test_db_migrations_seed | fresh DB | seed once; record counts and IDs | system user, prototype cards, labels, sentences, audio_assets, `moderation_status approved`, `visibility public`; `provider.call_count == 0` | FR-45 OQ-59 |
| TC-35.4 | UC-35 | Startup sweep | API | P1 | test_ai_failure_retry | expired processing row | start app | row failed | FR-65 |
| TC-35.5 | UC-35 | Second start re-applies nothing | API | P0 | test_db_migrations_seed | DB started once | start again | no migration re-run (version rows unchanged, timestamps equal), no duplicate seed rows | AC-29 |
| TC-35.6 | UC-35-A1 | New migration applies alone | API | P1 | test_db_migrations_seed | migrations dir with 001; add temp 002 | start | only 002 applied | FR-63 |
| TC-35.7 | UC-35-A2 | Startup race of two app instances | API | P1 | test_db_migrations_seed | two threads each create_app on same DB | start together | no corruption, no duplicate seed, both usable | OQ-58 |
| TC-35.8 | UC-35-A3 | Seed change keeps uuid5 IDs and history | API | P1 | test_seed_keys | user with review_state on seed label; seed_version bumped with a changed label text | re-seed | label id unchanged (uuid5 of seed_key); review_state row preserved; text updated | OQ-60 |
| TC-35.9 | UC-35-E1 | Migration SQL error rolls back | API | P0 | test_db_migrations_seed | temp migration with a bad statement 3 | start | exception, fail fast; schema_migrations unchanged; no partial tables | OQ-58 |
| TC-35.10 | UC-35-E2 | Lock timeout returns generic error | API | P2 | test_db_migrations_seed | other connection holds BEGIN IMMEDIATE for 6 s (busy_timeout shortened) | write request | 503 or 500 generic JSON, no partial writes, no SQL text | NFR-A1 |
| TC-35.11 | UC-35-E3 | Online backup consistent | API | P2 | test_db_migrations_seed | writes in progress | `sqlite3.Connection.backup` to a file | backup opens, `PRAGMA integrity_check` ok, FK check clean | NFR-A3 |
| TC-35.12 | UC-35-X1 | 50 concurrent attempts | API | P0 | test_perf | 50 users, barrier | 50 threads post attempts | all 201, zero `database is locked`; p95 <= 150 ms | NFR-F2 |
| TC-35.13 | UC-35-X2 | Writes during an in-flight AI call | API | P0 | test_upload_pipeline | see TC-20.18 | see TC-20.18 | pass | NFR-A1 |
| TC-35.14 | UC-35-X3 | Schema constraints | API | P1 | test_db_migrations_seed | raw SQL inserts | guardian_email without consent_at; registered without nickname/hash/birth_year; label x=1.5; cefr "C2" | each raises IntegrityError | FR-16 |
| TC-35.15 | UC-35-X4 | foreign_keys on each new connection | API | P0 | test_db_migrations_seed | connection factory; delete parent row | insert child with bad FK, delete user | constraint enforced on every connection incl. thread-local | OQ-17 |
| TC-35.16 | UC-35-X5 | Production seed is prototype only | API | P2 | test_db_migrations_seed | fresh DB | count cards | equals prototype card count; the 100-card generator is only importable from tests | OQ-59 |
| TC-35.17 | UC-35-X6 | Re-seed twice identical | API | P0 | test_seed_keys | seeded DB | seed again twice | identical counts and IDs; no duplicates | AC-29 AC-47 |
| TC-35.18 | UC-35-X7 | Every user-owned table cascades | API | P0 | test_db_migrations_seed | introspect `PRAGMA foreign_key_list` for all tables with a user id column | check each | FK to `users` with ON DELETE CASCADE (exceptions listed: `image_assets.first_uploaded_by` SET NULL); `card_progress`/`card_saves` also FK cards CASCADE; `cards.content_id` RESTRICT | OQ-17 FR-66 |
| TC-35.19 | UC-35-X8 | Failure in statement N rolls back whole file | API | P0 | test_db_migrations_seed | migration 002 with 5 statements, statement 4 fails | start | none of 002 applied; version absent | OQ-58 |
| TC-35.20 | UC-35 | Statement splitter | unit | P1 | test_migration_runner | SQL text with trigger body containing semicolons, comments, strings with `;` | split via `sqlite3.complete_statement` | correct statements; no `executescript` use (source scan) | OQ-58 |

## 36. UC-36 Audio playback

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-36.1 | UC-36 | audio_url served statically | API | P0 | test_audio_static | seed card | read `audio_url` from card; GET it | pattern `/audio/<slug>-<djb2>.mp3`; 200 `audio/mpeg`; cacheable (ETag or Cache-Control); no auth needed | AC-47 OQ-61 |
| TC-36.2 | UC-36 | No audio API route | API | P0 | test_audio_static | none | `GET /api/audio/1` | 404 | AC-47 |
| TC-36.3 | UC-36-A1 | NULL storage path gives null url; 404 triggers fallback | e2e | P1 | test_auto_mode | label with null url; static 404 | play | speech synthesis stub called, no error | FR-40 |
| TC-36.4 | UC-36-A2 | One asset per text+voice | API | P2 | test_upload_pipeline | see TC-20.15 | see TC-20.15 | pass | FR-40 |
| TC-36.5 | UC-36-E1 | Unknown audio file | API | P1 | test_audio_static | none | `GET /audio/nope.mp3` | 404 | NFR-F5 |
| TC-36.6 | UC-36-E2 | Gated guest gets no card payload; static still works | API | P2 | test_audio_static | `gated` | card payload; `/audio/<file>` | 403 for card; 200 for file | FR-10 |
| TC-36.7 | UC-36-X1 | Bundle size and no preload | e2e | P1 | test_perf_ui | built static assets | load `/`, sum JS+CSS transfer (uncompressed); watch audio requests | <= 300 KB; no `/audio/` request until user plays | NFR-F5 |
| TC-36.8 | UC-36-X2 | CSP allows blob and data media | e2e | P2 | test_a11y_mobile | recording replay | play a blob URL | no CSP violation in console | NFR-S5 |
| TC-36.9 | UC-36-X3 | Runtime serves frontend/audio only | API | P1 | test_audio_static | tool step copied | check every referenced file exists in `frontend/audio`; request for a docs path `/docs/audio/x.mp3` | files exist; docs path 404 | OQ-61 |
| TC-36.10 | UC-36 | File name hash matches generator | unit | P2 | test_seed_keys | sample texts from `tools/gen_audio.py` | compute slug + djb2 | name equals generator output | FR-40 |

## 37. UC-37 Accessibility and mobile

All e2e cases run at 360x640 and 390x844 unless stated. `axe-core` injected via Playwright.

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-37.1 | UC-37 | No horizontal scroll on every screen | e2e | P0 | test_a11y_mobile | guest and registered; list: Home, Explore, Practice, Reflex, Library, Profile, Register, Login, Review, Processing | visit each | `scrollWidth <= clientWidth` | NFR-X1 |
| TC-37.2 | UC-37 | Marker buttons | e2e | P0 | test_a11y_mobile | Review/Practice with markers | inspect | each marker is a `button` with `aria-label`; bounding box >= 44x44 | NFR-X2 |
| TC-37.3 | UC-37 | Text size and contrast | e2e | P1 | test_a11y_mobile | each screen | computed font-size scan; axe color-contrast | no text under 12 px; zero AA contrast violations | NFR-X2 |
| TC-37.4 | UC-37 | Registration form a11y | e2e | P0 | test_a11y_mobile | Register | tab through; submit invalid | every input has a label; errors in aria-live; logical focus order; focus on first invalid field | NFR-X3 |
| TC-37.5 | UC-37 | Gate screens keyboard behaviour | e2e | P0 | test_a11y_mobile | mandatory gate; camera gate | Tab, Shift+Tab, Escape; keyboard to Back | mandatory: no close, focus trapped in form, Escape inert; camera: Back reachable and activates | NFR-X3 |
| TC-37.6 | UC-37 | Flows work without the countdown | e2e | P1 | test_a11y_mobile | hide_timer on | complete a round | operable; timeout announced | NFR-X2 |
| TC-37.7 | UC-37-A1 | Safari iOS and Chrome Android | manual | P1 | manual | real devices | press-and-hold on practice button; pointercancel by scroll; long-press menu | recording works; no context menu; cancel does not submit | NFR-X4 |
| TC-37.8 | UC-37-A2 | Reduced motion | e2e | P2 | test_a11y_mobile | `prefers-reduced-motion: reduce` emulated | start reflex round | ring animation disabled or reduced (assumed) | assumed |
| TC-37.9 | UC-37-E1 | Mic blocked guidance is non-modal | e2e | P1 | test_a11y_mobile | permission denied | try recording | non-modal message with enable-permission link; page remains usable | NFR-X4 |
| TC-37.10 | UC-37-X1 | 200% text zoom | e2e | P2 | test_a11y_mobile | zoom emulation | open Register | all fields and submit reachable | NFR-X1 |
| TC-37.11 | UC-37-X2 | Landscape | e2e | P2 | test_a11y_mobile | 640x360 | open Practice and Reflex | controls reachable without clipping | NFR-X1 |
| TC-37.12 | UC-37-X3 | Screen reader reads gate reason | manual | P2 | manual | VoiceOver / TalkBack | open each gate | reason text announced on entry | NFR-X3 |

## 38. UC-38 Offline and network loss

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-38.1 | UC-38 | Attempt save fails offline then retry | e2e | P0 | test_network_offline | `context.set_offline(true)` during answer | answer; go online; click Retry | message "Mất kết nối, chưa lưu được"; displayed result kept; after Retry exactly one attempt row | OQ-46 |
| TC-38.2 | UC-38-A1 | Heartbeat failure is silent | e2e | P2 | test_network_offline | route abort heartbeat | wait 2 periods | no error UI; later heartbeat succeeds in same session | FR-12c |
| TC-38.3 | UC-38-A2 | Register fails offline | e2e | P1 | test_network_offline | offline on submit | submit | values kept except password; message shown | PRD#14 |
| TC-38.4 | UC-38-A3 | Upload fails offline | e2e | P1 | test_network_offline | offline during upload | retry online | success after retry | PRD#14 |
| TC-38.5 | UC-38-E1 | Timeout after server stored the write | API | P0 | test_attempt_replay | response dropped by test client | resend same `client_attempt_id` | exactly one attempt row (no duplicate, unlike the legacy wording in UC-38-E1) | OQ-46 |
| TC-38.6 | UC-38-E2 | Offline longer than idle then reconnect | e2e | P2 | test_network_offline | fake clock +31 min via hook | reconnect, answer | UC-5 behaviour (grace attempt, then gate) | UC-5 |
| TC-38.7 | UC-38-X1 | Cold start offline | e2e | P1 | test_network_offline | offline at load | open `/` | retry state (as UC-1-E1); no PWA offline mode | FR-1 |
| TC-38.8 | UC-38-X2 | Poll loop pauses offline | e2e | P2 | test_network_offline | processing screen | go offline 10 s then online | polling stops while offline, resumes after | NFR-F3 |

## 39. UC-39 Public endpoints, config, static, hygiene

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-39.1 | UC-39 | Health is public | API | P0 | test_public_endpoints | no cookies | `GET /api/health` | 200 | FR-10 |
| TC-39.2 | UC-39 | Config content, no secrets | API | P0 | test_public_endpoints | none | `GET /api/config` | avatars, CEFR [A1,A2,B1], upload limits, `GUEST_FREE_SESSIONS`, `GATE_GRACE_SECONDS`, birth-year bounds; no API key, salt, `TRUSTED_PROXY_HOPS`, secret | NFR-S2 |
| TC-39.3 | UC-39 | Static assets and CSP | API | P1 | test_public_endpoints | none | GET `/`, `/js/app.js`, `/css/app.css`, `/audio/<file>` | 200 without auth; CSP header allows same-origin scripts and blob:/data: img+media | FR-33 |
| TC-39.4 | UC-39 | User-specific JSON is no-store | API | P0 | test_security_hygiene | `reg` | `GET /api/me`, cards, bootstrap | `Cache-Control: no-store` | FR-33 |
| TC-39.5 | UC-39-A1 | Health stays up while gated | API | P2 | test_public_endpoints | `gated` | health | 200 | OQ-3 |
| TC-39.6 | UC-39-E1 | Unknown API path | API | P1 | test_public_endpoints | none | `GET /api/nope` | 404 JSON `{error}` | NFR-S6 |
| TC-39.7 | UC-39-E2 | Wrong method | API | P1 | test_public_endpoints | none | `PUT /api/health` | 405 | NFR-S6 |
| TC-39.8 | UC-39-X1 | No stack traces on server error | API | P0 | test_security_hygiene | fault injection causing unhandled exception | call endpoint | 500 generic JSON; no traceback, SQL or file path | NFR-S6 |
| TC-39.9 | UC-39-X2 | Config birth-year bounds in ICT | API | P1 | test_public_endpoints | clock 2026-12-31T18:00Z | config | max_birth_year 2017, min 1927 (computed from 2027) | OQ-10 |
| TC-39.10 | UC-39-X4 | Public vs gate-exempt matrix | API | P0 | test_public_endpoints | none | call each listed endpoint with no cookies | health/config/bootstrap succeed; heartbeat/me/register/login/logout need no gate but need CSRF/identity as specified | OQ-3 |
| TC-39.11 | UC-39-X3 | Global response scan | API | P0 | test_security_hygiene | fixtures recorded from all endpoints in the suite (collector in `TestClient` wrapper) | after the suite, scan all recorded bodies | no `token`, `token_hash`, `password_hash`, `guardian_email`, `raw_response`, raw IP keys | FR-5 FR-32 |

## 40. UC-40 Required automated acceptance suites

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-40.1 | UC-40 | AC-30 full flow | e2e | P0 | test_guest_to_registered | real server, MockProvider | 1 open `/` new visitor; 2 start Practice L1 and record an attempt; 3 tap camera, see Register with Back, press Back, continue (state intact); 4 tap camera, register age >= 16, land on upload screen with progress intact; 5 reload and still logged in; 6 close context, reopen with saved storage state, Home logged in without login screen | all steps pass | AC-30 AC-9 |
| TC-40.2 | UC-40-A1 | pytest inventory meta test | unit | P1 | test_suite_inventory | none | collect test IDs via pytest API | tests exist for: bootstrap, conversion, session rotation/revocation/expiry, rate limit, AI-once dedupe with concurrency, CSRF, upload type/size/EXIF, and AC-32..AC-47 (mapped by marker `@pytest.mark.ac("AC-n")`) | AC-31 |
| TC-40.3 | UC-40-E1 | No real long sleeps | unit | P1 | test_suite_inventory | pytest plugin | patch `time.sleep` guard (fail if > 2 s) during API tests | none violates; all time travel through `clock` | UC-40-E1 |
| TC-40.4 | UC-40-X1 | Clock is injectable everywhere | unit | P0 | test_suite_inventory | none | grep services for `datetime.now`/`time.time` outside `clock.py`; run a scenario with FakeClock | zero direct calls; scenario deterministic | UC-40-X1 |
| TC-40.5 | UC-40-X2 | MockProvider exposes call counter | unit | P0 | test_mock_provider | none | call `analyze` thrice | `call_count == 3`; deterministic result for same bytes; different bytes different result; scripted failure hooks work | UC-40-X2 |
| TC-40.6 | UC-40-X3 | E2E isolation and small idle override | e2e | P1 | test_gates | server started with `SESSION_IDLE_MINUTES=0.05` or clock endpoint (test-only) | two contexts | cookie jars isolated; second visit gate reachable in seconds | UC-40-X3 |

## 41. UC-41 Performance and capacity

Marked `@pytest.mark.slow` / `@pytest.mark.perf`; run in CI nightly and before release. Dataset: test-only 100-card fixture; machine reference: CI runner (thresholds in the use case).

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-41.1 | UC-41 | Read endpoints p95 | API | P1 | test_perf | 100-card fixture; 50 concurrent users | 20 calls each to cards, card detail, library, search, bootstrap, `GET /api/me` (XP/streak/mastery on read) | p95 <= 200 ms server-side | NFR-F1 AC-28 |
| TC-41.2 | UC-41 | Attempts p95 | API | P1 | test_perf | 50 users | 20 attempts each | p95 <= 150 ms | NFR-F2 |
| TC-41.3 | UC-41 | Mock upload to ready p95 | API | P2 | test_perf | 20 uploads | measure | p95 <= 3 s | NFR-F3 |
| TC-41.4 | UC-41 | scrypt cost and non-blocking | API | P1 | test_perf | real params | time hash/verify x20; concurrent GETs | each 50-250 ms (generous band, report only on CI variance); GET p95 stays <= 200 ms during 10 hashes | NFR-F4 |
| TC-41.5 | UC-41 | Initial payload <= 300 KB | e2e | P1 | test_perf_ui | static build | see TC-36.7 | pass | NFR-F5 |
| TC-41.6 | UC-41-A1 | Gemini latency | manual | P2 | manual | real key, staging | upload 10 photos | p50 <= 15 s; progress shown; navigation free | NFR-F3 |
| TC-41.7 | UC-41-E1 | Provider queue saturated | API | P1 | test_upload_pipeline | see TC-20.14 | see TC-20.14 | pass | NFR-A1 |
| TC-41.8 | UC-41-X1 | 50 simultaneous bootstraps | API | P0 | test_perf | no cookies | 50 threads bootstrap | all 200; exactly 50 new guest rows; no lock errors | NFR-F1 |
| TC-41.9 | UC-41-X2 | 50 concurrent logins do not starve reads | API | P1 | test_perf | 50 accounts | logins in parallel with GET cards | cards p95 <= 200 ms | NFR-F4 |

## 42. UC-42 Unshare a card

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-42.1 | UC-42 | Owner unshares | API | P0 | test_unshare_delete_card | A's public approved card; B saved it | `DELETE /api/cards/{id}/share` (A) | 200 `ShareOut{visibility private}`; `published_at` NULL; content `moderation_status` still approved; Explore no longer lists; B gets 404; B's `card_saves` row deleted | FR-58 OQ-42 Addendum#8 |
| TC-42.2 | UC-42 | Unshare in UI | e2e | P2 | test_library_explore | public card | tap "Ngừng chia sẻ" | card disappears from Explore for another context | FR-58 |
| TC-42.3 | UC-42-A1 | Already private | API | P1 | test_unshare_delete_card | private card | unshare | 200 idempotent | FR-58 |
| TC-42.4 | UC-42-A2 | Re-share afterwards | API | P1 | test_unshare_delete_card | unshared | `POST /share` | 200 public, no new moderation call | OQ-42 |
| TC-42.5 | UC-42-E1 | Non-owner / unknown | API | P0 | test_unshare_delete_card | B; random id | unshare | 404 | OQ-41 |
| TC-42.6 | UC-42-E2 | Guest | API | P0 | test_camera_gate | `guest`, `gated` | unshare | 403 camera / second_visit | AC-35 |
| TC-42.7 | UC-42-E3 | CSRF | API | P0 | test_csrf | `raw` | unshare | 403 | AC-17 |
| TC-42.8 | UC-42-X1 | In-flight explore cursor skips the card | API | P2 | test_pagination | page 1 fetched; card unshared | fetch page 2 | 200; card skipped, no error | OQ-43 |
| TC-42.9 | UC-42-X2 | Other users' progress after unshare | API | P1 | test_unshare_delete_card | B practised the card | unshare; B reads library and `GET /api/me` (XP) | B's progress/attempt rows remain; card invisible (404); saves removed (Addendum#8) | Addendum#8 |

## 43. UC-43 Delete a card

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-43.1 | UC-43 | Delete own card | API | P0 | test_unshare_delete_card | card with saves, progress, review_state, attempts | `DELETE /api/cards/{id}` | 204; cards row gone; cascades remove card_saves, card_progress, review_state, attempts for that card; content/asset/file GC'd if unreferenced and not seed | FR-58 OQ-27 AC-39 |
| TC-43.2 | UC-43 | Delete in UI | e2e | P1 | test_library_explore | owner | "Xóa thẻ" and confirm | card leaves Library; Explore if shared | FR-58 |
| TC-43.3 | UC-43-A1 | Shared card disappears for all | API | P0 | test_unshare_delete_card | public card saved by B | delete | gone from Explore and B's saved | FR-58 |
| TC-43.4 | UC-43-A2 | Content held by another card is kept | API | P0 | test_unshare_delete_card | A and B cards on same content | A deletes | content, asset and file remain; B's card works | OQ-27 |
| TC-43.5 | UC-43-A3 | Re-upload after delete | API | P1 | test_unshare_delete_card | A deleted last holder; GC ran | re-upload same bytes | either dedupe to surviving content (0 calls) or, if GC removed it, a new AI run (1 call) - both branches asserted separately | FR-58 |
| TC-43.6 | UC-43-E1 | Non-owner / unknown / other's private | API | P0 | test_unshare_delete_card | B | DELETE | 404 | OQ-41 |
| TC-43.7 | UC-43-E2 | Seed card | API | P0 | test_unshare_delete_card | registered user | DELETE seed card | 404; seed card still present | FR-58 |
| TC-43.8 | UC-43-E3 | Guest / gated / CSRF | API | P0 | test_camera_gate | `guest`, `gated`, `raw` | DELETE | 403 camera / second_visit / csrf_failed | AC-35 |
| TC-43.9 | UC-43-E4 | Double delete | API | P1 | test_unshare_delete_card | deleted card | DELETE again | 404 | FR-58 |
| TC-43.10 | UC-43-X1 | GC never deletes referenced content | API | P0 | test_unshare_delete_card | content with a second card | run GC directly | content kept (RESTRICT FK would also block) | OQ-27 |
| TC-43.11 | UC-43-X2 | Attempt after card deletion | API | P1 | test_attempts | open practice on card; card deleted | post attempt | 404 | FR-58 |
| TC-43.12 | UC-43 | Claim retained then cleaned | API | P2 | test_maintenance | deleted card, claim kept | claim < 7 d: content kept; claim > 7 d: maintenance removes claim and content | Addendum#3 |

## 44. UC-44 Guest login entry point

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-44.1 | UC-44 | Link visible everywhere for guests | e2e | P0 | test_login | guest | check Home header, Profile, Register, camera gate | "Đã có tài khoản? Đăng nhập" present on each | FR-1 OQ-19 |
| TC-44.2 | UC-44 | Opens Login with Back, no API call | e2e | P1 | test_login | guest | tap link; observe network; Back | Login screen with nickname/password; zero API requests on tap; Back restores state | FR-25 |
| TC-44.3 | UC-44 | Login from guest entry lands on Home | e2e | P0 | test_login | account exists; empty guest | log in | Home as registered account; guest removed | AC-9 |
| TC-44.4 | UC-44 | With progress the warning applies | e2e | P1 | test_login | guest with progress | submit | discard warning per UC-12 (see TC-12.2) | FR-28 |
| TC-44.5 | UC-44-A1 | Gated guest: link only on mandatory Register; login works | e2e | P0 | test_gates | `gated` guest | observe; log in | link present on Register screen only; login succeeds (exempt endpoint) | OQ-3 |
| TC-44.6 | UC-44-A2 | Hidden for registered users | e2e | P2 | test_login | registered | check UI | link absent | UC-44-A2 |
| TC-44.7 | UC-44-E1 | Wrong creds, rate limit, CSRF keep guest unchanged | API | P0 | test_login_discard | guest with progress | wrong password; locked bucket; no CSRF | 401 / 429 / 403; guest row and data intact | UC-11 UC-13 UC-18 |
| TC-44.8 | UC-44-X1 | Reveals nothing about previous account | e2e | P1 | test_login | A: never had account; B: session expired | screenshot/DOM compare of Home and Login | identical DOM/text for A and B | OQ-19 |
| TC-44.9 | UC-44-X2 | Back preserves previous state | e2e | P2 | test_login | guest mid-practice | open Login; Back | previous screen state intact | FR-9 |

## 45. UC-45 Register with reason=profile

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-45.1 | UC-45 | Register from banner returns to Profile | e2e | P0 | test_register_form | guest with progress | tap banner (Home) or Profile card; fill form age >= 16; submit | Back button present on Register; after 201 route is Profile; Profile shows registered fields; same user id; progress preserved (DB) | FR-9 FR-54 OQ-21 |
| TC-45.2 | UC-45-A1 | Back returns to origin | e2e | P1 | test_register_form | guest | open then Back | originating screen; no request; no account | OQ-21 |
| TC-45.3 | UC-45-A2 | Gate arrives meanwhile | e2e | P1 | test_gates | guest on Register(profile); clock moved +31 min; heartbeat/bootstrap | wait for heartbeat | Register becomes mandatory: Back disappears | FR-8 |
| TC-45.4 | UC-45-A3 | Login link from this screen | e2e | P2 | test_login | guest | tap link | Login opens | UC-44 |
| TC-45.5 | UC-45-E1 | Errors follow UC-8, 9, 10, 18 | API | P1 | test_register | see TC-8.x, TC-9.x, TC-10.x, TC-18.x | see those | pass | UC-8 |
| TC-45.6 | UC-45-X1 | Server never returns reason profile | API | P0 | test_camera_gate | none | parametrize all gated routes (guest, gated, non-gated) and inspect `reason` | reason in {camera, account, second_visit} only | OQ-8 |

## 46. UC-46 client_attempt_id replay

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-46.1 | UC-46 | Replay returns original with 200 | API | P0 | test_attempt_replay | first attempt 201 | resend same body | 200 identical `AttemptOut`; attempts count 1; xp, review_state, card_progress unchanged | AC-44 OQ-46 |
| TC-46.2 | UC-46-A1 | Two tabs same id concurrently | API | P0 | test_attempt_replay | two threads, barrier | post simultaneously | one 201, one 200; one row | OQ-46 |
| TC-46.3 | UC-46-A2 | Same id different user | API | P1 | test_attempt_replay | users A and B | both post same uuid | both 201; two rows | OQ-46 |
| TC-46.4 | UC-46-A3 | Replay in grace and after | API | P1 | test_attempt_replay | `gated` with an attempt made in grace | replay within grace; replay after 601 s | 200 original; 403 second_visit | UC-46-A3 |
| TC-46.5 | UC-46-E1 | Missing or non-UUID id | API | P0 | test_attempt_replay | `guest` | omit; "123"; empty string | 422 | OQ-46 |
| TC-46.6 | UC-46-E2 | Same id different payload | API | P1 | test_attempt_replay | first attempt transcript "cup" | replay with transcript "dog" and other card | 200 original result; new payload ignored; nothing new stored | Addendum#5 |
| TC-46.7 | UC-46-X1 | No offline queue | e2e | P2 | test_network_offline | offline answer | inspect localStorage/IndexedDB; reload | no queued attempts stored; replay only by manual retry | OQ-46 |
| TC-46.8 | UC-46-X2 | Replay after card deleted | API | P2 | test_attempt_replay | attempt stored; card deleted | replay | 404 | UC-46-X2 |

## 47. UC-47 level_locked

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-47.1 | UC-47 | Locked Practice and Reflex levels | API | P0 | test_level_locked | new user; Level 1 / R1 only | attempt on description sentence (L2), story (L3); `POST /api/reflex/sessions {level 2}`; attempt tied to R3 | 409 `{"error":"level_locked"}` each; no rows, XP, `had_write` unchanged | FR-47 FR-49 AC-44 |
| TC-47.2 | UC-47-A1 | Concurrent tab unlocks | API | P2 | test_level_locked | lock then unlock via another client | retry attempt | 201 | UC-47-A1 |
| TC-47.3 | UC-47-A2 | Level 1 and R1 never locked | API | P1 | test_level_locked | new user | attempt L1; start R1 | 201 | FR-47 |
| TC-47.4 | UC-47-E1 | 404 precedes 409 | API | P1 | test_level_locked | invisible card + locked level | attempt | 404 | OQ-44 |
| TC-47.5 | UC-47-E2 | second_visit precedes 409 | API | P1 | test_gate_grace | `gated` | attempt on locked level outside grace | 403 second_visit | OQ-5 |
| TC-47.6 | UC-47-X1 | 69.99 locked, 70 unlocked | unit | P0 | test_unlock_rules | none | DT-6 rows | per table | AC-25 |
| TC-47.7 | UC-47-X2 | Never relocks | unit | P1 | test_unlock_rules | none | DT-6 rows | per table | OQ-45 |
| TC-47.8 | UC-47-X3 | Practice and Reflex independent | API | P1 | test_level_locked | R2 unlocked | attempt on Practice L2 | 409 | OQ-52 |

## 48. UC-48 analysis_unavailable

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-48.1 | UC-48 | Spent budget returns 409 | API | P0 | test_ai_failure_retry | image failed 2 calls, then 2 manual retries failed (`manual_retries 2`, `ai_calls 6`) | upload again | 409 `{"error":"analysis_unavailable"}` with Vietnamese message; `provider.call_count` unchanged; `ai_calls` stays 6; status failed | FR-38 AC-40 AC-41 |
| TC-48.2 | UC-48-A1 | Other user, same bytes | API | P1 | test_ai_failure_retry | as above | user B uploads | same 409 | OQ-36 |
| TC-48.3 | UC-48-A2 | Budget not exhausted | API | P1 | test_ai_failure_retry | `manual_retries 1` | re-upload | run starts (UC-23) | OQ-34 |
| TC-48.4 | UC-48-E1 | Poll of failed image | API | P1 | test_ai_failure_retry | failed content | GET status | 200 `status failed` with same message; provider untouched | OQ-36 |
| TC-48.5 | UC-48-X1 | Cap boundary: ai_calls 5 | API | P1 | test_ai_failure_retry | `manual_retries 1`, `ai_calls 5`, provider always fails | re-upload | first call allowed (pre-call increment reaches 6), the automatic second call denied; end state failed with `ai_calls 6` (Addendum#6) | Addendum#6 |
| TC-48.6 | UC-48-X2 | Concurrent re-uploads at the boundary | API | P0 | test_ai_failure_retry | `manual_retries 1`, two threads | both re-upload | exactly one wins the last run; other attaches or gets 409; total calls never exceed 6 | OQ-36 |
| TC-48.7 | UC-48 | No claim inserted when budget exhausted | API | P1 | test_ai_failure_retry | exhausted; user C without claim | C uploads; then `GET /api/uploads/{id}` as C | 409; no upload_claims row for C; C's GET returns 404 | Addendum#6 |

## 49. UC-49 Keyset pagination

| ID | Flow | Title | Type | Pri | Module | Preconditions | Steps | Expected result | Covers |
|---|---|---|---|---|---|---|---|---|---|
| TC-49.1 | UC-49 | Walk all pages | API | P0 | test_pagination | 105 explore cards | follow `next_cursor` with limit 20 until null | every card exactly once, ordered `(created_at DESC, id DESC)`; last page `next_cursor null` | FR-59 OQ-43 |
| TC-49.2 | UC-49-A1 | Default and max limit | API | P1 | test_pagination | 60 cards | no limit; limit 50 | 20; 50 | OQ-43 |
| TC-49.3 | UC-49-A2 | Identical created_at | API | P0 | test_pagination | 45 cards with same `created_at` | page with limit 20 | ordered by id DESC; no duplicates or gaps at boundaries | OQ-43 |
| TC-49.4 | UC-49-A3 | Insert between fetches | API | P1 | test_pagination | page 1 fetched | insert newest card; fetch page 2 | no shift or repeat | OQ-43 |
| TC-49.5 | UC-49-A4 | Filter mismatch | API | P1 | test_pagination | cursor from `topic=food` | reuse with `topic=animals` | 422 `invalid_cursor` | Addendum#7 |
| TC-49.6 | UC-49-E1 | Invalid limits | API | P0 | test_pagination | none | `limit=0`, `51`, `abc`, `-1` | 422 | OQ-43 |
| TC-49.7 | UC-49-E2 | Malformed or tampered cursor | API | P0 | test_pagination | none | random string, valid base64 of junk, SQL text, truncated | 422; no 500, no SQL error | OQ-43 NFR-S3 |
| TC-49.8 | UC-49-E3 | Gated guest | API | P1 | test_gate | `gated` | paged call | 403 second_visit | FR-10 |
| TC-49.9 | UC-49-X1 | Empty result | API | P2 | test_pagination | no matches | query | `items []`, `next_cursor null` | OQ-43 |
| TC-49.10 | UC-49-X2 | Deleted or unshared card referenced by cursor | API | P1 | test_pagination | cursor points to a card then deleted | next page | 200; continues strictly after the keyset position | OQ-43 |
| TC-49.11 | UC-49-X3 | Pagination latency | API | P2 | test_perf | 100-card fixture | 200 page calls | p95 <= 200 ms | NFR-F1 |
| TC-49.12 | UC-49 | Cursor encode/decode | unit | P1 | test_cursor | none | round-trip `(created_at, id)`; tampered; wrong version; filter hash mismatch | round trip exact; others raise `InvalidCursor` | OQ-43 |

## 50. Pure-logic data tables (inputs and expected outputs)

These tables are the oracle for the `unit/` tests. Where the architecture review leaves a rounding or ordering detail open, the row is marked PIN: the Developer documents the rule in the module docstring and the test pins exactly that behaviour (flagged in the QA summary).

### DT-1 Accuracy (OQ-48), label item, accepted answers `["cup"]` unless stated

| Transcript | Accuracy | Note |
|---|---|---|
| `cup` | 100 | exact |
| `a cup` | 100 | whole-word containment |
| `Cup!` | 100 | lowercase + punctuation stripped |
| `CUP` | 100 | case |
| `ＣＵＰ` (fullwidth) | 100 | NFKC |
| `a red cup` | 100 | AC-42 |
| `cup.` | 100 | punctuation |
| `cupboard` | 55 | not a whole word; ratio 2x3/11 = 0.545 -> 55 (<= 60 cap) |
| `cups` | 60 | ratio 0.857 -> 86 capped at 60 |
| `cap` | 60 | ratio 0.667 -> 67 capped at 60 |
| `dog` | 0 | no common characters |
| empty string / skipped | 0 | |
| `my mug` with accepted `["mug","cup"]` | 100 | any accepted answer |

Sentence item `A red cup is on the table` (7 words), word-level recall via difflib matching blocks:

| Transcript | Accuracy | Note |
|---|---|---|
| identical | 100 | |
| `a red cup on table` | 71 | 5 of 7 matched = 71.4; PIN rounding (round vs floor gives 71 either way) |
| `um a red cup is on the table please` | 100 | recall only; extra words not penalised |
| `the table` | 29 | 2 of 7 = 28.6 -> 29; PIN rounding (floor would give 28) |
| empty | 0 | |

### DT-2 Quality q from score (OQ-47, AC-43)

| Score | q | | Score | q |
|---|---|---|---|---|
| 100 | 5 | | 49 | 1 |
| 95 | 5 | | 25 | 1 |
| 90 | 5 | | 20 | 1 |
| 89 | 4 | | 19 | 0 |
| 85 | 4 | | 10 | 0 |
| 80 | 4 | | 0 | 0 |
| 79 | 3 | | | |
| 75 | 3 | | | |
| 70 | 3 | | | |
| 69 | 2 | | | |
| 55 | 2 | | | |
| 50 | 2 | | | |

### DT-3 SM-2 transitions (OQ-47). Ease delta = 0.1 - (5-q) x (0.08 + 0.02 x (5-q)): q5 +0.10, q4 0.00, q3 -0.14, q2 -0.32, q1 -0.54, q0 -0.80; floor 1.3; default 2.5.

| Before (ease, reps, interval) | q | After ease | reps | interval days | lapses |
|---|---|---|---|---|---|
| 2.5, 0, 0 | 5 | 2.6 | 1 | 1 | +0 |
| 2.6, 1, 1 | 5 | 2.7 | 2 | 6 | +0 |
| 2.5, 2, 6 | 4 | 2.5 | 3 | 15 (round(6 x 2.5)) | +0 |
| 2.5, 2, 6 | 3 | 2.36 | 3 | PIN: 14 if the updated ease is used (round(6 x 2.36) = 14), 15 if the previous ease | +0 |
| 2.5, 3, 15 | 2 | 2.18 | 0 | 1 | +1 |
| 2.5, 3, 15 | 0 | 1.7 | 0 | 1 | +1 |
| 2.5, 0, 0 | 1 | 1.96 | 0 | 1 | +1 |
| 1.35, 3, 10 | 0 | 1.3 (floor) | 0 | 1 | +1 |
| 1.3, 2, 6 | 3 | 1.3 (floor) | 3 | 8 (round(6 x 1.3) = 7.8) | +0 |

Run of 20 consecutive q=3 from ease 2.5: 2.36, 2.22, 2.08, 1.94, 1.80, 1.66, 1.52, 1.38, then 1.3 for every later step (assert float tolerance 1e-9).

### DT-4 Reflex score (OQ-51): `reflex_score = 0.6 x accuracy + 0.4 x speed x [accuracy >= 70]`, `speed = clamp((limit - ms) / (limit - 1000) x 100, 0, 100)`. Limits: R1 6000 ms (hint shown), R2 5000, R3 3000, R4 8000.

| Level | reflex_ms | accuracy | speed | reflex_score |
|---|---|---|---|---|
| R2 | 3000 | 100 | 50 | 80 |
| R2 | 1000 | 100 | 100 | 100 |
| R2 | 500 | 100 | 100 | 100 |
| R2 | 5000 (= limit) | 100 | 0 | 60 (PIN: exactly at the limit with a transcript still scores; no transcript = timeout 0) |
| R2 | 5400 (timeout window) | any | 0 | 0 (timeout: accuracy forced 0) |
| R2 | 7000 (= limit + 2000) | any | n/a | accepted as timeout, score 0 |
| R2 | 7001 | n/a | n/a | rejected 422 |
| R3 | 2000 | 100 | 50 | 80 |
| R3 | 2000 | 69 | 50 (no bonus) | 41.4 |
| R2 | 3000 | 70 | 50 | 62 (42 + 20) |
| R1 | 500 | 0 (`dog`) | 100 (no bonus) | 0 |
| R1 | 500 | 60 | 100 (no bonus) | 36 |
| R4 | 4500 | 100 | 50 | 80 |

### DT-5 XP, level, streak (OQ-23)

| Case | Input | Output |
|---|---|---|
| XP per attempt | score 100 / 70 / 69 / 0 / skip | 10 / 10 / 2 / 2 / 2 |
| XP sum (AC-45) | scores 80 and 50 same day | 12 |
| Level | XP 0 | level 1, progress 0.0 |
| Level | XP 499 | level 1, progress 0.998 |
| Level | XP 500 | level 2, progress 0.0 |
| Level | XP 999 / 1000 | level 2 progress 0.998 / level 3 progress 0.0 |
| Level (AC-45) | XP 1200 | level 3, progress 0.4 |
| Streak, today = 2026-03-02 ICT | attempt days {03-01, 03-02} | 2 |
| | {03-01} only | 1 (yesterday keeps streak) |
| | {03-02} only | 1 |
| | {02-28} only | 0 |
| | {03-02, 02-28} | 1 (gap) |
| | {03-01, 02-28, 02-27}, none today | 3 |
| | none | 0 |
| ICT midnight | attempts at 2026-03-01T16:59:59Z and 2026-03-01T17:00:01Z | two different ICT days (03-01 23:59:59 and 03-02 00:00:01) |

### DT-6 Practice unlock (OQ-45). Level score = mean over the level's items of the LATEST score, unattempted = 0; `best_score` = max ever; unlock next level at best_score >= 70.

| Case | Items latest scores | Level score | best_score | Next level |
|---|---|---|---|---|
| UC-27-X5 step 1 | 100, 80, 60, none | 60 | 60 | locked |
| UC-27-X5 step 2 | 100, 80, 80, 100 | 90 | 90 | unlocked |
| UC-27-X5 step 3 | later 50, 50, 50, 50 | 50 | 90 | still unlocked |
| boundary | mean 69 / 69.99 / 70 / 70.01 | same | same | locked / locked / unlocked / unlocked |
| chain | L1 95, L2 60 | | | L3 locked |

### DT-6b Reflex unlock (OQ-52): session counts only with >= 5 answered rounds; `streak_over_80` +1 if score >= 80 else reset to 0; < 5 answered neither advances nor resets; unlock next level at streak 2.

| Sessions (score, answered) | Result |
|---|---|
| (80.0, 5), (85.0, 5) | streak 1 then 2 -> unlock |
| (80, 5), (79.9, 5) | streak 1 then 0 -> no unlock |
| (100, 4) | ignored |
| (90, 5), (100, 4), (90, 5) | 1, 1, 2 -> unlock |
| (90, 5), (70, 5), (90, 5) | 1, 0, 1 -> no unlock |
| 5 skipped rounds (score 0) | counted, resets streak |

### DT-7 Mastery (OQ-54/55): mean of last <= 5 combined scores (reflex_score for reflex mode, accuracy for shadow)

| Scores (oldest first) | Mean | Label |
|---|---|---|
| (none) | n/a | Chưa học |
| 59.99 | 59.99 | Cần ôn |
| 60 | 60 | Đang học |
| 84.99 | 84.99 | Đang học |
| 85 | 85 | Đã thuộc |
| 80, 90 | 85 | Đã thuộc |
| 50, 60, 70 | 60 | Đang học |
| 0, 100, 100, 100, 100, 100 | 100 (oldest dropped) | Đã thuộc |

### DT-8 Nickname (OQ-11): NFKC then trim, ASCII `[A-Za-z0-9_.-]`, length 3-20, denylist, not email/phone-like

| Input | Result |
|---|---|
| `ab` | reject (short) |
| `abc` | accept `abc` |
| 20 x `a` / 21 x `a` | accept / reject |
| `a b`, `a@b`, `a/b`, `😀ab`, `Nguyễn`, `аbc` (Cyrillic а) | reject (charset) |
| `Ｍinh` (fullwidth Ｍ) | accept, normalised `Minh` |
| `a.b-c_d` | accept |
| ` abc ` | accept `abc` |
| `a@b.vn`, `0912345678` | reject (looks like email / phone) |
| `admin`, `Admin`, `system` | reject (denylist, case-insensitive) |

### DT-9 Age and birth year (current year from ICT calendar; 2026 unless stated)

| birth_year | Result |
|---|---|
| 2016 | age 10: accepted, guardian required |
| 2017 | age 9: reject with "ReflexEnglish dành cho học sinh từ 10 tuổi" |
| 2011 | age 15: guardian required |
| 2010 | age 16: no guardian; guardian fields rejected |
| 1926 / 1925 | accepted / rejected |
| 2027 | reject (future) |
| `abc`, 2000.5 | reject (type) |
| clock 2026-12-31T18:00Z (2027 ICT): 2017 / 2018 | accepted (age 10) / rejected |

### DT-10 Usage session and gate

| Case | Input | Output |
|---|---|---|
| prior_sessions | sessions had_write [1, 1, 0 (current)] | 2 |
| | [1, 0, 0 (current)] | 1 |
| | current session had_write=1, no others | 0 (current excluded) |
| Gate (guest, prior, FREE, new session?) | (0, 1, yes) | none |
| | (1, 1, yes) | gate second_visit |
| | (2, 1, yes) | gate |
| | (0, 0, yes) | gate |
| | (2, 3, yes) | none |
| | (3, 3, yes) | gate |
| | (1, 1, no) | no change in same session |
| | gate flag set, (1, 3, yes) | flag cleared (OQ-6) |
| | registered or system user, any | none |

### DT-11 Sliding window (limit 5 per 900 s), failures at t = 0, 100, 200, 300, 400 s

| Query time | Allowed? | Retry-After |
|---|---|---|
| 500 | no | 400 (oldest leaves at 900) |
| 899 | no | 1 |
| 900 | yes (event aged exactly 900 s no longer counts; PIN) | n/a |
| 1000 | yes (events 0 and 100 gone, 3 left) | n/a |

### DT-12 Client IP (peer 10.0.0.9, header `X-Forwarded-For`)

| TRUSTED_PROXY_HOPS | XFF | Result |
|---|---|---|
| 0 | `1.1.1.1, 2.2.2.2` | 10.0.0.9 |
| 1 | `1.1.1.1, 2.2.2.2` | 2.2.2.2 |
| 2 | `1.1.1.1, 2.2.2.2` | 1.1.1.1 |
| 1 | `spoof, real` | real (leftmost never used) |
| 1 | absent | 10.0.0.9 |
| 3 | `1.1.1.1, 2.2.2.2` | 10.0.0.9 (fewer entries than hops: fall back to peer; PIN) |
| 1 | `garbage` | 10.0.0.9 |

### DT-12b Origin check (`APP_ORIGIN=http://localhost:8000`)

| Origin | Accepted |
|---|---|
| `http://localhost:8000` | yes |
| `HTTP://LOCALHOST:8000` | yes (scheme/host case-insensitive) |
| `http://localhost:9999`, `https://localhost:8000`, `http://localhost`, `null`, `http://localhost:8000.evil.com`, `http://evil.com#http://localhost:8000` | no |

### DT-13 Session arithmetic

| Case | Input | Result |
|---|---|---|
| idle expiry 90 d | last use 89 d / 90 d / 91 d ago | valid / expired (strict `now < expires_at`, PIN) / expired |
| absolute 365 d | age 364 / 365 / 366 d | valid / expired / expired |
| rotation | token age 29 d / 30 d / 31 d | no / no (strictly older, PIN) / yes |
| sliding | use on day 80 | expires_at = min(day 170, absolute) |

### DT-14 Retry budget (OQ-36, Addendum#6): action on upload of a known image

| ai_calls | manual_retries | status | Action |
|---|---|---|---|
| 0 | 0 | none | new run (<= 2 calls) |
| 2 | 0 | failed | allowed, manual_retries -> 1 |
| 4 | 1 | failed | allowed, manual_retries -> 2 |
| 6 | 2 | failed | 409 analysis_unavailable |
| 5 | 1 | failed | allowed but only 1 call (call allowed iff ai_calls < 6 at pre-call increment) |
| 6 | 1 | failed | 409 |
| 4 | 2 | failed | 409 |
| any | any | ready | dedupe ready, 0 calls |
| any | any | processing (live lease) | dedupe in_flight, 0 calls |

### DT-15 Review overrides (OQ-37)

| Input | Result |
|---|---|
| title 60 / 61 chars | ok / reject |
| word 1 / 40 / 41 / 0 chars | ok / ok / reject / reject |
| `Cup` and `cup` both present | reject |
| labels left 1 / 8 / 0 / 9 | ok / ok / reject / reject |
| marker x or y 0 / 1 / 1.01 / -0.01 | ok / ok / reject / reject |
| label id not in content; a brand-new label | reject; reject |
| edit meaning only | ok |

### DT-16 Image access policy and DT-16b share decision

| Viewer | Card | Access |
|---|---|---|
| owner | any own card | yes |
| anyone | seed (system) card | yes |
| non-owner or guest | public + approved | yes |
| non-owner or guest | public + pending or rejected | no (404) |
| non-owner or guest | private (incl. unshared, approved content) | no (404) |

| faces | personal_info | nsfw_or_violence | suitable | Share result |
|---|---|---|---|---|
| F | F | F | T | approved, public |
| T | F | F | T | 422 faces, rejected |
| F | T | F | T | 422 personal_info, rejected |
| F | F | T | T | 422 unsuitable, rejected |
| F | F | F | F | 422 unsuitable, rejected |
| T | T | F | T | 422 faces (PIN reason priority faces > personal_info > unsuitable) |

---

## 51. Test pyramid and file layout

Pyramid (counts are in section 55): the bulk are fast API integration tests (real SQLite, `TestClient`, injected clock/provider), backed by pure unit tests for the rule engines, and a deliberately small e2e layer for browser-only behaviour (gates, a11y, press-and-hold, auto mode, navigation, AC-30). Perf tests are API tests marked `perf`; manual tests are limited to real devices, real Gemini and legal review.

```
backend/tests/
  conftest.py              app factory, FakeClock, MockProvider, client/guest/reg/gated fixtures, DB helpers
  helpers/                 images.py (fixture generators), db.py (assertions), threads.py (barrier runner), cards100.py (test-only 100-card generator)
  unit/                    no HTTP, no app
  api/                     TestClient + real temp SQLite
e2e/
  conftest.py              uvicorn on a free port, isolated contexts, speech/audio stubs, clock control
```

Where `Type` is unit the module is under `backend/tests/unit/`; API under `backend/tests/api/`; e2e under `e2e/` (file name `<module>.py`, prefix `test_`). Every TC row carries its module; this table gives the purpose and the UC scope per module.

### 51.1 backend/tests/unit/

| Module | Scope | TCs from UC |
|---|---|---|
| test_security_tokens | token generation/hash, scrypt, dummy verify, session arithmetic (DT-13) | 1, 7, 11, 14 |
| test_nickname_validation | nickname/password rules (DT-8) | 8 |
| test_age_rules | birth year/age/guardian (DT-9) | 8 |
| test_usage_gate_logic | idle rule, prior_sessions, gate truth table, grace math, lease and stale-guest boundaries (DT-10) | 2, 3, 4, 5, 23, 34 |
| test_ratelimit_window | sliding window + Retry-After (DT-11) | 13 |
| test_client_ip | proxy hops (DT-12) | 10 |
| test_origin_check | Origin/Referer comparison (DT-12b) | 18 |
| test_scoring | accuracy and reflex score, level limits (DT-1, DT-4, DT-4b) | 28, 29 |
| test_srs | quality map and SM-2 (DT-2, DT-3) | 28 |
| test_stats | XP, level, streak, mastery (DT-5, DT-7) | 16, 32 |
| test_unlock_rules | practice and reflex unlock (DT-6, DT-6b) | 27, 29, 47 |
| test_retry_budget | AI retry budget (DT-14) | 23 |
| test_imaging | sniffing, clean/re-encode, orientation | 22 |
| test_upload_result | AnalysisResult validation, box conversion | 20 |
| test_provider_selection | Mock vs Gemini selection | 20 |
| test_card_overrides | review override validation (DT-15) | 24 |
| test_card_visibility_policy | image access and share decision (DT-16) | 25 |
| test_cursor | keyset cursor codec | 49 |
| test_migration_runner | statement splitter | 35 |
| test_seed_keys | uuid5 seed keys, audio file name hash | 35, 36 |
| test_sql_scan | no string-formatted SQL | 18 |
| test_mock_provider | MockProvider determinism and hooks | 40 |
| test_maintenance_schedule | scheduler loop | 34 |
| test_suite_inventory | meta tests: AC markers, clock discipline, sleep guard | 40 |

### 51.2 backend/tests/api/

| Module | Scope | UCs |
|---|---|---|
| test_bootstrap | guest creation, cookies, persistence, hygiene | 1, 2, 3, 19, 27 |
| test_usage_sessions | session counting, throttle | 2, 3, 29 |
| test_gate | gate, exempt list, precedence | 1, 3, 4, 16, 26, 32, 49 |
| test_gate_grace | grace window for attempts/complete | 3, 5, 28, 29, 47 |
| test_camera_gate | camera/account reasons | 5, 6, 16, 17, 20, 24, 25, 42, 43, 45 |
| test_register | conversion, taken nickname, already_registered | 4, 7, 8, 10, 27, 30, 32, 45 |
| test_register_validation | field validation through HTTP | 7, 8 |
| test_register_concurrency | double submit, races, atomicity | 7, 9 |
| test_register_ratelimit | 30/hour rule, IP rules | 7, 10 |
| test_login | login, revoke old token, timing | 11 |
| test_login_discard | discard guest, cascade | 4, 12, 30, 44 |
| test_login_ratelimit | login failure buckets | 11, 13, 18 |
| test_session_lifecycle | expiry, rotation, grace overlap | 14 |
| test_logout | logout, logout-all | 4, 15 |
| test_profile_settings | me, PATCH, settings, XP/streak | 3, 16, 30, 31 |
| test_account_delete | deletion, GC, PII | 17 |
| test_csrf | CSRF/Origin matrix | 1, 3, 7, 11, 15, 18, 19, 20, 28, 42 |
| test_guest_cookie_scenarios | cleared/blocked/multi-device | 19 |
| test_upload_pipeline | upload flow, concurrency limit, locks, audio assets | 9, 20, 36, 41 |
| test_upload_dedupe | dedupe, in-flight, races | 21 |
| test_upload_validation | type/size/pixel/bomb/EXIF/path | 20, 22 |
| test_ai_failure_retry | failures, leases, budget, analysis_unavailable | 20, 23, 35, 48 |
| test_review_save_card | review and POST /api/cards | 24 |
| test_card_visibility_share | visibility, share, moderation | 25, 26 |
| test_unshare_delete_card | unshare, delete card | 25, 42, 43 |
| test_explore_search | explore, search, save | 1, 2, 26 |
| test_practice_levels | card payload, levels, unlocks | 27 |
| test_attempts | attempts, SM-2 persistence | 1, 28, 43 |
| test_attempt_replay | idempotency | 28, 38, 46 |
| test_level_locked | 409 level_locked | 27, 28, 29, 47 |
| test_reflex | reflex sessions | 29 |
| test_settings_hide_timer | hide-timer endpoint | 30 |
| test_library | library scopes, mastery, badge | 32 |
| test_pagination | keyset pagination | 26, 42, 49 |
| test_maintenance | purge, GC, CLI | 2, 17, 19, 23, 34, 43 |
| test_db_migrations_seed | pragmas, migrations, seed, schema constraints | 7, 35 |
| test_audio_static | static audio | 4, 36 |
| test_public_endpoints | health, config, static, 404/405 | 39 |
| test_security_hygiene | response/log scan, headers, SQLi, CORS | 1, 8, 11, 14, 16, 18, 23, 39 |
| test_perf | p95 and capacity (marker perf) | 20, 32, 35, 41, 49 |

### 51.3 e2e/ (Playwright, Python)

| Spec | Scope | UCs |
|---|---|---|
| test_guest_to_registered | AC-30 headline flow | 6, 7, 14, 40 |
| test_guest_home | Home, bootstrap UX, cookies, incognito | 1, 16, 18, 19, 33 |
| test_gates | camera and mandatory gates, grace UI, router interception | 3, 4, 5, 6, 7, 9, 12, 18, 33, 40, 44, 45 |
| test_register_form | registration UX and concurrency in UI | 7, 8, 9, 45 |
| test_login | login, discard dialog, logout, profile | 6, 11, 12, 15, 16, 17, 33, 44 |
| test_practice_reflex | practice and reflex sessions, hide-timer, pointer events | 2, 27, 29, 30 |
| test_auto_mode | auto mode, fallbacks | 3, 5, 29, 30, 31, 36 |
| test_upload_review | upload, Review, share UI, XSS | 18, 20, 21, 23, 24, 25 |
| test_library_explore | Explore, Library, delete/unshare UI | 6, 26, 32, 42, 43 |
| test_a11y_mobile | viewport, axe, focus, CSP media | 24, 30, 36, 37 |
| test_network_offline | offline and retry | 1, 5, 20, 28, 38, 46 |
| test_perf_ui | Home paint and bundle size | 1, 36, 41 |

---

## 52. Test data and fixtures

### 52.1 Injected collaborators (mandatory seams)

- `create_app(settings, *, clock, provider)` builds the app with injected `Clock` and `AIProvider`; all time reads go through the clock (no `datetime.now()` in services, routers, repositories except in `clock.py`).
- `FakeClock`: `now()` (timezone-aware UTC), `advance(seconds=..., days=...)`, `set(dt)`; base instant 2026-03-02T03:00:00Z (10:00 ICT) so ICT day arithmetic is unambiguous. Server-side clock control for e2e: a test-only endpoint `POST /__test__/clock` (enabled only when `APP_ENV=test`, not routed otherwise) or a settings-file based clock; plus `SESSION_IDLE_MINUTES`, `GATE_GRACE_SECONDS`, rate limits and retention overridable by env.
- `MockProvider` (deterministic from sha256 of image bytes): `call_count`, `calls` (list of sha256), `on_enter(callback)` (used to read DB state at call time), `block_on(event)` or `delay=seconds`, `script([...])` of per-call outcomes (`ok`, `invalid_json`, `schema_fail`, `fewer_than_3_labels`, `raise`, `timeout`), `override_result(sha256 or bytes, labels=..., safety=...)`, `max_concurrency` tracker. Same bytes always return the same result; different bytes return different label sets drawn from a fixed word list (includes "cup", "plate", "dog").
- Settings fixture overrides: `APP_ORIGIN`, `DATA_DIR`, `DB_PATH`, `TRUSTED_PROXY_HOPS`, `GUEST_FREE_SESSIONS`, rate-limit sizes, `PROVIDER_TIMEOUT`, `SCRYPT_N` (small for speed in most tests; real params in TC-7.4 and perf tests), `MAX_UPLOAD_BYTES`, `MAX_PIXELS`.
- Client address override for NAT tests: `TestClient(app, client=("203.0.113.7", 50000))` per simulated device.

### 52.2 Image fixtures (all generated in code with Pillow/zlib/struct, no binary files committed; each under 100 KB except the deliberate size cases, which are generated on the fly)

| Helper | Content |
|---|---|
| `jpeg_bytes(w=640, h=480, seed=0)` | deterministic small JPEG (gradient + seed-dependent rectangles) so different seeds give different sha256 |
| `jpeg_with_gps_exif()` | JPEG with Exif IFD: GPSLatitude/Longitude, Make, Model, embedded thumbnail |
| `jpeg_orientation_6(w=40, h=20)` | EXIF orientation 6 |
| `png_with_text_chunks()` | PNG with tEXt, iTXt, eXIf |
| `webp_with_exif_xmp()` | WebP with EXIF and XMP chunks |
| `animated_webp(frames=2)`, `apng(frames=2)`, `animated_gif()` | multi-frame images |
| `gif_bytes()`, `bmp_bytes()`, `tiff_bytes()` | unsupported static formats |
| `truncated_jpeg(fraction=0.6)` | corrupt/truncated |
| `bomb_png(30000, 30000)` | hand-written PNG header (IHDR 30000x30000) plus a zlib stream of zeros emitted in chunks; file < 200 KB; never decoded by the test |
| `png_pixels(w, h)` | solid-colour PNG for 5000x5000 (exact 25 MP) and 5001x5000 |
| `jpeg_exact_size(n)` | valid JPEG padded with a COM segment to exactly n bytes (5 242 880 and +1) and a 12 MB variant |
| `html_as_jpg()`, `svg_with_script()`, `pdf_bytes()`, `polyglot_jpeg_script()` | non-image or polyglot payloads |
| `png_zero_width()` | IHDR with width 0 |
| `recompressed(jpeg, quality)` | same picture, different bytes (dedupe negative case) |
| `exif_variant(jpeg)` | same pixels, different raw bytes (UC-21-X3) |

### 52.3 Seed and bulk data

- Production seed: the prototype cards (system user, `moderation_status approved`, public), images from `backend/seed_assets/`.
- `cards100(db, n=100)` (tests only): inserts n additional public approved cards with 3-5 labels each, distinct `created_at` (plus a variant with identical `created_at` for tie-break tests), words including "cup", topics food/animals/home, CEFR A1/A2/B1; never importable from `backend/app`.
- DB seeding helpers (direct SQL through the test connection) to create aged guests (`last_seen_at`), usage sessions with `had_write`, session rows at chosen ages, `rate_events`, review_state rows with chosen `due_at`, and failed `card_contents` with chosen `ai_calls`/`manual_retries`.
- Users: `make_guest()`, `make_registered(nickname="Minh_An", birth_year=2000, under16=False)`, `make_gated_guest()`, `make_many(n)`.

### 52.4 Time travel needs

| Need | Mechanism |
|---|---|
| idle 30 min, session count, gate | `clock.advance(minutes=31)` |
| grace 600 s boundary | advance to exactly gate_at + 600 / 601 s |
| session expiry 90 d, absolute 365 d, rotation 30 d, grace 60 s | `clock.advance(days=...)` |
| streak across ICT midnight, year rollover for birth-year bounds | `clock.set(...)` with UTC instants 16:59:59Z/17:00:01Z and 2026-12-31T18:00Z |
| rate windows 15 min / 1 h / 1 day | `advance` |
| leases 90 s, poll cut-off 120 s (client) | `advance`; e2e uses Playwright `page.clock` for browser timers and the test clock endpoint for server time |
| purge 7 d / 180 d / 5 years | `advance`, then `run_maintenance()` |

### 52.5 Browser stubs (Playwright init scripts, no production test seams)

- `SpeechRecognition`/`webkitSpeechRecognition` stub whose result is set by `window.__stt.say("a red cup")`, and a variant that is absent, denied (`NotAllowedError`), or revoked mid-run.
- `speechSynthesis.speak` spy; `HTMLMediaElement.play` stub (resolve/reject for autoplay case); static audio route overrides for 404 cases.
- Network control through `page.route` (abort/delay) and `context.set_offline`.
- axe-core injected for a11y checks; viewport presets 360x640, 390x844, 640x360.

### 52.6 Shared assertion helpers

`assert_clean_response(resp, logs)` (section 0.3), `nothing_stored()` (no image_assets/card_contents/upload_claims rows and no new files), `no_orphans(user_id)` (all owned tables empty plus `PRAGMA foreign_key_check`), `run_threads(n, fn)` with `threading.Barrier`, `p95(samples)`.

---

## 53. Testability requirements for the implementation (hand-off to developers)

1. **Clock injection** everywhere (see 52.1); no hidden `datetime.now()`/`time.time()` (enforced by TC-40.4).
2. **Provider injection** into the app factory; `MockProvider` with the hooks of 52.1 shipped in `backend/app/ai/mock.py` (it is production code per project conventions, so the hooks must be inert by default).
3. **Settings injection** for every threshold in the use-case defaults, including `PROVIDER_TIMEOUT`, `LEASE`, `SCRYPT_N/r/p`, `LOGIN_NICK_LIMIT`, `LOGIN_IP_LIMIT`, `REGISTER_IP_LIMIT`, `SESSION_IDLE_MINUTES`, `GATE_GRACE_SECONDS`, `GUEST_*_RETENTION_DAYS`.
4. **Callable services**: `run_maintenance(conn, clock, settings)` and `init_db(path)` usable without starting the server; `python -m backend.app.maintenance` exits 0 and is idempotent.
5. **Fault-injection seams** reachable by monkeypatching named service/repository functions (the INSERT of usage_sessions, the users UPDATE during registration, the review_state UPDATE during an attempt, the storage write, the DB insert after file store, the per-user purge delete). Names must be stable module-level functions.
6. **Test-only e2e clock endpoint** (`/__test__/clock`) mounted only when `APP_ENV=test`; absent otherwise (TC-39.6 asserts 404 in prod config).
7. **Peer address** taken from the ASGI scope so `TestClient(client=(ip, port))` simulates NAT/IPs; `TRUSTED_PROXY_HOPS` implemented exactly per DT-12.
8. **One SQLite connection per request/thread**, `BEGIN IMMEDIATE` for write transactions; connection factory sets all pragmas on every connection (TC-35.1, 35.15).
9. **Pure modules** (`scoring.py`, `srs.py`, `stats.py`, unlock rules, nickname/age validators, cursor codec, client IP, origin check, image access policy, share decision) free of I/O so unit tests need no fixtures.
10. **Deterministic IDs and ordering**: stable `ORDER BY` with `(created_at, id)`; uuid5 seed keys.
11. **Frontend**: use the standard `SpeechRecognition`, `speechSynthesis` and `Audio` APIs only (so Playwright stubs work); markers are `button` elements with `aria-label`; gate screens expose stable test ids (`data-testid` allowed); `aria-live` regions for form errors and timeouts.
12. **Rule decisions that the tests must pin (open details to confirm with the Developer/Architect)**: SM-2 interval uses updated or previous ease (DT-3); rounding of accuracy (DT-1); `reflex_ms == limit` with a transcript (DT-4); sliding-window and expiry boundary inclusivity (DT-11, DT-13); share reason priority (DT-16b); transcript length cap (TC-28.24); fewer-entries-than-hops XFF behaviour (DT-12).

---

## 54. Acceptance-criteria matrix (AC -> primary TCs)

| AC | TCs | AC | TCs |
|---|---|---|---|
| AC-1 | 1.1, 1.2 | AC-25 | 27.4, 47.6 |
| AC-2 | 2.1, 2.2 | AC-26 | 30.2 |
| AC-3 | 6.1 | AC-27 | 31.4, 29.13 |
| AC-4 | 6.6, 20.8 | AC-28 | 26.2, 41.1 |
| AC-5 | 4.1, 4.2 | AC-29 | 35.5, 35.17 |
| AC-6 | 3.3 | AC-30 | 40.1, 7.8 |
| AC-7 | 3.2 | AC-31 | 40.2 and all P0 API tests |
| AC-8 | 7.1 | AC-32 | 5.1, 5.4, 5.8 |
| AC-9 | 14.1, 14.2 | AC-33 | 3.8, 3.9 |
| AC-10 | 11.1, 11.2 | AC-34 | 3.11, 1.5 |
| AC-11 | 7.10, 8.4 | AC-35 | 6.6, 6.7, 15.6 |
| AC-12 | 7.5, 8.17, 16.16 | AC-36 | 13.4, 10.3, 10.4 |
| AC-13 | 7.11, 8.10, 9.3 | AC-37 | 10.6, 10.7 |
| AC-14 | 13.1, 13.9 | AC-38 | 18.3, 18.11, 18.12 |
| AC-15 | 11.7, 11.11 | AC-39 | 17.3, 17.4, 17.6 |
| AC-16 | 12.1, 12.2, 12.6 | AC-40 | 24.8, 23.4, 48.1 |
| AC-17 | 18.7, 18.8, 18.9 | AC-41 | 20.3, 23.2, 23.8 |
| AC-18 | 15.1, 15.2, 15.3 | AC-42 | 28.1, 28.2, 28.12, 28.14 |
| AC-19 | 21.3, 21.9 | AC-43 | 28.4, 28.5, 28.11 |
| AC-20 | 21.1, 21.2 | AC-44 | 46.1, 47.1 |
| AC-21 | 22.4, 22.5, 22.6, 22.9 | AC-45 | 16.13, 16.14 |
| AC-22 | 22.1, 22.2 | AC-46 | 32.4, 32.5, 32.13 |
| AC-23 | 25.1, 25.16 | AC-47 | 36.1, 36.2, 35.2, 35.17, 34.18 |
| AC-24 | 25.3, 25.4, 25.5, 25.18 | | |

FR-1..FR-66 and NFR-* are covered through the UC coverage below (the BA traceability matrix maps every FR to a UC, and every UC has TCs); the Covers column of each TC names the FR/NFR it exercises. FR-64 (client IP) -> TC-10.6/10.7; FR-65 (lease) -> TC-23.8/23.12; FR-66 (cascade) -> TC-12.15, 34.14, 35.18.

---

## 55. Coverage matrix (UC -> TC) and totals

Every use-case scenario ID (primary, -A, -E, -X) of UC-1..UC-49 appears in the Flow column of at least one TC (checked flow by flow while writing; the section headings above list them in the same order as the use-case file). **Use cases without a TC: none.** Scenarios that are covered only indirectly (documented n/a or cross-referenced): UC-5-X1 (TC-5.12 proves guests cannot reach Review), UC-25-A6 and UC-25-X3 (cross-reference TC-42/43), UC-8-E3 (TC-8.15 asserts absence of a confirm field), UC-20-E6 (TC-20.10 delegates to TC-48.1).

| UC | TCs | Count | UC | TCs | Count |
|---|---|---|---|---|---|
| UC-1 | TC-1.1 to 1.17 | 17 | UC-26 | TC-26.1 to 26.18 | 18 |
| UC-2 | TC-2.1 to 2.7 | 7 | UC-27 | TC-27.1 to 27.16 | 16 |
| UC-3 | TC-3.1 to 3.19 | 19 | UC-28 | TC-28.1 to 28.25 | 25 |
| UC-4 | TC-4.1 to 4.19 | 19 | UC-29 | TC-29.1 to 29.26 | 26 |
| UC-5 | TC-5.1 to 5.15 | 15 | UC-30 | TC-30.1 to 30.10 | 10 |
| UC-6 | TC-6.1 to 6.11 | 11 | UC-31 | TC-31.1 to 31.15 | 15 |
| UC-7 | TC-7.1 to 7.22 | 22 | UC-32 | TC-32.1 to 32.16 | 16 |
| UC-8 | TC-8.1 to 8.22 | 22 | UC-33 | TC-33.1 to 33.10 | 10 |
| UC-9 | TC-9.1 to 9.13 | 13 | UC-34 | TC-34.1 to 34.20 | 20 |
| UC-10 | TC-10.1 to 10.9 | 9 | UC-35 | TC-35.1 to 35.20 | 20 |
| UC-11 | TC-11.1 to 11.16 | 16 | UC-36 | TC-36.1 to 36.10 | 10 |
| UC-12 | TC-12.1 to 12.15 | 15 | UC-37 | TC-37.1 to 37.12 | 12 |
| UC-13 | TC-13.1 to 13.17 | 17 | UC-38 | TC-38.1 to 38.8 | 8 |
| UC-14 | TC-14.1 to 14.17 | 17 | UC-39 | TC-39.1 to 39.11 | 11 |
| UC-15 | TC-15.1 to 15.12 | 12 | UC-40 | TC-40.1 to 40.6 | 6 |
| UC-16 | TC-16.1 to 16.17 | 17 | UC-41 | TC-41.1 to 41.9 | 9 |
| UC-17 | TC-17.1 to 17.15 | 15 | UC-42 | TC-42.1 to 42.9 | 9 |
| UC-18 | TC-18.1 to 18.22 | 22 | UC-43 | TC-43.1 to 43.12 | 12 |
| UC-19 | TC-19.1 to 19.12 | 12 | UC-44 | TC-44.1 to 44.9 | 9 |
| UC-20 | TC-20.1 to 20.21 | 21 | UC-45 | TC-45.1 to 45.6 | 6 |
| UC-21 | TC-21.1 to 21.13 | 13 | UC-46 | TC-46.1 to 46.8 | 8 |
| UC-22 | TC-22.1 to 22.19 | 19 | UC-47 | TC-47.1 to 47.8 | 8 |
| UC-23 | TC-23.1 to 23.20 | 20 | UC-48 | TC-48.1 to 48.7 | 7 |
| UC-24 | TC-24.1 to 24.17 | 17 | UC-49 | TC-49.1 to 49.12 | 12 |
| UC-25 | TC-25.1 to 25.19 | 19 | | | |

Flow-level check performed against the use-case file: for each UC the A-, E- and X-scenarios appear in the Flow column as follows (all present). UC-1 A1-A3, E1-E3, X1-X5; UC-2 A1-A2, E1, X1-X2; UC-3 A1-A4, E1-E2, X1-X10; UC-4 A1-A3, E1-E3, X1-X6; UC-5 A1-A3, E1-E3, X1-X3; UC-6 A1-A2, E1-E2, X1-X3; UC-7 A1-A5, E1-E6, X1-X6; UC-8 matrix rows 1-24, A1-A3, E1-E3, X1-X6; UC-9 A1-A3, E1-E3, X1-X3; UC-10 A1, E1-E2, X1-X4; UC-11 A1-A3, E1-E5, X1-X5; UC-12 A1-A3, E1-E3, X1-X6; UC-13 A1-A4, E1-E2, X1-X7; UC-14 A1-A3, E1-E4, X1-X6; UC-15 A1-A2, E1-E3, X1-X4; UC-16 A1-A2, E1-E4, X1-X4; UC-17 A1-A3, E1-E4, X1-X5; UC-18 A1-A4, E1-E8, X1-X7; UC-19 A1-A4, E1-E2, X1-X4; UC-20 A1-A3, E1-E6, X1-X7; UC-21 A1-A4, E1-E2, X1-X5; UC-22 A1-A2, E1-E9, X1-X5; UC-23 A1-A4, E1-E4, X1-X6; UC-24 A1-A3, E1-E5, X1-X5; UC-25 A1-A6, E1-E4, X1-X5; UC-26 A1-A3, E1-E5, X1-X5; UC-27 A1-A4, E1-E4, X1-X5; UC-28 A1-A6, E1-E7, X1-X6; UC-29 A1-A4, E1-E7, X1-X9; UC-30 A1-A2, E1-E2, X1-X3; UC-31 A1-A3, E1-E3, X1-X5; UC-32 A1-A3, E1-E2, X1-X6; UC-33 A1-A2, E1-E2, X1-X3; UC-34 A1-A2, E1-E2, X1-X9; UC-35 A1-A3, E1-E3, X1-X8; UC-36 A1-A2, E1-E2, X1-X3; UC-37 A1-A2, E1, X1-X3; UC-38 A1-A3, E1-E2, X1-X2; UC-39 A1, E1-E2, X1-X4; UC-40 A1, E1, X1-X3; UC-41 A1, E1, X1-X2; UC-42 A1-A2, E1-E3, X1-X2; UC-43 A1-A3, E1-E4, X1-X2; UC-44 A1-A2, E1, X1-X2; UC-45 A1-A3, E1, X1; UC-46 A1-A3, E1-E2, X1-X2; UC-47 A1-A2, E1-E2, X1-X3; UC-48 A1-A2, E1, X1-X2; UC-49 A1-A4, E1-E3, X1-X3.

**Gaps**: no use case is without a TC. Open items that block exact assertions are listed in section 53 item 12 (rule details to pin) and are carried as PIN rows in section 50.

### Totals

Total test cases: **709** (TC-1.1 to TC-49.12). Counts are mechanical (rows matching `| TC-n.m | flow | title | type | priority |`).

| Type | P0 | P1 | P2 | Total |
|---|---|---|---|---|
| unit | 32 | 15 | 6 | 53 |
| API (backend integration, httpx TestClient) | 249 | 197 | 53 | 499 |
| e2e (Playwright) | 37 | 66 | 48 | 151 |
| manual | 1 | 2 | 3 | 6 |
| **Total** | **319** | **280** | **110** | **709** |

Pyramid shape: API 70%, e2e 21%, unit 7.5%, manual 1%. The e2e share is high because the PRD places most gate/UX acceptance criteria in the browser; the P0 e2e subset (37) is the smoke suite to run on every merge, the rest nightly. Unit share is intentionally small in count but covers all the rule tables (DT-1..DT-16) with many parametrized rows each, so effective unit assertions number several hundred.

Release gates: all P0 pass; all P1 pass or have an approved waiver; P2 failures logged. Perf (`perf` marker) and manual cases run before release, not per commit.

