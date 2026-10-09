// Practice: three levels (name -> describe -> story) with hold-to-talk shadowing. Scores come from the server.
import { get, post } from "../api.js";
import { speak, stopSpeaking } from "../audio.js";
import { scene } from "../scene.js";
import { recognize } from "../speech.js";
import { el, errorMessage, hdr, screen, toast, uuid } from "../ui.js";

const LEVELS = [
  [1, "Gọi tên", "Level 1", "Gọi tên từng vật ngay khi nhìn thấy.", "label"],
  [2, "Mô tả", "Level 2", "Nói 1-2 câu đơn mô tả hành động.", "sentence"],
  [3, "Kể chuyện", "Level 3", "Kể lại 2-3 câu có ngữ cảnh.", "story"],
];

function itemsFor(card, level) {
  if (level === 1) return card.labels.map((l) => ({ id: l.id, text: l.word, ipa: l.ipa, vi: l.vi_meaning, audio: l.audio_url, type: "label" }));
  const kind = level === 2 ? "description" : "story";
  const type = level === 2 ? "sentence" : "story";
  return (card.sentences || []).filter((s) => s.kind === kind).map((s) => ({ id: s.id, text: s.en, ipa: null, vi: s.vi, audio: s.audio_url, type }));
}

export async function render(ctx) {
  let card;
  try {
    card = await get("/api/cards/" + encodeURIComponent(ctx.id));
  } catch (e) {
    return screen(
      hdr("Luyện tập", { onBack: () => ctx.navigate("home") }),
      el("div", { class: "body", "data-testid": "screen-practice" }, el("p", { class: "sub center", role: "alert" }, e.status === 404 ? "Không tìm thấy thẻ này." : errorMessage(e))),
    );
  }

  let level = 1;
  let unlocked = card.unlocked_levels && card.unlocked_levels.length ? card.unlocked_levels : [1];
  const target = { 1: 0, 2: 0, 3: 0 };
  const wrap = el("div", { class: "body", "data-testid": "screen-practice" });
  const fb = el("div", { class: "card", style: "background:linear-gradient(135deg,#ecfdf5,#eff6ff)" });
  const fbText = el("p", { class: "sub", role: "status", "aria-live": "polite", "data-testid": "practice-feedback" }, "Giữ nút bên dưới và nói theo câu đã chọn.");
  fb.append(el("b", { style: "font-size:13px" }, "Nhận xét"), fbText);
  const selfBox = el("div", { class: "card hidden", "data-testid": "practice-selfcheck" });
  let busy = false;

  async function submit(item, transcript) {
    if (busy) return;
    busy = true;
    try {
      const r = await post("/api/attempts", {
        client_attempt_id: uuid(),
        card_id: card.id,
        item_type: item.type,
        item_id: item.id,
        mode: "shadow",
        transcript: transcript.slice(0, 500),
      });
      fbText.textContent = `Chính xác ${r.accuracy}% · Điểm ${r.score} · +${r.xp} XP. ${r.accuracy >= 80 ? "Tốt lắm!" : "Nghe mẫu rồi thử lại nhé."}`;
      const before = unlocked.length;
      unlocked = r.unlocked_levels && r.unlocked_levels.length ? r.unlocked_levels : unlocked;
      if (unlocked.length > before) {
        toast("Đã mở khóa Level " + Math.max(...unlocked) + "!");
        draw();
        fbText.textContent = `Chính xác ${r.accuracy}% · Điểm ${r.score} · +${r.xp} XP.`;
      }
    } catch (e) {
      if (e.status === 409 && e.error === "level_locked") {
        toast("Level này chưa mở khóa. Đạt 70% ở cấp trước nhé.");
        try {
          card = await get("/api/cards/" + encodeURIComponent(card.id));
          unlocked = card.unlocked_levels || [1];
        } catch {
          /* keep the old state */
        }
        level = 1;
        draw();
      } else if (e.status !== 403) {
        fbText.textContent = errorMessage(e);
      }
    } finally {
      busy = false;
    }
  }

  function showSelfCheck(item) {
    selfBox.classList.remove("hidden");
    selfBox.replaceChildren(
      el("p", { class: "sub" }, "Tự đánh giá: máy này chưa nhận dạng được giọng nói nên bạn tự chọn. Điểm không do máy chấm từ giọng của bạn."),
      el(
        "button",
        {
          type: "button",
          class: "btn",
          "data-testid": "practice-selfcheck-ok",
          onclick: () => {
            selfBox.classList.add("hidden");
            submit(item, item.text);
          },
        },
        "Tôi nói đúng",
      ),
      el(
        "button",
        {
          type: "button",
          class: "btn sec",
          "data-testid": "practice-selfcheck-bad",
          onclick: () => {
            selfBox.classList.add("hidden");
            submit(item, "");
          },
        },
        "Tôi nói chưa đúng",
      ),
    );
  }

  function recorder(getItem) {
    const rec = el("button", { type: "button", class: "rec", "data-testid": "practice-record", "aria-label": "Giữ để nói" }, "🎤 Giữ để nói");
    rec.addEventListener("contextmenu", (e) => e.preventDefault());
    let recog = null;
    let t0 = 0;
    let on = false;
    const start = (e) => {
      e.preventDefault();
      if (on || busy) return;
      try {
        rec.setPointerCapture(e.pointerId);
      } catch {
        /* synthetic pointer */
      }
      on = true;
      selfBox.classList.add("hidden");
      rec.classList.add("on");
      rec.textContent = "● Đang nghe... thả để chấm";
      t0 = performance.now();
      recog = recognize({ continuous: false });
    };
    const stop = () => {
      if (!on) return;
      on = false;
      rec.classList.remove("on");
      rec.textContent = "🎤 Giữ để nói";
      const dur = performance.now() - t0;
      const item = getItem();
      const r = recog;
      recog = null;
      r.stop();
      if (dur < 500) {
        fbText.textContent = "Mình chưa nghe thấy gì. Giữ nút lâu hơn và nói nhé.";
        return;
      }
      setTimeout(
        () => {
          if (!r.active) return showSelfCheck(item);
          const heard = r.text();
          if (!heard) fbText.textContent = "Mình chưa nghe thấy gì. Nói to hơn rồi thử lại nhé.";
          else submit(item, heard);
        },
        r.active ? 700 : 0,
      );
    };
    rec.addEventListener("pointerdown", start);
    rec.addEventListener("pointerup", stop);
    rec.addEventListener("pointercancel", stop);
    rec.addEventListener("pointerleave", stop);
    return rec;
  }

  function draw() {
    const items = itemsFor(card, level);
    if (target[level] >= items.length) target[level] = 0;
    const cur = () => items[target[level]];
    const seg = el(
      "div",
      { class: "seg", role: "tablist" },
      ...LEVELS.map(([k, name, sub]) => {
        const open = unlocked.includes(k);
        return el(
          "button",
          {
            type: "button",
            class: k === level ? "on" : "",
            disabled: !open,
            role: "tab",
            "aria-selected": k === level ? "true" : "false",
            "data-testid": "practice-tab-" + k,
            title: open ? "" : "Đạt 70% ở cấp trước để mở khóa",
            onclick: () => {
              level = k;
              draw();
            },
          },
          el("b", {}, (open ? "" : "🔒 ") + name),
          el("small", {}, open ? sub : sub + " · khóa"),
        );
      }),
    );
    const lines = items.map((it, i) => {
      const vi = el("div", { class: "sub hidden" }, it.vi || "");
      const toggle = el(
        "button",
        {
          type: "button",
          class: "ib",
          "data-testid": "practice-vi-toggle",
          style: "min-height:44px;font-size:12px;justify-content:flex-start;padding:0;color:var(--blue)",
          onclick: (e) => {
            e.stopPropagation();
            vi.classList.toggle("hidden");
            toggle.textContent = vi.classList.contains("hidden") ? "Xem nghĩa" : "Ẩn nghĩa";
          },
        },
        "Xem nghĩa",
      );
      const row = el(
        "div",
        {
          class: "line" + (i === target[level] ? " on" : ""),
          role: "button",
          tabindex: "0",
          "data-testid": "practice-line",
          onclick: () => {
            target[level] = i;
            speak(it.text, it.audio);
            draw();
          },
        },
        el("div", { style: "flex:1" }, el("div", { class: "en" }, it.text), it.ipa ? el("div", { class: "ipa" }, it.ipa) : null, it.vi ? vi : null, it.vi ? toggle : null),
        el("button", { type: "button", class: "ib", "aria-label": "Nghe mẫu " + it.text, onclick: (e) => { e.stopPropagation(); speak(it.text, it.audio); } }, "🔊"),
      );
      row.addEventListener("keydown", (e) => {
        if (e.target === row && (e.key === "Enter" || e.key === " ")) {
          e.preventDefault();
          row.click();
        }
      });
      return row;
    });
    const hint = LEVELS[level - 1][3];
    wrap.replaceChildren(
      scene(card, { onMarker: (lb) => speak(lb.word, lb.audio_url) }),
      el("p", { class: "note" }, "Chạm chấm tròn để nghe từ."),
      seg,
      el("p", { class: "sub" }, hint),
      items.length ? el("div", { style: "display:grid;gap:8px" }, ...lines) : el("p", { class: "sub center" }, "Thẻ này chưa có nội dung cho cấp độ này."),
      items.length ? recorder(cur) : null,
      selfBox,
      fb,
      el("button", { type: "button", class: "btn sec", "data-testid": "practice-reflex", onclick: () => ctx.navigate("reflex") }, "⚡ Thử Reflex"),
    );
  }

  draw();
  ctx.onLeave(stopSpeaking);
  return screen(hdr(card.title || "Luyện tập", { onBack: () => ctx.back("library") }), wrap);
}
