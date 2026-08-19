"""Главное окно GUI: вкладки Аккаунты / Запуск / История."""
import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

from . import theme
from .accounts_tab import AccountsTab
from .history_tab import HistoryTab
from .run_tab import RunTab

_ICON_PATH = os.path.join(os.path.dirname(__file__), "assets", "app_icon.svg")


class MainWindow(QMainWindow):
    def __init__(self, project_dir: str):
        super().__init__()
        self.setWindowTitle("Ариель Бот")
        if os.path.exists(_ICON_PATH):
            self.setWindowIcon(QIcon(_ICON_PATH))
        self.resize(940, 720)
        self.setMinimumSize(640, 480)

        config_path = os.path.join(project_dir, "config.json")
        history_path = os.path.join(project_dir, "history.jsonl")

        self.accounts_tab = AccountsTab(config_path)
        self.run_tab = RunTab(cwd=project_dir)
        self.history_tab = HistoryTab(history_path)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.accounts_tab, "Аккаунты")
        self.tabs.addTab(self.run_tab, "Запуск")
        self.tabs.addTab(self.history_tab, "История")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.setCentralWidget(self.tabs)

    def _on_tab_changed(self, index: int):
        if self.tabs.widget(index) is self.history_tab:
            self.history_tab.load()


def main():
    # На Windows иконка в панели задач берётся не из setWindowIcon(), а из
    # ресурсов python.exe, если явно не задать свой AppUserModelID — иначе
    # там будет стандартная иконка Python, а не наша.
    if sys.platform == "win32":
        import ctypes
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("arielbot.gui.1")
        except Exception:
            pass

    # На Windows с дробным масштабированием (125%/150%) политика округления
    # DPI по умолчанию может давать нечёткий рендер — не зависит от того,
    # нативная рамка окна или нет, полезно оставить в любом случае.
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    if getattr(sys, "frozen", False):
        # В собранном .exe/.app __file__ указывает на временную распакованную
        # папку (_MEIPASS), а не туда, где реально лежит исполняемый файл —
        # config.json/history.jsonl должны жить рядом с ним, а не в temp.
        # ARIELBOT_DATA_DIR — явный переопределитель (использует, например,
        # обёртка /usr/bin/arielbot из .deb-пакета, где сам бинарник лежит в
        # /opt/arielbot без прав на запись у обычного пользователя).
        env_dir = os.environ.get("ARIELBOT_DATA_DIR")
        if env_dir:
            project_dir = env_dir
        elif sys.platform == "darwin" and ".app/Contents/MacOS" in sys.executable:
            # sys.executable = .../ArielBot.app/Contents/MacOS/ArielBot —
            # нужна папка РЯДОМ с самим .app, а не внутри его содержимого.
            bundle_dir = sys.executable
            for _ in range(3):
                bundle_dir = os.path.dirname(bundle_dir)
            project_dir = os.path.dirname(bundle_dir)
        else:
            project_dir = os.path.dirname(sys.executable)
    else:
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    app = QApplication(sys.argv)
    app.setStyleSheet(theme.QSS)

    if os.path.exists(_ICON_PATH):
        app.setWindowIcon(QIcon(_ICON_PATH))

    window = MainWindow(project_dir)
    window.show()
    sys.exit(app.exec())
