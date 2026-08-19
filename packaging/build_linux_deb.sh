#!/bin/bash
# Сборка .deb для Linux. Запускать из корня проекта на самом Linux
# (PyInstaller не кросс-компилирует — собрать .deb можно только на Linux):
#   bash packaging/build_linux_deb.sh
set -e
cd "$(dirname "$0")/.."

VERSION="1.0.0"
ARCH="amd64"
PKG_DIR="dist/arielbot_${VERSION}_${ARCH}"

python3 -m pip install -r requirements.txt
python3 -m pip install -r packaging/requirements-build.txt
python3 packaging/gen_icons.py

python3 -m PyInstaller --name ArielBot --onedir --windowed \
    --add-data "gui/assets:gui/assets" \
    run_gui.py

rm -rf "$PKG_DIR"
mkdir -p "$PKG_DIR/DEBIAN"
mkdir -p "$PKG_DIR/opt/arielbot"
mkdir -p "$PKG_DIR/usr/bin"
mkdir -p "$PKG_DIR/usr/share/applications"
mkdir -p "$PKG_DIR/usr/share/icons/hicolor/scalable/apps"

cp -r dist/ArielBot/* "$PKG_DIR/opt/arielbot/"
cp gui/assets/app_icon.svg "$PKG_DIR/usr/share/icons/hicolor/scalable/apps/arielbot.svg"

# Оборачивающий скрипт-запускатор: у /opt/arielbot могут не быть прав на
# запись у обычного пользователя (dpkg ставит от root) — при первом запуске
# копируем недостающий config.json в ~/.config/arielbot, если там пусто, и
# запускаем сам бинарник с рабочей директорией там же.
cat > "$PKG_DIR/usr/bin/arielbot" << 'EOF'
#!/bin/bash
DATA_DIR="$HOME/.config/arielbot"
mkdir -p "$DATA_DIR"
if [ ! -f "$DATA_DIR/config.json" ] && [ -f /opt/arielbot/config.example.json ]; then
    cp /opt/arielbot/config.example.json "$DATA_DIR/config.json"
fi
export ARIELBOT_DATA_DIR="$DATA_DIR"
exec /opt/arielbot/ArielBot "$@"
EOF
chmod +x "$PKG_DIR/usr/bin/arielbot"

cp config.example.json "$PKG_DIR/opt/arielbot/config.example.json"

cat > "$PKG_DIR/usr/share/applications/arielbot.desktop" << EOF
[Desktop Entry]
Type=Application
Name=Ariel Bot
Exec=/usr/bin/arielbot
Icon=arielbot
Terminal=false
Categories=Utility;
EOF

cat > "$PKG_DIR/DEBIAN/control" << EOF
Package: arielbot
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Maintainer: local <local@localhost>
Description: Ариель Бот — GUI для быстрой покупки на f-ariel.ru
EOF

dpkg-deb --build --root-owner-group "$PKG_DIR"

echo ""
echo "Готово: ${PKG_DIR}.deb"
echo "Установка: sudo dpkg -i ${PKG_DIR}.deb"
echo "Запуск: arielbot (из меню приложений или из терминала)"
echo "config.json будет создан в ~/.config/arielbot/ при первом запуске"
echo "(скопирован из шаблона) — отредактируй его или через саму вкладку Аккаунты."
