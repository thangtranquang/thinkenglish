// DOM helpers. Dynamic data is only ever inserted via textContent / text nodes.
export function el(tag, props = {}, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v === false || v == null) continue;
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (k === "value") e.value = v;
    else if (k === "checked") e.checked = !!v;
    else e.setAttribute(k, v === true ? "" : v);
  }
  for (const k of kids.flat()) {
    if (k == null || k === false) continue;
    e.append(k.nodeType ? k : document.createTextNode(String(k)));
  }
  return e;
}

export function toast(text) {
  const host = document.querySelector(".app") || document.body;
  const t = el("div", { class: "toast", role: "status" }, text);
  host.append(t);
  setTimeout(() => t.remove(), 2600);
}

export function hdr(title, { onBack, right, backTestId } = {}) {
  return el(
    "header",
    { class: "h" },
    onBack
      ? el("button", { type: "button", class: "ib", "aria-label": "Quay lại", "data-testid": backTestId || "back", onclick: onBack }, "←")
      : null,
    el("div", { class: "t" }, title),
    right || null,
  );
}

export function screen(header, body) {
  return el("div", { class: "screen" }, header, body);
}

export function confirmDialog({ title, message, confirmText = "Đồng ý", cancelText = "Hủy", testid = "confirm-dialog", danger = false }) {
  return new Promise((resolve) => {
    const host = document.querySelector(".app") || document.body;
    const done = (v) => {
      overlay.remove();
      resolve(v);
    };
    const ok = el("button", { type: "button", class: "btn" + (danger ? " bad" : ""), "data-testid": testid + "-ok", onclick: () => done(true) }, confirmText);
    const no = el("button", { type: "button", class: "btn sec", "data-testid": testid + "-cancel", onclick: () => done(false) }, cancelText);
    const overlay = el(
      "div",
      { class: "overlay" },
      el(
        "div",
        { class: "dialog", role: "dialog", "aria-modal": "true", "aria-label": title, "data-testid": testid },
        el("h2", {}, title),
        el("p", { class: "sub" }, message),
        el("div", { class: "acts" }, no, ok),
      ),
    );
    host.append(overlay);
    ok.focus();
  });
}

// Vietnamese message for an ApiError (or network failure).
export function errorMessage(err) {
  if (!err || err.status === undefined) return "Không kết nối được máy chủ. Vui lòng thử lại.";
  if (err.status === 429) return "Bạn thử quá nhiều lần. Vui lòng đợi một lúc rồi thử lại.";
  if (err.status >= 500) return "Có lỗi từ máy chủ. Vui lòng thử lại sau.";
  switch (err.error) {
    case "nickname_taken":
      return "Biệt danh này đã có người dùng. Hãy chọn biệt danh khác hoặc đăng nhập.";
    case "already_registered":
      return "Bạn đã có tài khoản rồi.";
    case "invalid_credentials":
      return "Biệt danh hoặc mật khẩu chưa đúng.";
    case "validation_error":
      return "Thông tin chưa hợp lệ. Vui lòng kiểm tra lại.";
    default:
      return "Có lỗi xảy ra. Vui lòng thử lại.";
  }
}

export function cardImageUrl(c) {
  return c.image_url || `/api/cards/${encodeURIComponent(c.id)}/image`;
}

export function labelWords(c) {
  return (c.labels || []).map((l) => (typeof l === "string" ? l : l.word || l.text || "")).filter(Boolean);
}

export function memColor(m) {
  return m >= 85 ? "var(--ok)" : m >= 60 ? "var(--warn)" : "var(--bad)";
}
export function memLabel(m) {
  return m >= 85 ? "Đã thuộc" : m >= 60 ? "Đang học" : "Cần ôn";
}

export function tile(c, { onclick, status = false }) {
  const ph = el("div", { class: "ph" }, el("span", { class: "ico", "aria-hidden": "true" }, "🖼️"));
  ph.append(el("img", { src: cardImageUrl(c), alt: "", loading: "lazy", onerror: (e) => e.target.remove() }));
  if (c.topic) ph.append(el("span", { class: "bd" }, c.topic));
  const tx = el("div", { class: "tx" }, el("b", {}, c.title || "Thẻ"), el("small", {}, labelWords(c).join(", ")));
  const mem = c.mastery ?? c.mem;
  if (status && typeof mem === "number") {
    ph.append(el("span", { class: "st", style: `background:${memColor(mem)}` }, memLabel(mem)));
    tx.append(
      el("div", { class: "row", style: "font-size:11px;color:var(--mut)" }, el("span", {}, "Độ nhớ"), el("b", { style: `color:${memColor(mem)}` }, mem + "%")),
      el("div", { class: "meter" }, el("i", { style: `width:${mem}%;background:${memColor(mem)}` })),
    );
  }
  return el("button", { type: "button", class: "tile", "data-testid": "card-tile", onclick }, ph, tx);
}

export function debounce(fn, ms) {
  let t = 0;
  return (...a) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...a), ms);
  };
}
