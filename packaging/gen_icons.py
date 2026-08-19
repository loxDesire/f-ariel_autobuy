"""Генерирует иконки для сборки из gui/assets/app_icon.svg: .ico (Windows) и .icns (macOS)."""
import os
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SVG_PATH = os.path.join(ROOT, "gui", "assets", "app_icon.svg")
OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    app = QApplication(sys.argv)
    icon = QIcon(SVG_PATH)

    ico_path = os.path.join(OUT_DIR, "app_icon.ico")
    icns_path = os.path.join(OUT_DIR, "app_icon.icns")

    icon.pixmap(256, 256).save(ico_path, "ICO")
    print(f"saved {ico_path}")

    icon.pixmap(512, 512).save(icns_path, "ICNS")
    print(f"saved {icns_path}")


if __name__ == "__main__":
    main()
