// Auto mode: hands-free loop. One tap on "Chạy tự động" starts it; then countdown -> beep -> listen -> reveal -> next.
// It pauses while the tab is hidden and resumes when it is visible again.
import { beep, speak, stopSpeaking, unlockAudio } from "../audio.js";
import { hasMic, hasRecognition, initMic, listen } from "../speech.js";
import { el, errorMessage, hdr, screen } from "../ui.js";
import { SETTLE_MS, hintOf, labelOf, loadCards, postAttempt, roundScene, sleep, startSession } from "../rounds.js";

const PREPARE_MS = 1300;
const AFTER_REVEAL_MS = 1200;

export function render(ctx) {
  const level = Math.min(3, Math.max(1, parseInt(ctx.query.level || "1", 10) || 1));
  const host = el("div", { class: "body", "data-testid": "screen-auto" });
  const status = el("p", { class: "sub center", role: "status", "aria-live": "polite", "data-testid": "auto-status" }, "Đang chuẩn bị…");
  const stopBtn = el("button", { type: "button", class: "btn sec", "aria-label": "Dừng chế độ tự động", "data-testid": "auto-stop", onclick: () => stop() }, "⏹ Dừng tự động");
  let tok = 0;
  let listener = null;
  let session = null;
  let cards = null;
  let index = 0;
  let stopped = false;
  let paused = false;
  const results = [];

  function halt() {
    tok++;
    if (listener) {
      listener.stop();
      listener = null;
    }
    stopSpeaking();
  }

  function stop() {
    stopped = true;
    halt();
    ctx.navigate("reflex");
  }

  const onVisibility = () => {
    if (stopped || !session) return;
    if (document.hidden) {
      paused = true;
      halt();
      status.textContent = "Đã tạm dừng vì bạn rời khỏi màn hình. Quay lại để chạy tiếp.";
    } else if (paused) {
      paused = false;
      loop();
    }
  };
  document.addEventListener("visibilitychange", onVisibility);
  ctx.onLeave(() => {
    stopped = true;
    halt();
    document.removeEventListener("visibilitychange", onVisibility);
  });

  async function loop() {
    const my = ++tok;
    const alive = () => my === tok && !stopped;
    while (index < session.rounds.length) {
      if (!alive()) return;
      const round = session.rounds[index];
      const card = cards.get(round.card_id);
      const label = labelOf(card, round);
      const hint = el("div", { class: "hint", "aria-live": "polite" }, level === 1 ? hintOf(round.word) : "");
      const q = el("div", { style: "font-size:16px;font-weight:700;text-align:center", "data-testid": "auto-question" }, "Chuẩn bị…");
      const progress = el("div", { class: "meter", style: "height:8px" }, el("i", { style: `width:${(index / session.rounds.length) * 100}%;background:var(--blue)` }));
      host.replaceChildren(progress, el("p", { class: "sub center", "data-testid": "auto-round" }, `Vòng ${index + 1}/${session.rounds.length}`), roundScene(card, label), q, hint, status, stopBtn);
      status.textContent = "Chuẩn bị… chờ tiếng bíp rồi nói.";
      await sleep(PREPARE_MS);
      if (!alive()) return;
      beep();
      q.textContent = "Đây là gì? Nói bằng tiếng Anh";
      status.textContent = "Đang nghe…";
      let onset = false;
      listener = listen(() => {
        onset = true;
        status.textContent = "Đã ghi nhận, nói tiếp đi…";
      });
      const scorable = listener.hasRecognition;
      const start = performance.now();
      const limit = session.limit_ms;
      while (alive() && performance.now() - start < limit) {
        await sleep(100);
        if (onset) {
          await sleep(SETTLE_MS);
          break;
        }
      }
      if (!alive()) return;
      const text = listener.stop();
      listener = null;
      let result = null;
      if (scorable) {
        try {
          result = await postAttempt(round, { mode: "auto", transcript: text });
        } catch (e) {
          status.textContent = errorMessage(e);
        }
      }
      if (!alive()) return;
      results.push({ round, result });
      if (result) status.textContent = `Chính xác ${result.accuracy}% · +${result.xp} XP`;
      else if (!scorable) status.textContent = "Máy này chưa nhận dạng được giọng nói: chỉ nghe và nói theo, không chấm điểm.";
      q.textContent = round.word;
      await speak(round.word, round.audio_file);
      if (!alive()) return;
      await sleep(AFTER_REVEAL_MS);
      if (!alive()) return;
      index++;
    }
    if (alive()) finished();
  }

  function finished() {
    const scored = results.filter((r) => r.result);
    const avg = scored.length ? Math.round(scored.reduce((a, r) => a + r.result.accuracy, 0) / scored.length) : null;
    host.replaceChildren(
      el("div", { class: "card", "data-testid": "auto-summary" }, el("h2", {}, "Xong vòng tự động"), el("p", { class: "sub" }, avg == null ? "Chưa có điểm vì máy không nhận dạng được giọng nói." : `Chính xác trung bình ${avg}%`)),
      el("button", { type: "button", class: "btn", onclick: () => ctx.navigate("home") }, "Về Trang chủ"),
    );
  }

  (async () => {
    unlockAudio();
    try {
      session = await startSession(level);
      cards = await loadCards(session.rounds);
    } catch (e) {
      status.textContent = e.error === "level_locked" ? "Cấp độ này chưa mở khóa." : errorMessage(e);
      host.replaceChildren(status, el("button", { type: "button", class: "btn sec", onclick: () => ctx.navigate("reflex") }, "Quay lại"));
      return;
    }
    if (!session.rounds.length) {
      host.replaceChildren(el("p", { class: "sub center" }, "Chưa có từ nào để luyện."), el("button", { type: "button", class: "btn sec", onclick: () => ctx.navigate("reflex") }, "Quay lại"));
      return;
    }
    await initMic();
    if (stopped) return;
    if (!hasMic() && !hasRecognition()) status.textContent = "Không có micro: chỉ nghe và nói theo, không chấm điểm.";
    if (document.hidden) {
      paused = true;
      return;
    }
    loop();
  })();

  host.append(status, stopBtn);
  return screen(hdr("Tự động", { onBack: stop, backTestId: "auto-back" }), host);
}
