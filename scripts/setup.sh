#!/usr/bin/env bash
# JARVIS 一鍵安裝（macOS）· One-step setup for macOS
#
#   ./scripts/setup.sh          問你幾個問題，然後裝好一切
#   ./scripts/setup.sh --yes    不問問題，全用預設值（中文、免費語音）
#
# 會做的事 / What it does:
#   1. 檢查 Python 3.11+、Node.js 18+、Claude Code（2.1.224 以上且已登入）
#   2. 建立 .venv 並安裝 Python 套件、Playwright 的 Chromium
#   3. 安裝前端套件（frontend/node_modules）
#   4. 產生本機 HTTPS 憑證（cert.pem / key.pem）——前端代理需要它
#   5. 建立 .env：對話語言、你的名字、Fish Audio 金鑰（可略過）
#   6. 跑一次環境檢查（scripts/doctor.py）
#
# 可以重複執行：已經做好的步驟會直接跳過。

set -euo pipefail
cd "$(dirname "$0")/.."

ASSUME_YES=0
[[ "${1:-}" == "--yes" || "${1:-}" == "-y" ]] && ASSUME_YES=1

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; }
die()  { printf '  \033[31m✗\033[0m %s\n' "$*" >&2; exit 1; }

ask() {  # ask "問題" 預設值 → 回答（--yes 時直接用預設值）
  local prompt="$1" default="${2:-}" reply
  if [[ $ASSUME_YES -eq 1 || ! -t 0 ]]; then
    printf '%s\n' "$default"
    return
  fi
  read -r -p "  $prompt " reply || true
  printf '%s\n' "${reply:-$default}"
}

version_ge() {  # version_ge 2.1.230 2.1.224 → true（數字逐段比，不是字串比）
  "$PY" -c 'import sys; v = lambda s: [int(x) for x in s.split(".")]; sys.exit(0 if v(sys.argv[1]) >= v(sys.argv[2]) else 1)' "$1" "$2"
}

# Which copy is running. "It still fails" and "it is still the old file"
# look identical from the outside — they did once, for a whole round trip —
# and a version on the first line tells them apart at a glance.
HAVE_GIT=0
if [[ -d .git ]] && command -v git >/dev/null 2>&1; then
  HAVE_GIT=1   # checked first: on a Mac without the developer tools, a bare `git` pops up an installer
fi
VERSION="不明（不是用 git 下載的副本）"
if [[ $HAVE_GIT -eq 1 ]]; then
  VERSION="$(git log -1 --format='%h，%cd' --date=short 2>/dev/null || echo 不明)"
fi
bold "J.A.R.V.I.S. 安裝程式（版本 ${VERSION}）"
echo

# A newer version on GitHub means a fix this copy does not have yet. Offer it
# before anything else runs: a quiet fetch, never a password prompt, and
# never on a copy with local changes, where a pull could not fast-forward.
if [[ $HAVE_GIT -eq 1 ]] &&
   GIT_TERMINAL_PROMPT=0 git -c http.lowSpeedLimit=1000 -c http.lowSpeedTime=10 \
     fetch --quiet 2>/dev/null; then
  BEHIND="$(git rev-list --count 'HEAD..@{u}' 2>/dev/null || echo 0)"
  if [[ "${BEHIND}" =~ ^[0-9]+$ && "${BEHIND}" -gt 0 ]]; then
    warn "GitHub 上有 ${BEHIND} 個更新還沒下載到這台電腦。"
    if [[ "$(ask '要先更新到最新版本嗎？[Y/n]' Y)" =~ ^[Yy] ]]; then
      if git pull --ff-only --quiet; then
        ok "已更新到 $(git log -1 --format='%h' 2>/dev/null)，重新啟動安裝程式…"
        echo
        # The running bash still holds the old file open; exec the new one.
        exec ./scripts/setup.sh "$@"
      fi
      warn "沒辦法自動更新（可能這份副本有改過的檔案）。請執行 git pull 看看原因。"
    fi
  fi
fi

# ── 0. macOS ────────────────────────────────────────────────────────────────
if [[ "$(uname)" != "Darwin" ]]; then
  warn "這不是 macOS。語音對話與儀表板可以用，但控制終端機、截圖、系統通知"
  warn "都依賴 AppleScript，只有 macOS 才有。"
else
  ok "macOS $(sw_vers -productVersion 2>/dev/null || echo)"
fi

# ── 1. 必要工具 ──────────────────────────────────────────────────────────────
bold "1. 檢查必要工具"

PY=""
for candidate in python3.13 python3.12 python3.11 python3; do
  if command -v "$candidate" >/dev/null 2>&1; then
    if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
      PY="$(command -v "$candidate")"
      break
    fi
  fi
done
[[ -n "$PY" ]] || die "找不到 Python 3.11 以上。請先安裝：brew install python@3.12"
# ${PY}, braced: macOS's bash 3.2 counts the first byte of a full-width
# character as part of a variable's name, so "$PY）" reads a variable called
# PY plus that byte and dies under `set -u`. Every variable next to Chinese
# text is braced (tests/test_shell_scripts.py holds the line).
ok "Python $("$PY" -c 'import platform; print(platform.python_version())')（${PY}）"

command -v node >/dev/null 2>&1 || die "找不到 Node.js。請先安裝：brew install node"
NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]')"
[[ "$NODE_MAJOR" -ge 18 ]] || die "Node.js 需要 18 以上（目前 $(node -v)）。請更新：brew upgrade node"
ok "Node.js $(node -v)"

command -v openssl >/dev/null 2>&1 || die "找不到 openssl（macOS 內建應該有）。"

if ! command -v claude >/dev/null 2>&1; then
  warn "找不到 Claude Code（JARVIS 的大腦，跑在你的 Claude 訂閱上）。"
  if [[ "$(ask '要現在用 npm 安裝嗎？[Y/n]' Y)" =~ ^[Yy] ]]; then
    npm install -g @anthropic-ai/claude-code
  else
    die "請先安裝：npm install -g @anthropic-ai/claude-code，再重新執行本程式。"
  fi
fi
CLAUDE_VERSION="$(claude --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -n1 || true)"
if [[ -n "$CLAUDE_VERSION" ]] && version_ge "$CLAUDE_VERSION" "2.1.224"; then
  ok "Claude Code $CLAUDE_VERSION"
else
  warn "Claude Code 版本是 ${CLAUDE_VERSION:-未知}，需要 2.1.224 以上。"
  warn "更新方式：npm install -g @anthropic-ai/claude-code@latest"
fi
if claude auth status 2>/dev/null | grep -q '"loggedIn": *true'; then
  ok "Claude Code 已登入"
else
  warn "Claude Code 還沒登入：請在終端機執行 claude，依照畫面登入你的 Claude 帳號（Pro/Max 訂閱）。"
  warn "JARVIS 不用 API 金鑰——它的大腦就是你登入的 Claude Code。"
fi
if [[ "$(uname)" == "Darwin" && ! -d "/Applications/Google Chrome.app" ]]; then
  warn "沒看到 Google Chrome。麥克風語音辨識只能在 Chrome 裡用：https://www.google.com/chrome/"
fi

# ── 2. Python 套件 ───────────────────────────────────────────────────────────
bold "2. 安裝 Python 套件"
if [[ ! -x .venv/bin/python ]]; then
  "$PY" -m venv .venv
fi
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -r requirements.txt
ok "Python 套件已安裝（.venv）"
if .venv/bin/python -m playwright install chromium >/dev/null 2>&1; then
  ok "Playwright Chromium（讀網頁功能用）"
else
  warn "Playwright Chromium 沒裝成功；只影響「讀網頁」功能。稍後可手動：.venv/bin/python -m playwright install chromium"
fi

# ── 3. 前端套件 ──────────────────────────────────────────────────────────────
bold "3. 安裝前端套件"
(cd frontend && if [[ -f package-lock.json ]]; then npm ci --silent; else npm install --silent; fi)
ok "frontend/node_modules"

# ── 4. HTTPS 憑證 ────────────────────────────────────────────────────────────
bold "4. 本機 HTTPS 憑證"
if [[ -f cert.pem && -f key.pem ]]; then
  ok "已存在 cert.pem / key.pem"
else
  openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 825 -nodes \
    -subj '/CN=localhost' >/dev/null 2>&1
  ok "已產生 cert.pem / key.pem（前端代理連到後端需要它）"
fi

# ── 5. .env 設定 ─────────────────────────────────────────────────────────────
bold "5. 設定 .env"

set_env() {  # set_env KEY VALUE —— 取代或新增 KEY=VALUE，保留註解
  .venv/bin/python - "$1" "$2" <<'PYEOF'
import pathlib
import sys

key, value = sys.argv[1], sys.argv[2]
path = pathlib.Path(".env")
# UTF-8 always, never the locale's encoding: read as Latin-1, the 0x85 byte
# inside 內 or 腦 decodes to NEL, which splitlines() treats as a line break.
lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
out, found = [], False
for line in lines:
    s = line.strip()
    if s and not s.startswith("#") and "=" in s and s.split("=", 1)[0].strip() == key:
        out.append(f"{key}={value}")
        found = True
    else:
        out.append(line)
if not found:
    out.append(f"{key}={value}")
path.write_text("\n".join(out) + "\n", encoding="utf-8")
PYEOF
}

valid() {  # valid 'regex' "text" —— 整段符合才算
  .venv/bin/python -c 'import re, sys; sys.exit(0 if re.fullmatch(sys.argv[1], sys.argv[2]) else 1)' "$1" "$2"
}

if [[ ! -f .env ]]; then
  cp .env.example .env
  ok "已從 .env.example 建立 .env"

  echo
  echo "  JARVIS 要用什麼語言跟你對話？"
  echo "    1) 繁體中文（台灣）"
  echo "    2) English（原版英國管家）"
  case "$(ask '請選擇 [1]：' 1)" in
    2) set_env JARVIS_LANGUAGE en && ok "對話語言：English" ;;
    *) set_env JARVIS_LANGUAGE zh-TW && ok "對話語言：繁體中文" ;;
  esac

  NAME="$(ask '你的名字（JARVIS 會記得，可直接按 Enter 略過）：' '')"
  if [[ -n "$NAME" ]]; then
    if valid "[\\w .'\\-]{1,64}" "$NAME"; then
      set_env USER_NAME "$NAME"
    else
      warn "名字只能有文字、數字、空格與 . ' -，已略過。之後可在設定頁修改。"
    fi
  fi

  echo
  echo "  Fish Audio 金鑰可讓 JARVIS 用電影裡的聲音說話（付費，https://fish.audio）。"
  echo "  沒有也沒關係：直接按 Enter，JARVIS 會用瀏覽器內建語音（免費）。"
  if [[ $ASSUME_YES -eq 1 || ! -t 0 ]]; then
    FISH=""
  else
    read -r -s -p "  Fish Audio API 金鑰（輸入時不會顯示）： " FISH || true
    echo
  fi
  if [[ -n "${FISH:-}" ]]; then
    if valid '[A-Za-z0-9_\-]{8,200}' "$FISH"; then
      set_env FISH_API_KEY "$FISH"
      ok "已設定 Fish Audio 金鑰"
    else
      warn "金鑰格式看起來不對，已略過。之後可在設定頁輸入。"
    fi
  else
    ok "使用免費的瀏覽器語音（之後隨時可在設定頁加上 Fish Audio 金鑰）"
  fi
else
  ok ".env 已存在，保留你的設定（要重設就刪掉 .env 再執行一次）"
fi

# ── 6. 環境檢查 ──────────────────────────────────────────────────────────────
bold "6. 環境檢查"
.venv/bin/python scripts/doctor.py || true

echo
bold "完成！啟動 JARVIS："
echo "    ./scripts/start.sh"
echo
echo "  然後在 Google Chrome 打開 http://localhost:5173 ，點一下畫面，就可以開口說話了。"
echo "  之後想檢查環境，隨時可以執行：python3 scripts/doctor.py"
