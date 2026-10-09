# Use Cases: ReflexEnglish Web App with Guest-First Onboarding

> Based on [PRD](../PRD.md) section 1 (FR-1..FR-54, AC-1..AC-31, NFR-*, D-1..D-12, edge-case groups 1.13 #1-#16). Domain source: [spec v1.1](../spec_v1.1.md). Prototype: `docs/reflex_app.html`.
>
> Created 2026-10-09: UC-1 through UC-41 (initial version, no earlier use-case file existed in `docs/use-cases/`).
> Updated 2026-10-09 (rev 2): aligned with the binding [architecture review](../architecture/guest_first_web_app_review.md) (OQ-1..OQ-63 resolved; the review wins over the PRD wherever they differ until the PRD is amended). Existing UC-1..UC-41 revised in place (IDs stable); new UC-42 through UC-49 appended (unshare, delete card, guest login entry, register `reason=profile`, `client_attempt_id` replay, `level_locked`, `analysis_unavailable`, keyset pagination). The open-questions list is replaced by "Resolved by architecture review" at the end. Marker "per architecture review OQ-n" = rule defined only in the review, not yet in the PRD.
> Note: the file name `guest_first_web_app_use_cases.md` is final (OQ-1: the PRD 1.15 link is renamed to this file).

## Implementation notes (lean build; PRD 1.17, plan "Deferred / deviations")

The flows below are the full design; the shipped app differs as follows. Where they conflict, this list wins.
- **No grace window (UC-5, UC-32-style flows):** a gated guest is blocked immediately on every non-exempt call; `GATE_GRACE_SECONDS` and the "pending attempt accepted for 600 s" rule do not exist.
- **No session rotation:** registered sessions use sliding idle expiry only; no rotate-on-use or rotation overlap cases.
- **Offset paging (UC-49):** lists use `offset`/`limit` (<= 50) and `has_more`, not keyset cursors.
- **Reflex R4** asks the label word (not a free sentence); Reflex unlock is simplified (>= 5 answered rounds and mean >= 80 unlocks the next level).
- **Practice tabs** (levels 1-3) show their lock state (unlock at 70%).
- **Self-check fallback:** without `SpeechRecognition` Practice lets the learner self-assess instead of auto-scoring a transcript.
- **Auto mode** without recognition (or microphone permission) runs listen-and-repeat only and posts no attempt.
- **Other:** maintenance only at startup/CLI; AI jobs use stale-on-read (120 s) and a hard cap of 6 calls, no manual-retry counter; idle is `SESSION_IDLE_SECONDS`; sharing also rejects titles/words with contact info (`share_not_allowed`, reason `text`); guest creation is limited to 60/hour/IP.

## Conventions

- IDs: `UC-n` primary flow; `UC-n-Am` alternative flow; `UC-n-Em` error flow; `UC-n-Xm` edge case. QA/E2E reference these IDs.
- HTTP calls are written at product level: `METHOD /path -> status {body keys}`. "csrf" = request carries `X-CSRF-Token` equal to the `re_csrf` cookie and a same-origin `Origin` header (FR-30), unless stated otherwise.
- Cookies: `re_device` (guest), `re_session` (registered), `re_csrf` (readable). UI strings are Vietnamese; quoted strings are normative only where the PRD quotes them, otherwise they are suggested copy.
- Error bodies: `{"error":"<code>","reason"?:...,"fields"?:[...]}` (OQ-22 envelope). Gate errors: `403 {"error":"registration_required","reason":"camera"|"account"|"second_visit"}` (reason `profile` is only a Register entry reason, never an error). Reasons: `camera` = uploads, `POST /api/cards`, share/unshare/delete card; `account` = PATCH/DELETE `/api/me`, logout-all; `profile` = skippable banner; `second_visit` = mandatory (per architecture review OQ-8).
- Dependency chain (OQ-5): identity -> `second_visit` gate -> registered check (camera/account). `second_visit` wins when both apply.
- **Exempt from the gate** (OQ-3/9): `/api/health`, `/api/config`, `/api/session/bootstrap`, `/api/session/heartbeat` (returns `{gate}`), `/api/auth/register`, `/api/auth/login`, `/api/auth/logout`, `GET /api/me`. **Grace**: a gated guest may still call `POST /api/attempts` and `POST /api/reflex/sessions/{id}/complete`, only for items/sessions that existed before `gate_required_at`, only within `GATE_GRACE_SECONDS=600` (checked against `reflex_sessions.started_at` or the attempted card's existing progress). Every other call -> 403.
- CSRF token is stable per browser (not rotated on login/register). Client rule: on `csrf_failed`, re-bootstrap once and retry once (OQ-13). When `Secure`, the CSRF cookie is `__Host-re_csrf` (OQ-28).
- Unknown JSON fields are rejected everywhere (`extra='forbid'`, `422`).
- Actors: **Visitor** (no cookies), **Guest** (`kind='guest'`), **Registered** (`kind='registered'`), **Guardian** (parent; data only, no interaction), **System** (server/maintenance), **Attacker**.
- Defaults: `GUEST_FREE_SESSIONS=1` (OQ-2), `SESSION_IDLE_MINUTES=30`, `GUEST_RETENTION_DAYS=180`, `GUEST_EMPTY_RETENTION_DAYS=7`, `GATE_GRACE_SECONDS=600`, `TRUSTED_PROXY_HOPS=0`, `MAX_UPLOAD_BYTES=5 MB`, `MAX_PIXELS=25 MP`, provider timeout 30 s, provider concurrency 2 (per process; pilot runs `--workers 1`).
- "OQ-n" references point to the architecture review decisions table; the last section maps each OQ to the UC that reflects it. Behaviour still marked **[ASSUMED]** is NOT covered by the review and is listed under "New gaps" at the end.
- Pagination, scoring, SRS, XP and unlock rules referenced by several UCs are defined once in UC-28, UC-29, UC-27 and UC-49.

---

## Part A - Guest identity, sessions, gates

## UC-1: First visit as a brand-new guest

**Actor**: Visitor (becomes Guest)
**Trigger**: Opens `/` in a browser with no cookies.
**Preconditions**: Server running, migrations and seed applied (UC-35). Browser accepts cookies.

### Primary Flow (Happy Path)
1. Browser loads static assets (`GET /`, `/js/*`, `/css/*`), public, no identity needed.
2. Client shows a skeleton (max 2 s) and calls `GET /api/config` (public) then `POST /api/session/bootstrap` (no body, no CSRF token yet; Origin header checked if present).
3. Server finds no `re_session` and no valid `re_device`; creates `users(kind='guest', cefr_level='A1')`, a `device_tokens` row holding only sha256 of a new 256-bit token, a `usage_sessions` row (`had_write=0`), and `user_settings` defaults lazily.
4. Server responds `200 {user, is_guest:true, gate:null, csrf_token, config}` with `Set-Cookie: re_device` (HttpOnly, SameSite=Lax, Path=/, Max-Age~400 d, `Secure` unless localhost) and `re_csrf` (non-HttpOnly, SameSite=Lax). Response has `Cache-Control: no-store`.
5. Client routes to Home within 2 s: greeting "Bạn khách", streak/XP, "Luyện tiếp" tile, camera button, non-blocking banner "Đăng ký để lưu tiến trình" and a header/Profile link "Đã có tài khoản? Đăng nhập" (UC-44). No welcome screen, no registration wall.
6. Seeded system cards are visible in Explore/Library (read from DB, 0 AI calls).

**Postconditions**: One guest user row, one device token hash, one usage session; cookies set; no raw token or hash in any response body or log.

### Alternative Flows
- **UC-1-A1: Localhost/dev** - On `localhost` cookies are set without `Secure`; on any other host `Secure` is present.
- **UC-1-A2: `GUEST_FREE_SESSIONS=0`** - Bootstrap returns `gate={"reason":"second_visit","mandatory":true}` immediately; first screen is Register without Back (see UC-4-A1).
- **UC-1-A3: Brand-new guest does a write immediately** - First attempt sets `usage_sessions.had_write=1` (UC-3).

### Error Flows
- **UC-1-E1: Bootstrap fails (5xx/network)** - Client shows a retry state in Vietnamese ("Không kết nối được, thử lại"); no guest is assumed; retry calls bootstrap again. If the failure occurred after the guest row was committed but before the cookie reached the browser, the next bootstrap creates another guest (an orphan guest is accepted, OQ-20; purged by UC-34 after `GUEST_EMPTY_RETENTION_DAYS=7` because it has no writes).
- **UC-1-E2: Cookies blocked by browser** - After bootstrap the client detects it did not receive/persist `re_device` or `re_csrf` (e.g., next call has no CSRF cookie) and shows a Vietnamese notice that progress cannot be saved without cookies. App stays read-only-capable for non-writing screens **[ASSUMED, see New gaps]**.
- **UC-1-E3: Foreign `Origin` on bootstrap** - `403 {"error":"csrf_failed"}`, no user created. If Origin AND Referer are both absent, bootstrap is still accepted (idempotent and harmless; OQ-28 exception).

### Edge Cases
- **UC-1-X1**: Malformed/forged `re_device` (random string, wrong length) -> treated as no cookie; a new guest is created; old cookie overwritten. No 4xx.
- **UC-1-X2**: `re_device` hash refers to a registered user (should not exist after FR-19; `device_tokens` are deleted on conversion) -> never honoured as identity; treated as invalid **[ASSUMED, see New gaps]**.
- **UC-1-X3**: Two tabs opened simultaneously with no cookies -> the client sends bootstrap as ONE shared promise per tab; two tabs can still create two guests; browser keeps the last `Set-Cookie`; the other guest is an orphan accepted by design (OQ-20) and purged after 7 days because it has no writes. Both tabs end on the same cookie identity after one more bootstrap/reload.
- **UC-1-X4**: Bootstrap latency: first Home paint <= 2 s with seeded 100+ cards.
- **UC-1-X5**: Bootstrap response JSON never contains `token`, `token_hash`, `password_hash`, `guardian_email`.

### Data Requirements
- **Input**: cookies (none), `Origin` header.
- **Output**: `{user:{id,kind,nickname|null,avatar_key,cefr_level,...}, is_guest, gate, csrf_token, config:{avatars,cefr_levels,upload limits,gate settings,min/max birth year}}`.
- **Side Effects**: INSERT `users`, `device_tokens`, `usage_sessions`; cookies set.

### Business Rules
- No welcome screen (PRD 1.15 supersedes spec section 7 flow). Gate is computed server-side only.
- **Covers**: FR-1, FR-3, FR-5, FR-7, FR-45 (seeded content visible), FR-33, AC-1, NFR-F1, NFR-X1; architecture review OQ-2, OQ-20, OQ-28.

---

## UC-2: Returning guest within the free sessions (persistence)

**Actor**: Guest
**Trigger**: Reload, return later, or open another tab.
**Preconditions**: Valid `re_device`; `prior_sessions < GUEST_FREE_SESSIONS` or no gate flag.

### Primary Flow
1. Guest completed Practice Level 1 with 80% yesterday (attempt rows, `card_progress(level=1,best_score=80)`, `card_progress(level=2,unlocked=1)`).
2. Guest reloads (same visit) or opens the app later. Client calls `POST /api/session/bootstrap`.
3. Server hashes `re_device`, finds the same user, updates `last_seen_at`, re-issues `re_device` with fresh Max-Age, continues or starts a usage session (UC-3), returns `gate:null`.
4. Client opens Home. `GET /api/cards/{id}` shows Level 2 unlocked; Library shows saved cards and "Cần ôn lại" badge from `review_state`.

**Postconditions**: Same `user.id`; no data duplicated.

### Alternative Flows
- **UC-2-A1: Second tab** - Another tab bootstraps with the same cookie; same user id; same usage session if within idle window.
- **UC-2-A2: Guest saves a seeded card / changes hide-timer** - Written under guest id (`card_saves`, `user_settings`).

### Error Flows
- **UC-2-E1: Cookie valid but guest row purged (>180 d idle, or no-write guest purged after 7 d)** - Treated as no cookie: new guest, empty progress (UC-34).

### Edge Cases
- **UC-2-X1**: Guest return after 399 days but purged at 181 d: cookie still sent; new guest silently replaces it.
- **UC-2-X2**: Server clock moves backwards -> `last_seen_at` never decreases below stored value **[ASSUMED, see New gaps]**; session math uses server time only (client clock ignored).

### Data Requirements
- **Output**: same user; **Side Effects**: UPDATE `users.last_seen_at`, `device_tokens.last_seen_at`.
- **Business Rules**: Guests may write attempts/review_state/saves/progress (FR-3).
- **Covers**: FR-2, FR-3, AC-2.

---

## UC-3: Usage-session counting ("what counts as a visit")

**Actor**: System, Guest
**Trigger**: Any bootstrap, heartbeat, or authenticated API call.
**Preconditions**: Identity resolved.

### Primary Flow
1. Bootstrap for user U. Server looks up U's latest `usage_sessions` row.
2. If none exists, or `now - last_activity_at > SESSION_IDLE_MINUTES` (30; strictly greater, so exactly 30:00 is still the same session, OQ-4), insert a new row (`started_at=now`, `had_write=0`) and evaluate the gate (UC-4). Otherwise continue that row (update `last_activity_at`).
3. A write action (attempt, card save, or completed Reflex round) sets `had_write=1`.
4. `prior_sessions` = count of U's `usage_sessions` with `had_write=1` other than the current one, recomputed every time, never stored (guests only, FR-12a; OQ-62).
5. Client sends `POST /api/session/heartbeat` (csrf) at most once per minute while foreground. Any identity-resolving call may start a usage session (the `touch` dependency) and set the gate (FR-7 vs FR-13 resolution); the touch is a conditional UPDATE at most once per 60 s per user (FR-12c) so SQLite write contention stays low.

**Postconditions**: `usage_sessions` row count reflects visits; clearing browser storage (not cookie) does not reset it (FR-12d).

### Alternative Flows
- **UC-3-A1: Two page loads 10 min apart** - Exactly 1 `usage_sessions` row (AC-7).
- **UC-3-A2: View-only first visit** - Visit with no write; return later: `prior_sessions=0`, no gate; the next visit with a write counts (AC-6).
- **UC-3-A3: `GUEST_FREE_SESSIONS=3`** - Gate appears at the start of the 4th session that has >=3 prior write sessions.
- **UC-3-A4: Background tab** - Hidden tab sends no heartbeat (client rule); if it exceeds 30 min idle and resumes, the next call starts a new session (UC-5).

### Error Flows
- **UC-3-E1: Heartbeat while gated** - Heartbeat is on the exempt list (OQ-3): `200 {gate:{reason:'second_visit',mandatory:true}}` (not 403), so a tab that sat idle learns about the gate without losing the in-progress round (UC-5). Other non-exempt calls still get 403.
- **UC-3-E2: Heartbeat without CSRF** - `403 csrf_failed`; not a session extension.

### Edge Cases
- **UC-3-X1**: Idle gap exactly 30:00 -> same session (rule is strictly "older than" 30 min, OQ-4); 30:01 -> new session.
- **UC-3-X9**: Heartbeat/any call twice within 60 s -> the second does not write (throttled conditional UPDATE); a call at 61 s does.
- **UC-3-X10 (re-evaluation, OQ-6)**: The gate is re-evaluated at every new usage-session start. If `GUEST_FREE_SESSIONS` was raised (or `prior_sessions` otherwise no longer meets the threshold), `gate_required_at` is cleared and no gate is returned.
- **UC-3-X2**: Visit that starts and ends within seconds with no write -> does not count.
- **UC-3-X3**: Two tabs both writing -> single session, `had_write=1`.
- **UC-3-X4**: Bootstrap fails midway (user created, session row not) -> next bootstrap creates the session; no duplicate rows within the same idle window (single transaction expected) **[ASSUMED]**.
- **UC-3-X5**: Client clock skewed hours -> no effect; all decisions use server time.
- **UC-3-X6**: Auto mode without mic (no attempts written) -> does not set `had_write`.
- **UC-3-X7**: Changing `hide_timer` or viewing profile is not a write action.
- **UC-3-X8**: A new usage session whose only write occurs after the gate was already set (gated) cannot happen except via grace write (UC-5).

### Data Requirements
- **Tables**: `usage_sessions(id,user_id,started_at,last_activity_at,had_write)`, `users.last_seen_at`.
- **Business Rules**: Count only write-sessions; idle timeout config-driven; server time only.
- **Covers**: FR-8 (counting half), FR-12 (incl. 12c throttle), AC-6, AC-7; OQ-3, OQ-4, OQ-6, OQ-62.

---

## UC-4: Second-visit mandatory gate (server-enforced, not skippable)

**Actor**: Guest
**Trigger**: Bootstrap starts a new usage session and `kind='guest' AND prior_sessions >= GUEST_FREE_SESSIONS`.
**Preconditions**: Guest has >=1 earlier write session; idle > 30 min since last activity.

### Primary Flow
1. Client calls `POST /api/session/bootstrap`.
2. Server starts a new session, sets `users.gate_required_at=now`, returns `gate={"reason":"second_visit","mandatory":true}` (AC-5).
3. Client shows Register with copy "Em đã luyện tập rồi - hãy tạo tài khoản để giữ tiến trình nhé.", **no Back and no close button**; links: "Đã có tài khoản? Đăng nhập" only.
4. Any other call (e.g., `GET /api/cards`, `POST /api/attempts` outside grace, `PUT /api/me/settings`) returns `403 {"error":"registration_required","reason":"second_visit"}`.
5. Exempt endpoints work: `/api/health`, `/api/config`, `/api/session/bootstrap`, `/api/session/heartbeat` (returns `{gate}`), `/api/auth/register`, `/api/auth/login`, `/api/auth/logout`, `GET /api/me` (OQ-3/9). The static `/audio/*` files are outside `/api` and stay reachable.
6. Guest registers (UC-7) or logs in (UC-12, guest discarded); `gate_required_at` is cleared "on conversion or on login (guest discarded)" (FR-11 wording per review).

**Postconditions**: Guest cannot use the product until they resolve the gate.

### Alternative Flows
- **UC-4-A1: `GUEST_FREE_SESSIONS=0`** - First bootstrap ever returns the gate; first screen is Register; default Home is never shown to anonymous visitors.
- **UC-4-A2: Gate persists across reload** - Reload, second tab, cleared localStorage/sessionStorage: next bootstrap returns the same gate because `gate_required_at` is set (FR-11).
- **UC-4-A3: Same-visit return** - Guest returns within 30 min of the previous session: no new session, no gate.

### Error Flows
- **UC-4-E1: Attacker bypasses UI** - Direct `GET /api/cards` with the guest cookie gets 403 `second_visit`. A direct `POST /api/uploads` (or `POST /api/cards`, share, `PATCH /api/me`, `DELETE /api/me`, `logout-all`) by a gated guest returns `reason:"second_visit"`, never `camera`/`account`: precedence is second_visit > camera/account (OQ-5, dependency chain order).
- **UC-4-E2: Back/Escape/browser back** - Pressing browser Back or Escape does not reveal app screens; the router re-checks the gate and re-renders Register.
- **UC-4-E3: Cleared `re_device` cookie** - Guest becomes a new guest; the gate is bypassed (accepted risk, PRD 1.13 #1; see UC-19). Guests cannot upload, so the exposure is limited.

### Edge Cases
- **UC-4-X1**: `/api/me` while gated returns the guest summary (no progress details beyond needed) and works.
- **UC-4-X2**: Static `/audio/*.mp3` remains reachable (outside `/api`); acceptable since content is public.
- **UC-4-X3**: `GUEST_FREE_SESSIONS` increased after the flag was set -> the flag stays set during the current usage session; at the next new usage-session start the gate is re-evaluated and `gate_required_at` is cleared if the guest no longer meets the threshold (OQ-6; UC-3-X10).
- **UC-4-X4**: Gate triggered while guest has no write in the new session: still mandatory.
- **UC-4-X5**: `POST /api/auth/logout` while gated guest -> idempotent `204` (anyone may call it; it clears `re_session` only, OQ-7). The guest identity and gate remain.
- **UC-4-X6**: Gated guest `PATCH /api/me`/`DELETE /api/me`/`logout-all` -> `403 registration_required` with `reason:"second_visit"` (precedence, OQ-5). A non-gated guest gets `reason:"account"` (OQ-8; UC-16-E1).

### Data Requirements
- **Tables**: `users.gate_required_at`, `usage_sessions`.
- **Business Rules**: Gate is enforced by server dependency on every `/api/*` route; client cannot override.
- **Covers**: FR-7, FR-8, FR-10, FR-11, AC-5, NFR-X3; OQ-3, OQ-5, OQ-6, OQ-7, OQ-8.

---

## UC-5: Second-visit gate arrives mid-practice (deferral, no lost work)

**Actor**: Guest
**Trigger**: Tab left open > 30 min, user resumes mid-practice/Reflex/auto mode.
**Preconditions**: Guest has `prior_sessions >= GUEST_FREE_SESSIONS` after this new session starts; round already displayed.

### Primary Flow
1. A round is on screen. The user answers; client sends `POST /api/attempts` (csrf).
2. Server sees idle > 30 min, starts a new usage session, sets `gate_required_at`.
3. Server accepts this write under the grace rule (OQ-3/9): `POST /api/attempts` and `POST /api/reflex/sessions/{id}/complete` remain allowed for a gated guest only for items/sessions that existed before `gate_required_at`, and only within `GATE_GRACE_SECONDS=600` of the gate being set (checked against `reflex_sessions.started_at` or the attempted card's existing progress). Response `201 AttemptOut`; the next heartbeat or non-exempt call surfaces the gate.
4. Client finishes the current round/summary, calls `POST /api/reflex/sessions/{id}/complete` (allowed by grace), then shows the mandatory Register screen before the next navigation.
5. After Register or Login, the user is returned to Home (not into the dead round).

**Postconditions**: In-flight result is stored; no loop; no data loss.

### Alternative Flows
- **UC-5-A1: Reflex session with remaining rounds** - Multi-round grace is defined (OQ-9): all remaining rounds of a session whose `started_at` precedes `gate_required_at` may still post attempts and be completed within the 600 s window, because each attempt references a session/item that existed before the gate. A session started AFTER the gate cannot exist (`POST /api/reflex/sessions` is gated -> 403). After 600 s every attempt is 403 and the client ends the session locally and shows the gate.
- **UC-5-A2: Auto mode** - Auto mode may finish within the grace window; client stops after the current round (Stop semantics), saves the attempt, calls complete, then shows the gate.
- **UC-5-A3: Microphone recording in progress** - Recording completes, attempt is posted (within grace it succeeds). If the grace window has expired the server returns 403 and the client shows the gate once and does NOT replay the result after registration (no offline queue, OQ-46).

### Error Flows
- **UC-5-E1: Attempt outside grace** - An attempt for an item/session that did not exist before `gate_required_at`, or any attempt after `GATE_GRACE_SECONDS` (boundary: 600 s allowed, 601 s -> 403) -> `403 registration_required/second_visit`; client does not retry, shows gate once (no infinite loop).
- **UC-5-E3: Grace on another user's session** - `POST /api/reflex/sessions/{id}/complete` for a foreign session -> 404 even within grace.
- **UC-5-E2: Network down at the grace write** - Attempt not saved; client message "Chưa lưu được kết quả" then gate; accepted loss.

### Edge Cases
- **UC-5-X1**: Gate flips while the user is on the Review/Processing screen: only guests can reach those via camera gate -> not applicable for guests (uploads need registration).
- **UC-5-X2**: Resumed tab calls `GET /api/cards` first (not an attempt) -> that call returns 403 `second_visit`; client defers gate display if a round is in progress.
- **UC-5-X3**: Gate flips for a guest on two tabs: Tab A mid-round, Tab B idle; both get 403; A defers, B shows gate immediately.

### Data Requirements
- **Tables**: `attempts`, `review_state`, `usage_sessions`, `users.gate_required_at`.
- **Business Rules**: Gate evaluated only at new-session start (D-4); never discard an in-flight round (grace 600 s, OQ-3/9).
- **Covers**: FR-13, FR-10, D-4 (PRD edge #10); OQ-3, OQ-9.

---

## UC-6: Camera / "Add photo" gate with Back option

**Actor**: Guest
**Trigger**: Taps camera / "Chụp ảnh" / "Thêm ảnh" on Home, bottom nav, or Library empty state.
**Preconditions**: Guest, no mandatory gate.

### Primary Flow
1. Client navigates to Register with `reason=camera`; no API call needed. Previous screen/state is kept in memory.
2. Register screen shows a Back button.
3. Guest taps Back -> returns to previous screen with its state intact (scroll, selected level, current card). No account created (AC-3).
4. Guest taps camera again -> gate appears again (repeats each tap, D-3).
5. Guest registers from here (UC-7); on 201 the client resumes the Add-photo flow (opens upload screen).

**Postconditions**: Guest unchanged on Back.

### Alternative Flows
- **UC-6-A1: Library empty state CTA** - "Chụp ảnh" in "Bài của tôi" triggers the same gate.
- **UC-6-A2: Login from this gate** - "Đã có tài khoản? Đăng nhập" leads to Login (UC-12); after login (UC-12/UC-44) the user lands on Home as the registered account; the add-photo flow is NOT auto-resumed (the discarded guest context is gone) **[ASSUMED, see New gaps]**.

### Error Flows
- **UC-6-E1: Direct `POST /api/uploads` by a guest** - `403 {"error":"registration_required","reason":"camera"}`; no file stored (AC-4). Same `reason:"camera"` for `POST /api/cards`, `POST|DELETE /api/cards/{id}/share`, `DELETE /api/cards/{id}`, `GET /api/uploads/{id}`. `PATCH /api/me`, `DELETE /api/me`, `POST /api/auth/logout-all` return `reason:"account"` (OQ-8; UC-16-E1).
- **UC-6-E2: Mandatory gate active** - second_visit takes precedence over camera/account (UC-4-E1, OQ-5).

### Edge Cases
- **UC-6-X1**: Browser Back button from Register(camera) behaves like the Back button.
- **UC-6-X2**: Deep link to the add-photo screen (`/#add`) by a guest -> redirected to the camera gate.
- **UC-6-X3**: A guest whose registered session expired/was revoked (UC-14-E1) is a brand-new guest and sees the camera gate, not an error, plus the "Đã có tài khoản? Đăng nhập" link (UC-44).

### Data Requirements
- **Tables**: none on Back; none for 403.
- **Covers**: FR-4, FR-9, AC-3, AC-4; OQ-5, OQ-8.

---

## Part B - Registration, login, session lifecycle

## UC-7: Registration with guest conversion (happy path)

**Actor**: Guest
**Trigger**: Submits the Register form (from camera gate, second-visit gate, Profile card, or Home banner).
**Preconditions**: Valid `re_device`; csrf available; guest has attempts/saves.

### Primary Flow
1. Guest fills: nickname "Minh_An", password (show/hide toggle), avatar preset, birth year (select, <= current-10, >= current-100; "current year" = calendar year in `Asia/Ho_Chi_Minh`, OQ-10), CEFR (A1/A2/B1). Age >= 16 so guardian fields are hidden. Nickname charset is ASCII `[A-Za-z0-9_.-]` after NFKC (OQ-11). Privacy notice link is available.
2. Client sends `POST /api/auth/register` (csrf) with `{nickname,password,avatar_key,birth_year,cefr_level}`.
3. Server validates (UC-8), records the request in the `register_ip` rate bucket and checks 30/IP/hour (UC-10), hashes password with scrypt (thread pool, per-user 16-byte salt, params stored).
4. In ONE transaction: updates the guest `users` row (`kind='registered'`, nickname, `nickname_ci`, hash, params, avatar, birth_year, cefr, `registered_at`, `gate_required_at=NULL`), creates a `sessions` row (new token), deletes the `device_tokens` row, revokes any session token the browser presented.
5. Server returns `201 {user,...}` (no hash, no guardian email) with `Set-Cookie: re_session` (HttpOnly, SameSite=Lax, Max-Age 90 d) and an expiring `re_device`.
6. Client keeps the user on the flow: for reason `camera` it resumes Add-photo; for `second_visit` it goes to Home; for `profile` it returns to Profile (UC-45). The CSRF token is NOT rotated by registration (OQ-13), so other tabs keep working.

**Postconditions**: `users.id` unchanged; all attempts, review_state, card_saves, card_progress, reflex_progress, usage_sessions remain; device is now a registered device (AC-8).

### Alternative Flows
- **UC-7-A1: Under-16 registration** - Birth year gives age < 16: form reveals guardian email + consent checkbox ("Cha mẹ/người giám hộ của em đồng ý cho em sử dụng ReflexEnglish và lưu thông tin tối thiểu"). Request includes `guardian_email` and `guardian_consent=true`; server stores `guardian_email` and `guardian_consent_at=now`; no response ever contains the email (AC-12). No email is sent.
- **UC-7-A5: Register from the Profile card/banner** - `reason=profile`; skippable; Back returns to Profile; success returns to Profile (UC-45).
- **UC-7-A2: Age exactly 16 by year difference** - e.g., current year 2026 (Asia/Ho_Chi_Minh), birth year 2010: age 16 -> no guardian fields; if present they are rejected `422` (FR-16).
- **UC-7-A3: Registering from the second-visit gate** - Same flow; clears `gate_required_at`; all gated endpoints work immediately after.
- **UC-7-A4: Registering from the camera gate** - After 201 the upload screen opens with previous progress intact (AC-30).

### Error Flows
- **UC-7-E1: Validation failure** - `422` with field errors; user row untouched; no session cookie; form keeps typed values except password (UC-8).
- **UC-7-E2: Nickname taken** - `409 {"error":"nickname_taken"}`; guest unchanged; nickname field highlighted; focus moved to it; `aria-live` message (UC-8).
- **UC-7-E3: Rate limited** - `429` (UC-10).
- **UC-7-E4: CSRF fail** - `403 csrf_failed` (UC-18).
- **UC-7-E5: DB error mid-transaction** - Full rollback: user remains guest with cookie intact; client shows generic retry message; retry is safe.
- **UC-7-E6: Already registered (other tab or retry)** - Request carries a valid `re_session` -> `409 {"error":"already_registered"}` (UC-9, OQ-14). Without a valid `re_session`, `nickname_taken` is returned and the UI offers "Đăng nhập".

### Edge Cases
- **UC-7-X1**: Guest gated by second-visit gate registers; `usage_sessions` retained (counts irrelevant after registration).
- **UC-7-X2**: Password never appears in the 201/422 body, logs, or DOM after submit (cleared).
- **UC-7-X3**: scrypt takes 50-250 ms and runs off the event loop; concurrent `GET /api/health` stays responsive while 10 registrations run.
- **UC-7-X4**: Avatar not in `config.avatars` -> `422` for `avatar_key`.
- **UC-7-X5**: `cefr_level=B2` -> `422` (accepted values A1|A2|B1).
- **UC-7-X6**: Birth-year select spans `current_year-10` down to `current_year-100`; the year is the calendar year in `Asia/Ho_Chi_Minh`, so a request at 2026-12-31 18:00 UTC (= 2027-01-01 01:00 ICT) uses 2027 (OQ-10). Legal sufficiency stays with the PO (OQ-63).

### Data Requirements
- **Input**: nickname, password, avatar_key, birth_year, cefr_level, [guardian_email, guardian_consent].
- **Output**: `201 {user}`; cookies.
- **Tables**: `users` (UPDATE), `sessions` (INSERT), `device_tokens` (DELETE), `rate_events` (INSERT, bucket `register_ip`).
- **Business Rules**: In-place conversion, one transaction, same id; password hashed scrypt N>=2^14, r=8, p=1, `hmac.compare_digest` on verify; personal data minimal (NFR-P1).
- **Covers**: FR-14, FR-16, FR-17, FR-19, FR-21, AC-8, AC-12, AC-30, NFR-P1, NFR-P2, NFR-F4.

---

## UC-8: Registration validation (nickname, password, age, guardian, birth year)

**Actor**: Guest / Visitor
**Trigger**: Submits `POST /api/auth/register` with invalid or borderline data.
**Preconditions**: csrf valid.

### Primary Flow (validation matrix; every row is one test)
1. Server trims and NFKC-normalises the nickname, then validates each field; on any failure returns `422 {"error":"validation_error","fields":[{field,code,message_vi}]}` listing all failing fields, never echoing the password, creating/changing nothing.
2. Client highlights each failing field, announces messages via `aria-live`, keeps typed values (except password), focus to first invalid field.

| # | Input | Expected |
|---|---|---|
| 1 | nickname 2 chars ("ab") | 422 nickname |
| 2 | nickname 3 chars ("abc") | accepted |
| 3 | nickname 20 chars | accepted; 21 chars -> 422 |
| 4 | nickname with space, "@", emoji, "/", any non-ASCII character (e.g. "Nguyễn", Cyrillic "а") | 422 with a Vietnamese message naming the allowed charset (OQ-11); fullwidth "Ｍ" is NFKC-folded to ASCII first and then accepted |
| 5 | nickname `a.b-c_d` (dot, hyphen, underscore) | accepted |
| 6 | nickname only after trim satisfying length (" abc ") | accepted as "abc" |
| 7 | nickname looks like email ("a@b.vn") or phone ("0912345678") | 422 |
| 8 | nickname in reserved/profanity denylist ("admin", "system") | 422 |
| 9 | password 7 chars | 422; 8 chars ok; 128 ok; 129 -> 422 |
| 10 | password equals nickname | 422 |
| 11 | password in common-password list ("12345678", "password") | 422 (weak password) |
| 12 | avatar_key not preset | 422 |
| 13 | birth_year = current-10 (age 10) | accepted (guardian required, age<16) |
| 14 | birth_year = current-9 (age 9) | 422 with message "ReflexEnglish dành cho học sinh từ 10 tuổi" |
| 15 | birth_year = current+1 (future) | 422 |
| 16 | birth_year = current-100 | accepted; current-101 -> 422 |
| 17 | birth_year non-integer / string | 422 |
| 18 | age < 16, no `guardian_email` | 422 on guardian_email, nothing changes (AC-11) |
| 19 | age < 16, email present, `guardian_consent` false or missing | 422 on guardian_consent (AC-11) |
| 20 | age < 16, malformed guardian email ("a@", "a b@c.vn") | 422 |
| 21 | guardian email 254 chars valid vs 255 chars | accepted / 422 |
| 22 | age >= 16 with `guardian_email` or `guardian_consent` present | 422 (guardian fields rejected) |
| 23 | unknown field (`role`, `kind`, `is_admin`) | 422 (extra='forbid') |
| 24 | missing required field | 422 |

**Postconditions**: No state change on any 422.

### Alternative Flows
- **UC-8-A1: Nickname taken (case-insensitive)** - "Minh_An" exists (registered); submit "minh_an" -> `409 {"error":"nickname_taken"}`; submitting guest keeps all progress and cookies (AC-13).
- **UC-8-A2: Nickname available after the other account deleted** - Succeeds.
- **UC-8-A3: Guest switches birth year after typing guardian fields** - UI hides guardian fields; client must omit them from the request (else 422 per row 22).

### Error Flows
- **UC-8-E1: Nickname taken by fullwidth look-alike** - NFKC folds fullwidth letters ("Ｍinh_An") to the same `nickname_ci` -> 409. Cross-script look-alikes (Cyrillic "а") never reach the uniqueness check: the ASCII-only charset rejects them with 422 (OQ-11).
- **UC-8-E2: Nickname equals a guest-only artifact** - Guests have no nickname, so no conflict.
- **UC-8-E3: Password confirm** - No confirm-password field and no password reset: accepted product limitation (OQ-12); a mismatch case does not exist.

### Edge Cases
- **UC-8-X1**: `422` body must not include the submitted password (grep response and logs).
- **UC-8-X2**: Guardian email never returned by any endpoint (`/api/me`, bootstrap, login, register) (FR-32, NFR-P2).
- **UC-8-X3**: Nickname of leading/trailing whitespace or NBSP -> trimmed/rejected consistently.
- **UC-8-X4**: Nickname with Vietnamese diacritics ("Nguyễn") -> `422` (ASCII only, OQ-11) with a Vietnamese message suggesting letters/digits/`_ . -` without diacritics.
- **UC-8-X5**: `guardian_consent` provided as string "true" -> `422` (strict boolean) **[ASSUMED]**.
- **UC-8-X6**: Turning-16 boundary: year difference only, using the `Asia/Ho_Chi_Minh` calendar year; a student born in Dec 2010 registering in Jan 2026 has age 2026-2010 = 16 by year difference although only 15 in real life -> no guardian required (documented behaviour, OQ-10). Legal sufficiency stays with the PO and is release-blocking for under-16 production sign-ups, not for the build (OQ-63).

### Data Requirements
- **Tables**: `users` (read for uniqueness), no writes on failure.
- **Business Rules**: FR-15/16 rules; uniqueness also enforced by DB partial unique index on `nickname_ci WHERE kind='registered'`.
- **Covers**: FR-15, FR-16, FR-20, FR-31, AC-11, AC-12, AC-13, NFR-S7, NFR-X3.

---

## UC-9: Registration concurrency (double-submit, race, multi-tab)

**Actor**: Guest, second tab/session
**Trigger**: Double click, retry after timeout, two tabs, or two users with the same nickname.
**Preconditions**: Guest with progress.

### Primary Flow (double-submit)
1. Guest double-clicks Submit; two `POST /api/auth/register` arrive with the same `re_device`.
2. Client should also disable the button after first click.
3. First request converts the guest and returns `201`.
4. Second request finds the user already `kind='registered'` inside its transaction and returns `409 {"error":"already_registered"}` with no side effects (no second session, no changed hash).

**Postconditions**: Exactly one conversion; exactly one valid session (the 201's) remains.

### Alternative Flows
- **UC-9-A1: Two users, same nickname, simultaneous** - Two distinct guests submit "Nam_01" at once; the unique index lets one win (201), the loser gets `409 nickname_taken` and remains a guest with progress intact (FR-20).
- **UC-9-A2: Register in tab 2 while tab 1 is a guest mid-action** - Browser cookie jar now has `re_session` and no `re_device`. Tab 1's next request carries `re_session`; server resolves the registered user (same id). Because the CSRF token is stable per browser and NOT rotated on login/register (OQ-13), tab 1's header still matches the cookie and its attempt is accepted under the registered identity. Safety net: if a `403 csrf_failed` ever occurs (e.g. cookie cleared), the client re-bootstraps once and retries once; no error loop; no new guest created.
- **UC-9-A3: Upload still processing in another context** - Not possible as a guest; a registered user's in-flight upload continues and attaches to the same user id.

### Error Flows
- **UC-9-E1: Retry after lost response** - 201 lost (timeout) so the browser never stored cookies, still holding `re_device` (token row now deleted). Retry has no valid guest and no valid `re_session`: the server takes the FR-18 direct-registration path, which fails with `409 nickname_taken` (the nickname now belongs to the converted account). Accepted (OQ-14): the UI shows "Nickname đã được dùng" plus an "Đăng nhập" button; the user logs in (progress intact on that account; the new empty guest is discarded without warning).
- **UC-9-E2: Retry with valid `re_session`** - `409 already_registered` (OQ-14).
- **UC-9-E3: Second tab submits after first succeeded** - `409 already_registered`; client should navigate to Home using `/api/session/bootstrap`.

### Edge Cases
- **UC-9-X1**: 10 parallel register calls for one guest -> exactly one 201 and nine 409; user count unchanged by the others.
- **UC-9-X2**: Tab 1 sends `POST /api/attempts` with stale `re_device` only (cookie jar not shared, e.g., different container) -> invalid device cookie -> client falls back to bootstrap (no error screen).
- **UC-9-X3**: Registration commit and `device_tokens` delete atomic; a crash between steps leaves no half-converted row.

### Data Requirements
- **Tables**: `users`, `sessions`, `device_tokens`.
- **Business Rules**: Idempotent conversion via transaction; unique index is the single arbiter.
- **Covers**: FR-17, FR-20, FR-18 (partly), AC-8, AC-13, AC-31 (race), PRD edge #4, #5, #7; OQ-13, OQ-14.

---

## UC-10: Registration without a guest cookie, and registration rate limit

**Actor**: Visitor (cookie cleared / direct API), Attacker
**Trigger**: `POST /api/auth/register` with no valid `re_device`.
**Preconditions**: csrf valid (bootstrap issued `re_csrf`).

### Primary Flow
1. A Visitor opens `/` (bootstrap creates a guest, UC-1) and registers: normal conversion (UC-7). Direct API call without any bootstrap needs a CSRF cookie, so it requires a prior bootstrap.
2. If the guest cookie is missing/invalid at submit time, server inserts a brand-new registered user (no progress to convert), issues a session, no `device_tokens` row to delete.
3. Response `201`, `re_session` set.

**Postconditions**: New registered user, empty progress.

### Alternative Flows
- **UC-10-A1: Cleared cookies then register** - After clearing cookies the user is a new guest on bootstrap and converts that fresh guest (old progress orphaned).

### Error Flows
- **UC-10-E1: Registration rate limit** - More than **30** registration requests from one IP within 1 hour (sliding window; overrides D-9's 5/hour for school NAT, OQ-15) -> `429` with `Retry-After` and Vietnamese message. Stored in the generic `rate_events(bucket='register_ip', key_hash, created_at)` table; `key_hash` = sha256 of IP + server secret; no raw IP stored.
- **UC-10-E2: What counts** - Every registration request that passed CSRF counts, including `422` and `409` outcomes and successes. CSRF failures (403) and `429` responses are NOT counted (OQ-15/18).

### Edge Cases
- **UC-10-X1**: School NAT: 30 students behind one IP register within the hour -> all 30 pass; the 31st gets `429` (residual risk of group lockout is monitored via 429 counts; review Risks).
- **UC-10-X2**: Client IP: `TRUSTED_PROXY_HOPS=0` (default) uses the socket peer and ignores `X-Forwarded-For`; if N>0 the Nth entry from the RIGHT of XFF is used; the leftmost (client-controlled) entry is never trusted (OQ-16). Spoofed XFF with hops=0 cannot evade the limit.
- **UC-10-X3**: Registration attempts failing CSRF are not counted.
- **UC-10-X4**: Rate-limit window expiry: the 31st request succeeds once the oldest counted event is older than 1 hour; `Retry-After` is an integer >= 1. `rate_events` older than 1 day are purged by maintenance (UC-34).

### Data Requirements
- **Tables**: `rate_events` (bucket `register_ip`), `users`, `sessions`.
- **Covers**: FR-18, FR-27 (registration limit), D-9 (overridden numbers); OQ-15, OQ-16, OQ-18.

---

## UC-11: Login on a new device (valid credentials)

**Actor**: Registered user (on a new/cookie-less device)
**Trigger**: Opens Login from Register ("Đã có tài khoản? Đăng nhập") and submits nickname + password.
**Preconditions**: Account exists; device is a guest or has no cookie; under rate limit.

### Primary Flow
1. Visitor opens `/`, is bootstrapped as an empty guest (UC-1) and navigates to Login.
2. Client sends `POST /api/auth/login` (csrf) `{nickname,password}`; the guest has no progress so no discard warning (UC-12).
3. Server normalises the nickname, checks rate limits (UC-13), finds the registered user by `nickname_ci`, verifies the scrypt hash with constant-time compare off the event loop.
4. In one transaction: revokes any session token the browser presented, deletes the empty guest row and its device token, creates a new `sessions` row. (Login counts failures only, so a success writes no `rate_events` row; whether a success clears earlier failures is listed under New gaps.)
5. Server returns `200 {user}`, sets a new `re_session`, clears `re_device`.
6. Client lands on Home with the user's progress, streak, XP, "Cần ôn lại" badge (AC-10).

**Postconditions**: Exactly one active session for this browser; previous token revoked.

### Alternative Flows
- **UC-11-A1: Nickname typed in a different case** ("MINH_AN") - logs in (case-insensitive).
- **UC-11-A2: Browser had an old session cookie** - Old token revoked in the same transaction.
- **UC-11-A3: Two accounts in sequence on one device** - Account A logs out, B logs in: no data leakage; no residual A data in client state (state reset on login/logout).

### Error Flows
- **UC-11-E1: Wrong password** - `401 {"error":"invalid_credentials"}`, generic Vietnamese message ("Nickname hoặc mật khẩu không đúng"); failure recorded; guest untouched.
- **UC-11-E2: Unknown nickname** - identical `401` body/status; the server burns an equivalent scrypt computation so response time is indistinguishable (AC-15).
- **UC-11-E3: Validation** - missing fields -> `422`; extra fields -> `422`.
- **UC-11-E4: Rate limited** - `429` (UC-13).
- **UC-11-E5: CSRF failure** - `403 csrf_failed`; not counted as a failed attempt.

### Edge Cases
- **UC-11-X1**: Timing test: median latency difference between unknown nickname and wrong password < a small tolerance (e.g., 30 ms) over N samples.
- **UC-11-X2**: Password with leading/trailing spaces is not trimmed.
- **UC-11-X3**: Login response never includes hash, token, or guardian email.
- **UC-11-X4**: Login while already logged in (valid `re_session`) as the same user -> new token issued, old revoked, 200. As a different user -> old session revoked (not the other account's other devices).
- **UC-11-X5**: User is logged in on 3 devices; each has its own session row; logging in on device 4 does not revoke the others.

### Data Requirements
- **Tables**: `rate_events` (failures), `sessions`, `users`, `device_tokens`. The CSRF token is not rotated by login (OQ-13).
- **Covers**: FR-22, FR-24, FR-26, AC-10, AC-15, NFR-F4, NFR-S7; OQ-13.

---

## UC-12: Login on a device that has a guest with progress (discard with warning)

**Actor**: Registered user whose device has a progress-bearing guest
**Trigger**: Opens Login while the device guest has at least one attempt, save, or completed round.
**Preconditions**: Valid `re_device`; guest has progress.

### Primary Flow
1. Login screen shows (client knows progress from `/api/me` or a bootstrap flag): "Tiến trình khách trên thiết bị này sẽ bị xóa khi bạn đăng nhập. Nếu muốn giữ lại, hãy đăng ký tài khoản mới." with buttons "Đăng nhập và xóa tiến trình khách" and "Quay lại".
2. User confirms. Client sends `POST /api/auth/login {nickname,password,discard_guest:true}`.
3. Server verifies credentials; in one transaction deletes the guest user (every user-owned table has an FK to `users` ON DELETE CASCADE, OQ-17: attempts, review_state, saves, progress, reflex data, settings, device token, usage sessions), creates the session; the gate disappears with the guest row ("cleared on login (guest discarded)").
4. Response `200`; cookies: new `re_session`, `re_device` cleared. Guest row no longer exists (AC-16).

**Postconditions**: No guest remains; user is on Home as the registered account.

### Alternative Flows
- **UC-12-A1: Guest without progress** - Login proceeds silently; `discard_guest` not required.
- **UC-12-A2: Cancel ("Quay lại")** - No request; guest unchanged; returns to previous screen (or Register for the mandatory gate).
- **UC-12-A3: Mandatory gate + login** - Guest gated by second-visit has progress, so warning always appears; after discard the user is registered-account Home.

### Error Flows
- **UC-12-E1: `discard_guest` omitted with progress** - `409 {"error":"guest_progress_exists"}`; nothing deleted; client shows the warning dialog (AC-16).
- **UC-12-E2: Wrong credentials with `discard_guest:true`** - `401 invalid_credentials`; the guest row and its data must NOT be deleted (PRD edge #11).
- **UC-12-E3: Rate-limited with discard** - `429`; guest intact.

### Edge Cases
- **UC-12-X1**: Login in tab 1 while tab 2 still shows the guest: tab 2's next request carries `re_session` (guest cookie cleared) -> becomes the registered user via bootstrap/identity; the CSRF token is stable per browser so tab 2's header remains valid (OQ-13); if a `csrf_failed` still occurs the client re-bootstraps once and retries once.
- **UC-12-X2**: Guest progress counted only if >=1 attempt/save/completed round; view-only guest is silent-discarded.
- **UC-12-X3**: `discard_guest:true` sent when there is no guest cookie -> ignored, normal login.
- **UC-12-X4**: Failed login must not clear `re_device`.
- **UC-12-X5**: Discard deletes the guest's `usage_sessions`; the registered user's own history unaffected.
- **UC-12-X6**: Decision D-1 has no merge; guest progress is permanently lost; no undo.

### Data Requirements
- **Tables**: DELETE `users` (guest) cascading to `attempts`, `review_state`, `card_saves`, `card_progress`*, `reflex_progress`*, `reflex_sessions`, `user_settings`, `device_tokens`, `usage_sessions`, `upload_claims` (all FK CASCADE per the review schema; `card_progress`/`card_saves` also FK to `cards` CASCADE, OQ-17).
- **Covers**: FR-28, FR-11 (cleared on discard), AC-16, D-1, PRD edge #11.

---

## UC-13: Login rate limiting (per nickname and per IP)

**Actor**: Attacker, Registered user
**Trigger**: Repeated failed `POST /api/auth/login`.
**Preconditions**: `rate_events` table (buckets `login_nick`, `login_ip`); limits **5 failures/nickname/15 min** and **100 failures/IP/15 min** (school-NAT override of D-9's 20, OQ-15). Only failed logins are counted; sliding window.

### Primary Flow
1. Attacker tries 5 wrong passwords for "minh_an" within 15 minutes (each `401`).
2. Sixth attempt, even with the correct password, returns `429` with `Retry-After` header (seconds) and Vietnamese message with remaining wait time (AC-14).
3. After the window expires (failures older than 15 min no longer count) the next correct attempt succeeds. A success does not add an event and does not reset the IP counter.

**Postconditions**: Attempts logged hashed by IP, no raw IP.

### Alternative Flows
- **UC-13-A1: Distributed attack** - 5 failures from five different IPs against one nickname -> the sixth from a sixth IP gets `429` (per-nickname limit).
- **UC-13-A2: One IP, many nicknames** - 100 failures against different nicknames from one IP within 15 min -> the 101st gets `429` regardless of nickname (a class of 30 students each mistyping a few times stays under the limit).
- **UC-13-A4: DELETE /api/me wrong password** - A wrong password on `DELETE /api/me` counts in the same nickname failure bucket and returns the same `429` once the bucket is full (OQ-25).
- **UC-13-A3: Unknown nickname** - Counted per normalised nickname exactly like known ones, so `429` behaviour does not reveal existence.

### Error Flows
- **UC-13-E1: CSRF failure** - Not counted as an attempt.
- **UC-13-E2: Validation `422`** (e.g., empty password) - Not counted: login counts credential failures only (OQ-15/18).

### Edge Cases
- **UC-13-X1**: Boundary: 4 failures then correct password succeeds; 5 failures then correct -> `429`.
- **UC-13-X2**: `429` responses are NOT counted, so hammering while limited does not extend the window (OQ-18).
- **UC-13-X3**: Retry-After equals time until the oldest counted failure leaves the window; header is an integer >= 1.
- **UC-13-X4**: Successful login never touches the IP counter (and writes no event). Whether it clears nickname A's earlier failures is not decided by the review (New gaps).
- **UC-13-X5**: Case/Unicode variants of a nickname count into one bucket (normalised key).
- **UC-13-X6**: Limits configurable via env; set to 2 in tests.
- **UC-13-X7**: Shared school IP: the 100/IP/15 min limit tolerates a classroom; residual lockout risk is monitored via 429 counts (review Risks). Per-nickname limit stays 5/15 min.

### Data Requirements
- **Tables**: `rate_events(id, bucket in login_nick|login_ip|register_ip, key_hash, created_at)` + index (bucket, key_hash, created_at); rows older than 1 day purged by maintenance.
- **Covers**: FR-27, AC-14, D-9 (overridden), PRD edge #8; OQ-15, OQ-16, OQ-18, OQ-25.

---

## UC-14: Auto-login and session lifecycle (expiry, rotation, revocation)

**Actor**: Registered user, System
**Trigger**: Browser opens the app with `re_session`.
**Preconditions**: Session row exists.

### Primary Flow
1. A week after the last visit, the browser sends `re_session` on `POST /api/session/bootstrap`.
2. Server hashes it, finds a non-revoked row with `now < expires_at` and `now < absolute_expires_at`, updates `last_seen_at`, extends `expires_at` (sliding 90 d), refreshes the cookie at most once per day.
3. Response `200 {user, is_guest:false, gate:null, csrf_token}`; client goes straight to Home, no login/register/gate screen (AC-9).

**Postconditions**: Same session continues.

### Alternative Flows
- **UC-14-A1: Rotate-on-use** - Token older than 30 days at use: server issues a new token (new row, `rotated_from` = old hash) and sets the new cookie; the old row gets `grace_until = now+60s`: it stays valid until then but never rotates again from it (OQ rotate-on-use rule), so a parallel tab with the old cookie still works.
- **UC-14-A2: Sliding extension** - Use on day 80 pushes `expires_at` to day 170 but never beyond `absolute_expires_at`.
- **UC-14-A3: Two tabs during rotation** - Tab B's request within 60 s with the old token succeeds; after 60 s the old token is invalid.

### Error Flows
- **UC-14-E1: Expired (idle > 90 d or absolute > 365 d)** - Decided (OQ-19, overrides PRD edge #1): behaves like no cookie; bootstrap creates a NEW guest (fresh progress, free session) and reveals nothing about the account. To avoid a dead end, the guest Home header and Profile show "Đã có tài khoản? Đăng nhập" (UC-44).
- **UC-14-E2: Revoked token** - Same as expired (new guest + login link); AC-18 replay returns a fresh guest.
- **UC-14-E3: Session cookie present but user deleted** - Row cascaded away; treated as no cookie -> new guest.
- **UC-14-E4: Tampered/unknown token** - Treated as no cookie.

### Edge Cases
- **UC-14-X1**: Day 364 use with sliding extension: `expires_at` capped to absolute (day 365); day 366 -> expired.
- **UC-14-X2**: Cookie refresh at most once per 24 h even with many requests.
- **UC-14-X3**: Rotate-on-use race: two concurrent requests with the same old token both succeed and do not create two competing live tokens beyond the overlap rule.
- **UC-14-X4**: Both `re_session` and `re_device` present (should not happen post-registration): `re_session` wins.
- **UC-14-X5**: Rotated-from token (`grace_until`) still valid for exactly 60 s (boundary tests at 59 s / 61 s) and does not rotate again during that time.
- **UC-14-X6**: `Max-Age` of refreshed cookie = 90 days.

### Data Requirements
- **Tables**: `sessions(token_hash,user_id,created_at,last_seen_at,expires_at,absolute_expires_at,revoked_at,grace_until,rotated_from)`.
- **Covers**: FR-22, FR-23, FR-24, FR-25 (expired/revoked behaviour), AC-9, AC-31 (rotation, expiry), D-5, PRD edge #12 (overridden by OQ-19).

---

## UC-15: Logout and logout-all

**Actor**: Registered user
**Trigger**: Profile > "Đăng xuất" or "Đăng xuất mọi thiết bị".
**Preconditions**: Logged in; csrf valid.

### Primary Flow (logout)
1. Client sends `POST /api/auth/logout` (csrf).
2. Server sets `revoked_at` on the current session, clears `re_session` ONLY (expiring cookie; `re_device`/`re_csrf` untouched), returns `204`. Logout is idempotent for anyone (OQ-7).
3. Client resets in-memory state and calls bootstrap, which creates a new empty guest; Home shows as a guest (AC-18).
4. Replaying the old cookie returns a fresh guest, not the registered account.

**Postconditions**: Session revoked; other devices unaffected.

### Alternative Flows
- **UC-15-A1: Logout-all** - `POST /api/auth/logout-all` revokes all sessions of the user; other devices fall back to new guest on their next bootstrap/identity resolution; this device is logged out too.
- **UC-15-A2: Logout then login again** - New session; progress intact.

### Error Flows
- **UC-15-E1: Guest calls logout** - `204` no-op (idempotent for anyone; clears `re_session` only, OQ-7). Guest calls `logout-all` -> `403 registration_required` `reason:"account"` (second_visit if gated).
- **UC-15-E2: CSRF failure** - `403 csrf_failed`, nothing revoked.
- **UC-15-E3: Logout with expired/revoked session** - `204` (idempotent); client still clears UI state.

### Edge Cases
- **UC-15-X1**: Logout in tab 1 while tab 2 is mid-request -> tab 2's request with the revoked token gets treated as a guest/no identity; registered-only endpoints return `403 registration_required` (`camera`/`account`); the client must handle by re-bootstrap (no crash loop, no data written under a wrong user).
- **UC-15-X2**: Double logout (two clicks) -> second is harmless.
- **UC-15-X3**: After logout, a new guest on the same device has `prior_sessions=0` (fresh free session) - noted behaviour.
- **UC-15-X4**: Logout-all during a rotation overlap revokes both old/new tokens.

### Data Requirements
- **Tables**: `sessions.revoked_at`.
- **Covers**: FR-25, AC-18, US-8; OQ-7.

---

## UC-16: Profile, settings, and account fields

**Actor**: Guest, Registered
**Trigger**: Opens Profile; changes avatar/CEFR/hide-timer.
**Preconditions**: Identity (not gated).

### Primary Flow (registered)
1. Client `GET /api/me` (gate-exempt) -> `200 MeOut {user (no guardian email, no hashes), settings, streak, xp, level, level_progress}` computed on read (OQ-23): XP = sum of `attempts.xp` (10 if score >= 70 else 2; listen-only earns none); streak = consecutive `Asia/Ho_Chi_Minh` days with >= 1 attempt ending today or yesterday; level = floor(XP/500)+1; level_progress = (XP mod 500)/500.
2. Profile shows avatar, nickname, streak, XP, level progress; actions logout, logout-all, delete account.
3. User changes avatar: `PATCH /api/me {avatar_key}` (csrf) -> `200`.
4. User changes CEFR: `PATCH /api/me {cefr_level}` -> `200` (accepted values A1, A2, B1 only; B2 is content-only, OQ-24).
5. User toggles hide-timer: `PUT /api/me/settings {hide_timer:true}` -> `200`.

**Postconditions**: Fields updated; nickname and birth year unchanged.

### Alternative Flows
- **UC-16-A1: Guest views Profile** - Prominent card "Đăng ký để lưu tiến trình" (skippable, no gate; tapping opens Register with `reason=profile`, with Back, returning to Profile after success - UC-45, OQ-21), plus the "Đã có tài khoản? Đăng nhập" link (UC-44); no editable profile fields, no logout-all/delete actions; shows avatar placeholder, "Bạn khách", streak, XP.
- **UC-16-A2: Guest toggles hide-timer** - `PUT /api/me/settings` is `identity` level: allowed for guests and persisted (FR-50).

### Error Flows
- **UC-16-E1: Guest `PATCH /api/me`** - `403 {"error":"registration_required","reason":"account"}` (OQ-8). Same for `DELETE /api/me` and `logout-all`. Gated guest -> reason `second_visit`.
- **UC-16-E2: PATCH with nickname or birth_year** - `422` (extra/immutable).
- **UC-16-E3: Invalid avatar/CEFR** - `422`.
- **UC-16-E4: Gated guest `PUT /api/me/settings`** - `403 second_visit`.

### Edge Cases
- **UC-16-X1**: Resolved (OQ-22): `hide_timer` is changed ONLY via `PUT /api/me/settings` (any identity). `PATCH /api/me {hide_timer}` -> `422` (unknown field). `PATCH /api/me` = avatar and CEFR for registered users only.
- **UC-16-X2**: Streak/XP/level rules per OQ-23 (step 1). Boundaries: score 70 -> 10 XP, 69 -> 2 XP; XP 499 -> level 1 (progress 0.998), 500 -> level 2 (progress 0); attempts at 23:59 and 00:01 ICT count as two streak days; no attempt today but one yesterday keeps the streak; none yesterday or today -> streak 0.
- **UC-16-X3**: `GET /api/me` for a registered user has no `guardian_email` key at all (also for under-16).
- **UC-16-X4**: `PATCH /api/me {cefr_level:"B2"}` -> `422`; A1, A2, B1 accepted (OQ-24).

### Data Requirements
- **Tables**: `users`, `user_settings`.
- **Covers**: FR-29 (PATCH), FR-32, FR-50, FR-54, AC-12 (me), US-8; OQ-8, OQ-21, OQ-22, OQ-23, OQ-24.

---

## UC-17: Account deletion (DELETE /api/me)

**Actor**: Registered user
**Trigger**: Profile > "Xóa tài khoản", confirms with password.
**Preconditions**: Logged in; csrf; correct password.

### Primary Flow
1. Client shows a confirmation with password field (Vietnamese warning that it is irreversible).
2. `DELETE /api/me` (csrf) with `{password}`.
3. Server verifies the password (a wrong password counts in the nickname login-failure bucket with the same `429`, OQ-25) and in one transaction deletes the user. Cascades: `sessions`, `device_tokens`, `usage_sessions`, `upload_claims`, `attempts`, `review_state`, `card_saves`, `card_progress`, `reflex_progress`, `reflex_sessions`, `user_settings`, and ALL owned `cards` including shared/public ones (OQ-26 overrides PRD edge #16: shared cards disappear from Explore and other users' `card_saves` of them cascade away). `image_assets.first_uploaded_by` -> NULL.
4. AFTER the commit the server garbage-collects orphans (OQ-27): every `card_contents` that has no remaining `cards` row and is not owned by the seed is deleted together with its `image_assets` row and the image file (GC first verifies NO `cards` row references the content, because `cards.content_id` is RESTRICT). Server clears `re_session` and `re_device`; returns `204`.
5. Client shows the logged-out guest state (new guest via bootstrap).

**Postconditions**: No personal data (nickname, birth year, guardian email, avatar) for the user remains; no orphaned private image file remains on disk.

### Alternative Flows
- **UC-17-A1: Owner of a shared, approved card** - Owner's `cards` row is deleted (cascade) so the card disappears from Explore (OQ-26). If no other `cards` row references the content, GC deletes contents + asset + file; otherwise they stay for the other holders.
- **UC-17-A2: Content also held by another user** - Other user's `cards` row (UNIQUE owner+content) unaffected; `card_contents`, `image_assets` and the file are kept (GC finds a referencing `cards` row).
- **UC-17-A3: Other users saved the deleted user's card** - Their `card_saves` rows cascade away.

### Error Flows
- **UC-17-E1: Wrong password** - `401 invalid_credentials`; nothing deleted; counted in the nickname failure bucket (OQ-25); when the bucket is full -> `429`.
- **UC-17-E2: Missing password** - `422`.
- **UC-17-E3: Guest** - `403 registration_required` `reason:"account"` (second_visit when gated).
- **UC-17-E4: Deletion while an upload is processing** - The background job may finish; the content has no `cards` row and the user's `upload_claims` are gone, so the next GC (maintenance, UC-34) removes contents/asset/file. If another user's identical upload attached to the in-flight job, that user's `upload_claims` row keeps the content alive (GC counts claims as references **[ASSUMED, see New gaps]**).

### Edge Cases
- **UC-17-X1**: Deleted user's private image with no other holder is removed from DB AND disk by the post-commit GC (OQ-27); a GC crash between commit and cleanup is repaired by the maintenance GC (idempotent). Seed contents are never GC'd.
- **UC-17-X2**: Old cookies replayed after deletion -> new guest; no error.
- **UC-17-X3**: Second DELETE from another tab -> treated as no identity.
- **UC-17-X4**: Foreign keys: `cards.content_id ON DELETE RESTRICT` must not block user deletion (delete cards first by cascade; content survives).
- **UC-17-X5**: Nickname becomes available again immediately after deletion.

### Data Requirements
- **Tables**: all user-owned tables above; `image_assets.first_uploaded_by` SET NULL; GC deletes `card_contents`/`image_assets` rows and files.
- **Covers**: FR-29 (DELETE; amended per review), NFR-P5, PRD edge #16 (overridden); OQ-25, OQ-26, OQ-27.

---

## UC-18: CSRF and request-security failures

**Actor**: Attacker, Client
**Trigger**: State-changing request with missing/wrong CSRF or Origin.
**Preconditions**: Any identity.

### Primary Flow (protected request accepted)
1. Client bootstraps; receives `re_csrf` cookie and `csrf_token`.
2. Client sends every POST/PUT/PATCH/DELETE with `X-CSRF-Token` equal to the cookie and same-origin `Origin` (or `Referer`).
3. Server accepts and processes.

### Alternative Flows
- **UC-18-A1: Bootstrap exemption** - `POST /api/session/bootstrap` without a CSRF token succeeds, even when Origin and Referer are both missing (idempotent, harmless); a present foreign `Origin` is rejected.
- **UC-18-A2: Origin missing, Referer same-origin** - Accepted. If Origin is present it must equal `APP_ORIGIN` exactly.
- **UC-18-A3: Cookie name under HTTPS** - When `Secure`, the CSRF cookie is `__Host-re_csrf` (Path=/, no Domain); on localhost `re_csrf`. The client reads whichever is configured (OQ-28).
- **UC-18-A4: Stable token** - The CSRF token is stable per browser and not rotated on login/register (OQ-13).

### Error Flows
- **UC-18-E1: Missing `X-CSRF-Token`** - `403 {"error":"csrf_failed"}`; no state change (AC-17).
- **UC-18-E2: Token mismatch with cookie** - `403 csrf_failed`.
- **UC-18-E3: Foreign Origin ("https://evil.example")** - `403 csrf_failed`.
- **UC-18-E4: Origin with different port/scheme** (e.g., `http://localhost:9999` vs configured `http://localhost:8000`) - `403 csrf_failed`.
- **UC-18-E5: `re_csrf` cookie missing** (bootstrap failed, cleared) - `403 csrf_failed`; client rule: re-bootstrap ONCE and retry the request ONCE; a second `csrf_failed` is shown as an error (no loop) (OQ-13).
- **UC-18-E6: Both Origin and Referer absent on a state-changing request** - `403 csrf_failed` (only bootstrap is exempt, OQ-28).
- **UC-18-E7: Unknown JSON field / wrong type** - `422` field errors with no password echo (FR-31).
- **UC-18-E8: Login CSRF** - `POST /api/auth/login` cross-site -> `403`, not counted for rate limiting.

### Edge Cases
- **UC-18-X1**: GET endpoints (images, audio) need no CSRF; they never change state.
- **UC-18-X2**: Origin comparison is exact (scheme+host+port), case-insensitive host.
- **UC-18-X3**: CORS disabled: preflight `OPTIONS` from another origin gets no `Access-Control-Allow-Origin`.
- **UC-18-X4**: SQL injection strings in nickname/search `q` are inert; a repository test scans for string-formatted SQL (NFR-S3).
- **UC-18-X5**: Frontend renders hostile nicknames/labels (`<img onerror>`) as text only (NFR-S5); CSP blocks inline scripts.
- **UC-18-X6**: Logs never contain passwords, tokens, hashes, guardian emails (FR-32).
- **UC-18-X7**: Response headers: `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`, restrictive CSP, `Cache-Control: no-store` on user-specific `/api/` JSON (FR-33).

### Data Requirements
- **Tables**: none changed on failures.
- **Covers**: FR-30, FR-31, FR-32, FR-33, AC-17, NFR-S1, NFR-S2, NFR-S3, NFR-S5, PRD edge #15; OQ-13, OQ-28.

---

## UC-19: Cookie-cleared, cookies-blocked, and multi-device guests

**Actor**: Guest, Registered
**Trigger**: User clears browser data, uses a private window, or uses a second device.
**Preconditions**: Prior state as listed.

### Primary Flow (guest clears cookies)
1. Guest with progress clears cookies, reopens the app.
2. Bootstrap sees no `re_device`: creates a new guest with a fresh `usage_sessions` counter and empty progress; Home/Profile show "Đã có tài khoản? Đăng nhập" (UC-44).
3. Old guest rows/progress are orphaned and purged later (UC-34: 180 d idle, or 7 d if the orphan never wrote). The second-visit gate is thereby bypassable (accepted risk; guests cannot upload).

**Postconditions**: Old progress unreachable.

### Alternative Flows
- **UC-19-A1: Registered user clears cookies** - Sessions on the server remain valid until expiry, but the token is lost; bootstrap creates a new guest that reveals nothing about the account; the guest uses the "Đã có tài khoản? Đăng nhập" entry (UC-44, OQ-19).
- **UC-19-A2: Guest on two devices** - Device A and B are independent guests with independent session counters and progress; each can hit the gate separately.
- **UC-19-A3: Same nickname on second device** - Device A registered "Lan_95"; device B guest tries "Lan_95" -> `409 nickname_taken`; no merge; B should use Login (then discard warning if B has progress, UC-12).
- **UC-19-A4: Private/incognito window** - Behaves as a brand-new device; no persistence after closing.

### Error Flows
- **UC-19-E1: Cookies blocked/disabled** - Notice in Vietnamese; each bootstrap would create a new guest; register/login cannot persist; client detects missing cookie after bootstrap (UC-1-E2).
- **UC-19-E2: Third-party/embedded context** - SameSite=Lax cookies are not sent on cross-site POST; app is same-origin only.

### Edge Cases
- **UC-19-X1**: Orphan guests count for retention purge only; no auto-merge. Guests with no writes are purged after `GUEST_EMPTY_RETENTION_DAYS=7` (OQ-20).
- **UC-19-X2**: Guest B (device B) registering is unaffected by guest A's registration (different user rows).
- **UC-19-X3**: Clearing only `re_csrf` while keeping `re_device`: next bootstrap re-issues it.
- **UC-19-X4**: Browser storage cleared but cookies kept -> identity retained; server state unaffected (FR-12d).

### Data Requirements
- **Tables**: `users`, `device_tokens`, `usage_sessions`.
- **Covers**: FR-1 (new guest), FR-12d, FR-6 (orphans), PRD edge #1 (amended: new guest + login link), #2, #14 (cookies blocked); OQ-19, OQ-20.

---

## Part C - AI-once upload pipeline and cards

## UC-20: Upload a new image (AI called once)

**Actor**: Registered user
**Trigger**: Add photo > picks/takes a photo.
**Preconditions**: Registered, not rate-limited, provider available (Mock in tests), disk writable.

### Primary Flow
1. Client compresses the image to ~1280 px long edge and sends `POST /api/uploads` (multipart, csrf).
2. Server sniffs the type (JPEG/PNG/WebP by content), checks size <= 5 MB and pixels <= 25 MP, computes `source_sha256` over the RAW uploaded bytes (the dedupe key, OQ-32), re-encodes with Pillow (strips EXIF/GPS), computes `clean_sha256` of the cleaned file (stored separately; `phash` stays a NULL unused column), stores the cleaned file under `DATA_DIR` with a random name (relative path in DB).
3. In one `BEGIN IMMEDIATE` transaction: inserts `image_assets` (UNIQUE `source_sha256`), `card_contents(status='processing', ai_calls=0, lease_expires_at=now+2x30s+30s=90s)` and `upload_claims(user_id, content_id)`. **An upload NEVER creates a `cards` row** (OQ-29): there is no draft; cancelling saves nothing; the card is created only by `POST /api/cards` (UC-24). If the user already owns a card for this content, the response includes its `card_id`.
4. Server returns `202 UploadOut {content_id, status:'processing', dedupe:'none', ai_calls:0, card_id?}`. `dedupe` is `none|ready|in_flight` (UC-21).
5. Outside any DB transaction a FastAPI BackgroundTask in the worker that won the insert calls `AIProvider.analyze(image_bytes)` with a 30 s timeout under a per-process concurrency limit of 2. `ai_calls` is incremented in a committed write BEFORE each provider call (OQ-33); after one successful call `ai_calls=1`.
6. Result validated (pydantic): topic, tags, CEFR, 3-5 labels with `box_2d [ymin,xmin,ymax,xmax]` (0-1000), IPA, `vi_meaning`, accepted answers, descriptions en+vi, story en+vi, safety flags. `box_2d` converted to normalised x,y centre and box corners; labels outside 0-1 dropped.
7. Server writes `card_labels`, descriptions, story, safety, `model`, `prompt_version`, `raw_response`; `status='ready'`; creates/finds `audio_assets` by (text, voice) for each label word, description sentence, and story sentence.
8. Client polls `GET /api/uploads/{content_id}` (registered; requires an `upload_claims` row for (user, content), else 404 - OQ-38) showing steps and "Số lần gọi AI: 1"; when `ready` opens Review (UC-24). Navigation is never blocked by processing. The client stops polling after 120 s and shows a retry state (OQ-35).

**Postconditions**: One `image_assets`, one `card_contents(status='ready', ai_calls=1)`, labels, audio assets, one `upload_claims` row for the uploader, NO `cards` row yet; EXIF-free file on disk.

### Alternative Flows
- **UC-20-A1: Gemini provider** - Selected only if `GEMINI_API_KEY` is set; otherwise `MockProvider` (deterministic from sha256).
- **UC-20-A2: User navigates away during processing** - Job continues; because no card exists yet, "Bài của tôi" does not list it; the client remembers the pending `content_id` in memory/session storage and can resume the Review screen via `GET /api/uploads/{id}` (claim-protected) **[resume entry point ASSUMED, see New gaps]**.
- **UC-20-A3: Slow provider** - UI shows progress for p50 <= 15 s (Gemini) and <= 3 s p95 (mock).

### Error Flows
- **UC-20-E1: Guest** - `403 registration_required/camera` (UC-6-E1); a gated guest gets `second_visit` (precedence).
- **UC-20-E2: Network loss on upload** - Client shows a retryable message; no partial DB rows (rows are created only after the file is validated and stored) - every failure path leaves no `image_assets`/`upload_claims` row without a file.
- **UC-20-E6: AI budget exhausted** - Re-uploading an image whose cap is exhausted returns `409 analysis_unavailable` (UC-48).
- **UC-20-E3: Disk full / write error** - `500/507` generic Vietnamese error; no `image_assets` row without a file (transaction rolled back, partial file removed) (PRD edge #13).
- **UC-20-E4: Missing CSRF** - `403 csrf_failed`.
- **UC-20-E5: Label with out-of-range coordinates** - Dropped; if fewer than 3 labels remain the result is invalid -> counts as a failed call and follows the retry budget (UC-23).

### Edge Cases
- **UC-20-X1**: Concurrency limit: 5 uploads of different images with limit 2 -> at most 2 concurrent provider calls; others queue and all finish. The semaphore is per process, so the pilot runs `--workers 1`.
- **UC-20-X2**: Same word in several images (e.g., "cup") -> one `audio_assets` row; `UNIQUE(text,voice)` prevents duplicates even concurrently.
- **UC-20-X3**: `audio_assets.storage_path` may be NULL for text not in the pre-generated catalogue (`frontend/audio`, UC-36); the card payload then carries `audio_url: null` and the client falls back to browser speech.
- **UC-20-X4**: Image file name is random; no user-supplied name used (no path traversal).
- **UC-20-X5**: The DB transaction never wraps the AI call (lock contention test: other writes proceed during a 5 s mock delay).
- **UC-20-X6**: Pixel limit exceeded (> 25 MP) or decompression bomb -> `413 image_too_large` (OQ-30); see UC-22.
- **UC-20-X7**: A failure after the file is stored but before the DB insert removes the partial file (no orphan file).

### Data Requirements
- **Input**: multipart image.
- **Output**: `UploadOut{content_id, status, dedupe, ai_calls, card_id?}`, later `UploadStatusOut` with the AI result.
- **Tables**: `image_assets`, `card_contents`, `card_labels`, `card_sentences`, `audio_assets`, `upload_claims` (NO `cards` write).
- **Covers**: FR-34, FR-35, FR-36 (overridden: no cards row), FR-38 (amended), FR-39, FR-40, FR-41, FR-42, FR-46, NFR-F3, NFR-A1, AC-22 (storage), PRD edge #3; OQ-29, OQ-30, OQ-31, OQ-32, OQ-33, OQ-35, OQ-38.

---

## UC-21: Dedupe and concurrent identical uploads (AI-once guarantee)

**Actor**: Registered users (A and B, or one user in two tabs)
**Trigger**: Upload of identical bytes after or during processing.
**Preconditions**: `MockProvider` with a call counter.

### Primary Flow (already processed)
1. User A's image is `ready` (`ai_calls=1`).
2. User B uploads identical bytes. The sha256 of the RAW uploaded bytes (`source_sha256`) matches `image_assets` (OQ-32).
3. Server inserts only `upload_claims(B, content_id)` (no `cards` row; B's card is created by `POST /api/cards` after Review); provider call count stays 1; response `202 {dedupe:'ready', status:'ready', ai_calls:0}` (plus `card_id` if B already owns a card for the content).
4. Processing screen shows "Ảnh này đã có sẵn, không cần gọi AI" and "Số lần gọi AI: 0 - ảnh đã có sẵn" (AC-20); Review opens immediately.

**Postconditions**: `SUM(ai_calls)` unchanged; one new `upload_claims` row.

### Alternative Flows
- **UC-21-A1: Simultaneous uploads by A and B (AC-19)** - Both arrive while no row exists. `BEGIN IMMEDIATE` plus the unique `source_sha256` ensure one inserts `processing` (response `dedupe:'none'`); the other inserts only its `upload_claims` row and attaches to the in-flight job (response `dedupe:'in_flight'`, 0 provider calls from this request). Counter = 1; `card_contents.ai_calls=1`; each user later creates their own `cards` row via `POST /api/cards`, both referencing one `card_contents`. Test: two threads and a MockProvider counter.
- **UC-21-A2: Same user, two tabs** - `upload_claims` PK(user, content) makes the second insert a no-op; later `POST /api/cards` is idempotent via UNIQUE(owner_id, content_id) -> returns the existing card; one AI call.
- **UC-21-A3: Same user re-uploads own ready image later** - Response includes the existing `card_id` when the user already has a card; 0 AI calls; `dedupe:'ready'`.
- **UC-21-A4: Attach to in-flight job** - Response `status:'processing'`, `dedupe:'in_flight'`, message "Ảnh này đang được xử lý, vui lòng chờ…" (OQ-31); this request made 0 provider calls; client polls; both finish together.

### Error Flows
- **UC-21-E1: In-flight job fails** - Both attached users see `failed`; retry rules (shared per image, not per user) in UC-23.
- **UC-21-E2: Unique constraint race on insert** - The loser retries by reading the winner's row, not returning 500.

### Edge Cases
- **UC-21-X1**: 10 simultaneous identical uploads from 10 users -> provider counter 1, 1 `image_assets`, 1 `card_contents`, 10 `upload_claims`, and 10 `cards` once each user saves.
- **UC-21-X2**: Dedupe key is `source_sha256` of the RAW uploaded bytes (OQ-32), independent of Pillow determinism; the cleaned file and `clean_sha256` are stored separately. Re-compressed copies of the same visual image are NOT deduped (accepted; costs more than 1.05 calls per visual image).
- **UC-21-X3**: Different raw bytes that would clean to identical pixels are NOT deduped (key is raw bytes) - supersedes the earlier cleaned-bytes rule.
- **UC-21-X4**: "<= 1.05 calls/image" is an AGGREGATE pilot metric over unique raw images in normal operation, not a per-image cap (OQ-34/36); the per-image cap is 6 calls (UC-23).
- **UC-21-X5**: Another user's private photo dedupes: user B gets 0 AI calls and an `upload_claims` row only because B uploaded identical bytes; B never receives A's image via A's card id (A's card stays private -> 404 for B, OQ-41).

### Data Requirements
- **Tables**: `image_assets` (UNIQUE `source_sha256`), `card_contents` (UNIQUE image_asset_id), `upload_claims` (PK user+content), `cards` (UNIQUE owner+content, created later).
- **Business Rules**: AI at most once per unique raw image (retries per UC-23 are the only exception).
- **Covers**: FR-36, FR-37, FR-42, AC-19, AC-20, AC-31 (dedupe incl. concurrency), PRD edge #3; OQ-31, OQ-32, OQ-34, OQ-36.

---

## UC-22: Upload validation and privacy cleaning (type, size, content sniff, EXIF/GPS)

**Actor**: Registered user, Attacker
**Trigger**: Uploads an unsupported, oversized, disguised, or metadata-bearing file.
**Preconditions**: Registered, csrf valid.

### Primary Flow (EXIF strip)
1. User uploads a JPEG containing GPS EXIF tags.
2. Server re-encodes with Pillow; only the clean image is stored.
3. Opening the stored file shows no EXIF tags (AC-22). Original bytes are not retained.

### Alternative Flows
- **UC-22-A1: PNG/WebP with metadata chunks** - Cleaned similarly.
- **UC-22-A2: Orientation** - EXIF orientation applied (transposed) before metadata is dropped so the saved image is upright **[ASSUMED]**.

### Error Flows
- **UC-22-E1: GIF** - `415`, nothing stored (AC-21).
- **UC-22-E2: 12 MB JPEG** - `413`, nothing stored (AC-21).
- **UC-22-E3: HTML renamed `.jpg` (or with `Content-Type: image/jpeg`)** - `415` by content sniffing; nothing stored (AC-21).
- **UC-22-E4: Corrupt/truncated JPEG** - `422` (OQ-30).
- **UC-22-E5: Pixel limit exceeded / decompression bomb (e.g., 30000x30000 px small file)** - Rejected before full decode (Pillow `MAX_IMAGE_PIXELS` enforced); no memory blow-up; `413 {"error":"image_too_large"}` (OQ-30).
- **UC-22-E9: Animated WebP/APNG** - `415 {"error":"unsupported_image"}` (OQ-30); nothing stored.
- **UC-22-E6: SVG, PDF, polyglot (JPEG header + script)** - Sniffed type decides; polyglots are re-encoded so scripts are dropped; non-image rejected `415`.
- **UC-22-E7: Missing file part / multiple files / empty file** - `422`.
- **UC-22-E8: Network abort mid-upload** - Nothing stored.

### Edge Cases
- **UC-22-X1**: Exactly `MAX_UPLOAD_BYTES` accepted; +1 byte -> `413`.
- **UC-22-X2**: Exactly 25 MP accepted; above -> `413 image_too_large`.
- **UC-22-X3**: Filename `../../etc/passwd.jpg` ignored; stored under random name.
- **UC-22-X4**: Zero-dimension image -> `422`; animated WebP/APNG -> `415 unsupported_image` (never "first frame only", OQ-30).
- **UC-22-X5**: Extension `.png` with JPEG bytes -> accepted as JPEG (sniff wins).

### Data Requirements
- **Tables**: none on failure (no orphan files, no `upload_claims`).
- **Covers**: FR-34, FR-35, AC-21, AC-22, NFR-S4; OQ-30.

---

## UC-23: AI failure, retry rules, and crash recovery

**Actor**: Registered user, System
**Trigger**: Provider returns invalid JSON, times out, or the server restarts during processing.
**Preconditions**: A `processing` row exists.

### Primary Flow (invalid output)
1. Provider returns invalid/unparseable or schema-failing output (or times out / raises - these count too).
2. Per run the service makes ONE automatic retry (at most 2 provider calls per run). `ai_calls` is incremented in a committed write BEFORE each call, so a timeout or exception counts as a call (OQ-33/34).
3. After the second failed call the run ends: `card_contents.status='failed'`, `error` recorded; UI shows the Vietnamese retry message ("Không phân tích được ảnh, thử lại") with a Retry button.
4. Manual retry = re-uploading the same failed image (any user holding/creating a claim); each manual retry starts a fresh run (<= 2 calls) and increments `manual_retries`. At most **2 manual retries per image in total** (shared by all users, not per user). Hard cap: **6 calls per image** (1 initial run + 2 manual runs, each <= 2 calls).

**Postconditions**: `failed` with `error`; no half-written labels (labels are written only with a validated result).

### Alternative Flows
- **UC-23-A1: Retry succeeds** - `status='ready'`; `ai_calls` is cumulative (e.g., 2 or 3); `manual_retries` records manual runs.
- **UC-23-A2: Provider timeout (30 s)** - Counts as a call and as a failure of the run; the automatic retry follows the same rule.
- **UC-23-A3: Failed image re-uploaded by another user** - Allowed; consumes the SHARED manual-retry budget; the new user gets an `upload_claims` row.
- **UC-23-A4: Lease and lazy sweep (OQ-35)** - `card_contents.lease_expires_at = now + (2x timeout + 30 s)` (= 90 s with a 30 s timeout). Any poll or upload that sees a `processing` row with an expired lease sets it to `failed` (lazy sweep); the startup sweep does the same. The client stops polling after 120 s and shows the retry state.

### Error Flows
- **UC-23-E1: Budget exhausted** - Re-upload when `manual_retries=2` (or `ai_calls` has reached 6) -> `409 {"error":"analysis_unavailable"}` with a Vietnamese message; status stays `failed`; zero provider calls (UC-48).
- **UC-23-E2: Concurrent re-upload of a failed image (two tabs)** - Exactly one retry run starts (decided inside `BEGIN IMMEDIATE`: flips `failed -> processing`, `manual_retries+1`); the other attaches (`dedupe:'in_flight'`), no duplicated provider calls.
- **UC-23-E3: Server restart/worker crash during `processing`** - Startup sweep and lazy sweep mark rows with expired leases as `failed` (retryable within the budget); rows with a live lease stay `processing` until the lease expires, so nothing stays stuck forever.
- **UC-23-E4: Provider unavailable (quota/5xx)** - Same as failure; UI never blocks navigation.

### Edge Cases
- **UC-23-X1**: Persistent failure of the first run -> exactly 2 calls (`ai_calls=2`); after two manual retries `ai_calls=6` and the image is permanently `failed` (cap). The "<= 1.05 calls/image" figure is an aggregate pilot metric, not a per-image cap (OQ-36).
- **UC-23-X2**: Polling never makes provider calls.
- **UC-23-X3**: `raw_response` stored for debugging, never returned to clients.
- **UC-23-X4**: After the cap the image remains failed permanently; only maintenance GC (if no one holds it) removes it.
- **UC-23-X5**: Lease boundary: poll at lease+0 s keeps `processing`, at lease+1 s flips to `failed` **[boundary inclusivity ASSUMED]**.
- **UC-23-X6**: A crash after the pre-call `ai_calls` increment but before the call is counted as a used call (budget is conservative).

### Data Requirements
- **Tables**: `card_contents(status,error,ai_calls,manual_retries,lease_expires_at,raw_response)`.
- **Covers**: FR-38 (overridden), NFR-A4, PRD edge #13; OQ-33, OQ-34, OQ-35, OQ-36.

---

## UC-24: Review AI result and save the card

**Actor**: Registered user
**Trigger**: Processing completes (`ready`).
**Preconditions**: Content `ready`; the user holds an `upload_claims` row for it (there is no draft card, OQ-29).

### Primary Flow
1. `GET /api/uploads/{content_id}` (claim required, else 404) returns the AI result (topic, labels, boxes, descriptions, story, safety summary).
2. Review shows the photo with draggable markers (button elements, `aria-label`, >= 44x44 px hit area), label list.
3. User drags a marker (position updated client-side), edits a label word/IPA/meaning, deletes a label, sets a title.
4. User taps Save: `POST /api/cards` (csrf, claim required) `{content_id,title,label_overrides}` -> `201 CardDetail`; this is the ONLY place a card is created; it is private by default (`visibility='private'`). Review limits (OQ-37): 1-8 labels; word 1-40 chars; no duplicate words (case-insensitive); title <= 60 chars; overrides may only edit, move or delete EXISTING labels (adding labels is not allowed).
5. Edits are stored only on the user's card (`cards.label_overrides` JSON); shared `card_contents`/`card_labels` remain unchanged and other users see the original.

**Postconditions**: Card appears in "Bài của tôi".

### Alternative Flows
- **UC-24-A1: Cancel** - Nothing is saved (no card, no draft); the `upload_claims` row and the ready content remain so the user can re-open Review via the same `content_id`.
- **UC-24-A2: Duplicate label word** - Rejected: `422` field error (case-insensitive: "Cup" vs "cup"); between 1 and 8 labels must remain (OQ-37).
- **UC-24-A3: Keyboard operation of markers** - Arrow keys nudge a focused marker (testable a11y, NFR-X2).

### Error Flows
- **UC-24-E1: Guest** - `403 registration_required/camera` (gated: `second_visit`).
- **UC-24-E2: Another user's `content_id` (IDOR)** - `GET /api/uploads/{id}`, `POST /api/cards` and the retry path require an `upload_claims` row for (user, content); otherwise `404` identical to a non-existent id (OQ-38).
- **UC-24-E3: Invalid override** - Marker coordinates outside 0-1, title > 60, word > 40 chars, more than 8 labels, zero labels, a label id not belonging to the content, an added (new) label -> `422`.
- **UC-24-E4: Content not `ready`** - `409` "chưa sẵn sàng".
- **UC-24-E5: Save twice (double click)** - UNIQUE(owner,content) -> second returns the existing card (idempotent) rather than 500.

### Edge Cases
- **UC-24-X1**: Deleting all labels -> blocked (min 1 label, OQ-37; `422` on the server too).
- **UC-24-X2**: User A edits a label; user B's view of the same content is unaffected.
- **UC-24-X3**: Title containing HTML is rendered as text.
- **UC-24-X4**: Markers near the edge keep 44 px hit area inside viewport at 360x640.
- **UC-24-X5**: Review screen refresh restores from server (`GET /api/uploads/{id}`), unsaved edits lost (message).

### Data Requirements
- **Tables**: `upload_claims` (read), `cards(label_overrides, title)` (INSERT), reads `card_contents`, `card_labels`.
- **Business Rules**: Shared AI result is immutable per user edits; claim-based access control.
- **Covers**: FR-41 (amended), FR-42, FR-43 (private default), US-9, NFR-X2; OQ-29, OQ-37, OQ-38.

---

## UC-25: Card visibility, image access control, sharing and moderation status

**Actor**: Registered owner, Other user, Guest
**Trigger**: Requests card image/detail; taps Share.
**Preconditions**: Cards exist.

### Primary Flow (access)
1. User A owns private card C. A requests `GET /api/cards/{C}/image` -> `200` bytes.
2. User B requests the same URL -> `404` (not `403`; AC-23). A guest also gets `404`. The same 404 applies to EVERY card subroute (`GET /api/cards/{id}`, `/image`, `/save`, `/share`; OQ-41).
3. Seeded system cards: any identity gets `200`.

### Alternative Flows
- **UC-25-A1: Share clean card** - Safety flags all clean (`has_identifiable_faces=false`, `has_personal_info=false`, `has_nsfw_or_violence=false`, `is_suitable_for_students=true`): `POST /api/cards/{id}/share` (csrf) sets `moderation_status='approved'` and `visibility='public'` (`class` stays in the CHECK but is never set, OQ-39); returns `200 ShareOut`; the card appears in Explore for everyone with the owner's nickname only; image becomes accessible to all identities.
- **UC-25-A2: Share flagged card (faces)** - `has_identifiable_faces=true` (AC-24 as amended, OQ-40): there is no reviewer so there is NO pending state. Server sets `moderation_status='rejected'`, visibility stays `private`, and returns `422 {"error":"share_not_allowed","reason":"faces"}` with a Vietnamese message (faces / personal info / unsuitable). The UI never shows "chờ kiểm duyệt".
- **UC-25-A3: Personal info / NSFW / not suitable** - Same path: any unsafe flag -> `rejected` + `422 share_not_allowed` with reason `personal_info` or `unsuitable`; card stays private and fully usable by the owner.
- **UC-25-A4: Re-share after rejection** - Share again returns the same `422` (rejection is per content and permanent; no UI to clear it).
- **UC-25-A5: Share twice (already public)** - Idempotent `200`.
- **UC-25-A6: Unshare / delete** - See UC-42 (`DELETE /api/cards/{id}/share`) and UC-43 (`DELETE /api/cards/{id}`).

### Error Flows
- **UC-25-E1: Non-owner share** - `404`.
- **UC-25-E2: Guest share** - `403 registration_required/camera` (gated: `second_visit`).
- **UC-25-E3: Share while content not ready** - Not reachable: cards are only created from `ready` content (UC-24); a card whose content later became unusable still returns `409`.
- **UC-25-E4: Private card detail by non-owner** - `GET /api/cards/{id}` is `404` too (OQ-41).

### Edge Cases
- **UC-25-X1**: Image served only when owner, or system card, or (visibility != private AND `moderation_status='approved'`).
- **UC-25-X2**: Moderation is per content; if A's share approved the content, B's own card of the same content stays private until B shares.
- **UC-25-X3**: Unshare and delete are defined (OQ-42): UC-42, UC-43.
- **UC-25-X4**: Enumeration: `404` bodies identical for non-existent and forbidden ids.
- **UC-25-X5**: NFR-P4: other users' nicknames appear only on approved shared cards.

### Data Requirements
- **Tables**: `cards.visibility,published_at`, `card_contents.moderation_status,safety`.
- **Covers**: FR-43, FR-44 (overridden: no pending), AC-23, AC-24 (amended: 422 share_not_allowed), NFR-P3, NFR-P4; OQ-39, OQ-40, OQ-41, OQ-42.

---

## Part D - Explore, practice, Reflex, library

## UC-26: Explore, search, and topic filter (no AI calls)

**Actor**: Guest, Registered
**Trigger**: Opens Explore, filters, or searches.
**Preconditions**: Not gated.

### Primary Flow
1. `GET /api/topics` -> topics with counts.
2. `GET /api/cards?scope=explore&topic=food&cefr=A1&limit=20` -> `CardPage` of seeded cards + approved public cards matching filters, ordered `(created_at DESC, id DESC)` with an opaque `cursor` for the next page (UC-49).
3. User searches "cup": `GET /api/cards?q=cup` uses the `lower(word)` index; returns cards whose labels contain "cup" case-insensitively (AC-28), p95 <= 200 ms with >=100 seeded cards.
4. Save: `POST /api/cards/{id}/save` (csrf) -> `200`; unsave: `DELETE /api/cards/{id}/save`.
5. Practice action opens UC-27.

**Postconditions**: Zero provider calls on any read path (verifiable by the mock call counter).

### Alternative Flows
- **UC-26-A1: Guest saves a seeded card** - Stored under guest id; survives reload; converts on registration.
- **UC-26-A2: Combined filters** - topic + CEFR + `q` AND-combine.
- **UC-26-A3: Empty result** - Vietnamese empty state.

### Error Flows
- **UC-26-E1: Invalid `scope`/`cefr`** - `422`.
- **UC-26-E2: Saving a private card of another user** - `404` (OQ-41).
- **UC-26-E5: Invalid `cursor`/`limit`** - Malformed or tampered `cursor`, `limit=0`, `limit=51` -> `422` (UC-49).
- **UC-26-E3: Saving twice / unsaving unsaved** - Idempotent success.
- **UC-26-E4: Gated guest** - `403 second_visit`.

### Edge Cases
- **UC-26-X1**: `q` with SQL wildcard `%`/`_` and quotes handled literally/escaped; empty `q` = no filter; very long `q` (>100) trimmed or `422`.
- **UC-26-X2**: Search "CUP" and "cup" return same results.
- **UC-26-X3**: Explore never lists private cards of other users or pending/rejected content.
- **UC-26-X4**: Keyset pagination: default `limit=20`, max 50, stable ordering on `(created_at DESC, id DESC)` (OQ-43; UC-49).
- **UC-26-X5**: Vietnamese-diacritic search not required (English words only).

### Data Requirements
- **Tables**: `cards`, `card_labels(lower(word))`, `card_contents`, `card_saves`.
- **Covers**: FR-53, FR-52 (search, topics), FR-3, AC-28, NFR-F1; OQ-41, OQ-43.

---

## UC-27: Practice levels (Labeling, Describing, Storytelling) and unlock rules

**Actor**: Guest, Registered
**Trigger**: Opens a card in Practice.
**Preconditions**: Card visible to the user.

### Primary Flow
1. `GET /api/cards/{id}` returns labels, sentences, story, audio ids, and `progress` (levels unlocked, best scores).
2. Level 1 (Labeling): markers + IPA shown; the Vietnamese meaning is hidden until "Xem nghĩa" is tapped. User press-and-holds to speak a word; transcript posts via UC-28.
3. Level definitions (OQ-45): Level 1 = the card's labels, Level 2 = description sentences, Level 3 = story sentences. Level score = mean over the level's items of the LATEST score per item; items not yet attempted count 0. `best_score` = the maximum of this level score ever reached. When Level 1 `best_score >= 70`, Level 2 unlocks; Level 2 >= 70 unlocks Level 3. Tabs show lock states.
4. Scores/unlocks are stored in `card_progress(user_id, card_id, level 1..3, best_score, unlocked)`; rows are created lazily; Level 1 is unlocked by default. Practice and Reflex unlocks are independent (OQ-52).

**Postconditions**: `card_progress` updated; unlocks persisted server-side.

### Alternative Flows
- **UC-27-A1: Boundary 69/70** - Level 1 at 69%: Level 2 locked; at 70%: unlocked (AC-25).
- **UC-27-A2: `best_score` never decreases** - `best_score` is the max ever (OQ-45); a lower later level score does not relock an unlocked level.
- **UC-27-A3: Replay model audio/own recording** - Local playback only; no network upload of recordings.
- **UC-27-A4: Guest practice** - Same as registered for seeded cards.

### Error Flows
- **UC-27-E1: Mic permission denied** - Vietnamese guidance; Practice remains usable without scoring (listen only).
- **UC-27-E2: Silence/noise** - Message to retry; no attempt written for silence **[ASSUMED]**.
- **UC-27-E3: Attempt on a locked level** - `POST /api/attempts` for a Level 2/3 item while that level is locked -> `409 {"error":"level_locked"}`; nothing written (OQ-44; UC-47).
- **UC-27-E4: Invalid card id / not visible** - `404`.

### Edge Cases
- **UC-27-X1**: Level 3 requires Level 2 >= 70 even if Level 1 is high.
- **UC-27-X2**: Two users' progress on the same seeded card is independent.
- **UC-27-X3**: Unlock state survives reload and conversion (same user id).
- **UC-27-X4**: Press-and-hold uses Pointer Events; `pointercancel` stops recording and does not submit; context menu disabled on the button (NFR-X4).
- **UC-27-X5**: Worked example: Level 1 with 4 labels, latest scores 100, 80, 60 and one unattempted (0) -> level score 60 -> Level 2 stays locked; attempting the 4th with 100 and re-doing the 60-item with 80 -> (100+80+80+100)/4 = 90 -> unlocks; later latest scores dropping to 50 average does not relock (best_score = 90).

### Data Requirements
- **Tables**: `card_progress(user_id,card_id,level,best_score,unlocked)` (FK `cards` CASCADE), `attempts`.
- **Covers**: FR-47, AC-25, AC-2, NFR-X4; OQ-44, OQ-45, OQ-52.

---

## UC-28: Recording attempts and SM-2 review state

**Actor**: Guest, Registered
**Trigger**: User answers an item (practice or Reflex).
**Preconditions**: Identity not gated (or one grace write, UC-5).

### Primary Flow
1. Client sends `POST /api/attempts` (csrf) `AttemptIn {client_attempt_id (UUID), card_id, item_type, item_id, mode, reflex_level?, reflex_session_id?, transcript?, pronunciation?, reflex_ms?, skipped}`. There is NO client `accuracy` field (OQ-48); unknown fields -> 422.
2. Server validates (`item_type` in label|sentence|story, `mode` in shadow|reflex, `reflex_level` 1-4, `pronunciation` clamped 0-100 and stored only - never used for unlock/SRS, `reflex_ms` in 0..limit+2000), checks the card is visible (404 otherwise) and the target level is unlocked (409 `level_locked`, UC-47), then COMPUTES accuracy server-side (OQ-48): transcript and accepted answers are NFKC-lowercased with punctuation stripped; for a label: 100 if any accepted answer appears as a whole word, else round(100 x difflib ratio) capped at 60; for a sentence/story item: word-level recall via difflib matching blocks.
3. Combined score per attempt: mode `reflex` -> `reflex_score = 0.6 x accuracy + 0.4 x speed x [accuracy >= 70]` (OQ-51; speed per UC-29); mode `shadow` -> accuracy. Quality `q` from the score (OQ-47): >=90 -> 5, >=80 -> 4, >=70 -> 3, >=50 -> 2, >=20 -> 1, else 0. XP per attempt (OQ-23): 10 if score >= 70 else 2 (stored in `attempts.xp`; listen-only fallback creates no attempt).
4. In ONE `BEGIN IMMEDIATE` transaction: inserts `attempts` (UNIQUE(user_id, client_attempt_id)), updates `review_state` (SM-2, below), updates `card_progress` (level score/`best_score`/unlock, UC-27), sets `usage_sessions.had_write=1`.
5. Returns `201 AttemptOut {accuracy, score, q, unlocks, xp}`; p95 <= 150 ms. A replay with the same `client_attempt_id` returns the original result with `200` and writes nothing (UC-46).

SM-2 (OQ-47): q < 3 -> `reps=0`, `interval_days=1`, `lapses+1`. Otherwise `interval_days` = 1 for the first success, 6 for the second, then `round(previous_interval x ease)`; `reps+1`. `ease += 0.1 - (5-q) x (0.08 + 0.02 x (5-q))`, floor 1.3 (default 2.5). `due_at = now + interval_days days`, `last_reviewed_at = now`.

**Postconditions**: Atomic update; due list reflects the new schedule.

### Alternative Flows
- **UC-28-A1: Good answer (q=5, score 95)** - `reps+1`, interval 1 -> 6 -> round(6 x ease), ease +0.1.
- **UC-28-A2: Wrong/very low answer (score < 50 => q <= 1)** - `reps=0`, `lapses+1`, interval 1 day, ease reduced (q=0: -0.8; floor 1.3). Score 50-69 (q=2) also resets (q<3) but with ease -0.32.
- **UC-28-A3: Accepted answer variants** - "cup", "a cup", "Cup!" match (NFKC-lowercase, punctuation stripped, whole-word containment of an accepted answer -> accuracy 100). "cupboard" does not match "cup" as a whole word (falls to fuzzy, capped 60).
- **UC-28-A4: First attempt for an item** - Creates the `review_state` row with defaults (ease 2.5, reps 0, lapses 0) then applies SM-2.
- **UC-28-A5: Skip** - `skipped=true` -> treated as timeout: transcript null, accuracy 0, q=0, counted as an attempt, `lapses+1`, XP 2 (OQ-49).
- **UC-28-A6: Boundary quality** - score 90 -> q5; 89 -> q4; 80 -> q4; 79 -> q3; 70 -> q3 (success); 69 -> q2 (reset); 50 -> q2; 49 -> q1; 20 -> q1; 19 -> q0.

### Error Flows
- **UC-28-E1: Out-of-range values** (`reflex_ms` -5 or > limit+2000, `reflex_level` 5, unknown `item_type`/`mode`) - `422`; nothing written. `pronunciation` outside 0-100 is clamped, not rejected.
- **UC-28-E2: Unknown `item_id`/card not visible** - `404`; item not belonging to the card -> `404`/`422`.
- **UC-28-E3: Unknown fields (incl. a client `accuracy`)** - `422`.
- **UC-28-E4: Network loss** - No offline queue (OQ-46): client shows "Chưa lưu được" with a manual Retry that re-sends the SAME `client_attempt_id`, so a duplicate cannot double count.
- **UC-28-E5: CSRF failure** - `403`.
- **UC-28-E6: Locked level** - `409 level_locked` (UC-47).
- **UC-28-E7: Gated guest** - `403 second_visit` unless the grace rule applies (UC-5).

### Edge Cases
- **UC-28-X1**: Atomicity: if the `review_state` update fails the attempt is rolled back.
- **UC-28-X2**: Duplicate POST (retry after timeout, double tap) -> original result, `200`, exactly one `attempts` row (UC-46).
- **UC-28-X3**: SM-2 examples: ease 2.5, reps 2, interval 6, q=4 -> interval round(6 x 2.5)=15, ease 2.5+0.1-(1)(0.08+0.02)=2.5; q=3 -> ease 2.36; a run of q=3 attempts never drops ease below 1.3.
- **UC-28-X4**: Server recomputes accuracy and the reflex score from transcript and `reflex_ms`; a cheating client cannot set the score directly (the transcript itself is still client-supplied, which the review accepts).
- **UC-28-X5**: Concurrent attempts for the same item from two tabs serialise through `BEGIN IMMEDIATE`; no lost update; distinct `client_attempt_id`s both count.
- **UC-28-X6**: `transcript` length cap (e.g., 500) to prevent abuse **[ASSUMED, see New gaps]**.

### Data Requirements
- **Tables**: `attempts` (UNIQUE(user_id, client_attempt_id)), `review_state`, `card_progress`, `usage_sessions`.
- **Covers**: FR-48 (amended), FR-12 (write), FR-3, NFR-F2; OQ-23, OQ-44, OQ-46, OQ-47, OQ-48, OQ-49, OQ-51.

---

## UC-29: Reflex mode R1-R4 (rounds, timeout, wrong answer, scoring, unlocks)

**Actor**: Guest, Registered
**Trigger**: Opens Reflex and starts a session.
**Preconditions**: Not gated; at least one item available.

### Primary Flow
1. `POST /api/reflex/sessions {level}` (csrf) -> `201 {session_id, rounds:[<=10]}`. Rounds are chosen from due `review_state` items first, then new items with weak words first.
2. Level rules: R1 hint shown, 6 s limit; R2 no hint, 5 s; R3 no hint, 3 s; R4 describe the highlighted region, 8 s.
3. Each round: countdown ring starts, user speaks; client posts `POST /api/attempts` (mode `reflex`, `reflex_level`, `reflex_session_id`, `client_attempt_id`, transcript, `reflex_ms`); the SERVER computes accuracy (UC-28). `reflex_ms` must be 0..limit+2000; above the limit = timeout.
4. Score (OQ-51/FR-55): `reflex_score = 0.6 x accuracy + 0.4 x speed x [accuracy >= 70]`; speed = 100 at `reflex_ms <= 1000`, linear to 0 at the level limit (e.g., R2 at 3000 ms -> speed 50: (5000-3000)/(5000-1000)*100). A wrong-but-fast answer therefore scores at most 0.6 x accuracy (< 42 when accuracy < 70).
5. Feedback ("Phản xạ tốt" for good speed), then next round.
6. After the last round `POST /api/reflex/sessions/{id}/complete` (csrf, idempotent) computes the summary (session score = mean `reflex_score`), sets `reflex_sessions.completed_at/score`, updates `reflex_progress`. A session counts toward unlock only with >= 5 answered rounds (skips count as answered) (OQ-52).
7. Summary screen shows score, items to review.

**Postconditions**: Attempts and `review_state` updated per round; `reflex_progress.streak_over_80` updated.

### Alternative Flows
- **UC-29-A1: Unlock** - Next level unlocks after >=80% in 2 consecutive completed sessions of the level (each with >= 5 answered rounds); a counted session below 80 resets `streak_over_80` to 0; a session with < 5 answered rounds neither advances nor resets. Reflex unlocks are independent of Practice unlocks.
- **UC-29-A2: Skip** - `skipped=true` = timeout: transcript null, accuracy 0, q=0, counted as an answered round (OQ-49).
- **UC-29-A3: Fewer than 10 items** - Session has fewer rounds (up to 10); with zero items an empty-state message; with 3 rounds the session never counts toward unlock (< 5).
- **UC-29-A4: R4** - Scored against the highlighted label's word and accepted answers using whole-word containment in the transcript (OQ-50).

### Error Flows
- **UC-29-E1: Timeout (no answer)** - At the limit the round ends: `reflex_ms=limit` (or any value above the limit up to limit+2000), accuracy 0, speed 0 -> score 0, attempt recorded, q=0, `lapses+1`. `reflex_ms > limit+2000` -> `422`.
- **UC-29-E2: Wrong answer** - Accuracy < 70 earns no speed bonus (OQ-51): a wrong answer in 500 ms scores 0.6 x accuracy only.
- **UC-29-E3: No mic** - Falls to listen-and-repeat (UC-31); no attempts.
- **UC-29-E4: Session of another user** - `POST .../complete` for foreign session -> `404`.
- **UC-29-E5: Complete twice** - Idempotent: the second call returns the stored `ReflexSummaryOut` with the same score; `reflex_progress` is not double-counted.
- **UC-29-E6: Start/attempt on locked Reflex level** - `POST /api/reflex/sessions {level}` for a locked level, or an attempt tied to it -> `409 level_locked` (OQ-44; UC-47).
- **UC-29-E7: Gated guest** - `POST /api/reflex/sessions` -> `403 second_visit`; complete/attempts of a pre-gate session allowed within grace (UC-5).

### Edge Cases
- **UC-29-X1**: Speed boundaries: `reflex_ms=1000` -> speed 100; `reflex_ms=limit` -> 0; `reflex_ms>limit` clamps to 0.
- **UC-29-X2**: Exactly 80% counts as success (>=80).
- **UC-29-X3**: Abandoned session (user leaves) is never `completed`; does not affect `reflex_progress`.
- **UC-29-X4**: Guest Reflex: same rules; writes under guest id.
- **UC-29-X5**: Gate arrives mid-session -> UC-5 (the remaining rounds are not lost silently).
- **UC-29-X6**: Rounds contain no duplicate item within a session; due-first ordering verifiable with seeded `review_state`.
- **UC-29-X7**: R1 is unlocked by default; `reflex_progress` rows are created lazily (OQ-52).
- **UC-29-X9**: Two completed sessions of 5 answered rounds at 80.0 and 85.0 -> next level unlocks; 80 then 79.9 -> no unlock and streak reset; 4 answered rounds of 100 -> not counted.
- **UC-29-X8**: A completed round sets `had_write` (FR-12a).

### Data Requirements
- **Tables**: `reflex_sessions`, `reflex_progress`, `attempts`, `review_state`.
- **Covers**: FR-49, FR-48, FR-55, FR-56, FR-61, FR-12 (completed round), US-1; AC-42, AC-44; OQ-44, OQ-49, OQ-50, OQ-51, OQ-52.

---

## UC-30: Hide-timer option

**Actor**: Guest, Registered
**Trigger**: Toggles the timer visibility in Reflex or Profile.
**Preconditions**: Identity.

### Primary Flow
1. User turns "Ẩn đồng hồ" on; client sends `PUT /api/me/settings {hide_timer:true}` (csrf).
2. At R3 the countdown ring is not displayed, but `reflex_ms` is measured and recorded for each attempt (AC-26).
3. Setting persists across reload and device login (registered) and across reloads (guest).

### Alternative Flows
- **UC-30-A1: Toggle off** - Ring reappears.
- **UC-30-A2: Auto mode with timer hidden** - Still enforces limits.

### Error Flows
- **UC-30-E1: Non-boolean** - `422`.
- **UC-30-E2: Gated guest** - `403 second_visit` (`PUT /api/me/settings` is gate-dependent; `GET /api/me` is exempt). `hide_timer` is changed only via this endpoint, never `PATCH /api/me` (OQ-22).

### Edge Cases
- **UC-30-X1**: Hidden timer still ends the round at the limit; accessible text announces "hết giờ" via `aria-live` (every flow operable without the countdown, NFR-X2).
- **UC-30-X2**: Guest setting is carried over on conversion (same row).
- **UC-30-X3**: Guest setting is deleted on login-discard.

### Data Requirements
- **Tables**: `user_settings.hide_timer`.
- **Covers**: FR-50, FR-60, AC-26, NFR-X2; OQ-22.

---

## UC-31: Hands-free auto mode and fallbacks

**Actor**: Guest, Registered
**Trigger**: Taps "Tự động" in Reflex.
**Preconditions**: Reflex available.

### Primary Flow
1. One tap starts: countdown -> beep -> mic opens automatically -> user speaks -> scoring -> model audio plays -> next round.
2. Attempts are written per round with `mode='reflex'` (as UC-28).
3. A "Dừng" (Stop) button is always visible and works at every phase (countdown, listening, scoring, audio); stops mic and timers, keeps results saved so far, and shows the summary.

**Postconditions**: Completed rounds saved; the session may be completed.

### Alternative Flows
- **UC-31-A1: Without microphone permission (AC-27)** - Runs listen-and-repeat: model audio plays, the user repeats, no scoring; Vietnamese notice ("Chưa bật micro: chế độ nghe và nhắc lại"); no `attempts` rows, no `review_state` changes, no `had_write`.
- **UC-31-A2: Permission revoked mid-run** - Switches to listen-and-repeat for the remaining rounds.
- **UC-31-A3: TTS audio missing** - Falls back to browser speech synthesis.

### Error Flows
- **UC-31-E1: Browser lacks speech recognition** - Same as no-mic fallback with notice.
- **UC-31-E2: Audio autoplay blocked** - User gesture start (the tap) enables playback; if still blocked, show "Chạm để nghe".
- **UC-31-E3: Gate flips during auto** - UC-5-A2.

### Edge Cases
- **UC-31-X1**: Stop pressed during the beep or while a POST is in flight -> in-flight POST completes; no further rounds start; no timers leak (verify no attempts after Stop).
- **UC-31-X2**: Screen leaves (navigation) stops auto mode and releases the mic.
- **UC-31-X3**: Tab hidden during auto mode: pause or stop (no recording in background) **[ASSUMED, see New gaps]**.
- **UC-31-X5**: Listen-only fallback earns no XP (OQ-23) and writes no attempts; auto-mode attempts follow UC-28 scoring incl. `client_attempt_id`.
- **UC-31-X4**: Auto mode with hide-timer on works identically.

### Data Requirements
- **Tables**: `attempts`, `review_state` (not on fallback).
- **Covers**: FR-51, AC-27, NFR-X4.

---

## UC-32: Library tabs, review queue, mastery, profile summary

**Actor**: Guest, Registered
**Trigger**: Opens Library.
**Preconditions**: Not gated.

### Primary Flow
1. Tabs: "Bài của tôi" (`scope=mine`), "Đã lưu" (`scope=saved`), "Cần ôn lại" (`scope=due`) with a badge count of due items.
2. "Cần ôn lại" lists cards with `review_state.due_at <= now`.
3. Each card shows mastery = mean of the last <= 5 attempts on the card, where an attempt's combined score is `reflex_score` (reflex mode) or accuracy (shadow mode) (OQ-54/55): < 60% "Cần ôn", 60-84% "Đang học", >= 85% "Đã thuộc"; 0 attempts = "Chưa học". The "Cần ôn lại" badge counts CARDS with at least one due item, not items (OQ-56). Lists use keyset pagination (UC-49).
4. Search by word and topic filters/counts as in UC-26.
5. Registered "Bài của tôi" lists owned `cards` only (newest first). Uploads still processing or failed have no card yet (UC-20), so they are not listed here; their status is shown on the upload/processing screen.

**Postconditions**: None (read-only).

### Alternative Flows
- **UC-32-A1: Guest "Bài của tôi"** - Always the empty state with a "Chụp ảnh" CTA that triggers the camera gate (UC-6-A1). A saved seeded card appears ONLY in "Đã lưu", never in "Bài của tôi" (OQ-53, FR-52 as amended, AC-46).
- **UC-32-A2: Registered with no uploads** - Empty state with CTA to Add photo.
- **UC-32-A3: Empty due list** - "Không có bài cần ôn" and badge hidden/0.

### Error Flows
- **UC-32-E1: Invalid scope** - `422`.
- **UC-32-E2: Gated guest** - `403 second_visit`.

### Edge Cases
- **UC-32-X1**: Mastery boundaries: 59.99 -> "Cần ôn"; 60 -> "Đang học"; 84.99 -> "Đang học"; 85 -> "Đã thuộc".
- **UC-32-X2**: Fewer than 5 attempts -> mean of those available; zero attempts -> "Chưa học" (OQ-54); combined score as in step 3 (OQ-55).
- **UC-32-X3**: Due boundary: `due_at == now` counts as due **[ASSUMED, see New gaps]**.
- **UC-32-X4**: Badge counts cards: a card with 3 due items counts 1 (OQ-56).
- **UC-32-X5**: Guests see their own progress after conversion with no gaps (same user).
- **UC-32-X6**: p95 <= 200 ms for library endpoints on seeded data.

### Data Requirements
- **Tables**: `cards`, `card_saves`, `review_state(user_id,due_at)`, `attempts`.
- **Covers**: FR-52, FR-3, FR-59, US-2; AC-46; OQ-43, OQ-53, OQ-54, OQ-55, OQ-56.

---

## UC-33: Home and navigation

**Actor**: Guest, Registered
**Trigger**: Lands on Home or taps bottom nav.
**Preconditions**: Not gated.

### Primary Flow
1. Home shows greeting by nickname or "Bạn khách", streak/XP, "Luyện tiếp" and "Cần ôn lại" tiles, camera button.
2. Bottom nav: Home, Explore, Camera, Library, Profile. For guests the Camera item opens the camera gate (UC-6).
3. Guest banner "Đăng ký để lưu tiến trình" is visible but never blocks; tapping opens Register with `reason=profile` (skippable, Back, returns to the originating screen after success; UC-45, OQ-21). The header shows "Đã có tài khoản? Đăng nhập" (UC-44).

### Alternative Flows
- **UC-33-A1: Registered Home** - No banner; camera opens Add photo.
- **UC-33-A2: New guest tile** - "Luyện tiếp" starts the first seeded card.

### Error Flows
- **UC-33-E1: Gate error from any API** - Router intercepts `registration_required` and shows the matching gate (camera -> Back-able; second_visit -> mandatory).
- **UC-33-E2: Unknown route** - Redirect to Home.

### Edge Cases
- **UC-33-X1**: A returning registered user whose session expired sees guest Home with the visible "Đã có tài khoản? Đăng nhập" entry (OQ-19; UC-44).
- **UC-33-X2**: Browser back from Home does not exit into a blank page.
- **UC-33-X3**: Deep links to practice cards the user cannot see -> `404` screen with Home link.

### Data Requirements
- **Tables**: reads only.
- **Covers**: FR-9, FR-54 (guest card), FR-3, FR-57, US-1, AC-1; OQ-19, OQ-21.

---

## Part E - Maintenance, data integrity, quality

## UC-34: Guest data purge after 180 days idle

**Actor**: System (maintenance routine)
**Trigger**: The maintenance job runs at startup and then every 24 h as an asyncio task; also runnable as `python -m backend.app.maintenance` (OQ-57, FR-62). It is idempotent.
**Preconditions**: Guests with `last_seen_at` older than `GUEST_RETENTION_DAYS`.

### Primary Flow
1. Routine selects `users WHERE kind='guest' AND last_seen_at < now - 180 d`.
2. Also selects guests with NO writes (`had_write=0` in every usage session) and `last_seen_at < now - GUEST_EMPTY_RETENTION_DAYS (7 d)` (OQ-20 orphans).
3. Deletes each guest in a transaction by deleting the `users` row; every user-owned table cascades (OQ-17).
4. Other maintenance steps in the same run: stale `processing` sweep (expired leases -> `failed`), orphan `card_contents`/`image_assets`/file GC (only contents with no `cards` row, not seed-owned), `rate_events` older than 1 day deleted.
5. Logs counts only (no identifiers). Running it again deletes nothing new (idempotent).

**Postconditions**: Active guests, registered users and the `system` user are untouched.

### Alternative Flows
- **UC-34-A1: Orphans from cookie clears** - Purged by the same rule.
- **UC-34-A2: Custom `GUEST_RETENTION_DAYS=1` in tests**.

### Error Flows
- **UC-34-E1: Mid-run failure** - Per-user transaction rolls back that user; others proceed; re-run completes.
- **UC-34-E2: Locked DB** - `busy_timeout` retry; no partial deletes.

### Edge Cases
- **UC-34-X1**: Guest at exactly 180 days idle: boundary rule `<` (OQ-4-style; **[ASSUMED]** strict).
- **UC-34-X2**: A guest returning at day 181 while purge has not run yet continues normally; after purge it gets a new guest.
- **UC-34-X3**: Registered user idle for 5 years is never purged by this routine.
- **UC-34-X4**: A guest holding a pending gate (`gate_required_at`) is still purged.
- **UC-34-X5**: The `system` user is never purged.
- **UC-34-X6**: FK cascade is the mechanism (OQ-17, FR-66): after a guest purge no row in any user-owned table references the deleted id (verify with `PRAGMA foreign_key_check`).
- **UC-34-X7**: Empty-guest purge: a guest with writes is NOT purged at day 7 (only at 180); a guest with `had_write=0` last seen 6 d ago survives, 8 d ago is purged.
- **UC-34-X8**: GC never deletes a `card_contents` that any `cards` row references, nor seed contents; a file whose DB row is gone is not left behind.
- **UC-34-X9**: `rate_events` older than 1 day removed; newer rows untouched.

### Data Requirements
- **Tables**: all guest-owned tables.
- **Covers**: FR-6, FR-62, FR-66, D-6, PRD edge #1 (orphan purge); AC-47; OQ-17, OQ-20, OQ-27, OQ-57.

---

## UC-35: Database concurrency, startup migration, and seed idempotency

**Actor**: System, Developer
**Trigger**: App startup; concurrent requests.
**Preconditions**: SQLite file path configured.

### Primary Flow
1. On startup the app opens SQLite with `journal_mode=WAL`, `foreign_keys=ON`, `busy_timeout=5000`, `synchronous=NORMAL`.
2. Migration runner (OQ-58, FR-63): `BEGIN EXCLUSIVE`, re-read `schema_migrations` INSIDE the lock, split each file with `sqlite3.complete_statement`, execute statements one by one (never `executescript`, which auto-commits), insert the version, commit. Two processes starting together apply each migration exactly once.
3. Seed runs afterwards in its own `BEGIN IMMEDIATE` (idempotent): `system` user (`kind='system'`, no password hash, never logs in), prototype cards with images shipped under `backend/seed_assets/` copied into `DATA_DIR`, labels/audio assets; public, `moderation_status='approved'`, no AI call. Rows are keyed by a stable `seed_key`; IDs are `uuid5(seed_key)` so label/sentence IDs survive re-seeds; upsert; seed content is never deleted while referenced; `seed_version` stored in `app_meta` (OQ-59/60).
4. Startup sweep marks `processing` rows with an expired lease as `failed`; the maintenance task is scheduled (UC-34).
5. Starting the server a second time on the same DB: no migration re-applied, no duplicated seed rows (AC-29).

**Postconditions**: Schema version current; seed counts stable.

### Alternative Flows
- **UC-35-A1: New migration file** - Only the missing version applies; forward-only.
- **UC-35-A2: Multiple uvicorn workers** - Concurrent readers during writes; writes serialise (`BEGIN IMMEDIATE`); startup races on migration/seed do not corrupt or duplicate (OQ-58). The pilot nevertheless runs `--workers 1` because the AI semaphore and BackgroundTasks are per process.
- **UC-35-A3: Seed changes** - A new `seed_version` upserts by `seed_key`; a changed label keeps its uuid5 ID so users' `review_state` history survives; changing a `seed_key` would orphan history (documented risk).

### Error Flows
- **UC-35-E1: Migration SQL error** - Transaction rolls back; `schema_migrations` not updated; app fails fast with a clear log.
- **UC-35-E2: DB locked beyond 5 s** - A request returns `503/500` generic; no partial writes.
- **UC-35-E3: Backup** - Online backup API copy while serving requests yields a consistent DB (documented in README).

### Edge Cases
- **UC-35-X1**: 50 concurrent `POST /api/attempts` from different users all succeed (no `database is locked` errors) within p95 <= 150 ms.
- **UC-35-X2**: Concurrent writes by two users to different tables during an in-flight AI call: AI call outside any transaction.
- **UC-35-X3**: Constraint checks: guardian_email NOT NULL requires `guardian_consent_at`; registered requires nickname, password_hash, birth_year; `x,y` outside 0-1 rejected; `cefr_level` domain.
- **UC-35-X4**: `foreign_keys=ON` verified per connection.
- **UC-35-X5**: Production seed = the prototype cards only (OQ-59). The >= 100-card performance dataset is a TEST-ONLY fixture generator, never shipped.
- **UC-35-X6**: Re-seed twice -> identical row counts and identical IDs (uuid5 of `seed_key`); no duplicates (AC-29, AC-47). There is no admin editing of seed rows, so overwrite semantics are simply "upsert from seed".
- **UC-35-X7**: Every user-owned table has FK to `users` ON DELETE CASCADE; `card_progress`/`card_saves` also FK to `cards` (OQ-17); `PRAGMA foreign_keys=ON` per connection.
- **UC-35-X8**: Migration failure in statement N rolls back the whole file, `schema_migrations` unchanged, startup aborts with a clear log.

### Data Requirements
- **Tables**: `schema_migrations`, all.
- **Covers**: FR-45, FR-63, FR-66, NFR-A1, NFR-A2, NFR-A3, NFR-A4, AC-29, AC-31 (SQLite), AC-47; OQ-17, OQ-58, OQ-59, OQ-60.

---

## UC-36: Audio playback (pre-generated and fallback)

**Actor**: Guest, Registered
**Trigger**: Taps a speaker, auto mode model audio, Practice replay.
**Preconditions**: Not gated.

### Primary Flow
1. The card payload carries `audio_url` per label/sentence (OQ-61), e.g. `/audio/<slug>-<djb2>.mp3`; the client requests it lazily per item.
2. The files are the pre-generated catalogue copied from `docs/audio` to `frontend/audio` by a tool step and served as STATIC files at `/audio/<file>` (no auth, cacheable). `GET /api/audio/{id}` does NOT exist (404).
3. Audio plays; repeated plays use the HTTP cache.

### Alternative Flows
- **UC-36-A1: `storage_path` NULL** - `audio_url` is null; the client falls back to browser speech synthesis (en-US). A 404 on a static file triggers the same fallback.
- **UC-36-A2: Same text across images** - One `audio_assets` row (UNIQUE text+voice).

### Error Flows
- **UC-36-E1: Unknown file** - `/audio/<unknown>` -> `404`.
- **UC-36-E2: Gated guest** - Card payloads are gated (`403 second_visit`), so a gated guest gets no `audio_url`s; static `/audio/*` itself is public and unaffected.

### Edge Cases
- **UC-36-X1**: Initial JS+CSS <= 300 KB; audio not preloaded.
- **UC-36-X2**: CSP permits `blob:`/`data:` media.
- **UC-36-X3**: Directory: source catalogue `docs/audio` is copied to `frontend/audio` by a tool step; runtime serves only `frontend/audio` (OQ-61).

### Data Requirements
- **Tables**: `audio_assets` (`storage_path` NULL allowed).
- **Covers**: FR-40 (amended), NFR-F5; AC-47; OQ-61.

---

## UC-37: Accessibility and mobile expectations (testable)

**Actor**: Any user
**Trigger**: Uses the app on mobile viewports and assistive tech.
**Preconditions**: Playwright at 360x640 and 390x844.

### Primary Flow
1. Each screen renders without horizontal scroll at 360x640 and 390x844.
2. Marker buttons have `aria-label` and a computed hit area >= 44x44 px.
3. Minimum text size is 12 px; contrast meets WCAG AA (automated axe check).
4. Registration form: every field has a label; error messages live in an `aria-live` region; focus order is logical; focus moves to the first invalid field after a failed submit.
5. Mandatory gate: no close button, focus trapped to the form, Escape does nothing; camera gate: Back reachable by keyboard.
6. Hide-timer: every flow operable without the visible countdown.

### Alternative Flows
- **UC-37-A1: Safari iOS / Chrome Android** - Press-and-hold works with Pointer Events; `pointercancel` handled; context menu disabled on the hold button.
- **UC-37-A2: Reduced motion preference** - Countdown ring animation can be reduced **[ASSUMED]**.

### Error Flows
- **UC-37-E1: Mic blocked** - Non-modal guidance with link to enable permission.

### Edge Cases
- **UC-37-X1**: Text zoom 200% keeps the form usable.
- **UC-37-X2**: Landscape orientation keeps controls reachable.
- **UC-37-X3**: Screen reader announces gate reason text.

### Data Requirements
- **Covers**: NFR-X1, NFR-X2, NFR-X3, NFR-X4.

---

## UC-38: Offline and network-loss behaviour

**Actor**: Guest, Registered
**Trigger**: Connection drops mid-action.
**Preconditions**: App loaded.

### Primary Flow
1. During `POST /api/attempts` the network drops; fetch rejects.
2. Client shows a Vietnamese message ("Mất kết nối, chưa lưu được") and offers Retry (or queues one retry) without losing the displayed result.
3. On reconnect, the retry posts; the attempt is stored once.

### Alternative Flows
- **UC-38-A1: Heartbeat fails silently** - Next success resumes the session if within idle.
- **UC-38-A2: Register fails offline** - Form values kept (except password).
- **UC-38-A3: Upload fails offline** - Retry from the Add-photo screen.

### Error Flows
- **UC-38-E1: Timeout after the server processed the write** - Retry may duplicate an attempt (OQ-46).
- **UC-38-E2: Offline longer than idle timeout** - UC-5 may apply on reconnect.

### Edge Cases
- **UC-38-X1**: Bootstrap offline at cold start -> retry state (UC-1-E1); no PWA offline mode (out of scope).
- **UC-38-X2**: Poll loop on processing screen pauses offline and resumes online.

### Data Requirements
- **Covers**: PRD edge #14, FR-12(c) (heartbeat), US-2.

---

## UC-39: Public endpoints, config, static assets, and response hygiene

**Actor**: Any client
**Trigger**: Calls `/api/health`, `/api/config`, static files.
**Preconditions**: Server running.

### Primary Flow
1. `GET /api/health` -> `200` with no auth.
2. `GET /api/config` -> avatars, CEFR levels (A1|A2|B1), upload limits, gate settings (`GUEST_FREE_SESSIONS`, `GATE_GRACE_SECONDS`), min/max birth year; no secrets (no API keys, no salts, no `TRUSTED_PROXY_HOPS`).
3. Static: `/`, `/js/*`, `/css/*`, `/audio/*` served without auth; CSP allows same-origin scripts, `blob:`/`data:` images and media.
4. Every user-specific `/api/` JSON has `Cache-Control: no-store`.

### Alternative Flows
- **UC-39-A1: Health works while gated and with a broken DB?** Liveness only; DB check not required.

### Error Flows
- **UC-39-E1: Unknown `/api/*` path** - `404` JSON.
- **UC-39-E2: Wrong method** - `405`.

### Edge Cases
- **UC-39-X1**: No stack traces or SQL in error responses.
- **UC-39-X2**: `/api/config` birth-year bounds computed from the `Asia/Ho_Chi_Minh` calendar year (OQ-10).
- **UC-39-X4**: `/api/health`, `/api/config` and `POST /api/session/bootstrap` are public; heartbeat, `GET /api/me`, register, login, logout are gate-exempt (see Conventions).
- **UC-39-X3**: No token/hash fields in any response (grep over all response fixtures) (FR-5).

### Data Requirements
- **Covers**: FR-5, FR-33, FR-10 (exempt list incl. heartbeat and `GET /api/me`), NFR-S2, NFR-S6; OQ-3, OQ-10.

---

## UC-40: Required automated acceptance suites (traceability to AC-30, AC-31)

**Actor**: QA / CI
**Trigger**: `python -m pytest` and Playwright run.
**Preconditions**: Mock provider; temp DB per test.

### Primary Flow (E2E, AC-30)
0. Suites also cover AC-32..AC-47 (UC-3, 4, 5, 10, 13, 15-18, 23-25, 28, 29, 32, 34-36, 42-49); concurrency tests use two threads and a MockProvider call counter.
1. Open `/` as a new visitor (Home, guest cookie set).
2. Start a Practice level (UC-27) and record an attempt.
3. Tap the camera -> Register screen with Back (UC-6); press Back and continue (state intact).
4. Tap the camera again; register with age >= 16 (UC-7); land on the upload screen with previous progress intact.
5. Reload; still logged in (UC-14).
6. Close and reopen the browser context with saved cookies; land on Home logged in with no login screen (AC-9).

### Alternative Flows
- **UC-40-A1: pytest (AC-31)** must include tests for: guest bootstrap (UC-1/2), conversion same id + data retained (UC-7), sessions rotation/revocation/expiry (UC-14/15), rate limit (UC-13), AI-once dedupe incl. concurrency (UC-21), CSRF (UC-18), uploads type/size/EXIF (UC-22).

### Error Flows
- **UC-40-E1: Flaky timing tests** - Use configurable `SESSION_IDLE_MINUTES` and injectable clock; tests must not sleep 30 minutes.

### Edge Cases
- **UC-40-X1**: Tests use an injectable clock for session expiry/rotation/gate/purge.
- **UC-40-X2**: Provider call counter exposed by `MockProvider` for AI-once assertions.
- **UC-40-X3**: E2E contexts use isolated cookie jars; second-visit gate test uses `SESSION_IDLE_MINUTES` small (e.g., 0.05) or a clock override.

### Data Requirements
- **Covers**: AC-30, AC-31, NFR-S3 (SQL scan test).

---

## UC-41: Performance and capacity expectations

**Actor**: QA / Load test
**Trigger**: Load run with seeded dataset >= 100 cards, 50 concurrent users.
**Preconditions**: Single instance.

### Primary Flow
1. Read endpoints (`/api/cards`, `/api/cards/{id}`, library, search, bootstrap, `GET /api/me` incl. XP/streak/mastery computed on read): p95 <= 200 ms server-side on the test-only 100-card fixture (OQ-59), keyset-paginated (UC-49).
2. `POST /api/attempts`: p95 <= 150 ms.
3. Mock upload to `ready`: p95 <= 3 s.
4. Login/register scrypt 50-250 ms CPU in thread pool; other requests are not blocked.
5. Initial JS+CSS <= 300 KB uncompressed.

### Alternative Flows
- **UC-41-A1: Gemini** - p50 <= 15 s, UI progress shown, navigation not blocked.

### Error Flows
- **UC-41-E1: Provider queue saturated** - Uploads wait (limit 2) with progress; none dropped.

### Edge Cases
- **UC-41-X1**: Burst of 50 simultaneous bootstraps for new guests (a classroom) -> all succeed, 50 guest rows.
- **UC-41-X2**: 50 concurrent logins do not starve reads (thread pool).

### Data Requirements
- **Covers**: NFR-F1, NFR-F2, NFR-F3, NFR-F4, NFR-F5, AC-28 (latency).

---

## Part F - Added by the architecture review (rev 2)

## UC-42: Unshare a card (DELETE /api/cards/{id}/share)

**Actor**: Registered owner
**Preconditions**: Owner of a card with `visibility='public'`; csrf valid; not gated.
**Trigger**: Taps "Ngừng chia sẻ" on the card.

### Primary Flow (Happy Path)
1. Client sends `DELETE /api/cards/{id}/share` (csrf).
2. Server verifies ownership, sets `visibility='private'`, `published_at=NULL`; `moderation_status` of the content is unchanged (`approved`).
3. Returns `200 ShareOut {visibility:'private'}`. The card disappears from Explore for everyone; other users' `card_saves` of it no longer resolve and the card is `404` for them (OQ-41); their saved list drops it.

**Postconditions**: Card is private; image returns `404` to non-owners.

### Alternative Flows
- **UC-42-A1: Already private** - Idempotent `200`.
- **UC-42-A2: Re-share afterwards** - `POST /api/cards/{id}/share` works again (UC-25-A1) with no new moderation step if the content is still approved.

### Error Flows
- **UC-42-E1: Non-owner / unknown id / another user's private card** - `404`.
- **UC-42-E2: Guest** - `403 registration_required/camera`; gated guest -> `second_visit`.
- **UC-42-E3: Missing CSRF** - `403 csrf_failed`.

### Edge Cases
- **UC-42-X1**: An in-flight Explore page cursor referencing the card does not error; the card is simply skipped.
- **UC-42-X2**: Two other users' practice progress/attempts on the card are removed by cascade or become unreachable **[ASSUMED, see New gaps]**.

### Data Requirements
- **Output**: `ShareOut`. **Side Effects**: UPDATE `cards`. **Covers**: FR-58, FR-44; OQ-42; AC-35 (guest reasons).

---

## UC-43: Delete a card (DELETE /api/cards/{id})

**Actor**: Registered owner
**Preconditions**: Owns the card; csrf valid; not gated.
**Trigger**: Taps "Xóa thẻ" and confirms.

### Primary Flow (Happy Path)
1. Client sends `DELETE /api/cards/{id}` (csrf).
2. Server deletes the `cards` row in one transaction; `card_saves`, `card_progress`, `review_state` and `attempts` for that card cascade (FK to `cards`, OQ-17).
3. After commit, GC (OQ-27) deletes the `card_contents`, `image_assets` row and file ONLY if no `cards` row references the content and it is not seed-owned. The owner's `upload_claims` row remains (or is removed with the content) **[claim cleanup ASSUMED]**.
4. Returns `204`.

**Postconditions**: Card gone from Library/Explore for all; private image file removed if unreferenced.

### Alternative Flows
- **UC-43-A1: Shared card** - Same; the card also disappears from Explore and others' "Đã lưu".
- **UC-43-A2: Content held by another user's card** - Content, asset and file are kept.
- **UC-43-A3: Re-upload after delete** - Re-uploading the same bytes either dedupes to the surviving content (0 AI calls) or, if GC removed it, runs the AI again as a new image.

### Error Flows
- **UC-43-E1: Non-owner / unknown / other user's private card** - `404`.
- **UC-43-E2: Seed card** - `404` for non-owners (seed owner is the `system` user).
- **UC-43-E3: Guest / gated / CSRF** - `403 camera` / `403 second_visit` / `403 csrf_failed`.
- **UC-43-E4: Double delete** - Second call `404`.

### Edge Cases
- **UC-43-X1**: GC must not delete content while a `cards` row still references it (RESTRICT FK would also block it).
- **UC-43-X2**: Delete while the owner's practice session on the card is open -> next attempt `404`.

### Data Requirements
- **Side Effects**: DELETE `cards` (+cascades), GC of contents/assets/files. **Covers**: FR-58, FR-29 (GC), FR-66; AC-39; OQ-27, OQ-42.

---

## UC-44: Guest "Đã có tài khoản? Đăng nhập" entry point

**Actor**: Guest (new, or returning after cleared cookies / expired / revoked session)
**Trigger**: Taps the link in the Home header or on the Profile screen.

### Primary Flow (Happy Path)
1. Home header and Profile (guest view) show "Đã có tài khoản? Đăng nhập" at all times (also on Register and the camera gate).
2. Tap opens the Login screen (nickname, password) with Back; no API call.
3. Submit follows UC-11 (guest without progress, silent discard) or UC-12 (guest with progress, discard warning).
4. After login the user lands on Home as the registered account.

**Postconditions**: Registered session; guest row deleted.

### Alternative Flows
- **UC-44-A1: Gated guest (second_visit)** - Link is on the mandatory Register screen only; Login still works (exempt).
- **UC-44-A2: Registered user** - Link hidden.

### Error Flows
- **UC-44-E1**: Wrong credentials / rate limit / CSRF per UC-11, UC-13, UC-18; guest unchanged.

### Edge Cases
- **UC-44-X1**: The screen reveals nothing about whether the browser previously had an account (OQ-19).
- **UC-44-X2**: Back from Login returns to the previous screen with state intact.

### Data Requirements
- **Covers**: FR-1 (amended), FR-25, FR-28; AC-9; OQ-19.

---

## UC-45: Register with reason=profile (skippable banner)

**Actor**: Guest
**Trigger**: Taps the "Đăng ký để lưu tiến trình" banner (Home) or card (Profile).

### Primary Flow (Happy Path)
1. Client opens Register with `reason=profile`; a Back button is present (as for camera), no gate involved.
2. Guest submits (UC-7); on `201` the client returns to Profile (not Home, not Add-photo).
3. Profile now shows registered fields; progress preserved (same user id).

**Postconditions**: Converted account; user on Profile.

### Alternative Flows
- **UC-45-A1: Back** - Returns to the originating screen; no account, no API call.
- **UC-45-A2: Mandatory gate arrives meanwhile** - Next bootstrap/heartbeat returns `second_visit`; the screen becomes mandatory (no Back).
- **UC-45-A3: Login link** - UC-44.

### Error Flows
- **UC-45-E1**: Validation, duplicate nickname, rate limit, CSRF per UC-8, UC-9, UC-10, UC-18.

### Edge Cases
- **UC-45-X1**: `reason=profile` is a client-side route/entry reason only; the server never returns `reason:"profile"` in an error.

### Data Requirements
- **Covers**: FR-9, FR-54; OQ-8, OQ-21.

---

## UC-46: `client_attempt_id` replay (idempotent attempts)

**Actor**: Guest or Registered (client retry, double tap, lost response)
**Trigger**: `POST /api/attempts` sent twice with the same `client_attempt_id`.

### Primary Flow (Happy Path)
1. Client generates a UUID `client_attempt_id` per answered round and sends the attempt.
2. Response is lost; client retries with the SAME id.
3. Server finds UNIQUE(user_id, client_attempt_id), returns the ORIGINAL `AttemptOut {accuracy, score, q, unlocks, xp}` with `200` (first call was `201`). No new `attempts` row, no XP, no SM-2 or progress change.

**Postconditions**: Exactly one attempt row.

### Alternative Flows
- **UC-46-A1: Two tabs, same id** - Concurrent calls serialise (`BEGIN IMMEDIATE`); one `201`, one `200`.
- **UC-46-A2: Same id, different user** - Scoped per user: both are new attempts.
- **UC-46-A3: Replay inside the grace window of a gated guest** - Still returns `200` original (if past the window and gated: `403`).

### Error Flows
- **UC-46-E1: Missing / non-UUID `client_attempt_id`** - `422`.
- **UC-46-E2: Same id, different payload** - Original result returned unchanged (payload ignored) **[ASSUMED, see New gaps]**.

### Edge Cases
- **UC-46-X1**: No offline queue; replay happens only from a manual/auto client retry.
- **UC-46-X2**: Replay after the card was deleted -> `404` (cascade removed the attempt).

### Data Requirements
- **Tables**: `attempts` UNIQUE(user_id, client_attempt_id). **Covers**: FR-48, AC-44; OQ-46.

---

## UC-47: Attempt or session on a locked level (`level_locked` 409)

**Actor**: Guest or Registered (stale UI, or a crafted request)
**Trigger**: `POST /api/attempts` for Level 2/3 content, or `POST /api/reflex/sessions {level: R2..R4}`, while that level is locked.

### Primary Flow (Happy Path)
1. Server resolves the target level (label -> 1, description sentence -> 2, story -> 3; Reflex level from the request).
2. Level is locked (Practice: lower level `best_score < 70`; Reflex: previous level not unlocked, R1 always unlocked).
3. Returns `409 {"error":"level_locked"}`; nothing is written (no attempt, XP, review state, `had_write`).
4. Client refreshes the card/progress and shows the locked tab.

### Alternative Flows
- **UC-47-A1: Unlocked by a concurrent tab** - Next attempt succeeds normally.
- **UC-47-A2: Level 1 / R1** - Never locked.

### Error Flows
- **UC-47-E1: Card not visible** - `404` takes precedence over `409`.
- **UC-47-E2: Gated guest** - `403 second_visit` takes precedence.

### Edge Cases
- **UC-47-X1**: `best_score` 69.99 -> locked; 70 -> unlocked (AC-25).
- **UC-47-X2**: Unlocked levels never relock (best_score is a max).
- **UC-47-X3**: Practice and Reflex unlocks are independent: Reflex R2 unlocked does not unlock Practice Level 2.

### Data Requirements
- **Covers**: FR-47, FR-49, FR-61, AC-44; OQ-44, OQ-52.

---

## UC-48: Image analysis unavailable (`analysis_unavailable` 409)

**Actor**: Registered user
**Trigger**: Re-uploads an image whose AI budget is spent.

### Primary Flow (Happy Path)
1. Image X failed twice in its first run (2 calls), then two manual re-uploads each failed (`manual_retries=2`, `ai_calls=6`).
2. User uploads X again. Server detects the exhausted budget (`manual_retries>=2` or `ai_calls>=6`) inside `BEGIN IMMEDIATE`.
3. Returns `409 {"error":"analysis_unavailable"}` with a Vietnamese message ("Không phân tích được ảnh này, hãy thử ảnh khác"); 0 provider calls; `ai_calls` unchanged; status stays `failed`.

**Postconditions**: No state change; the new user still gets an `upload_claims` row only if the budget check is after claim creation **[ASSUMED, see New gaps]**.

### Alternative Flows
- **UC-48-A1: Different user, same raw bytes** - Same `409` (budget is per image, shared).
- **UC-48-A2: Budget not exhausted** - Retry runs (UC-23).

### Error Flows
- **UC-48-E1: Poll of a failed image** - Returns `status:'failed'` (200) with the same message; never calls the provider.

### Edge Cases
- **UC-48-X1**: Boundary: `manual_retries=1` still allows one more run; `ai_calls=5` with `manual_retries=1` allows a run limited to the remaining calls (hard cap 6) **[exact behaviour ASSUMED]**.
- **UC-48-X2**: Concurrent re-uploads at the boundary: exactly one wins the last retry.

### Data Requirements
- **Covers**: FR-38 (amended); AC-40, AC-41; OQ-34, OQ-36.

---

## UC-49: Keyset pagination (GET /api/cards and library lists)

**Actor**: Guest or Registered
**Trigger**: Scrolls Explore/Library or requests another page.

### Primary Flow (Happy Path)
1. `GET /api/cards?scope=explore&limit=20` -> `CardPage {items<=20, next_cursor}` ordered by `(created_at DESC, id DESC)`.
2. Client requests `GET /api/cards?...&cursor=<next_cursor>`; the cursor is opaque (encodes the last `(created_at, id)`); the next page continues strictly after it.
3. Last page: `next_cursor=null`.

**Postconditions**: Every card appears exactly once across pages.

### Alternative Flows
- **UC-49-A1: Default / max limit** - No `limit` -> 20; `limit=50` accepted.
- **UC-49-A2: Rows with identical `created_at`** - Ordered by `id DESC`; no duplicates or gaps at page boundaries.
- **UC-49-A3: Insert between page fetches** - New newest card does not shift or repeat later pages.
- **UC-49-A4: Filters** - Cursor valid only with the same filters; mismatch -> `422` **[ASSUMED]**.

### Error Flows
- **UC-49-E1: `limit=0`, `limit=51`, non-integer** - `422`.
- **UC-49-E2: Malformed/tampered cursor** - `422` (no SQL error, no 500).
- **UC-49-E3: Gated guest** - `403 second_visit`.

### Edge Cases
- **UC-49-X1**: Empty result -> `items=[]`, `next_cursor=null`.
- **UC-49-X2**: Deleted/unshared card referenced by a cursor does not break the next page.
- **UC-49-X3**: p95 <= 200 ms with the 100-card test fixture.

### Data Requirements
- **Covers**: FR-52, FR-53, FR-59; OQ-43.

---

## Business-rule summary (cross-cutting)

| Rule | Where |
|---|---|
| Guest has no upload/share/profile edit; server returns `403 registration_required` with `camera` (cards/uploads/share) or `account` (PATCH/DELETE me, logout-all); `second_visit` wins | UC-6, UC-16, UC-20, UC-24, UC-25, UC-4 |
| Upload never creates a card; claims gate access; unsafe share -> 422 `share_not_allowed` | UC-20, UC-24, UC-25, UC-48 |
| Server-computed scoring, SM-2, XP, `client_attempt_id` idempotency, `level_locked` | UC-28, UC-29, UC-46, UC-47 |
| Second-visit gate persisted by `gate_required_at`, server-enforced | UC-4, UC-5 |
| Only write-sessions count; 30 min idle | UC-3 |
| Conversion keeps user id | UC-7, UC-9 |
| Discard with warning at login | UC-12 |
| Rotation / revocation / expiry | UC-14, UC-15 |
| AI once per unique image | UC-20, UC-21, UC-23 |
| Private by default, `404` for hidden | UC-24, UC-25 |
| Tokens/hashes/guardian email never returned or logged | UC-1, UC-7, UC-8, UC-18, UC-39 |

---

## Traceability Matrix

### Functional requirements

| FR | Use cases |
|---|---|
| FR-1 | UC-1, UC-19 |
| FR-2 | UC-2 |
| FR-3 | UC-1, UC-2, UC-26, UC-27, UC-28, UC-32, UC-33 |
| FR-4 | UC-6, UC-16, UC-20, UC-24, UC-25 |
| FR-5 | UC-1, UC-39, UC-18 |
| FR-6 | UC-34, UC-19, UC-2 |
| FR-7 | UC-1, UC-4 |
| FR-8 | UC-3, UC-4 |
| FR-9 | UC-6, UC-33 |
| FR-10 | UC-4, UC-39, UC-3 |
| FR-11 | UC-4, UC-12 |
| FR-12 | UC-3, UC-28, UC-29, UC-31 |
| FR-13 | UC-5 |
| FR-14 | UC-7, UC-8 |
| FR-15 | UC-8 |
| FR-16 | UC-7, UC-8 |
| FR-17 | UC-7, UC-9 |
| FR-18 | UC-10, UC-9 |
| FR-19 | UC-7 |
| FR-20 | UC-8, UC-9 |
| FR-21 | UC-7, UC-11 |
| FR-22 | UC-11, UC-14 |
| FR-23 | UC-14 |
| FR-24 | UC-11, UC-14 |
| FR-25 | UC-15, UC-14 |
| FR-26 | UC-11 |
| FR-27 | UC-13, UC-10 |
| FR-28 | UC-12 |
| FR-29 | UC-16, UC-17 |
| FR-30 | UC-18 |
| FR-31 | UC-8, UC-18 |
| FR-32 | UC-18, UC-8, UC-39 |
| FR-33 | UC-18, UC-39, UC-1 |
| FR-34 | UC-20, UC-22 |
| FR-35 | UC-20, UC-22 |
| FR-36 | UC-20, UC-21 |
| FR-37 | UC-21 |
| FR-38 | UC-23, UC-20 |
| FR-39 | UC-20 |
| FR-40 | UC-36, UC-20 |
| FR-41 | UC-24 |
| FR-42 | UC-20, UC-21, UC-24 |
| FR-43 | UC-25, UC-24 |
| FR-44 | UC-25 |
| FR-45 | UC-35, UC-1 |
| FR-46 | UC-20 |
| FR-47 | UC-27 |
| FR-48 | UC-28, UC-29 |
| FR-49 | UC-29 |
| FR-50 | UC-30, UC-16 |
| FR-51 | UC-31 |
| FR-52 | UC-32, UC-26 |
| FR-53 | UC-26 |
| FR-54 | UC-16, UC-33, UC-45 |
| FR-55 (scoring) | UC-28, UC-29 |
| FR-56 (SM-2) | UC-28 |
| FR-57 (XP/streak/level) | UC-16, UC-28, UC-33 |
| FR-58 (unshare/delete card) | UC-42, UC-43 |
| FR-59 (keyset pagination) | UC-26, UC-32, UC-49 |
| FR-60 (`/api/me`, settings for guests) | UC-16, UC-30, UC-4 |
| FR-61 (reflex_progress, unlocks) | UC-29, UC-47 |
| FR-62 (maintenance job) | UC-34 |
| FR-63 (migration runner, seed) | UC-35 |
| FR-64 (client IP, trusted proxy) | UC-10, UC-13 |
| FR-65 (processing lease) | UC-23, UC-20 |
| FR-66 (FK cascade) | UC-12, UC-17, UC-34, UC-35, UC-43 |
| Amended: FR-10/FR-13 grace + exempt list | UC-3, UC-4, UC-5 |
| Amended: FR-29/FR-36/FR-38/FR-41/FR-44/FR-52 | UC-17, UC-20, UC-23, UC-24, UC-25, UC-32 |
| Guest login entry (OQ-19) | UC-44, UC-14, UC-19 |
| `analysis_unavailable`, `level_locked`, replay | UC-48, UC-47, UC-46 |

### Acceptance criteria

| AC | Use cases (flow) |
|---|---|
| AC-1 | UC-1 |
| AC-2 | UC-2, UC-27 |
| AC-3 | UC-6 |
| AC-4 | UC-6-E1, UC-20-E1 |
| AC-5 | UC-4 |
| AC-6 | UC-3-A2 |
| AC-7 | UC-3-A1 |
| AC-8 | UC-7 |
| AC-9 | UC-14, UC-40 |
| AC-10 | UC-11 |
| AC-11 | UC-8 (rows 18, 19) |
| AC-12 | UC-7-A1, UC-8-X2, UC-16-X3 |
| AC-13 | UC-8-A1, UC-9-A1 |
| AC-14 | UC-13 |
| AC-15 | UC-11-E2 |
| AC-16 | UC-12 |
| AC-17 | UC-18-E1..E3 |
| AC-18 | UC-15 |
| AC-19 | UC-21-A1 |
| AC-20 | UC-21 |
| AC-21 | UC-22-E1..E3 |
| AC-22 | UC-22 |
| AC-23 | UC-25 |
| AC-24 (amended: 422 share_not_allowed) | UC-25-A2, UC-25-A3 |
| AC-25 | UC-27-A1 |
| AC-26 | UC-30 |
| AC-27 | UC-31-A1 |
| AC-28 | UC-26, UC-41 |
| AC-29 | UC-35 |
| AC-30 | UC-40, UC-7-A4 |
| AC-31 | UC-40-A1 and UC-1, 7, 13, 14, 18, 21, 22 |
| AC-32 | UC-5, UC-3-E1, UC-4 |
| AC-33 | UC-3-X1 |
| AC-34 | UC-3-X10, UC-4-X3, UC-1-A2 |
| AC-35 | UC-6-E1, UC-15-E1, UC-16-E1, UC-4-X6 |
| AC-36 | UC-13, UC-10 |
| AC-37 | UC-10-X2 |
| AC-38 | UC-18-E5, UC-18-E6, UC-18-A1 |
| AC-39 | UC-17, UC-43 |
| AC-40 | UC-24-E2, UC-23-E1, UC-48 |
| AC-41 | UC-23-A4, UC-23-X6, UC-20 |
| AC-42 | UC-28, UC-29-E1, UC-29-E2 |
| AC-43 | UC-28-A6, UC-28-X3 |
| AC-44 | UC-46, UC-47, UC-27-E3 |
| AC-45 | UC-16-X2 |
| AC-46 | UC-32-A1, UC-32-X4 |
| AC-47 | UC-36, UC-35, UC-34 |

### Non-functional and PRD edge-case groups (secondary)

| Item | Use cases |
|---|---|
| NFR-S1..S7 | UC-18, UC-8, UC-11, UC-22, UC-39 |
| NFR-P1..P5 | UC-7, UC-8, UC-17, UC-25, UC-34 |
| NFR-F1..F5 | UC-41, UC-26, UC-28 |
| NFR-A1..A4 | UC-35, UC-23 |
| NFR-X1..X4 | UC-37, UC-24, UC-27, UC-31 |
| Edge #1 cookie cleared | UC-19, UC-34 |
| Edge #2 guest two devices | UC-19-A2/A3 |
| Edge #3 simultaneous uploads | UC-21 |
| Edge #4 register while upload | UC-9-A2/A3 |
| Edge #5 double submit | UC-9 |
| Edge #6 age/consent | UC-8, UC-7-A1/A2 |
| Edge #7 nickname race | UC-8-A1/E1, UC-9-A1 |
| Edge #8 brute force | UC-13 |
| Edge #9 session counting | UC-3 |
| Edge #10 mid-practice gate | UC-5 |
| Edge #11 login with discard | UC-12 |
| Edge #12 session lifecycle | UC-14, UC-15 |
| Edge #13 upload failures | UC-23, UC-20-E3, UC-25-A3 |
| Edge #14 offline / cookies blocked | UC-38, UC-1-E2, UC-19-E1 |
| Edge #15 CSRF edges | UC-18 |
| Edge #16 account deletion shared cards (overridden: shared cards deleted) | UC-17-A1 |
| Edge #1 (overridden: new guest + login link) | UC-14-E1, UC-19, UC-44 |

**Coverage result**: all FR-1..FR-66 and AC-1..AC-47 map to at least one use case. New: UC-42..UC-49.

---

## Resolved by architecture review

All former open questions are decided by [guest_first_web_app_review.md](../architecture/guest_first_web_app_review.md). Where the review differs from the PRD text, the review wins until the PRD is amended (the PRD §1 amendments FR-55..FR-66 / AC-32..AC-47 now carry most of these).

| OQ | Decision (short) | Reflected in |
|---|---|---|
| OQ-1 | File name final | header |
| OQ-2 | `GUEST_FREE_SESSIONS=1` | Conventions, UC-1-A2, UC-3-X10 |
| OQ-3, OQ-9 | Heartbeat and `GET /api/me` exempt; grace 600 s for attempts/complete | Conventions, UC-3-E1, UC-4, UC-5 |
| OQ-4 | Strictly older than idle; 30:00 same session | UC-3, UC-3-X1 |
| OQ-5 | second_visit wins over camera/account | Conventions, UC-4-E1, UC-6-E2 |
| OQ-6 | Gate re-evaluated at new session start, cleared if not met | UC-3-X10, UC-4-X3 |
| OQ-7 | logout idempotent 204; logout-all guest 403 account | UC-15, UC-4-X5 |
| OQ-8 | Reasons camera/account/profile/second_visit | Conventions, UC-6, UC-16, UC-45 |
| OQ-10 | Asia/Ho_Chi_Minh calendar year | UC-7-X6, UC-8-X6, UC-39-X2 |
| OQ-11 | ASCII nickname charset | UC-7, UC-8 |
| OQ-12 | No confirm/reset accepted | UC-8-E3 |
| OQ-13 | Stable CSRF; re-bootstrap once, retry once | Conventions, UC-9-A2, UC-12-X1, UC-18 |
| OQ-14 | already_registered only with valid session; else nickname_taken + Login | UC-7-E6, UC-9-E1/E2 |
| OQ-15, OQ-18 | `rate_events`; 100 login fails/IP/15 min, 30 registrations/IP/h; counting rules | UC-10, UC-13 |
| OQ-16 | `TRUSTED_PROXY_HOPS` | UC-10-X2 |
| OQ-17 | FK cascades everywhere | UC-12, UC-34-X6, UC-35-X7 |
| OQ-19 | Expired/revoked = new guest + login link | UC-14-E1/E2, UC-19, UC-33-X1, UC-44 |
| OQ-20 | Orphan guest accepted; one bootstrap promise per tab; 7-day empty purge | UC-1, UC-34 |
| OQ-21 | `reason=profile`, Back, return to Profile | UC-16-A1, UC-33, UC-45 |
| OQ-22 | PATCH = avatar/CEFR; PUT settings = hide_timer | UC-16-X1, UC-30 |
| OQ-23 | XP/streak/level computed on read | UC-16, UC-28 |
| OQ-24 | CEFR A1/A2/B1 only | UC-16-X4 |
| OQ-25 | Wrong password on DELETE counts in nickname bucket | UC-13-A4, UC-17-E1 |
| OQ-26, OQ-27 | Deletion removes shared cards; orphan GC | UC-17, UC-34, UC-43 |
| OQ-28 | Origin/Referer both missing -> 403 (bootstrap excepted); `__Host-` cookie | UC-18, UC-1-E3 |
| OQ-29, OQ-38 | Upload creates no card; `upload_claims`; 404 without claim | UC-20, UC-21, UC-24 |
| OQ-30 | 413 image_too_large; 415 unsupported_image; 422 corrupt | UC-22 |
| OQ-31 | `dedupe` none/ready/in_flight + message | UC-21 |
| OQ-32 | Dedupe on raw-byte sha256 | UC-20, UC-21 |
| OQ-33, OQ-34, OQ-36 | Pre-call `ai_calls`; 1 auto retry; 2 manual; cap 6; 409 analysis_unavailable | UC-23, UC-48 |
| OQ-35 | Lease + lazy sweep; poll stops at 120 s | UC-23-A4 |
| OQ-37 | Review limits | UC-24 |
| OQ-39, OQ-40 | public; unsafe -> 422 share_not_allowed, no pending | UC-25 |
| OQ-41 | 404 on every foreign private card subroute | UC-25, UC-26-E2 |
| OQ-42 | Unshare and delete endpoints | UC-42, UC-43 |
| OQ-43 | Keyset pagination | UC-49 |
| OQ-44 | 409 level_locked | UC-27-E3, UC-29-E6, UC-47 |
| OQ-45 | Level score definition | UC-27 |
| OQ-46 | `client_attempt_id` replay -> 200 | UC-28, UC-46 |
| OQ-47 | SM-2 mapping | UC-28 |
| OQ-48, OQ-49, OQ-50, OQ-51 | Server accuracy, skip, R4, speed gating | UC-28, UC-29 |
| OQ-52 | Lazy reflex_progress, >=5 rounds | UC-29 |
| OQ-53 | Guest "Bài của tôi" empty state | UC-32-A1 |
| OQ-54, OQ-55, OQ-56 | Mastery, combined score, card-count badge | UC-32 |
| OQ-57 | Maintenance job | UC-34 |
| OQ-58, OQ-59, OQ-60 | Migration runner, seed content, uuid5 seed keys | UC-35 |
| OQ-61 | Audio via `/audio`; no `/api/audio` | UC-36 |
| OQ-62 | `prior_sessions` recomputed | UC-3 |
| OQ-63 | Stays with PO; release-blocking for under-16 production | UC-7-X6, UC-8-X6 |
| FR-11, FR-7 vs FR-13, persona vs D-7 | Wording/priority rulings | UC-4, UC-3, UC-8 |

## New gaps (not covered by the review; need PO/architect confirmation)

1. Does a successful login clear that nickname's earlier failures (rate bucket)? (UC-11, UC-13-X4)
2. Resuming an abandoned upload: with no draft card, where does the user re-enter Review for a ready `content_id`? (UC-20-A2)
3. Do `upload_claims` count as references for orphan GC, and are claims cleaned when a card is deleted? (UC-17-E4, UC-43)
4. After login from the camera gate, is Add-photo resumed? Assumed no. (UC-6-A2)
5. Behaviour when a replayed `client_attempt_id` carries a different payload; assumed original returned. (UC-46-E2)
6. Does `analysis_unavailable` check run before or after inserting the `upload_claims` row, and the exact last-retry rule near the 6-call cap. (UC-48)
7. Cursor/filter mismatch handling (422 assumed). (UC-49-A4)
8. Effect of unsharing on other users' progress/attempts on the card. (UC-42-X2)
9. Minor assumptions: cookies-blocked read-only mode (UC-1-E2), registered-user `re_device` rejection (UC-1-X2), server-clock regression (UC-2-X2), transcript length cap (UC-28-X6), hidden-tab auto mode (UC-31-X3), `due_at == now` counts as due (UC-32-X3), lease boundary inclusivity (UC-23-X5), EXIF orientation applied before strip (UC-22-A2), silence creates no attempt (UC-27-E2).

