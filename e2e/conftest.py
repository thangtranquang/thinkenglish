"""End-to-end fixtures: a real uvicorn process on a free port + Playwright (Chromium) with browser stubs.

The server runs with `SESSION_IDLE_SECONDS=3` and `GUEST_FREE_SESSIONS=1` so the second-visit gate can be
reached in seconds, the mock AI provider (no GEMINI_API_KEY) and a throw-away DB/data dir.

Browser stubs (installed in every context before any page script runs):
- `SpeechRecognition`/`webkitSpeechRecognition`: `start()` reports `window.__stt.text` after `window.__stt.delay` ms.
  When `__stt.text` is empty it answers with the word of the current Reflex/Auto round (learnt from the
  `/api/reflex/sessions` response, round number read from the "Vòng N/M" label on screen).
- `speechSynthesis`, `HTMLMediaElement.play`: instant, silent.
- `navigator.mediaDevices.getUserMedia`: rejects (no microphone), so onset comes from the recognition stub.
"""
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]

STUBS = """
(() => {
  window.__stt = { text: '', delay: 300, starts: 0 };
  window.__rounds = null;
  const wordNow = () => {
    if (window.__stt.text) return window.__stt.text;
    const m = /Vòng (\\d+)\\/(\\d+)/.exec(document.body ? document.body.innerText : '');
    return m && window.__rounds && window.__rounds[+m[1] - 1] ? window.__rounds[+m[1] - 1].word : '';
  };
  class FakeRecognition {
    constructor() { this.lang = ''; this.interimResults = false; this.continuous = false; this.onresult = null; this.onerror = null; this.onend = null; this._t = null; }
    start() {
      window.__stt.starts++;
      this._t = setTimeout(() => {
        const text = wordNow();
        if (text && this.onresult) this.onresult({ resultIndex: 0, results: [[{ transcript: text, confidence: 0.9 }]] });
      }, window.__stt.delay);
    }
    stop() { clearTimeout(this._t); if (this.onend) this.onend(); }
    abort() { this.stop(); }
  }
  window.SpeechRecognition = FakeRecognition;
  window.webkitSpeechRecognition = FakeRecognition;
  Object.defineProperty(window, 'speechSynthesis', { configurable: true, value: {
    speak(u) { setTimeout(() => u && u.onend && u.onend(), 10); }, cancel() {}, getVoices() { return []; } } });
  HTMLMediaElement.prototype.play = function () { setTimeout(() => this.dispatchEvent(new Event('ended')), 20); return Promise.resolve(); };
  HTMLMediaElement.prototype.pause = function () {};
  if (navigator.mediaDevices) navigator.mediaDevices.getUserMedia = () => Promise.reject(new DOMException('no mic', 'NotAllowedError'));
  const realFetch = window.fetch.bind(window);
  window.fetch = async (...args) => {
    const res = await realFetch(...args);
    try {
      const url = String(args[0] && args[0].url ? args[0].url : args[0]);
      if (/\\/api\\/reflex\\/sessions$/.test(url)) res.clone().json().then((j) => { window.__rounds = j.rounds; });
    } catch (e) { /* ignore */ }
    return res;
  };
})();
"""


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def server(tmp_path_factory):
    port = _free_port()
    origin = f"http://127.0.0.1:{port}"
    data = tmp_path_factory.mktemp("e2e_data")
    env = {k: v for k, v in os.environ.items() if k != "GEMINI_API_KEY"}
    env.update(GEMINI_API_KEY="", LLM_API_KEY="", LLM_BASE_URL="", APP_ORIGIN=origin, DATA_DIR=str(data), DB_PATH=str(data / "e2e.db"), SESSION_IDLE_SECONDS="3",
               GUEST_FREE_SESSIONS="1", SCRYPT_N="1024", PYTHONUNBUFFERED="1")
    log = open(data / "server.log", "w", encoding="utf-8")
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1",
                             "--port", str(port), "--workers", "1", "--log-level", "warning"],
                            cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    deadline = time.time() + 30
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError("uvicorn exited early: " + (data / "server.log").read_text(encoding="utf-8"))
        try:
            urllib.request.urlopen(origin + "/api/health", timeout=1)
            break
        except OSError:
            time.sleep(0.2)
    else:
        proc.kill()
        raise RuntimeError("uvicorn did not start")
    yield origin
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
    log.close()


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture
def new_context(browser, server):
    """Factory: a fresh browser context (own cookies/storage) with the stubs installed."""
    made = []

    def make(**kw):
        ctx = browser.new_context(base_url=server, viewport={"width": 420, "height": 860}, **kw)
        ctx.set_default_timeout(15000)
        ctx.add_init_script(STUBS)
        made.append(ctx)
        return ctx

    yield make
    for c in made:
        c.close()


@pytest.fixture
def page(new_context):
    return new_context().new_page()
