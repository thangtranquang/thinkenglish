// Shared by Reflex and Auto mode: session start, card prefetch, round view parts, attempt posting.
import { get, post } from "./api.js";
import { scene } from "./scene.js";
import { normalizeMe, S } from "./state.js";
import { el, uuid } from "./ui.js";

export const LEVELS = {
  1: { name: "R1 · Có gợi ý", desc: "Hiện chữ cái đầu, 6 giây." },
  2: { name: "R2 · Không gợi ý", desc: "Chỉ nhìn ảnh, 5 giây." },
  3: { name: "R3 · Nhanh", desc: "Chỉ nhìn ảnh, 3 giây." },
  4: { name: "R4 · Khó", desc: "Chỉ nhìn ảnh, 8 giây, nói cả cụm từ." },
};
export const SETTLE_MS = 1800;

export async function startSession(level) {
  return post("/api/reflex/sessions", { level });
}

// Fetch each distinct card once: image, marker coordinates and Vietnamese meaning of every round.
export async function loadCards(rounds) {
  const ids = [...new Set(rounds.map((r) => r.card_id))];
  const cards = new Map();
  await Promise.all(ids.map(async (id) => cards.set(id, await get("/api/cards/" + encodeURIComponent(id)))));
  return cards;
}

export function labelOf(card, round) {
  return (card.labels || []).find((l) => l.id === round.item_id) || { id: round.item_id, word: round.word, x: 0.5, y: 0.5 };
}

export const hintOf = (word) =>
  word
    .split(" ")
    .map((p) => p[0] + (p.length > 1 ? " " + "_ ".repeat(p.length - 1).trim() : ""))
    .join("   ");

// Photo with one pulsing marker on the item being asked about.
export function roundScene(card, label) {
  const mk = el("div", { class: "mk", "data-testid": "round-marker", style: `left:${(label.x ?? 0.5) * 100}%;top:${(label.y ?? 0.5) * 100}%` }, el("i"));
  return scene(card, { markers: false, extra: mk });
}

export function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

export function postAttempt(round, extra) {
  return post("/api/attempts", { client_attempt_id: uuid(), card_id: round.card_id, item_type: "label", item_id: round.item_id, ...extra });
}

export async function refreshMe() {
  try {
    const me = await get("/api/me");
    S.me = normalizeMe(me.user);
  } catch {
    /* keep the cached values */
  }
}
