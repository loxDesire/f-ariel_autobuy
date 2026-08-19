"""Вкладка «История» — читает history.jsonl, одна строка = один запуск."""
import json
import os

from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class HistoryTab(QWidget):
    def __init__(self, history_path: str = "history.jsonl", parent=None):
        super().__init__(parent)
        self.history_path = history_path
        self.records = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        header_row = QHBoxLayout()
        title = QLabel("История запусков")
        title.setObjectName("sectionTitle")
        header_row.addWidget(title)
        header_row.addStretch(1)
        refresh_btn = QPushButton("Обновить")
        refresh_btn.setObjectName("secondaryButton")
        refresh_btn.clicked.connect(self.load)
        header_row.addWidget(refresh_btn)
        layout.addLayout(header_row)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Время", "Аккаунтов", "Успешно", "Товары"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.itemSelectionChanged.connect(self._on_selection)
        layout.addWidget(self.table, stretch=1)

        detail_label = QLabel("Детали запуска:")
        detail_label.setObjectName("muted")
        layout.addWidget(detail_label)

        self.detail_view = QTextEdit()
        self.detail_view.setObjectName("logView")
        self.detail_view.setReadOnly(True)
        self.detail_view.setMaximumHeight(160)
        layout.addWidget(self.detail_view)

        self.load()

    def load(self):
        self.records = []
        if os.path.exists(self.history_path):
            with open(self.history_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        self.records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        self.records.reverse()  # новые сверху

        self.table.setRowCount(len(self.records))
        for row, rec in enumerate(self.records):
            products = sorted(
                {
                    str(pid)
                    for a in rec.get("accounts", [])
                    for pid in a.get("product_ids", [])
                }
            )
            self.table.setItem(row, 0, QTableWidgetItem(rec.get("timestamp", "")))
            self.table.setItem(row, 1, QTableWidgetItem(str(len(rec.get("accounts", [])))))
            success = rec.get("success_count", 0)
            ready = rec.get("ready_count", 0)
            self.table.setItem(row, 2, QTableWidgetItem(f"{success}/{ready}"))
            self.table.setItem(row, 3, QTableWidgetItem(", ".join(products)))

        self.detail_view.clear()

    def _on_selection(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        rec = self.records[rows[0].row()]
        lines = [f"Запуск: {rec.get('timestamp', '?')}"]
        for a in rec.get("accounts", []):
            status = "OK" if a.get("order_link") else "—"
            link = f" -> {a['order_link']}" if a.get("order_link") else ""
            scout = " [scout]" if a.get("scout") else ""
            lines.append(
                f"  {a.get('email')}{scout}: products={a.get('product_ids')} {status}{link}"
            )
        self.detail_view.setPlainText("\n".join(lines))
