"""Диалог выбора товаров: подтягивает список с сайта + позволяет вписать ID вручную."""
import asyncio

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .product_finder import fetch_available_products


class FetchWorker(QThread):
    finished_ok = Signal(list)
    finished_error = Signal(str)

    def run(self):
        try:
            products = asyncio.run(fetch_available_products())
            self.finished_ok.emit(products)
        except Exception as e:
            self.finished_error.emit(f"{type(e).__name__}: {e}")


class ProductPickerDialog(QDialog):
    def __init__(self, current_ids, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Найти товары на сайте")
        self.resize(440, 480)
        self.current_ids = {str(i) for i in current_ids}
        self._checkboxes = {}
        self._worker = None

        layout = QVBoxLayout(self)

        self.status_label = QLabel("Загрузка списка товаров...")
        self.status_label.setObjectName("muted")
        layout.addWidget(self.status_label)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.addStretch(1)
        self.scroll.setWidget(self.list_container)
        layout.addWidget(self.scroll, stretch=1)

        manual_row = QHBoxLayout()
        self.manual_input = QLineEdit()
        self.manual_input.setPlaceholderText("Добавить ID вручную (например 415)")
        self.manual_input.returnPressed.connect(self._add_manual)
        manual_add_btn = QPushButton("Добавить")
        manual_add_btn.setObjectName("secondaryButton")
        manual_add_btn.clicked.connect(self._add_manual)
        manual_row.addWidget(self.manual_input)
        manual_row.addWidget(manual_add_btn)
        layout.addLayout(manual_row)

        btn_row = QHBoxLayout()
        refresh_btn = QPushButton("Обновить список")
        refresh_btn.setObjectName("secondaryButton")
        refresh_btn.clicked.connect(self._start_fetch)
        btn_row.addWidget(refresh_btn)
        btn_row.addStretch(1)
        cancel_btn = QPushButton("Отмена")
        cancel_btn.setObjectName("secondaryButton")
        cancel_btn.clicked.connect(self.reject)
        apply_btn = QPushButton("Применить")
        apply_btn.setObjectName("primaryButton")
        apply_btn.clicked.connect(self.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(apply_btn)
        layout.addLayout(btn_row)

        self._start_fetch()

    def _start_fetch(self):
        self.status_label.setText("Загрузка списка товаров...")
        self._worker = FetchWorker()
        self._worker.finished_ok.connect(self._on_fetch_ok)
        self._worker.finished_error.connect(self._on_fetch_error)
        self._worker.start()

    def _on_fetch_ok(self, products):
        for pid, cb in list(self._checkboxes.items()):
            if not cb.text().endswith("(вручную)"):
                cb.setParent(None)
                del self._checkboxes[pid]

        if not products:
            self.status_label.setText("На странице не найдено товаров (карточки не распознаны).")
        else:
            self.status_label.setText(f"Найдено товаров: {len(products)}")

        for p in products:
            pid = p["id"]
            if pid in self._checkboxes:
                continue
            label = f'{pid} — {p["name"]}' if p["name"] else pid
            cb = QCheckBox(label)
            cb.setChecked(pid in self.current_ids)
            self._checkboxes[pid] = cb
            self.list_layout.insertWidget(self.list_layout.count() - 1, cb)

    def _on_fetch_error(self, message):
        self.status_label.setText(f"Не удалось загрузить список: {message}")

    def _add_manual(self):
        text = self.manual_input.text().strip()
        if not text:
            return
        if text in self._checkboxes:
            self._checkboxes[text].setChecked(True)
        else:
            cb = QCheckBox(f"{text} (вручную)")
            cb.setChecked(True)
            self._checkboxes[text] = cb
            self.list_layout.insertWidget(self.list_layout.count() - 1, cb)
        self.manual_input.clear()

    def selected_ids(self) -> list:
        return [pid for pid, cb in self._checkboxes.items() if cb.isChecked()]

    def closeEvent(self, event):
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait(11000)
        super().closeEvent(event)
