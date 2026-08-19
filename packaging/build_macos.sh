#!/bin/bash
# Сборка macOS .app. Запускать из корня проекта на самой macOS
# (PyInstaller не кросс-компилирует — собрать .app можно только на Mac):
#   bash packaging/build_macos.sh
set -e
cd "$(dirname "$0")/.."

python3 -m pip install -r requirements.txt
python3 -m pip install -r packaging/requirements-build.txt
python3 packaging/gen_icons.py

# --windowed на macOS автоматически заворачивает результат в dist/ArielBot.app
python3 -m PyInstaller --name ArielBot --windowed --onefile \
    --icon packaging/app_icon.icns \
    --add-data "gui/assets:gui/assets" \
    run_gui.py

echo ""
echo "Готово: dist/ArielBot.app"
echo "config.json и history.jsonl будут создаваться рядом с приложением при запуске"
echo "(рядом с самим .app, либо запусти .app один раз, чтобы создать, и следи за"
echo "правами на запись в эту папку)."
