"""The voice page, end to end, in Mandarin with the browser's own voice.

The REAL built bundle (`frontend/dist`, built by `tests/dashboard_page.py`'s
`build_bundle`) in Playwright's headless Chromium, against the REAL server —
`server.app` under uvicorn, in-process — with a stand-in brain. What is
scripted is only what headless Chromium does not have: a microphone for
`SpeechRecognition` and a voice for `speechSynthesis`. Both are replaced by
fakes that record what the page asked of them, so the test can say "the page
listened in zh-TW", "it spoke these sentences, in this order, in a Taiwanese
voice", and "Escape silenced it" about the code that ships.

Nothing here touches the network, a real `claude`, or the user's data, and it
skips cleanly where `npm` or Playwright is missing, exactly as the dashboard
tests do.
"""

from __future__ import annotations

import importlib
import sys
import threading
import time
from pathlib import Path

import pytest
import pytest_asyncio

sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.dashboard_page import _free_port, build_bundle, why_unavailable

UNAVAILABLE = why_unavailable()
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(UNAVAILABLE is not None, reason=UNAVAILABLE or ""),
]

WAIT_MS = 10_000

# What headless Chromium lacks, scripted. `__voice` is the record the test
# reads; `__hear(text)` is the user saying something.
FAKES = r"""
(() => {
  const log = window.__voice = { recognisers: [], spoken: [], cancels: 0 };

  class FakeRecognition {
    constructor() {
      this.continuous = false; this.interimResults = false; this.lang = "";
      this.running = false;
      log.recognisers.push(this);
    }
    start() {
      this.running = true;
      setTimeout(() => { this.onstart && this.onstart(); this.onaudiostart && this.onaudiostart(); }, 10);
    }
    stop() {
      this.running = false;
      setTimeout(() => { this.onaudioend && this.onaudioend(); this.onend && this.onend(); }, 10);
    }
    abort() { this.stop(); }
  }
  window.SpeechRecognition = FakeRecognition;
  window.webkitSpeechRecognition = FakeRecognition;

  window.__hear = (text) => {
    const live = log.recognisers.filter((r) => r.running).pop();
    if (!live) return null;
    const result = [{ transcript: text }];
    result.isFinal = true;
    live.onresult({ resultIndex: 0, results: [result] });
    return live.lang;
  };

  window.SpeechSynthesisUtterance = class {
    constructor(text) { this.text = text; this.lang = ""; this.voice = null; this.rate = 1; this.pitch = 1; }
  };
  const voices = [
    { name: "Daniel", lang: "en-GB", localService: true, default: true, voiceURI: "Daniel" },
    { name: "Sin-ji", lang: "zh-HK", localService: true, default: false, voiceURI: "Sin-ji" },
    { name: "Meijia", lang: "zh-TW", localService: true, default: false, voiceURI: "Meijia" },
  ];
  const synth = {
    speaking: false, pending: false, paused: false, _current: null,
    getVoices() { return voices; },
    addEventListener() {}, removeEventListener() {},
    speak(u) {
      log.spoken.push({ text: u.text, lang: u.lang, voice: u.voice && u.voice.name });
      this._current = u; this.speaking = true;
      setTimeout(() => {
        if (this._current !== u) return;
        u.onstart && u.onstart({});
        setTimeout(() => {
          if (this._current !== u) return;
          this._current = null; this.speaking = false;
          u.onend && u.onend({});
        }, window.__speakMs || 120);
      }, 10);
    },
    cancel() {
      log.cancels++;
      const u = this._current;
      this._current = null; this.speaking = false;
      if (u && u.onerror) setTimeout(() => u.onerror({ error: "interrupted" }), 0);
    },
    pause() {}, resume() {},
  };
  Object.defineProperty(window, "speechSynthesis", { value: synth, configurable: true });
})();
"""


class ChineseBrain:
    def __init__(self):
        self.ready = True
        self.failed = False
        self.turns = []

    async def stop(self):
        pass

    async def turn(self, text, origin="user", on_delta=None, on_tool=None):
        from brain import TurnResult
        self.turns.append((text, origin))
        out = "好的，先生。我已經準備好了。"
        if on_delta:
            on_delta(out)
        return TurnResult(origin=origin, text=out, stop_reason="result", context_tokens=1,
                          output_tokens=5, duration_sec=0.01, first_delta_sec=0.001)


class LiveServer:
    """`server.app` under uvicorn on its own thread and its own loop."""

    def __init__(self, app, port: int):
        import uvicorn
        self.server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port,
                                                    log_level="warning", lifespan="on"))
        self.thread = threading.Thread(target=self.server.run, daemon=True)

    def __enter__(self):
        self.thread.start()
        deadline = time.time() + 20
        while not self.server.started:
            if time.time() > deadline or not self.thread.is_alive():
                raise RuntimeError("the server did not start")
            time.sleep(0.05)
        return self

    def __exit__(self, *exc):
        self.server.should_exit = True
        self.thread.join(timeout=15)


@pytest_asyncio.fixture
async def page_on_live_server(monkeypatch, tmp_path):
    build_bundle()
    port = _free_port()
    for key, value in {
        "JARVIS_DATA_DIR": str(tmp_path / "data"),
        "JARVIS_LANGUAGE": "zh-TW",
        "JARVIS_TTS": "browser",
        "FISH_API_KEY": "",
        "JARVIS_PORT": str(port),
        "JARVIS_BIND_HOST": "127.0.0.1",
        "JARVIS_SCHEME": "http",
    }.items():
        monkeypatch.setenv(key, value)
    import data_paths
    importlib.reload(data_paths)
    import run_store
    importlib.reload(run_store)
    import server
    importlib.reload(server)

    async def nothing(*a, **kw):
        return None

    # Startup work that would reach outside the test: the real `claude` CLI
    # (preflight) and the real ~/.claude roster (the session watcher).
    monkeypatch.setattr(server, "_run_preflight", nothing)
    monkeypatch.setattr(server, "start_session_watcher", nothing)
    monkeypatch.setattr(server, "stop_session_watcher", nothing)
    server._last_greeting_time = 0

    from playwright.async_api import async_playwright
    with LiveServer(server.app, port):
        server.brain_instance = ChineseBrain()
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(args=[
                "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
                "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
            ])
            try:
                page = await browser.new_page()
                errors: list[str] = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                await page.add_init_script(FAKES)
                await page.goto(f"http://127.0.0.1:{port}/")
                yield page, server, errors
            finally:
                await browser.close()


async def test_the_page_listens_and_answers_in_mandarin_with_its_own_voice(page_on_live_server):
    page, server, errors = page_on_live_server

    # The config frame turned the recogniser to Taiwanese Mandarin.
    await page.wait_for_function(
        "window.__voice.recognisers.some(r => r.running && r.lang === 'zh-TW')", timeout=WAIT_MS)
    assert await page.evaluate("document.documentElement.lang") == "zh-TW"
    assert await page.text_content("#btn-settings") == "設定"

    # Chrome will not speak before the page has had a click: the greeting
    # waits for one rather than failing.
    await page.wait_for_timeout(800)
    assert await page.evaluate("window.__voice.spoken.length") == 0
    await page.mouse.click(5, 5)
    await page.wait_for_function("window.__voice.spoken.length >= 1", timeout=WAIT_MS)
    greeting = (await page.evaluate("window.__voice.spoken"))[0]
    assert greeting["text"] in ("早安，先生。", "午安，先生。", "晚上好，先生。")
    assert greeting["lang"] == "zh-TW"
    assert greeting["voice"] == "Meijia", "Taiwan Mandarin, never the Cantonese voice"

    # The greeting's ack lets the server settle, then the user speaks.
    await page.wait_for_function(
        "document.getElementById('status-text').textContent === '聆聽中…'", timeout=WAIT_MS)
    heard_in = await page.evaluate("window.__hear('哪些對話在等我')")
    assert heard_in == "zh-TW"
    await page.wait_for_function("window.__voice.spoken.length >= 3", timeout=WAIT_MS)
    spoken = [s["text"] for s in await page.evaluate("window.__voice.spoken")]
    assert spoken[1:] == ["好的，先生。", "我已經準備好了。"], spoken
    assert server.brain_instance.turns == [("哪些對話在等我", "user")]

    # Every sentence acked: the server is idle, the page back to listening.
    await page.wait_for_function(
        "document.getElementById('status-text').textContent === '聆聽中…'", timeout=WAIT_MS)
    deadline = time.time() + 5
    while server.speech.is_speaking and time.time() < deadline:
        await page.wait_for_timeout(50)
    assert not server.speech.is_speaking
    assert errors == [], errors


async def test_escape_silences_the_browser_voice(page_on_live_server):
    page, server, errors = page_on_live_server
    await page.wait_for_function(
        "window.__voice.recognisers.some(r => r.running && r.lang === 'zh-TW')", timeout=WAIT_MS)
    await page.mouse.click(5, 5)
    await page.wait_for_function("window.__voice.spoken.length >= 1", timeout=WAIT_MS)
    await page.wait_for_function(
        "document.getElementById('status-text').textContent === '聆聽中…'", timeout=WAIT_MS)

    await page.evaluate("window.__speakMs = 4000")          # a long sentence
    await page.evaluate("window.__hear('說點什麼')")
    await page.wait_for_function("window.__voice.spoken.length >= 2", timeout=WAIT_MS)
    assert await page.is_visible("#hush")
    assert await page.text_content("#hush") == "停止"
    await page.keyboard.press("Escape")

    await page.wait_for_function("window.__voice.cancels >= 1", timeout=WAIT_MS)
    deadline = time.time() + 5
    while server.speech.is_speaking and time.time() < deadline:
        await page.wait_for_timeout(50)
    assert not server.speech.is_speaking, "the hush reached the server"
    await page.wait_for_timeout(500)
    spoken = [s["text"] for s in await page.evaluate("window.__voice.spoken")]
    assert "我已經準備好了。" not in spoken, f"the rest was dropped, not said: {spoken}"
    assert errors == [], errors
