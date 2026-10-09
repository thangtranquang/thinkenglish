// Sample audio: pre-generated mp3 from /audio, falling back to the browser's voice.
let current = null;

function pickVoice() {
  try {
    const vs = speechSynthesis.getVoices().filter((v) => /^en[-_]/i.test(v.lang));
    const male = /brian|andrew|guy|ryan|eric|christopher|roger|mark|david|daniel|alex|male/i;
    return (
      vs.find((v) => /microsoft/i.test(v.name) && /natural|online/i.test(v.name) && male.test(v.name)) ||
      vs.find((v) => male.test(v.name)) ||
      vs.find((v) => v.lang === "en-US") ||
      null
    );
  } catch {
    return null;
  }
}

function speakFallback(text, done) {
  try {
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "en-US";
    u.rate = 0.9;
    const v = pickVoice();
    if (v) u.voice = v;
    u.onend = u.onerror = () => done();
    speechSynthesis.speak(u);
  } catch {
    done();
  }
}

function urlOf(file) {
  if (!file) return null;
  if (file.startsWith("/") || file.startsWith("http")) return file;
  return "/audio/" + encodeURIComponent(file);
}

// speak(text, file?) resolves when the sound has finished (or was interrupted / failed).
export function speak(text, file = null) {
  return new Promise((resolve) => {
    stopSpeaking();
    let finished = false;
    const done = () => {
      if (!finished) {
        finished = true;
        resolve();
      }
    };
    const src = urlOf(file);
    if (!src) return speakFallback(text, done);
    let a;
    try {
      a = new Audio(src);
    } catch {
      return speakFallback(text, done);
    }
    current = a;
    a.addEventListener("ended", done);
    a.addEventListener("pause", done);
    a.addEventListener("error", () => (current === a ? speakFallback(text, done) : done()), { once: true });
    let p;
    try {
      p = a.play();
    } catch {
      p = Promise.reject(new Error("play"));
    }
    if (p && p.catch) p.catch(() => (current === a && a.error ? speakFallback(text, done) : done()));
    setTimeout(done, 20000);
  });
}

export function stopSpeaking() {
  try {
    speechSynthesis.cancel();
  } catch {
    /* no speech synthesis */
  }
  if (current) {
    const a = current;
    current = null;
    try {
      a.pause();
    } catch {
      /* ignore */
    }
  }
}

let actx = null;
export function unlockAudio() {
  try {
    actx = actx || new (window.AudioContext || window.webkitAudioContext)();
    if (actx.state === "suspended") actx.resume();
  } catch {
    /* ignore */
  }
}

// Short beep that tells the learner it is their turn (hands-free mode).
export function beep(freq = 880, ms = 130) {
  try {
    unlockAudio();
    const o = actx.createOscillator();
    const g = actx.createGain();
    o.frequency.value = freq;
    g.gain.value = 0.08;
    o.connect(g);
    g.connect(actx.destination);
    o.start();
    o.stop(actx.currentTime + ms / 1000);
  } catch {
    /* ignore */
  }
}
