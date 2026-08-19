# Сборка Windows .exe. Запускать из корня проекта:
#   powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

python -m pip install -r requirements.txt
python -m pip install -r packaging\requirements-build.txt
python packaging\gen_icons.py

python -m PyInstaller --name ArielBot --windowed --onefile `
    --icon packaging\app_icon.ico `
    --add-data "gui/assets;gui/assets" `
    run_gui.py

Write-Output ""
Write-Output "Готово: dist\ArielBot.exe"
Write-Output "config.json и history.jsonl будут создаваться рядом с exe при запуске."
