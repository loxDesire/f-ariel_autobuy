"""Диалог проверки/выбора/создания получателя и способа доставки аккаунта."""
import asyncio
import webbrowser

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from . import recipient_finder as rf
from . import theme
from .widgets import RadioToggle


class _Worker(QThread):
    done = Signal(dict)

    def __init__(self, coro_factory, parent=None):
        super().__init__(parent)
        self._coro_factory = coro_factory

    def run(self):
        result = asyncio.run(self._coro_factory())
        self.done.emit(result)


class RecipientDialog(QDialog):
    # Куда открыть браузер для добавления нового способа доставки — на сайте
    # нет API для этого, только форма в личном кабинете.
    DELIVERY_SETUP_URL = "https://f-ariel.ru/profile/info/?add_recipient"

    def __init__(self, email: str, password: str, proxy: str, parent=None):
        super().__init__(parent)
        self.email = email
        self.password = password
        self.proxy = proxy
        self.setWindowTitle(f"Получатель и доставка — {email}")
        self.resize(460, 600)
        self._worker = None
        self._recipients = []
        self._delivery = []

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        self.status_label = QLabel("Загрузка...")
        layout.addWidget(self.status_label)

        recipient_title = QLabel("Получатель")
        recipient_title.setObjectName("sectionTitle")
        layout.addWidget(recipient_title)

        self.recipient_group = QButtonGroup(self)
        self.recipient_list_layout = QVBoxLayout()
        self.recipient_list_layout.setSpacing(4)
        layout.addLayout(self.recipient_list_layout)

        new_row = QHBoxLayout()
        self.new_name = QLineEdit()
        self.new_name.setPlaceholderText("Имя")
        self.new_last_name = QLineEdit()
        self.new_last_name.setPlaceholderText("Фамилия")
        self.new_phone = QLineEdit()
        self.new_phone.setPlaceholderText("+7 (___) ___-__-__")
        new_row.addWidget(self.new_name)
        new_row.addWidget(self.new_last_name)
        new_row.addWidget(self.new_phone)
        layout.addLayout(new_row)

        recipient_btn_row = QHBoxLayout()
        create_btn = QPushButton("+ Создать получателя")
        create_btn.setObjectName("secondaryButton")
        create_btn.clicked.connect(self._create_recipient)
        apply_recipient_btn = QPushButton("Сделать выбранным")
        apply_recipient_btn.setObjectName("secondaryButton")
        apply_recipient_btn.clicked.connect(self._apply_recipient)
        recipient_btn_row.addWidget(create_btn)
        recipient_btn_row.addWidget(apply_recipient_btn)
        layout.addLayout(recipient_btn_row)

        delivery_title = QLabel("Способ доставки")
        delivery_title.setObjectName("sectionTitle")
        layout.addWidget(delivery_title)

        self.delivery_group = QButtonGroup(self)
        self.delivery_list_layout = QVBoxLayout()
        self.delivery_list_layout.setSpacing(4)
        layout.addLayout(self.delivery_list_layout)

        delivery_btn_row = QHBoxLayout()
        apply_delivery_btn = QPushButton("Сделать выбранным")
        apply_delivery_btn.setObjectName("secondaryButton")
        apply_delivery_btn.clicked.connect(self._apply_delivery)
        add_delivery_btn = QPushButton("+ Добавить (в браузере)")
        add_delivery_btn.setObjectName("secondaryButton")
        add_delivery_btn.clicked.connect(self._open_browser)
        delivery_btn_row.addWidget(apply_delivery_btn)
        delivery_btn_row.addWidget(add_delivery_btn)
        layout.addLayout(delivery_btn_row)

        layout.addStretch(1)

        bottom_row = QHBoxLayout()
        refresh_btn = QPushButton("Обновить")
        refresh_btn.setObjectName("secondaryButton")
        refresh_btn.clicked.connect(self._refresh)
        bottom_row.addWidget(refresh_btn)
        bottom_row.addStretch(1)
        close_btn = QPushButton("Закрыть")
        close_btn.setObjectName("primaryButton")
        close_btn.clicked.connect(self.accept)
        bottom_row.addWidget(close_btn)
        layout.addLayout(bottom_row)

        self._refresh()

    def _run(self, coro_factory):
        self.status_label.setText("Выполняется запрос...")
        self.status_label.setStyleSheet(f"color: {theme.TEXT_MUTED};")
        self._worker = _Worker(coro_factory)
        self._worker.done.connect(self._on_result)
        self._worker.start()

    def _refresh(self):
        self._run(lambda: rf.check_account(self.email, self.password, self.proxy))

    def _create_recipient(self):
        name = self.new_name.text().strip()
        last_name = self.new_last_name.text().strip()
        phone = self.new_phone.text().strip()
        if not (name and last_name and phone):
            self.status_label.setText("Заполните имя, фамилию и телефон")
            self.status_label.setStyleSheet(f"color: {theme.RED};")
            return
        self._run(
            lambda: rf.create_recipient(self.email, self.password, self.proxy, name, last_name, phone)
        )

    def _apply_recipient(self):
        checked = self.recipient_group.checkedButton()
        if checked is None:
            return
        identifier = checked.property("identifier")
        self._run(lambda: rf.select_recipient(self.email, self.password, self.proxy, identifier))

    def _apply_delivery(self):
        checked = self.delivery_group.checkedButton()
        if checked is None:
            return
        delivery_type = checked.property("delivery_type")
        delivery_identifier = checked.property("delivery_identifier")
        self._run(
            lambda: rf.select_delivery(
                self.email, self.password, self.proxy, delivery_type, delivery_identifier
            )
        )

    def _open_browser(self):
        webbrowser.open(self.DELIVERY_SETUP_URL)

    def _on_result(self, result: dict):
        if not result.get("ok"):
            self.status_label.setText(f"Ошибка: {result.get('error')}")
            self.status_label.setStyleSheet(f"color: {theme.RED};")
            return
        self.status_label.setText("Готово")
        self.status_label.setStyleSheet(f"color: {theme.GREEN};")
        self._recipients = result.get("recipients", [])
        self._delivery = result.get("delivery", [])
        self._rebuild_recipient_list()
        self._rebuild_delivery_list()

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

    def _rebuild_recipient_list(self):
        self._clear_layout(self.recipient_list_layout)
        for btn in list(self.recipient_group.buttons()):
            self.recipient_group.removeButton(btn)

        if not self._recipients:
            warn = QLabel("⚠ Получатель не создан")
            warn.setObjectName("badgeError")
            self.recipient_list_layout.addWidget(warn)
            return

        if not any(r.get("selected") for r in self._recipients):
            warn = QLabel("⚠ Получатель не выбран по умолчанию")
            warn.setObjectName("badgeError")
            self.recipient_list_layout.addWidget(warn)

        for r in self._recipients:
            label = f'{r.get("name", "")} {r.get("last_name", "")} — {r.get("phone_number", "")}'
            radio = RadioToggle(label)
            radio.setProperty("identifier", r.get("identifier"))
            radio.setChecked(bool(r.get("selected")))
            self.recipient_group.addButton(radio)
            self.recipient_list_layout.addWidget(radio)

    def _rebuild_delivery_list(self):
        self._clear_layout(self.delivery_list_layout)
        for btn in list(self.delivery_group.buttons()):
            self.delivery_group.removeButton(btn)

        if not self._delivery:
            warn = QLabel("⚠ Способ доставки не настроен")
            warn.setObjectName("badgeError")
            self.delivery_list_layout.addWidget(warn)
            return

        if not any(d.get("selected") for d in self._delivery):
            warn = QLabel("⚠ Способ доставки не выбран по умолчанию")
            warn.setObjectName("badgeError")
            self.delivery_list_layout.addWidget(warn)

        for d in self._delivery:
            address = d.get("address") or ""
            label = f'{d.get("name", "")} — {address}' if address else d.get("name", "")
            radio = RadioToggle(label)
            radio.setProperty("delivery_type", d.get("type"))
            radio.setProperty("delivery_identifier", d.get("identifier"))
            radio.setChecked(bool(d.get("selected")))
            self.delivery_group.addButton(radio)
            self.delivery_list_layout.addWidget(radio)

    def closeEvent(self, event):
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait(11000)
        super().closeEvent(event)
