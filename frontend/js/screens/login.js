// Login. If the guest has progress the server answers 409 and we ask before discarding it.
import { S } from "../state.js";
import { post, adoptMe } from "../api.js";
import { el, hdr, screen, toast, errorMessage, confirmDialog } from "../ui.js";

export function render(ctx) {
  const reason = ctx.query.reason || "";
  const mandatory = S.gate === "second_visit" || reason === "second_visit";
  const err = el("div", { class: "err", id: "login-err", role: "alert", "aria-live": "assertive", "data-testid": "login-error" });
  const nick = el("input", { type: "text", id: "lnick", maxlength: "20", autocomplete: "username", "aria-describedby": "login-err", "data-testid": "login-nickname" });
  const pw = el("input", { type: "password", id: "lpw", autocomplete: "current-password", "aria-describedby": "login-err", "data-testid": "login-password" });
  const btn = el("button", { type: "submit", class: "btn", "data-testid": "login-submit" }, "Đăng nhập");

  async function attempt(discard) {
    const me = await post("/api/auth/login", { nickname: nick.value.trim(), password: pw.value, discard_guest: discard });
    adoptMe(me);
    toast("Chào " + (S.me.nickname || "bạn") + "!");
    ctx.navigate("home", { replace: true });
  }

  async function onSubmit(ev) {
    ev.preventDefault();
    err.textContent = "";
    if (!nick.value.trim() || !pw.value) {
      err.textContent = "Vui lòng nhập biệt danh và mật khẩu.";
      return;
    }
    btn.disabled = true;
    try {
      await attempt(false);
    } catch (e) {
      if (e.status === 409) {
        const yes = await confirmDialog({
          title: "Bỏ tiến độ của khách?",
          message: "Thiết bị này đang có tiến độ học của khách. Nếu đăng nhập, tiến độ đó sẽ bị xóa và bạn dùng dữ liệu của tài khoản.",
          confirmText: "Xóa và đăng nhập",
          cancelText: "Giữ lại",
          testid: "discard-dialog",
          danger: true,
        });
        if (yes) {
          try {
            await attempt(true);
            return;
          } catch (e2) {
            err.textContent = errorMessage(e2);
          }
        }
      } else {
        err.textContent = e.status === 401 || e.status === 400 ? errorMessage({ status: 401, error: "invalid_credentials" }) : errorMessage(e);
      }
      btn.disabled = false;
    }
  }

  const form = el(
    "form",
    { class: "body", novalidate: "", "data-testid": "login-form", "aria-label": "Đăng nhập", onsubmit: onSubmit },
    el("label", { class: "f", for: "lnick" }, "Biệt danh", nick),
    el("label", { class: "f", for: "lpw" }, "Mật khẩu", pw),
    err,
    btn,
    el("button", { type: "button", class: "link", "data-testid": "login-register-link", onclick: () => ctx.navigate("register", { query: reason ? { reason } : {} }) }, "Chưa có tài khoản? Tạo tài khoản"),
  );
  return screen(hdr("Đăng nhập", mandatory ? {} : { onBack: () => ctx.navigate(reason === "camera" ? "gate" : "home", reason === "camera" ? { id: "camera" } : {}), backTestId: "login-back" }), form);
}
