// Gate screens. reason: camera | account | profile | second_visit (mandatory, no escape).
import { S } from "../state.js";
import { el, screen } from "../ui.js";

const TEXT = {
  camera: {
    icon: "📷",
    title: "Tạo tài khoản để thêm ảnh",
    msg: "Bạn cần tài khoản để tải ảnh lên và lưu bài của mình. Chỉ mất một phút, chỉ cần biệt danh.",
  },
  account: {
    icon: "👤",
    title: "Cần tài khoản để tiếp tục",
    msg: "Tính năng này chỉ dành cho người có tài khoản. Tạo tài khoản để tiếp tục.",
  },
  second_visit: {
    icon: "🎉",
    title: "Hãy tạo tài khoản để học tiếp",
    msg: "Bạn đã dùng hết lượt thử miễn phí. Tạo tài khoản (chỉ cần biệt danh) hoặc đăng nhập để giữ tiến độ và tiếp tục luyện tập.",
  },
};

export function render(ctx) {
  let reason = ctx.id || "camera";
  if (S.gate === "second_visit") reason = "second_visit";
  const mandatory = reason === "second_visit";
  const t = TEXT[reason] || TEXT.account;

  const body = el(
    "div",
    { class: "body", style: "justify-content:center;gap:16px;padding:24px", "data-testid": mandatory ? "gate-second-visit" : "gate-" + reason },
    el("div", { class: "gate-ico", "aria-hidden": "true" }, t.icon),
    el("h1", { class: "center" }, t.title),
    el("p", { class: "sub center", style: "font-size:15px" }, t.msg),
    el("button", { type: "button", class: "btn", "data-testid": "gate-register", onclick: () => ctx.navigate("register", { query: { reason } }) }, "Tạo tài khoản"),
    el("button", { type: "button", class: "btn sec", "data-testid": "gate-login", onclick: () => ctx.navigate("login", { query: { reason } }) }, "Đã có tài khoản? Đăng nhập"),
    mandatory ? null : el("button", { type: "button", class: "btn sec", "data-testid": "gate-back", "aria-label": "Quay lại", onclick: () => ctx.navigate("home") }, "← Quay lại"),
  );
  return screen(null, body);
}
