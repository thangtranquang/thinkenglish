import { S, avatarEmoji } from "../state.js";
import { get } from "../api.js";
import { openCamera } from "../router.js";
import { el, hdr, screen, tile } from "../ui.js";

export function render(ctx) {
  const me = S.me || {};
  const name = me.nickname || "bạn";
  const row = el("div", { class: "grid2", "data-testid": "home-cards" });
  const sectionTitle = el("h2", {}, S.isGuest ? "Thẻ mẫu để thử" : "Tiếp tục luyện");

  const body = el(
    "div",
    { class: "body" },
    el(
      "div",
      { class: "row" },
      el("div", {}, el("h1", { style: "font-size:20px" }, "Xin chào, " + name + " " + avatarEmoji(me.avatar_key)), el("p", { class: "sub" }, "Hôm nay luyện một chút nhé")),
      me.cefr_level ? el("span", { class: "badge info" }, "Trình độ " + me.cefr_level) : null,
    ),
    el(
      "div",
      { class: "stat" },
      el("div", {}, el("b", {}, "🔥 " + me.streak), el("span", {}, "Ngày liên tiếp")),
      el("div", {}, el("b", {}, String(me.xp)), el("span", {}, "Điểm XP")),
      el("div", {}, el("b", {}, String(me.level)), el("span", {}, "Cấp độ")),
    ),
    el(
      "div",
      { class: "hero" },
      el("h2", { style: "font-size:17px" }, "Phiên Reflex hôm nay"),
      el("p", { class: "sub" }, "Khoảng 3 phút. Chữ sẽ bị ẩn, hãy nói thật nhanh."),
      el("button", { type: "button", class: "btn", "data-testid": "home-reflex", onclick: () => ctx.navigate("reflex") }, "⚡ Bắt đầu phiên Reflex"),
    ),
    S.isGuest
      ? el(
          "div",
          { class: "row", style: "justify-content:center" },
          el("span", { class: "sub" }, "Đã có tài khoản?"),
          el("button", { type: "button", class: "link", "data-testid": "home-login-link", onclick: () => ctx.navigate("login") }, "Đã có tài khoản? Đăng nhập"),
        )
      : null,
    el(
      "div",
      { class: "row" },
      sectionTitle,
      el("button", { type: "button", class: "btn sec sm", onclick: () => ctx.navigate(S.isGuest ? "explore" : "library") }, "Xem tất cả"),
    ),
    row,
    el(
      "div",
      { class: "card", style: "flex-direction:row;align-items:center" },
      el("span", { style: "font-size:28px", "aria-hidden": "true" }, "📷"),
      el("div", { style: "flex:1" }, el("b", { style: "font-size:14px" }, "Chụp ảnh quanh bạn"), el("div", { class: "sub" }, "AI gắn nhãn, bạn luyện nói ngay.")),
      el("button", { type: "button", class: "btn sm", "data-testid": "home-camera", "aria-label": "Chụp ảnh", onclick: openCamera }, "Chụp"),
    ),
  );

  const scope = S.isGuest ? "explore" : "mine";
  get("/api/cards", { scope, limit: 2 })
    .then((r) => {
      const items = Array.isArray(r) ? r : r.items || r.cards || [];
      items.forEach((c) => row.append(tile(c, { status: !S.isGuest, onclick: () => ctx.navigate(S.isGuest ? "detail" : "practice", { id: c.id }) })));
    })
    .catch(() => {});

  return screen(null, body);
}
