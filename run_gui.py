#!/usr/bin/env python3
"""
Точка входа: python run_gui.py — GUI.
python run_gui.py --run-bot — запуск самого бота (используется как отдельный
процесс через QProcess из вкладки «Запуск», а также в собранном .exe/.app,
где нет отдельного python.exe и run_fast.py как файла на диске — тот же
исполняемый файл перезапускает сам себя с этим флагом).
"""
import sys


def main():
    if "--run-bot" in sys.argv:
        import asyncio
        from run_fast import run

        asyncio.run(run())
    else:
        from gui.app import main as gui_main

        gui_main()


if __name__ == "__main__":
    main()
