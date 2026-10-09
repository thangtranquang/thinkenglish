import { S } from "../state.js";
import { get, post } from "../api.js";
import { el, hdr, screen, toast, errorMessage, cardImageUrl } from "../ui.js";
import { createCardList, filterControls } from "../cardlist.js";

export function render(ctx) {
  const list = createCardList({
    scope: "explore",
    state: S,
    topicKey: "expTopic",
    qKey: "expQ",
    onOpen: (c) => ctx.navigate("detail", { id: c.id }),
  });
  const { q, chips } = filterControls({ state: S, topicKey: "expTopic", qKey: "expQ", onChange: (typing) => (typing ? list.reloadSoon() : list.reload()) });
  const body = el(
    "div",
    { class: "body" },
    q,
    chips,
    el("p", { class: "note" }, "Thẻ cộng đồng chỉ hiện sau khi được duyệt."),
    list.root,
  );
  list.reload();
  return screen(hdr("Khám phá"), body);
}

let currentAudio = null;
function play(url) {
  if (!url) return;
  try {
    if (currentAudio) currentAudio.pause();
    currentAudio = new Audio(url);
    currentAudio.play().catch(() => {});
  } catch {
    /* ignore */
  }
}

export async function renderDetail(ctx) {
  const body = el("div", { class: "body" });
  const header = hdr("Chi tiết", { onBack: () => ctx.navigate("explore") });
  try {
    const c = await get("/api/cards/" + encodeURIComponent(ctx.id));
    const labels = c.labels || [];
    body.append(
      el("div", { class: "scene" }, el("img", { src: cardImageUrl(c), alt: "Ảnh " + (c.title || "") }), el("span", { class: "cap" }, c.title || "")),
      el("div", { class: "row" }, c.topic ? el("span", { class: "badge info" }, c.topic) : el("span"), el("span", { class: "sub" }, "Tạo bởi: " + (c.owner_nickname || c.by || "Hệ thống"))),
      el(
        "div",
        { class: "card" },
        el("h3", {}, "Từ vựng trong ảnh"),
        ...labels.map((l) =>
          el(
            "div",
            { class: "row" },
            el("span", {}, el("b", {}, l.word || ""), " ", el("span", { class: "ipa" }, l.ipa || "")),
            el("button", { type: "button", class: "ib", "aria-label": "Nghe " + (l.word || ""), onclick: () => play(l.audio_url) }, "🔊"),
          ),
        ),
      ),
    );
    const msg = el("p", { class: "err", role: "alert", "aria-live": "assertive" });
    const save = el(
      "button",
      {
        type: "button",
        class: "btn",
        "data-testid": "detail-save",
        onclick: async () => {
          save.disabled = true;
          msg.textContent = "";
          try {
            if (!c.saved && !c.is_mine) await post("/api/cards/" + encodeURIComponent(c.id) + "/save");
            toast("Đã lưu vào Thư viện");
            ctx.navigate("practice", { id: c.id });
          } catch (e) {
            msg.textContent = errorMessage(e);
            save.disabled = false;
          }
        },
      },
      "Lưu và luyện tập",
    );
    body.append(save, msg);
  } catch (e) {
    body.append(el("p", { class: "sub center", role: "alert" }, e.status === 404 ? "Không tìm thấy thẻ này." : errorMessage(e)));
  }
  return screen(header, body);
}
