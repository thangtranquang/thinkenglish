// Add photo: upload one image, show how many AI calls it cost, poll until the labels are ready, then open Review.
import { api, get } from "../api.js";
import { S } from "../state.js";
import { el, errorMessage, hdr, screen } from "../ui.js";

const MAX_BYTES = 5 * 1024 * 1024;
const ALLOWED = ["image/jpeg", "image/png", "image/webp"];
const POLL_MS = 1000;
const POLL_LIMIT_MS = 120000;

const DEDUPE_TEXT = {
  ready: "Ảnh này đã có người tải lên, không tốn lượt AI",
  in_flight: "Ảnh này đang được xử lý, vui lòng chờ…",
  none: "Đang phân tích ảnh bằng AI…",
};

export function render(ctx) {
  if (S.isGuest) {
    ctx.navigate("gate", { id: "camera", replace: true });
    return screen(hdr("Thêm ảnh mới"), el("div", { class: "body" }));
  }
  let alive = true;
  let timer = 0;
  ctx.onLeave(() => {
    alive = false;
    clearTimeout(timer);
  });

  const msg = el("p", { class: "err", role: "alert", "aria-live": "assertive", "data-testid": "addphoto-error" });
  const info = el("div", { class: "card hidden", "data-testid": "addphoto-progress" });
  const input = el("input", {
    type: "file",
    accept: "image/jpeg,image/png,image/webp",
    capture: "environment",
    class: "hidden",
    "aria-label": "Chọn ảnh",
    "data-testid": "addphoto-file",
  });
  const pick = el("button", { type: "button", class: "btn", "data-testid": "addphoto-pick", onclick: () => input.click() }, "📷 Chụp / Chọn ảnh");
  let lastFile = null;

  function show(text, calls, extra) {
    info.classList.remove("hidden");
    info.replaceChildren(
      el("p", { class: "sub", role: "status", "aria-live": "polite", "data-testid": "addphoto-status" }, text),
      calls != null ? el("div", { class: "stat two" }, el("div", {}, el("b", { "data-testid": "addphoto-ai-calls" }, String(calls)), el("span", {}, "Lần gọi AI cho ảnh này"))) : null,
      extra || null,
    );
  }

  function fail(text, retry = false) {
    msg.textContent = text;
    info.classList.add("hidden");
    pick.disabled = false;
    if (retry && lastFile) show(text, null, el("button", { type: "button", class: "btn sec", "data-testid": "addphoto-retry", onclick: () => upload(lastFile) }, "Thử lại"));
  }

  async function poll(contentId, started) {
    if (!alive) return;
    let s;
    try {
      s = await get("/api/uploads/" + encodeURIComponent(contentId));
    } catch (e) {
      return fail(errorMessage(e));
    }
    if (!alive) return;
    if (s.status === "ready") return done(contentId, s.ai_calls);
    if (s.status === "failed") {
      return fail(s.retryable ? "AI chưa phân tích được ảnh này. Bạn có thể thử lại." : "Ảnh này không phân tích được. Vui lòng thử ảnh khác.", s.retryable);
    }
    if (Date.now() - started > POLL_LIMIT_MS) return fail("Việc xử lý ảnh quá lâu. Vui lòng thử lại sau.", true);
    show(DEDUPE_TEXT.none, s.ai_calls);
    timer = setTimeout(() => poll(contentId, started), POLL_MS);
  }

  function done(contentId, calls, note) {
    show((note ? note + ". " : "Xong rồi! ") + "Đang mở màn hình xem lại kết quả…", calls, el("button", { type: "button", class: "btn", "data-testid": "addphoto-continue", onclick: () => ctx.navigate("review", { id: contentId }) }, "Xem lại kết quả"));
    timer = setTimeout(() => alive && ctx.navigate("review", { id: contentId }), 2500);
  }

  async function upload(file) {
    msg.textContent = "";
    if (!ALLOWED.includes(file.type)) return fail("Chỉ nhận ảnh JPEG, PNG hoặc WebP.");
    if (file.size > MAX_BYTES) return fail("Ảnh quá lớn (tối đa 5 MB). Hãy chọn ảnh nhỏ hơn.");
    lastFile = file;
    pick.disabled = true;
    show("Đang tải ảnh lên…", null);
    const form = new FormData();
    form.append("file", file);
    let r;
    try {
      r = await api("POST", "/api/uploads", { form });
    } catch (e) {
      if (e.status === 403) return fail("Bạn cần tài khoản để thêm ảnh.");
      if (e.status === 409 && e.error === "analysis_unavailable") return fail("Ảnh này tạm thời không phân tích được. Vui lòng thử ảnh khác hoặc quay lại sau.");
      if (e.status === 413) return fail("Ảnh quá lớn (tối đa 5 MB). Hãy chọn ảnh nhỏ hơn.");
      if (e.status === 415) return fail("Chỉ nhận ảnh JPEG, PNG hoặc WebP.");
      if (e.status === 422) return fail("Không đọc được ảnh này. Vui lòng chọn ảnh khác.");
      return fail(errorMessage(e));
    }
    if (!alive) return;
    show(DEDUPE_TEXT[r.dedupe] || DEDUPE_TEXT.none, r.ai_calls);
    if (r.status === "ready") return done(r.content_id, r.ai_calls, r.dedupe === "ready" ? DEDUPE_TEXT.ready : null);
    if (r.status === "failed") return poll(r.content_id, Date.now());
    poll(r.content_id, Date.now());
  }

  input.addEventListener("change", () => {
    const f = input.files && input.files[0];
    if (f) upload(f);
    input.value = "";
  });

  return screen(
    hdr("Thêm ảnh mới", { onBack: () => ctx.navigate("home") }),
    el(
      "div",
      { class: "body", "data-testid": "screen-addphoto" },
      el("p", { class: "sub" }, "Chụp hoặc chọn một ảnh đời thường. Tránh chụp rõ mặt người, giấy tờ hoặc biển số."),
      input,
      pick,
      info,
      msg,
      el("p", { class: "note" }, "Mỗi ảnh chỉ gọi AI một lần. Nếu ảnh đã có người tải lên, bạn nhận kết quả ngay."),
    ),
  );
}
