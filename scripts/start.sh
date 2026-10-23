#!/usr/bin/env bash
# 啟動 JARVIS · Start JARVIS
#
#   ./scripts/start.sh
#
# 一次啟動兩個程式：後端（server.py，https://localhost:8340）與前端
# （Vite，http://localhost:5173），等兩邊都就緒後用 Google Chrome 打開。
# 按 Ctrl+C 會把兩個一起關掉。
#
# 前端固定用 5173 埠（--strictPort）：Chrome 的麥克風權限是「連同連接埠」
# 一起記的，Vite 若悄悄換到 5174，麥克風會默默失效。所以 5173 被占用時
# 這裡會直接告訴你，而不是換一個埠。

set -euo pipefail
cd "$(dirname "$0")/.."

say()  { printf '\033[1m%s\033[0m\n' "$*"; }
die()  { printf '\033[31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

[[ -x .venv/bin/python ]]     || die "還沒安裝。請先執行 ./scripts/setup.sh"
[[ -d frontend/node_modules ]] || die "前端套件還沒裝。請先執行 ./scripts/setup.sh"
[[ -f cert.pem && -f key.pem ]] || die "缺少 cert.pem / key.pem。請先執行 ./scripts/setup.sh"

port_busy() { lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; }
port_busy 8340 && die "8340 埠已被占用（可能 JARVIS 已經在跑了）。先關掉它再啟動。"
port_busy 5173 && die "5173 埠已被占用。麥克風權限綁定在這個埠，請先關掉占用它的程式。"

mkdir -p data
LOG_BACK="data/server.log"
LOG_FRONT="data/vite.log"

BACK_PID=""
FRONT_PID=""
cleanup() {
  trap - INT TERM EXIT
  echo
  say "正在關閉 JARVIS…"
  [[ -n "$FRONT_PID" ]] && kill "$FRONT_PID" 2>/dev/null || true
  [[ -n "$BACK_PID" ]] && kill "$BACK_PID" 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup INT TERM EXIT

say "啟動後端（server.py）… 紀錄：$LOG_BACK"
.venv/bin/python server.py --host 127.0.0.1 >"$LOG_BACK" 2>&1 &
BACK_PID=$!

say "啟動前端（Vite）… 紀錄：$LOG_FRONT"
(cd frontend && exec npx vite --port 5173 --strictPort) >"$LOG_FRONT" 2>&1 &
FRONT_PID=$!

wait_for() {  # wait_for 網址 秒數
  local url="$1" seconds="$2" i
  for ((i = 0; i < seconds * 4; i++)); do
    if curl -sk -o /dev/null "$url"; then
      return 0
    fi
    if ! kill -0 "$BACK_PID" 2>/dev/null || ! kill -0 "$FRONT_PID" 2>/dev/null; then
      return 1
    fi
    sleep 0.25
  done
  return 1
}

if ! wait_for "https://localhost:8340/api/health" 30; then
  echo "----- $LOG_BACK -----"; tail -n 30 "$LOG_BACK" || true
  die "後端沒有啟動成功，請看上面的紀錄。"
fi
if ! wait_for "http://localhost:5173/" 30; then
  echo "----- $LOG_FRONT -----"; tail -n 30 "$LOG_FRONT" || true
  die "前端沒有啟動成功，請看上面的紀錄。"
fi

URL="http://localhost:5173"
say "JARVIS 已上線：$URL   （儀表板：$URL/dashboard.html）"
if [[ "$(uname)" == "Darwin" ]]; then
  if [[ -d "/Applications/Google Chrome.app" ]]; then
    open -a "Google Chrome" "$URL"
  else
    open "$URL"
    echo "  注意：麥克風語音辨識只能在 Google Chrome 裡使用。"
  fi
fi
echo "  在 Chrome 裡點一下畫面以啟用聲音，然後直接開口說話。按 Ctrl+C 結束。"

# Follow the server log so what JARVIS hears and says is visible here.
tail -n 0 -f "$LOG_BACK" &
TAIL_PID=$!
wait "$BACK_PID" || true
kill "$TAIL_PID" 2>/dev/null || true
