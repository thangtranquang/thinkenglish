// Reflex mode R1-R4: look at the marked object and say its name before time runs out.
import { post, put } from "../api.js";
import { speak, stopSpeaking, unlockAudio } from "../audio.js";
import { hasMic, hasRecognition, initMic, listen } from "../speech.js";
import { S } from "../state.js";
import { el, errorMessage, hdr, screen, toast } from "../ui.js";
import { LEVELS, SETTLE_MS, hintOf, labelOf, loadCards, postAttempt, refreshMe, roundScene, startSession } from "../rounds.js";

export function render(ctx) {
  const me = S.me || {};
  const maxLevel = me.reflex_level_unlocked || 1;
  let level = Math.min(2, maxLevel);
  let tok = 0; // bumped to cancel everything that is still running
  let listener = null;
  let raf = 0;
  const timers = [];
  const later = (fn, ms) => timers.push(setTimeout(fn, ms));
  const host = el("div", { class: "body", "data-testid": "screen-reflex" });

  function cleanup() {
    tok++;
    timers.splice(0).forEach(clearTimeout);
    cancelAnimationFrame(raf);
    if (listener) {
      listener.stop();
      listener = null;
    }
    stopSpeaking();
  }
  ctx.onLeave(cleanup);

  function setup() {
    cleanup();
    const err = el("p", { class: "err", role: "alert", "aria-live": "assertive", "data-testid": "reflex-error" });
    const group = el(
      "div",
      { style: "display:grid;gap:8px", role: "radiogroup", "aria-label": "Chọn cấp độ" },
      ...Object.entries(LEVELS).map(([k, v]) => {
        const open = +k <= maxLevel;
        const input = el("input", { type: "radio", name: "rl", value: k, checked: +k === level, disabled: !open, "data-testid": "reflex-level-" + k });
        input.addEventListener("change", () => (level = +k));
        return el("label", { class: "opt" }, input, el("div", {}, el("b", {}, (open ? "" : "🔒 ") + v.name), el("span", {}, open ? v.desc : "Hoàn thành phiên ở cấp trước với điểm tốt để mở khóa.")));
      }),
    );
    const hide = el("input", { type: "checkbox", id: "hide", checked: !!me.hide_timer, "data-testid": "reflex-hide-timer" });
    hide.addEventListener("change", async () => {
      if (S.me) S.me.hide_timer = hide.checked;
      try {
        await put("/api/me/settings", { hide_timer: hide.checked });
      } catch {
        /* the choice still applies to this session */
      }
    });
    host.replaceChildren(
      el("p", { class: "sub" }, "Nhìn vật được đánh dấu và nói tiếng Anh thật nhanh, trước khi hết giờ. Chữ bị ẩn. Sai cũng không sao: bạn sẽ thấy đáp án và từ đó được ôn lại."),
      group,
      el("label", { class: "row", for: "hide" }, el("span", {}, "Ẩn đồng hồ (vẫn đo thời gian)"), el("span", { class: "sw" }, hide)),
      el("button", { type: "button", class: "btn", "data-testid": "reflex-start", onclick: () => begin(err) }, "Bắt đầu phiên Reflex"),
      el(
        "button",
        {
          type: "button",
          class: "btn sec",
          "data-testid": "auto-start",
          onclick: () => {
            unlockAudio();
            ctx.navigate("auto", { query: { level: String(Math.min(level, 3)) } });
          },
        },
        "🎧 Chạy tự động (rảnh tay)",
      ),
      err,
      el("p", { class: "note" }, "Chế độ tự động: một lần chạm, máy tự đếm ngược, bíp, nghe, chấm và chuyển vòng. Không có micro thì bạn bấm \"Tôi bắt đầu nói\"."),
    );
  }

  async function begin(err) {
    err.textContent = "";
    unlockAudio();
    const my = ++tok;
    let sess;
    let cards;
    try {
      sess = await startSession(level);
      cards = await loadCards(sess.rounds);
    } catch (e) {
      if (my === tok) err.textContent = e.error === "level_locked" ? "Cấp độ này chưa mở khóa." : errorMessage(e);
      return;
    }
    if (my !== tok) return;
    if (!sess.rounds.length) {
      err.textContent = "Chưa có từ nào để luyện. Hãy thêm hoặc lưu vài thẻ trước nhé.";
      return;
    }
    await initMic();
    if (my !== tok) return;
    runRound(sess, cards, 0, []);
  }

  function runRound(sess, cards, i, results) {
    cleanup();
    const my = tok;
    const round = sess.rounds[i];
    const card = cards.get(round.card_id);
    const label = labelOf(card, round);
    const limit = sess.limit_ms;
    const fill = el("i");
    const timer = el("div", { class: "timer" + (S.me && S.me.hide_timer ? " hid" : ""), "data-testid": "reflex-timer" }, fill);
    const hint = el("div", { class: "hint", "aria-live": "polite" }, sess.level === 1 ? hintOf(round.word) : "");
    const micTxt = el("span", {}, "Đang nghe…");
    const mic = el("div", { class: "mic" }, el("span", { class: "dot on" }), micTxt);
    const canHear = hasMic() || hasRecognition();
    let onsetMs = null;
    let done = false;
    const t0 = performance.now();

    const tick = () => {
      const f = Math.max(0, 1 - (performance.now() - t0) / limit);
      fill.style.transform = `scaleX(${f})`;
      fill.style.background = f < 0.34 ? "#e11d48" : f < 0.67 ? "#d97706" : "#2563eb";
      if (f > 0 && onsetMs === null && !done) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);

    const onset = (t) => {
      if (onsetMs !== null || done || my !== tok) return;
      onsetMs = Math.max(0, Math.min(Math.round(t - t0), limit - 1));
      micTxt.textContent = "Đã ghi nhận, nói tiếp đi…";
      later(() => finish(false), SETTLE_MS);
    };

    async function finish(timedOut) {
      if (done || my !== tok) return;
      done = true;
      cancelAnimationFrame(raf);
      let text = "";
      const recognised = !!(listener && listener.hasRecognition);
      if (listener) {
        text = listener.stop();
        listener = null;
      }
      if (timedOut) return record({ reflex_ms: limit, timedOut: true });
      if (recognised) return record({ reflex_ms: onsetMs, transcript: text });
      selfCheck();
    }

    async function record(extra) {
      const { timedOut = false, ...body } = extra;
      let result = null;
      let error = null;
      try {
        result = await postAttempt(round, { mode: "reflex", reflex_level: sess.level, reflex_session_id: sess.session_id, ...body });
      } catch (e) {
        error = e;
      }
      if (my !== tok) return;
      results.push({ round, ms: timedOut ? null : body.reflex_ms, result, timedOut });
      reveal(result, error, timedOut, body.reflex_ms);
    }

    function selfCheck() {
      host.replaceChildren(
        el("div", { class: "card", "data-testid": "reflex-selfcheck" },
          el("p", { class: "sub" }, "Tự đánh giá: máy này chưa nhận dạng được giọng nói nên bạn tự chọn. Điểm không do máy chấm từ giọng của bạn."),
          el("div", { class: "word" }, round.word),
          round.ipa ? el("div", { class: "ipa" }, round.ipa) : null,
        ),
        el("button", { type: "button", class: "btn", "data-testid": "reflex-self-ok", onclick: () => record({ reflex_ms: onsetMs, transcript: round.word }) }, "Tôi nói đúng"),
        el("button", { type: "button", class: "btn sec", "data-testid": "reflex-self-bad", onclick: () => record({ reflex_ms: onsetMs, transcript: "" }) }, "Tôi nói chưa đúng"),
      );
      speak(round.word, round.audio_file);
    }

    function reveal(result, error, timedOut, ms) {
      const last = i + 1 >= sess.rounds.length;
      const vi = el("div", { class: "sub hidden" }, label.vi_meaning || "");
      const viBtn = el("button", {
        type: "button",
        class: "btn sec sm",
        onclick: () => {
          vi.classList.toggle("hidden");
          viBtn.textContent = vi.classList.contains("hidden") ? "Xem nghĩa" : "Ẩn nghĩa";
        },
      }, "Xem nghĩa");
      const verdict = timedOut ? ["Hết giờ, không sao cả", "miss"] : result && result.accuracy >= 70 ? (result.score >= 70 ? ["Phản xạ tốt", "good"] : ["Đúng, nhưng hơi chậm", "slow"]) : ["Chưa đúng, thử lại sau nhé", "miss"];
      host.replaceChildren(
        el("div", { class: "card", "data-testid": "reflex-reveal" },
          error ? el("span", { class: "badge info", style: "align-self:flex-start" }, errorMessage(error)) : el("span", { class: "badge " + verdict[1], style: "align-self:flex-start" }, verdict[0]),
          el("div", { class: "word" }, round.word),
          round.ipa ? el("div", { class: "ipa" }, round.ipa) : null,
          vi,
          el("div", { class: "row" }, el("button", { type: "button", class: "btn sec sm", onclick: () => speak(round.word, round.audio_file) }, "🔊 Nghe mẫu"), label.vi_meaning ? viBtn : null),
        ),
        el("div", { class: "stat two" },
          el("div", {}, el("b", { "data-testid": "reflex-ms" }, timedOut || ms == null ? "—" : (ms / 1000).toFixed(1) + "s"), el("span", {}, "Thời gian bắt đầu nói")),
          el("div", {}, el("b", { "data-testid": "reflex-score" }, result ? String(result.score) : "—"), el("span", {}, result ? `Điểm phản xạ · +${result.xp} XP` : "Điểm phản xạ")),
        ),
        el("button", { type: "button", class: "btn", "data-testid": "reflex-next", onclick: () => (last ? summary(sess, results) : runRound(sess, cards, i + 1, results)) }, last ? "Xem tổng kết" : "Vòng tiếp theo"),
      );
      speak(round.word, round.audio_file);
    }

    host.replaceChildren(
      el("div", { class: "meter", style: "height:8px" }, el("i", { style: `width:${(i / sess.rounds.length) * 100}%;background:var(--blue)` })),
      el("p", { class: "sub center", "data-testid": "reflex-round" }, `Vòng ${i + 1}/${sess.rounds.length}`),
      roundScene(card, label),
      timer,
      el("div", { style: "text-align:center" }, el("div", { style: "font-size:16px;font-weight:700" }, "Đây là gì? Nói bằng tiếng Anh"), hint),
      canHear ? mic : el("div", { class: "mic" }, el("button", { type: "button", class: "btn sm", "data-testid": "reflex-onset", onclick: () => onset(performance.now()) }, "Tôi bắt đầu nói")),
    );
    if (canHear) listener = listen(onset);
    later(() => {
      if (onsetMs === null) finish(true);
    }, limit);
  }

  async function summary(sess, results) {
    cleanup();
    let out = null;
    try {
      out = await post(`/api/reflex/sessions/${encodeURIComponent(sess.session_id)}/complete`);
    } catch {
      /* summary still shows local numbers */
    }
    const before = (S.me && S.me.reflex_level_unlocked) || 1;
    await refreshMe();
    const timed = results.filter((r) => r.ms != null);
    const avgMs = timed.length ? Math.round(timed.reduce((a, r) => a + r.ms, 0) / timed.length) : null;
    const scores = results.filter((r) => r.result).map((r) => r.result.score);
    const avg = out && out.score != null ? out.score : scores.length ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) : null;
    const weak = results.filter((r) => !r.result || r.result.score < 70);
    if (out && out.reflex_level_unlocked > before) toast("Đã mở khóa Reflex R" + out.reflex_level_unlocked + "!");
    host.replaceChildren(
      el("div", { class: "stat two", "data-testid": "reflex-summary" },
        el("div", {}, el("b", {}, avgMs == null ? "—" : (avgMs / 1000).toFixed(1) + "s"), el("span", {}, "Phản hồi trung bình")),
        el("div", {}, el("b", { "data-testid": "summary-score" }, avg == null ? "—" : String(avg)), el("span", {}, "Điểm phản xạ")),
      ),
      out && !out.counted ? el("p", { class: "note" }, "Phiên này có ít hơn 5 câu trả lời nên chưa tính để mở khóa cấp mới.") : null,
      weak.length
        ? el("div", { class: "card" }, el("h2", {}, "Sẽ đưa vào lịch ôn tập"), ...weak.map((r) => el("div", { class: "row" }, el("span", {}, r.round.word), el("span", { class: "sub" }, r.timedOut ? "hết giờ" : "cần ôn lại"))))
        : el("div", { class: "card" }, el("h2", {}, "Tuyệt vời! Cả phiên đều phản xạ tốt.")),
      el("button", { type: "button", class: "btn", "data-testid": "reflex-home", onclick: () => ctx.navigate("home") }, "Về Trang chủ"),
      el("button", { type: "button", class: "btn sec", onclick: () => ctx.navigate("library") }, "Xem Thư viện"),
    );
  }

  setup();
  return screen(hdr("Reflex Mode", { onBack: () => ctx.navigate("home") }), host);
}
