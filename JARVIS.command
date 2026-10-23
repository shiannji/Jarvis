#!/usr/bin/env bash
# 在 Finder 裡按兩下這個檔案就能啟動 JARVIS（第一次會先自動安裝）。
# Double-click in Finder to start JARVIS (the first run installs it first).
cd "$(dirname "$0")" || exit 1
if [[ ! -x .venv/bin/python || ! -d frontend/node_modules ]]; then
  ./scripts/setup.sh || { read -r -p "安裝沒有完成，按 Enter 關閉視窗…" _; exit 1; }
fi
exec ./scripts/start.sh
