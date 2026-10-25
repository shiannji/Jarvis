"""Check this machine is ready to run JARVIS, and say what to fix.

    python3 scripts/doctor.py

Whichever Python runs it — mise's, Homebrew's, Apple's — it hands itself over
to the project's own interpreter, `.venv/bin/python` (made by
scripts/setup.sh), when there is one: the packages JARVIS needs live there
and nowhere else. Run with a global Python it once died with
`No module named 'httpx'` before it could say anything useful.

It reports two things. What is installed — the virtual environment and its
packages, the frontend's, the certificates, `.env` — and then the server's
own first-run checks (`preflight.run_checks`, the same ones `server.py` runs
at startup and speaks aloud when something fails), so what this reports and
what JARVIS later complains about can never disagree. Nothing here changes
anything: it reads, and it prints. It never ends in a traceback.
"""
from __future__ import annotations

import asyncio
import importlib.util
import os
import platform
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

# Set before handing over, so a project interpreter that is somehow not the
# one that ends up running can never bounce us back and forth.
REEXEC_FLAG = "JARVIS_DOCTOR_REEXEC"

# What server.py cannot start without (requirements.txt).
REQUIRED_PACKAGES = ("fastapi", "uvicorn", "httpx", "pydantic", "websockets", "playwright")

OK, WARN, FAIL = "ok", "warn", "fail"
_MARKS = {OK: "✅", WARN: "⚠️ ", FAIL: "❌"}


def venv_python(repo: Path = REPO) -> Path:
    return repo / ".venv" / "bin" / "python"


def in_project_venv(prefix: str, repo: Path = REPO) -> bool:
    try:
        return Path(prefix).resolve() == (repo / ".venv").resolve()
    except OSError:
        return False


def should_hand_over(prefix: str, environ, repo: Path = REPO) -> bool:
    """Whether to re-run under the project's interpreter: it exists, it is
    not the one running, and we have not already handed over once."""
    return (environ.get(REEXEC_FLAG) != "1"
            and venv_python(repo).exists()
            and not in_project_venv(prefix, repo))


def _hand_over_to_project_python() -> None:
    if not should_hand_over(sys.prefix, os.environ):
        return
    target = str(venv_python())
    os.environ[REEXEC_FLAG] = "1"
    try:
        os.execv(target, [target, str(Path(__file__).resolve()), *sys.argv[1:]])
    except OSError:
        pass  # a broken .venv: carry on here, and the report below says so


def _say(zh: bool, en: str, mandarin: str) -> str:
    return mandarin if zh else en


def install_report(zh: bool, repo: Path = REPO, prefix: str | None = None,
                   find_spec=importlib.util.find_spec) -> list[tuple[str, str, str]]:
    """(status, what, remedy) for each thing scripts/setup.sh installs."""
    setup = _say(zh, "Run ./scripts/setup.sh", "請執行 ./scripts/setup.sh")
    prefix = sys.prefix if prefix is None else prefix
    out: list[tuple[str, str, str]] = []

    version = platform.python_version()
    if sys.version_info < (3, 11):
        out.append((FAIL, f"Python {version}",
                    _say(zh, "JARVIS needs Python 3.11 or newer — brew install python@3.12, then ./scripts/setup.sh",
                         "JARVIS 需要 Python 3.11 以上——brew install python@3.12 之後執行 ./scripts/setup.sh")))
    elif in_project_venv(prefix, repo):
        out.append((OK, _say(zh, f"Python {version}, the project's .venv",
                             f"Python {version}（專案的 .venv）"), ""))
    elif (repo / ".venv").is_dir():
        # There is one, and we are not running in it: the hand-over failed,
        # usually because the Python it was made from has gone (a mise or
        # Homebrew upgrade). Rebuilding it is the whole fix.
        out.append((FAIL, _say(zh, f"Python {version}; the project's .venv exists but cannot run",
                               f"Python {version}；專案的 .venv 存在但無法執行（可能壞了）"),
                    _say(zh, "rm -rf .venv, then ./scripts/setup.sh",
                         "刪掉它再重裝：rm -rf .venv 之後執行 ./scripts/setup.sh")))
    else:
        out.append((FAIL, _say(zh, f"Python {version}; the project's .venv has not been made yet",
                               f"Python {version}；專案的 .venv 還沒建立"), setup))

    missing = [name for name in REQUIRED_PACKAGES if find_spec(name) is None]
    if missing:
        out.append((FAIL, _say(zh, "Missing Python packages: ", "缺少 Python 套件：") + ", ".join(missing),
                    setup))
    else:
        out.append((OK, _say(zh, "Python packages installed", "Python 套件都裝好了"), ""))

    if (repo / "frontend" / "node_modules").is_dir():
        out.append((OK, _say(zh, "Frontend packages installed", "前端套件都裝好了"), ""))
    else:
        out.append((FAIL, _say(zh, "Frontend packages are not installed", "前端套件還沒安裝"), setup))

    if (repo / "cert.pem").is_file() and (repo / "key.pem").is_file():
        out.append((OK, _say(zh, "HTTPS certificates present", "HTTPS 憑證已產生"), ""))
    else:
        out.append((FAIL, _say(zh, "No cert.pem / key.pem — the frontend cannot reach the server without them",
                               "沒有 cert.pem / key.pem——前端連不到後端"), setup))

    if (repo / ".env").is_file():
        out.append((OK, _say(zh, ".env present", ".env 設定檔已建立"), ""))
    else:
        out.append((WARN, _say(zh, "No .env — the defaults will be used", "沒有 .env——會用預設值"), setup))
    return out


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


async def main() -> int:
    # A terminal that cannot show Chinese gets "?" in their place, not a
    # traceback: a report with question marks in it is still a report.
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass
    _load_dotenv()
    try:
        import i18n
        zh = i18n.is_zh()
    except Exception:                       # an interpreter too old to read it
        zh = os.getenv("JARVIS_LANGUAGE", "").lower().startswith("zh")

    print(_say(zh, "JARVIS environment check", "JARVIS 環境檢查"))
    print("-" * 40)
    print(_say(zh, "Installed:", "安裝狀態："))
    failed = 0
    for status, what, remedy in install_report(zh):
        print(f"{_MARKS[status]} {what}")
        if remedy:
            print(f"     → {remedy}")
        failed += status == FAIL

    print("-" * 40)
    print(_say(zh, "This machine:", "這台電腦："))
    try:
        import preflight
        import tts
        checks = await preflight.run_checks()
    except Exception as e:
        print(_say(zh, f"❌ The checks could not run here ({e}).",
                   f"❌ 這裡沒辦法執行完整檢查（{e}）。"))
        print("     → " + _say(zh, "Run ./scripts/setup.sh", "請執行 ./scripts/setup.sh"))
        return 1
    for c in checks:
        print(f"{_MARKS.get(c.status, '•')} {c.name}: {c.message}")
        if c.status != preflight.STATUS_OK and c.remedy:
            print(f"     → {c.remedy}")
        failed += c.status == preflight.STATUS_FAIL

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
    if failed:
        print(_say(zh, f"{failed} thing(s) to fix.", f"還有 {failed} 項需要處理。"))
        return 1
    print(_say(zh, "Ready. Start it with ./scripts/start.sh", "一切就緒。用 ./scripts/start.sh 啟動。"))
    return 0


if __name__ == "__main__":
    _hand_over_to_project_python()
    sys.exit(asyncio.run(main()))
