// Speech input helpers. Only standard APIs (SpeechRecognition, getUserMedia, WebAudio) so tests can stub them.
const SR = () => window.SpeechRecognition || window.webkitSpeechRecognition || null;
let mic = null;

export const hasRecognition = () => !!SR();

// Ask for the microphone once. Resolves true when a VAD analyser is available.
export async function initMic() {
  if (mic) return true;
  try {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return false;
    const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const src = ctx.createMediaStreamSource(stream);
    const an = ctx.createAnalyser();
    an.fftSize = 1024;
    src.connect(an);
    mic = { stream, ctx, an };
    return true;
  } catch {
    return false;
  }
}

export const hasMic = () => !!mic;

function joined(ev) {
  return [...ev.results].map((r) => r[0].transcript).join(" ").trim();
}

// One recognition run. onResult(text) fires on every (interim) result; stop() returns the text heard so far.
export function recognize({ continuous = true, onResult = () => {} } = {}) {
  let text = "";
  let rec = null;
  const Ctor = SR();
  if (Ctor) {
    try {
      rec = new Ctor();
      rec.lang = "en-US";
      rec.interimResults = true;
      rec.continuous = continuous;
      rec.onresult = (ev) => {
        text = joined(ev);
        onResult(text);
      };
      rec.onerror = () => {};
      rec.start();
    } catch {
      rec = null;
    }
  }
  return {
    active: !!rec,
    text: () => text,
    stop() {
      if (rec) {
        try {
          rec.stop();
        } catch {
          /* already stopped */
        }
        rec = null;
      }
      return text;
    },
  };
}

// Voice-activity detector on the microphone: calls onOnset(performance.now()) once when speech starts.
export function detectOnset(onOnset) {
  if (!mic) return () => {};
  const buf = new Float32Array(mic.an.fftSize);
  let noise = 0.01;
  let hot = 0;
  let raf = 0;
  let stopped = false;
  const loop = () => {
    if (stopped) return;
    mic.an.getFloatTimeDomainData(buf);
    let s = 0;
    for (const v of buf) s += v * v;
    const rms = Math.sqrt(s / buf.length);
    if (rms > Math.max(0.05, noise * 4)) hot++;
    else {
      hot = 0;
      noise = noise * 0.95 + rms * 0.05;
    }
    if (hot >= 2) {
      stopped = true;
      onOnset(performance.now());
      return;
    }
    raf = requestAnimationFrame(loop);
  };
  raf = requestAnimationFrame(loop);
  return () => {
    stopped = true;
    cancelAnimationFrame(raf);
  };
}

// Listen for one answer: reports onset from the VAD and/or the first recognition result.
export function listen(onOnset) {
  let fired = false;
  const fire = (t) => {
    if (!fired) {
      fired = true;
      onOnset(t);
    }
  };
  const stopVad = detectOnset(fire);
  const rec = recognize({ onResult: (t) => t && fire(performance.now()) });
  return {
    hasRecognition: rec.active,
    text: rec.text,
    stop() {
      stopVad();
      return rec.stop();
    },
  };
}
