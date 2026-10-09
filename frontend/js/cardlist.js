// Shared paged card grid with topic chips and search (Explore + Library).
import { get } from "./api.js";
import { el, tile, debounce, errorMessage } from "./ui.js";

const PAGE = 20;

export async function loadTopics() {
  try {
    const r = await get("/api/topics");
    const list = Array.isArray(r) ? r : r.topics || r.items || [];
    return list.map((t) => (typeof t === "string" ? t : t.name || t.topic || t.key || "")).filter(Boolean);
  } catch {
    return [];
  }
}

// opts: { scope, state: {topic, q}, status, onOpen(card), empty() -> Element }
export function createCardList({ scope, state, topicKey, qKey, status = false, onOpen, empty }) {
  const grid = el("div", { class: "grid2", "data-testid": "card-grid" });
  const more = el("button", { type: "button", class: "btn sec", "data-testid": "load-more" }, "Tải thêm");
  const msg = el("p", { class: "sub center", role: "status", "aria-live": "polite" });
  more.classList.add("hidden");
  const root = el("div", { style: "display:flex;flex-direction:column;gap:12px" }, grid, msg, more);
  let offset = 0;
  let token = 0;

  async function load(reset) {
    const my = ++token;
    if (reset) {
      offset = 0;
      grid.replaceChildren();
    }
    msg.textContent = "Đang tải...";
    more.classList.add("hidden");
    try {
      const r = await get("/api/cards", { scope, topic: state[topicKey], q: state[qKey] ? state[qKey].trim() : "", offset, limit: PAGE });
      if (my !== token) return;
      const items = Array.isArray(r) ? r : r.items || r.cards || [];
      items.forEach((c) => grid.append(tile(c, { status, onclick: () => onOpen(c) })));
      offset += items.length;
      msg.textContent = "";
      const hasMore = r && !Array.isArray(r) && r.has_more !== undefined ? r.has_more : items.length === PAGE;
      if (hasMore && items.length) more.classList.remove("hidden");
      if (!grid.children.length) {
        grid.append(empty ? empty() : el("p", { class: "sub center", style: "grid-column:1/3;padding:20px" }, "Chưa có ảnh nào khớp."));
      }
    } catch (e) {
      if (my !== token) return;
      msg.textContent = errorMessage(e);
    }
  }
  more.addEventListener("click", () => load(false));
  return { root, reload: () => load(true), reloadSoon: debounce(() => load(true), 300) };
}

// Search box + topic chips wired to a state object; calls onChange on edits.
export function filterControls({ state, topicKey, qKey, onChange, searchLabel }) {
  const q = el("input", { type: "search", class: "", placeholder: "Tìm theo đồ vật: coffee, helmet, desk...", "aria-label": searchLabel || "Tìm theo từ vựng", "data-testid": "search", value: state[qKey] });
  const chips = el("div", { class: "chips", role: "group", "aria-label": "Chủ đề" });
  let topics = [];
  const draw = () => {
    const all = ["", ...topics];
    chips.replaceChildren(
      ...all.map((t) =>
        el(
          "button",
          {
            type: "button",
            class: "chip" + (t === state[topicKey] ? " on" : ""),
            "aria-pressed": t === state[topicKey] ? "true" : "false",
            onclick: () => {
              state[topicKey] = t;
              draw();
              onChange(false);
            },
          },
          t || "Tất cả",
        ),
      ),
    );
  };
  q.addEventListener("input", () => {
    state[qKey] = q.value;
    onChange(true);
  });
  draw();
  loadTopics().then((t) => {
    topics = t;
    draw();
  });
  return { q, chips };
}
