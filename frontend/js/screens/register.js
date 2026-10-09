// Registration converts the current guest in place. reason: camera | profile | account | second_visit.
import { S, AVATAR_EMOJI } from "../state.js";
import { post, adoptMe } from "../api.js";
import { el, hdr, screen, toast, errorMessage } from "../ui.js";

const LEVELS = [
  ["A1", "A1 · Mới bắt đầu", "Từ và câu rất cơ bản"],
  ["A2", "A2 · Cơ bản", "Câu đơn, chủ đề quen thuộc"],
  ["B1", "B1 · Trung cấp", "Kể chuyện ngắn, nói liên tục"],
];
const FIELD_MSG = {
  nickname: "Biệt danh 3-20 ký tự, chỉ gồm chữ không dấu, số, dấu gạch dưới, chấm hoặc gạch ngang. Không dùng tên thật.",
  password: "Mật khẩu cần ít nhất 8 ký tự.",
  birth_year: "Năm sinh chưa hợp lệ.",
  guardian_email: "Cần email phụ huynh hợp lệ.",
  guardian_consent: "Cần phụ huynh xác nhận đồng ý.",
};

export function render(ctx) {
  const reason = ctx.query.reason || "";
  const mandatory = reason === "second_visit" || S.gate === "second_visit";
  const cfg = S.config || {};
  const thisYear = new Date().getFullYear();
  const maxY = cfg.birth_year_max || thisYear - 10;
  const minY = cfg.birth_year_min || thisYear - 100;
  const avatarKeys = cfg.avatars && cfg.avatars.length ? cfg.avatars : Object.keys(AVATAR_EMOJI);
  const levels = cfg.cefr_levels && cfg.cefr_levels.length ? LEVELS.filter(([k]) => cfg.cefr_levels.includes(k)) : LEVELS;

  let avatar = avatarKeys[0];
  let level = "A2";

  const err = el("div", { class: "err", id: "reg-err", role: "alert", "aria-live": "assertive", "data-testid": "register-error" });
  const nick = el("input", { type: "text", id: "nick", maxlength: "20", autocomplete: "username", placeholder: "ví dụ: huy_nguyen", "aria-describedby": "reg-err", "data-testid": "register-nickname" });
  const pw = el("input", { type: "password", id: "pw", autocomplete: "new-password", "aria-describedby": "reg-err", "data-testid": "register-password" });
  const years = [];
  for (let y = maxY; y >= minY && years.length < 40; y--) years.push(y);
  const year = el("select", { id: "year", "data-testid": "register-year" }, ...years.map((y) => el("option", { value: y }, y + " (tuổi " + (thisYear - y) + ")")));
  year.value = String(Math.min(maxY, thisYear - 14));
  const mail = el("input", { type: "email", id: "pm", autocomplete: "off", placeholder: "email phụ huynh", "data-testid": "register-guardian-email" });
  const okc = el("input", { type: "checkbox", id: "okc", "data-testid": "register-guardian-consent" });
  const consent = el(
    "div",
    { class: "card", style: "border-color:#fcd34d;background:#fffbeb", "data-testid": "register-guardian" },
    el("h2", {}, "Cần phụ huynh đồng ý"),
    el("p", { class: "sub" }, "Bạn dưới 16 tuổi. Theo quy định bảo vệ dữ liệu cá nhân, cha mẹ/người giám hộ cần đồng ý trước khi bạn dùng ứng dụng. Chúng mình chỉ lưu biệt danh và ảnh bạn tự tải lên."),
    el("label", { class: "f", for: "pm" }, "Email phụ huynh", mail),
    el("label", { class: "opt", for: "okc" }, okc, el("div", {}, el("b", {}, "Phụ huynh đã đồng ý"))),
  );
  const isMinor = () => thisYear - Number(year.value) < 16;
  const update = () => consent.classList.toggle("hidden", !isMinor());
  year.addEventListener("change", update);
  update();

  const avs = el("div", { class: "row", style: "justify-content:flex-start;flex-wrap:wrap;gap:8px", role: "radiogroup", "aria-label": "Chọn avatar" });
  avatarKeys.forEach((k) => {
    const b = el(
      "button",
      {
        type: "button",
        class: "av" + (k === avatar ? " on" : ""),
        "aria-label": "Avatar " + k,
        role: "radio",
        "aria-checked": k === avatar ? "true" : "false",
        "data-avatar": k,
        onclick: () => {
          avatar = k;
          [...avs.children].forEach((x) => {
            x.classList.toggle("on", x === b);
            x.setAttribute("aria-checked", x === b ? "true" : "false");
          });
        },
      },
      AVATAR_EMOJI[k] || "🙂",
    );
    avs.append(b);
  });
  const lv = el(
    "div",
    { style: "display:grid;gap:8px", role: "radiogroup", "aria-label": "Trình độ hiện tại" },
    ...levels.map(([k, t, d]) => {
      const i = el("input", { type: "radio", name: "lv", value: k, checked: k === level });
      i.addEventListener("change", () => (level = k));
      return el("label", { class: "opt" }, i, el("div", {}, el("b", {}, t), el("span", {}, d)));
    }),
  );

  const submitBtn = el("button", { type: "submit", class: "btn", "data-testid": "register-submit" }, "Vào học");

  function showError(text, focusEl) {
    err.textContent = text;
    if (focusEl) focusEl.focus();
  }

  async function onSubmit(ev) {
    ev.preventDefault();
    err.textContent = "";
    const n = nick.value.trim();
    if (!/^[A-Za-z0-9_.-]{3,20}$/.test(n)) return showError(FIELD_MSG.nickname, nick);
    if (pw.value.length < 8) return showError(FIELD_MSG.password, pw);
    const payload = { nickname: n, password: pw.value, avatar_key: avatar, birth_year: Number(year.value), cefr_level: level };
    if (isMinor()) {
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(mail.value.trim()) || !okc.checked) return showError("Cần email phụ huynh và xác nhận đồng ý để tiếp tục.", mail);
      payload.guardian_email = mail.value.trim();
      payload.guardian_consent = true;
    }
    submitBtn.disabled = true;
    try {
      const me = await post("/api/auth/register", payload);
      adoptMe(me);
      toast("Chào " + n + "!");
      if (reason === "camera") ctx.navigate("addphoto", { replace: true });
      else if (reason === "profile") ctx.navigate("profile", { replace: true });
      else ctx.navigate("home", { replace: true });
    } catch (e) {
      if (e.error === "validation_error" && e.fields) {
        const k = Object.keys(e.fields)[0];
        showError(FIELD_MSG[k] || errorMessage(e));
      } else {
        showError(errorMessage(e));
      }
      submitBtn.disabled = false;
    }
  }

  const onBack = mandatory ? null : () => (reason === "profile" ? ctx.navigate("profile") : reason === "camera" ? ctx.navigate("gate", { id: "camera" }) : ctx.navigate("home"));
  const form = el(
    "form",
    { class: "body", novalidate: "", "data-testid": "register-form", "aria-label": "Tạo tài khoản", onsubmit: onSubmit },
    el("p", { class: "sub" }, "Dùng biệt danh, không dùng tên thật. Ảnh của bạn mặc định chỉ mình bạn xem được."),
    el("label", { class: "f", for: "nick" }, "Biệt danh", nick),
    el("label", { class: "f", for: "pw" }, "Mật khẩu (ít nhất 8 ký tự)", pw),
    err,
    el("div", { class: "f", style: "display:flex;flex-direction:column;gap:6px;font-size:13px;font-weight:700" }, "Chọn avatar", avs),
    el("label", { class: "f", for: "year" }, "Năm sinh", year),
    consent,
    el("div", { class: "f", style: "display:flex;flex-direction:column;gap:6px;font-size:13px;font-weight:700" }, "Trình độ hiện tại", lv),
    submitBtn,
    el("button", { type: "button", class: "link", "data-testid": "register-login-link", onclick: () => ctx.navigate("login", { query: reason ? { reason } : {} }) }, "Đã có tài khoản? Đăng nhập"),
  );
  return screen(hdr("Tạo tài khoản", onBack ? { onBack, backTestId: "gate-back" } : {}), form);
}
