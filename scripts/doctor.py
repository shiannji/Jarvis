"""Check this machine is ready to run JARVIS, and say what to fix.

    .venv/bin/python scripts/doctor.py

It runs the server's own first-run checks (`preflight.run_checks` — the same
ones `server.py` runs at startup and speaks aloud when something fails), so
what this reports and what JARVIS later complains about can never disagree.
Nothing here changes anything: it reads, and it prints.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))


def _load_dotenv() -> None:
    """The settings the server would boot with, read the way it reads them."""
    env = REPO / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_MARKS = {"ok": "✅", "warn": "⚠️ ", "fail": "❌"}


async def main() -> int:
    # A terminal that cannot show Chinese gets "?" in their place, not a
    # traceback: a report with question marks in it is still a report.
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass
    _load_dotenv()
    import i18n
    import preflight
    import tts

    zh = i18n.is_zh()
    print("JARVIS 環境檢查" if zh else "JARVIS environment check")
    print("-" * 40)
    checks = await preflight.run_checks()
    for c in checks:
        print(f"{_MARKS.get(c.status, '•')} {c.name}: {c.message}")
        if c.status != preflight.STATUS_OK and c.remedy:
            print(f"     → {c.remedy}")
    print("-" * 40)
    voice = tts.voice_mode(os.getenv("FISH_API_KEY"))
    if zh:
        print("語言：繁體中文（zh-TW）")
        print("語音：" + ("Fish Audio（電影版 JARVIS 聲音）" if voice == "fish"
                         else "瀏覽器內建語音（免費）"))
    else:
        print("Language: English")
        print("Voice: " + ("Fish Audio (the JARVIS voice)" if voice == "fish"
                           else "the browser's built-in voice (free)"))
    failed = [c for c in checks if c.status == preflight.STATUS_FAIL]
    if failed:
        print(("還有 {} 項需要處理。" if zh else "{} thing(s) to fix.").format(len(failed)))
        return 1
    print("一切就緒。" if zh else "Ready.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
