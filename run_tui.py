#!/usr/bin/env python3
"""
Ариель Бот — терминальный интерфейс (TUI).

  python run_tui.py

Бот (run_fast.py) запускается отдельным процессом с экрана «Запуск».
На сервере удобно запускать внутри tmux, чтобы TUI и бот жили после ssh.
"""
import os
import sys

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJECT_DIR)  # config.json / history.jsonl лежат рядом

# Внутри tmux переменная COLORTERM часто не доходит — без неё TUI считает,
# что доступно только 256 цветов, и палитра выглядит грязно. Сам tmux должен
# уметь truecolor: в ~/.tmux.conf  set -as terminal-features ",*:RGB"
if os.environ.get("TMUX") and not os.environ.get("COLORTERM"):
    os.environ["COLORTERM"] = "truecolor"
sys.path.insert(0, PROJECT_DIR)

from tui.app import main  # noqa: E402

if __name__ == "__main__":
    main(PROJECT_DIR)
