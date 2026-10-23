"""
tts.py — Fish Audio synthesis, one request per sentence chunk.

The response is streamed so time-to-first-byte can be measured; the chunk is
returned whole because the browser decodes one complete MP3 per chunk.

Fish Audio is no longer the only voice. `JARVIS_TTS` picks:

    auto     (default) Fish Audio when there is a key; the browser's own
             voice when there is not, and for any sentence Fish could not
             voice. Nobody is left with a silent assistant.
    fish     Fish Audio or nothing — the original behaviour: a sentence it
             cannot voice is shown as text.
    browser  Never call Fish Audio. The page speaks with Chrome's built-in
             speechSynthesis: free, offline-capable, and it has Mandarin.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Optional

import httpx

log = logging.getLogger("jarvis.tts")

FISH_TTS_URL = "https://api.fish.audio/v1/tts"

# The value .env.example used to ship with. Copying the example without
# editing it must not read as "has a key", or every sentence would wait out
# a 401 before anything was said.
PLACEHOLDER_KEY = "your-fish-audio-api-key-here"

TTS_MODES = ("auto", "fish", "browser")
VOICE_FISH = "fish"
VOICE_BROWSER = "browser"


def usable_key(key: Optional[str]) -> str:
    """The Fish Audio key, or "" if there is not really one."""
    key = (key or "").strip()
    return "" if key == PLACEHOLDER_KEY else key


def normalize_mode(raw: Optional[str]) -> str:
    """`auto`, `fish` or `browser`; anything else is auto."""
    mode = (raw or "auto").strip().lower()
    return mode if mode in TTS_MODES else "auto"


def tts_mode() -> str:
    """`auto`, `fish` or `browser`, from `JARVIS_TTS`."""
    return normalize_mode(os.getenv("JARVIS_TTS"))


def voice_mode(key: Optional[str]) -> str:
    """Which voice speaks a sentence by default: `fish` or `browser`."""
    mode = tts_mode()
    if mode == "browser":
        return VOICE_BROWSER
    if mode == "fish":
        return VOICE_FISH
    return VOICE_FISH if usable_key(key) else VOICE_BROWSER


def browser_fallback() -> bool:
    """Whether a sentence with no Fish audio is handed to the page to speak."""
    return tts_mode() != "fish"


@dataclass
class SynthResult:
    audio: bytes
    first_byte_sec: float
    total_sec: float


async def synthesize_chunk(text: str, *, api_key: str, voice_id: str,
                           client: Optional[httpx.AsyncClient] = None,
                           latency: str = "balanced", timeout: float = 15.0) -> Optional[SynthResult]:
    text = (text or "").strip()
    if not text or not api_key:
        return None
    own = client is None
    client = client or httpx.AsyncClient(timeout=timeout)
    t0 = time.monotonic()
    first: Optional[float] = None
    buf = bytearray()
    try:
        async with client.stream(
            "POST", FISH_TTS_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"text": text, "reference_id": voice_id, "format": "mp3", "mp3_bitrate": 128, "latency": latency},
            timeout=timeout,
        ) as resp:
            if resp.status_code != 200:
                log.error(f"TTS {resp.status_code} for {text[:40]!r}")
                return None
            async for part in resp.aiter_bytes():
                if first is None:
                    first = time.monotonic() - t0
                buf.extend(part)
    except (httpx.HTTPError, OSError) as e:
        log.error(f"TTS error: {e}")
        return None
    finally:
        if own:
            try:
                await client.aclose()
            except Exception as e:      # never turn a clean None into an exception
                log.debug(f"TTS client close failed: {e}")
    if not buf:
        return None
    return SynthResult(bytes(buf), first if first is not None else 0.0, time.monotonic() - t0)
