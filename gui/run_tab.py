"""Вкладка «Запуск» — Start/Stop бота через QProcess + живой лог."""
import os
import sys

from PySide6.QtCore import QProcess, QProcessEnvironment
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from . import theme

OK_MARKERS = ("OK ", "++", "ADDED")
FAIL_MARKERS = ("FAIL", "ERR", "Timeout", "config error", "Fatal", "не залогинился")


class RunTab(QWidget):
    def __init__(self, cwd: str = None, parent=None):
        super().__init__(parent)
        self.cwd = cwd
        self.process = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        header_row = QHBoxLayout()
        title = QLabel("Запуск бота")
        title.setObjectName("sectionTitle")
        header_row.addWidget(title)
        header_row.addStretch(1)
        self.status_badge = QLabel("Ожидание")
        self.status_badge.setObjectName("badge")
        header_row.addWidget(self.status_badge)
        layout.addLayout(header_row)

        self.log_view = QTextEdit()
        self.log_view.setObjectName("logView")
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view, stretch=1)

        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.start_btn.setObjectName("primaryButton")
        self.start_btn.clicked.connect(self.start)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setObjectName("dangerButton")
        self.stop_btn.clicked.connect(self.stop)
        self.stop_btn.setEnabled(False)
        clear_btn = QPushButton("Очистить лог")
        clear_btn.setObjectName("secondaryButton")
        clear_btn.clicked.connect(self.log_view.clear)
        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.stop_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(clear_btn)
        layout.addLayout(btn_row)

    def _program_and_args(self):
        """
        В собранном .exe/.app (PyInstaller) нет отдельного python.exe и
        run_fast.py как файла на диске — тот же исполняемый файл перезапускает
        сам себя с флагом --run-bot. При запуске из исходников — обычный
        python run_gui.py --run-bot.
        """
        if getattr(sys, "frozen", False):
            return sys.executable, ["--run-bot"]
        run_gui_path = os.path.join(self.cwd or os.getcwd(), "run_gui.py")
        return sys.executable, [run_gui_path, "--run-bot"]

    def start(self):
        if self.process is not None:
            return
        self.log_view.clear()
        self.process = QProcess(self)
        if self.cwd:
            self.process.setWorkingDirectory(self.cwd)
        self.process.setProcessChannelMode(QProcess.MergedChannels)

        # PYTHONUNBUFFERED: без буферизации stdout — иначе лог не льётся в
        # реальном времени (особенно при долгом ожидании до дропа).
        # PYTHONUTF8: форсирует UTF-8 для stdout/stderr — без этого Python в
        # дочернем процессе (без реальной консоли) кодирует по системной
        # кодовой странице, а не UTF-8, и кириллица превращается в кракозябры.
        # Через переменные окружения (а не -u/-X utf8) — работает одинаково
        # что при запуске из исходников, что в собранном .exe/.app.
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONUNBUFFERED", "1")
        env.insert("PYTHONUTF8", "1")
        self.process.setProcessEnvironment(env)

        self.process.readyReadStandardOutput.connect(self._on_output)
        self.process.finished.connect(self._on_finished)
        program, args = self._program_and_args()
        self.process.start(program, args)
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_badge.setText("Выполняется")

    def stop(self):
        if self.process is None:
            return
        self.process.terminate()
        if not self.process.waitForFinished(2000):
            self.process.kill()

    def _on_output(self):
        if self.process is None:
            return
        data = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
        for line in data.splitlines():
            self._append_line(line)

    def _append_line(self, line: str):
        color = theme.TEXT_MUTED
        if any(m in line for m in FAIL_MARKERS):
            color = theme.RED
        elif any(m in line for m in OK_MARKERS):
            color = theme.GREEN
        safe = (
            line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        ) or "&nbsp;"
        self.log_view.append(f'<span style="color:{color};">{safe}</span>')

    def _on_finished(self, exit_code, exit_status):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_badge.setText("Завершено")
        self.process = None
