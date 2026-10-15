#!/usr/bin/env bash
# Создаёт venv/ рядом со скриптом и ставит зависимости из requirements.txt.
# venv в git не попадает (.gitignore) — на новой машине просто: bash setup.sh
set -e
cd "$(dirname "$0")"
python3 -m venv venv
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt
[ -f config.json ] || cp config.example.json config.json
[ -f .env ] || cp .env.example .env
echo
echo "Готово. Запуск:"
echo "  venv/bin/python run_tui.py          # интерфейс"
echo "  venv/bin/python run_fast.py now     # бот без интерфейса (now | time)"
