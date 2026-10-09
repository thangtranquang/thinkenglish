// Hash router: #/<name>[/<id>][?k=v]. Screens: render(ctx) -> Element | Promise<Element>.
import { S } from "./state.js";
import { el } from "./ui.js";

const FORCED_OK = new Set(["gate", "register", "login"]);
let table = {};
let token = 0;
let leave = [];

export function configure(t) {
  table = t;
}

export function parseHash(hash = location.hash) {
  const raw = hash.replace(/^#\/?/, "");
  const [path, qs] = raw.split("?");
  const seg = path.split("/").filter(Boolean).map(decodeURIComponent);
  return { name: seg[0] || "home", id: seg[1] || null, query: Object.fromEntries(new URLSearchParams(qs || "")) };
}

export function navigate(name, { id, query, replace = false } = {}) {
  let h = "#/" + name + (id ? "/" + encodeURIComponent(id) : "");
  const qs = new URLSearchParams(query || {}).toString();
  if (qs) h += "?" + qs;
  if (location.hash === h) {
    renderRoute();
    return;
  }
  if (replace) location.replace(h);
  else location.hash = h;
}

export function back(fallback = "home") {
  if (history.length > 1) history.back();
  else navigate(fallback);
}

// Camera button: guests see the camera gate, registered users go to Add-photo.
export function openCamera() {
  if (S.isGuest) navigate("gate", { id: "camera" });
  else navigate("addphoto");
}

export function onGateRequired(reason) {
  if (reason === "second_visit") S.gate = "second_visit";
  navigate("gate", { id: reason, replace: true });
}

function drawNav(active) {
  const nav = document.getElementById("nav");
  if (!active || S.gate === "second_visit") {
    nav.classList.add("hidden");
    nav.replaceChildren();
    return;
  }
  nav.classList.remove("hidden");
  const items = [
    ["home", "🏠", "Trang chủ"],
    ["explore", "🧭", "Khám phá"],
    ["camera", "📷", "Thêm ảnh"],
    ["library", "📚", "Thư viện"],
    ["profile", "👤", "Hồ sơ"],
  ];
  nav.replaceChildren(
    ...items.map(([k, e, t]) =>
      el(
        "button",
        {
          type: "button",
          class: (k === "camera" ? "cam " : "") + (k === active ? "on" : ""),
          "aria-label": t,
          "aria-current": k === active ? "page" : null,
          "data-testid": "nav-" + k,
          onclick: () => (k === "camera" ? openCamera() : navigate(k)),
        },
        el("span", { class: "e", "aria-hidden": "true" }, e),
        k === "camera" ? null : t,
      ),
    ),
  );
}

export async function renderRoute() {
  const my = ++token;
  leave.forEach((f) => {
    try {
      f();
    } catch {
      /* ignore */
    }
  });
  leave = [];
  let r = parseHash();
  if (S.gate === "second_visit" && !FORCED_OK.has(r.name)) {
    navigate("gate", { id: "second_visit", replace: true });
    return;
  }
  if (!table[r.name]) r = { name: "home", id: null, query: {} };
  const route = table[r.name];
  const ctx = { id: r.id, query: r.query, navigate, back, onLeave: (f) => leave.push(f) };
  const host = document.getElementById("screen");
  let node;
  try {
    node = await route.render(ctx);
  } catch (e) {
    node = el("div", { class: "body" }, el("p", { class: "sub", role: "alert" }, "Không tải được màn hình. Vui lòng thử lại."));
  }
  if (my !== token) return;
  host.replaceChildren(node);
  drawNav(route.nav);
}

export function start() {
  window.addEventListener("hashchange", renderRoute);
  renderRoute();
}
