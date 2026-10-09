// The only module that talks to the backend. Every call goes through api().
import { S, normalizeMe } from "./state.js";

export class ApiError extends Error {
  constructor(status, body = {}, retryAfter = null) {
    super(body.error || "http_error");
    this.status = status;
    this.error = body.error || "http_error";
    this.reason = body.reason || null;
    this.fields = body.fields || null;
    this.retryAfter = retryAfter;
  }
}

let bootPromise = null;
let gateHandler = () => {};

export function setGateHandler(fn) {
  gateHandler = fn;
}

function readCookie(name) {
  for (const part of document.cookie.split("; ")) {
    const i = part.indexOf("=");
    const k = part.slice(0, i);
    if (k === name || k === "__Host-" + name) return decodeURIComponent(part.slice(i + 1));
  }
  return null;
}

async function parse(res) {
  if (res.status === 204) return null;
  try {
    return await res.json();
  } catch {
    return null;
  }
}

async function doBootstrap() {
  const res = await fetch("/api/session/bootstrap", { method: "POST", credentials: "same-origin", headers: { Accept: "application/json" } });
  const data = await parse(res);
  if (!res.ok) throw new ApiError(res.status, data || {});
  S.csrf = data.csrf_token || S.csrf;
  S.me = normalizeMe(data.user);
  S.isGuest = data.is_guest ?? !(data.user && data.user.kind === "registered");
  S.gate = data.gate && data.gate.reason ? data.gate.reason : null;
  if (data.config) S.config = data.config;
  if (!S.config) {
    const c = await fetch("/api/config", { credentials: "same-origin" });
    if (c.ok) S.config = await c.json();
  }
  return data;
}

// One shared bootstrap promise per tab. force=true re-runs it (after logout, csrf failure, login).
export function bootstrap(force = false) {
  if (!bootPromise || force) {
    bootPromise = doBootstrap().catch((e) => {
      bootPromise = null;
      throw e;
    });
  }
  return bootPromise;
}

function withQuery(path, query) {
  if (!query) return path;
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
  const s = p.toString();
  return s ? path + "?" + s : path;
}

export async function api(method, path, { body, form, query, _retried = false } = {}) {
  await bootstrap();
  const headers = { Accept: "application/json" };
  const opts = { method, credentials: "same-origin", headers };
  if (method !== "GET" && method !== "HEAD") headers["X-CSRF-Token"] = readCookie("re_csrf") || S.csrf || "";
  if (form) opts.body = form;
  else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }

  const res = await fetch(withQuery(path, query), opts);
  const data = await parse(res);
  if (res.ok) return data;

  const err = new ApiError(res.status, data || {}, res.headers.get("Retry-After"));
  if (res.status === 403 && err.error === "csrf_failed" && !_retried) {
    await bootstrap(true);
    return api(method, path, { body, form, query, _retried: true });
  }
  if (res.status === 403 && (err.reason === "second_visit" || err.error === "registration_required")) {
    gateHandler(err.reason || "camera");
  }
  throw err;
}

export const get = (path, query) => api("GET", path, { query });
export const post = (path, body) => api("POST", path, { body });
export const put = (path, body) => api("PUT", path, { body });
export const patch = (path, body) => api("PATCH", path, { body });
export const del = (path, body) => api("DELETE", path, { body });

// Adopt a MeOut response (register / login / patch).
export function adoptMe(me) {
  S.me = normalizeMe(me && me.user ? me.user : me); // register/login/patch answer with MeOut {user, ...}
  S.isGuest = false;
  S.gate = null;
}

// Re-run bootstrap after logout / account deletion so the tab becomes a fresh guest.
export async function resetToGuest() {
  await bootstrap(true);
}

export function startHeartbeat(onGate) {
  setInterval(async () => {
    if (document.hidden) return;
    try {
      const r = await post("/api/session/heartbeat");
      if (r && r.gate && r.gate.reason === "second_visit" && S.gate !== "second_visit") {
        S.gate = "second_visit";
        onGate();
      }
    } catch {
      /* ignore */
    }
  }, 60000);
}
