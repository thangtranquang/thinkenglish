import { S, AVATAR_EMOJI, avatarEmoji, normalizeMe } from "../state.js";
import { put, patch, post, del, adoptMe, resetToGuest } from "../api.js";
import { el, hdr, screen, toast, errorMessage, confirmDialog } from "../ui.js";

export function render(ctx) {
  const me = S.me || {};
  const guest = S.isGuest;
  const msg = el("p", { class: "err", role: "alert", "aria-live": "assertive", "data-testid": "profile-error" });

  const hide = el("input", { type: "checkbox", id: "hide-timer", checked: me.hide_timer, "data-testid": "profile-hide-timer" });
  hide.addEventListener("change", async () => {
    msg.textContent = "";
    try {
      await put("/api/me/settings", { hide_timer: hide.checked });
      S.me = normalizeMe({ ...S.me, hide_timer: hide.checked });
    } catch (e) {
      hide.checked = !hide.checked;
      msg.textContent = errorMessage(e);
    }
  });

  async function changeMe(fields) {
    msg.textContent = "";
    try {
      adoptMe(await patch("/api/me", fields));
      ctx.navigate("profile", { replace: true });
    } catch (e) {
      msg.textContent = errorMessage(e);
    }
  }

  const avatarKeys = (S.config && S.config.avatars) || Object.keys(AVATAR_EMOJI);
  const levelKeys = (S.config && S.config.cefr_levels) || ["A1", "A2", "B1"];

  const avatars = el(
    "div",
    { class: "row", style: "justify-content:flex-start;flex-wrap:wrap;gap:8px", role: "radiogroup", "aria-label": "Chọn avatar" },
    ...avatarKeys.map((k) =>
      el("button", { type: "button", class: "av" + (k === me.avatar_key ? " on" : ""), role: "radio", "aria-checked": k === me.avatar_key ? "true" : "false", "aria-label": "Avatar " + k, onclick: () => changeMe({ avatar_key: k }) }, AVATAR_EMOJI[k] || "🙂"),
    ),
  );
  const levels = el(
    "div",
    { class: "seg", role: "radiogroup", "aria-label": "Trình độ" },
    ...levelKeys.map((k) =>
      el("button", { type: "button", class: k === me.cefr_level ? "on" : "", role: "radio", "aria-checked": k === me.cefr_level ? "true" : "false", "data-testid": "level-" + k, onclick: () => changeMe({ cefr_level: k }) }, k),
    ),
  );

  async function logout() {
    try {
      await post("/api/auth/logout");
    } catch {
      /* logout is idempotent; continue */
    }
    await resetToGuest();
    ctx.navigate("home", { replace: true });
  }

  const pw = el("input", { type: "password", id: "del-pw", autocomplete: "current-password", "data-testid": "delete-password" });
  const delBox = el(
    "div",
    { class: "card hidden", "data-testid": "delete-box" },
    el("p", { class: "sub" }, "Xóa tài khoản sẽ xóa toàn bộ bài và tiến độ của bạn. Không thể hoàn tác. Nhập mật khẩu để xác nhận."),
    el("label", { class: "f", for: "del-pw" }, "Mật khẩu", pw),
    el(
      "button",
      {
        type: "button",
        class: "btn bad",
        "data-testid": "delete-confirm",
        onclick: async () => {
          msg.textContent = "";
          if (!pw.value) {
            msg.textContent = "Vui lòng nhập mật khẩu.";
            return;
          }
          const ok = await confirmDialog({ title: "Xóa tài khoản?", message: "Hành động này không thể hoàn tác.", confirmText: "Xóa vĩnh viễn", testid: "delete-dialog", danger: true });
          if (!ok) return;
          try {
            await del("/api/me", { password: pw.value });
            await resetToGuest();
            toast("Đã xóa tài khoản");
            ctx.navigate("home", { replace: true });
          } catch (e) {
            msg.textContent = e.status === 403 || e.status === 401 ? "Mật khẩu chưa đúng." : errorMessage(e);
          }
        },
      },
      "Xóa vĩnh viễn",
    ),
  );

  const body = el(
    "div",
    { class: "body" },
    el(
      "div",
      { class: "row", style: "justify-content:flex-start;gap:14px" },
      el("div", { class: "av on", style: "cursor:default", "aria-hidden": "true" }, avatarEmoji(me.avatar_key)),
      el("div", {}, el("h1", { style: "font-size:18px" }, guest ? "Khách" : me.nickname), me.cefr_level ? el("span", { class: "badge info" }, "Trình độ " + me.cefr_level) : null),
    ),
    el(
      "div",
      { class: "stat" },
      el("div", {}, el("b", {}, "🔥 " + me.streak), el("span", {}, "Streak")),
      el("div", {}, el("b", {}, String(me.xp)), el("span", {}, "XP")),
      el("div", {}, el("b", {}, String(me.level)), el("span", {}, "Cấp độ")),
    ),
    guest
      ? el(
          "div",
          { class: "card", "data-testid": "profile-guest-banner" },
          el("h2", {}, "Giữ tiến độ của bạn"),
          el("p", { class: "sub" }, "Tạo tài khoản để lưu bài, tải ảnh và học trên nhiều thiết bị."),
          el("button", { type: "button", class: "btn", "data-testid": "profile-register", onclick: () => ctx.navigate("register", { query: { reason: "profile" } }) }, "Tạo tài khoản"),
          el("button", { type: "button", class: "link", "data-testid": "profile-login-link", onclick: () => ctx.navigate("login") }, "Đã có tài khoản? Đăng nhập"),
        )
      : el("div", { class: "card" }, el("h3", {}, "Avatar"), avatars, el("h3", {}, "Trình độ"), levels),
    el("div", { class: "card" }, el("h3", {}, "Cài đặt luyện tập"), el("label", { class: "row", for: "hide-timer" }, el("span", {}, "Ẩn đồng hồ trong Reflex"), el("span", { class: "sw" }, hide))),
    el(
      "div",
      { class: "card" },
      el("h3", {}, "Riêng tư"),
      el("div", { class: "row" }, el("span", {}, "Ảnh mặc định"), el("span", { class: "badge good" }, "Riêng tư")),
      el("div", { class: "row" }, el("span", {}, "Vị trí/EXIF trong ảnh"), el("span", { class: "badge good" }, "Đã xóa")),
      el("p", { class: "sub" }, "Chúng mình chỉ lưu biệt danh, avatar và ảnh bạn tải lên."),
    ),
    msg,
    guest ? null : el("button", { type: "button", class: "btn sec", "data-testid": "profile-logout", onclick: logout }, "Đăng xuất"),
    guest ? null : el("button", { type: "button", class: "btn sec", "data-testid": "profile-delete", onclick: () => delBox.classList.toggle("hidden") }, "Xóa tài khoản"),
    guest ? null : delBox,
  );
  return screen(hdr("Hồ sơ"), body);
}
