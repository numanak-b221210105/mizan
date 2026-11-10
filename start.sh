#!/usr/bin/env bash
# Mizan - macOS / Linux icin tek komutla kurulum ve calistirma
set -euo pipefail
cd "$(dirname "$0")"
PY=$(command -v python3 || command -v python) || { echo "Python 3.11+ gerekli"; exit 1; }
if [ ! -d .venv ]; then
  echo "[1/2] Sanal ortam olusturuluyor..."
  "$PY" -m venv .venv
  echo "[2/2] Paketler yukleniyor..."
  .venv/bin/python -m pip install -q --upgrade pip
  .venv/bin/python -m pip install -q -e ".[dev]"
fi
[ -f .env ] || cp .env.example .env
echo -e "\n  Mizan calisiyor:  http://localhost:8000\n  Durdurmak icin:   Ctrl+C\n"
exec .venv/bin/python -m uvicorn mizan.api:app --env-file .env
