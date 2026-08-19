"""Вкладка «Аккаунты» — редактор config.json."""
import json
import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .product_picker import ProductPickerDialog
from .recipient_dialog import RecipientDialog
from .widgets import PasswordField, RadioToggle, TagListWidget


def _coerce(pid):
    return int(pid) if str(pid).isdigit() else pid


class AccountCard(QFrame):
    remove_requested = Signal(object)

    def __init__(self, data: dict, parent=None):
        super().__init__(parent)
        self.setObjectName("card")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        top_row = QHBoxLayout()
        self.scout_radio = RadioToggle("Scout (разведчик)")
        top_row.addWidget(self.scout_radio)
        top_row.addStretch(1)
        remove_btn = QPushButton("Удалить")
        remove_btn.setObjectName("linkButton")
        remove_btn.clicked.connect(lambda: self.remove_requested.emit(self))
        top_row.addWidget(remove_btn)
        layout.addLayout(top_row)

        form = QFormLayout()
        form.setSpacing(8)

        self.email_input = QLineEdit(data.get("email", ""))
        self.email_input.setPlaceholderText("email@example.com")
        form.addRow("Email:", self.email_input)

        self.password_field = PasswordField(data.get("password", ""))
        form.addRow("Пароль:", self.password_field)

        self.proxy_input = QLineEdit(data.get("proxy") or "")
        self.proxy_input.setPlaceholderText("http://user:pass@host:port (необязательно)")
        form.addRow("Proxy:", self.proxy_input)

        layout.addLayout(form)

        recipient_row = QHBoxLayout()
        recipient_btn = QPushButton("Получатель и доставка")
        recipient_btn.setObjectName("secondaryButton")
        recipient_btn.clicked.connect(self._open_recipient_dialog)
        recipient_row.addWidget(recipient_btn)
        recipient_row.addStretch(1)
        layout.addLayout(recipient_row)

        products_header = QHBoxLayout()
        products_label = QLabel("Товары (product_ids):")
        products_label.setObjectName("muted")
        products_header.addWidget(products_label)
        products_header.addStretch(1)
        find_btn = QPushButton("Найти на сайте")
        find_btn.setObjectName("linkButton")
        find_btn.clicked.connect(self._open_picker)
        products_header.addWidget(find_btn)
        layout.addLayout(products_header)

        self.tags = TagListWidget()
        self.tags.set_tags(data.get("product_ids", []))
        layout.addWidget(self.tags)

        self.scout_radio.setChecked(bool(data.get("scout", False)))

    def _open_picker(self):
        dlg = ProductPickerDialog(self.tags.tags(), self)
        if dlg.exec() == QDialog.Accepted:
            for pid in dlg.selected_ids():
                self.tags.add_tag(pid)

    def _open_recipient_dialog(self):
        email = self.email_input.text().strip()
        password = self.password_field.text()
        if not email or not password:
            return
        proxy = self.proxy_input.text().strip() or None
        dlg = RecipientDialog(email, password, proxy, self)
        dlg.exec()

    def to_dict(self) -> dict:
        return {
            "email": self.email_input.text().strip(),
            "password": self.password_field.text(),
            "proxy": self.proxy_input.text().strip() or None,
            "scout": self.scout_radio.isChecked(),
            "product_ids": [_coerce(p) for p in self.tags.tags()],
        }


class AccountsTab(QWidget):
    def __init__(self, config_path: str = "config.json", parent=None):
        super().__init__(parent)
        self.config_path = config_path
        self.cards = []
        self.scout_group = QButtonGroup(self)
        self.scout_group.setExclusive(True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(12)

        time_card = QFrame()
        time_card.setObjectName("card")
        time_layout = QHBoxLayout(time_card)
        time_layout.setContentsMargins(16, 12, 16, 12)
        time_title = QLabel("Время дропа (МСК)")
        time_title.setObjectName("sectionTitle")
        time_layout.addWidget(time_title)
        time_layout.addStretch(1)

        self.hour_spin = QSpinBox()
        self.hour_spin.setRange(0, 23)
        self.minute_spin = QSpinBox()
        self.minute_spin.setRange(0, 59)
        self.second_spin = QSpinBox()
        self.second_spin.setRange(0, 59)
        for label_text, spin in (
            ("Час", self.hour_spin),
            ("Мин", self.minute_spin),
            ("Сек", self.second_spin),
        ):
            time_layout.addWidget(QLabel(label_text))
            time_layout.addWidget(spin)

        ntp_note = QLabel("Время сверяется через NTP (интернет), на всех ОС")
        ntp_note.setObjectName("muted")
        time_layout.addWidget(ntp_note)
        outer.addWidget(time_card)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setSpacing(10)
        self.cards_layout.addStretch(1)
        self.scroll.setWidget(self.cards_container)
        outer.addWidget(self.scroll, stretch=1)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("+ Добавить аккаунт")
        add_btn.setObjectName("secondaryButton")
        add_btn.clicked.connect(lambda: self.add_card({}))
        btn_row.addWidget(add_btn)
        btn_row.addStretch(1)
        self.status_label = QLabel("")
        btn_row.addWidget(self.status_label)
        save_btn = QPushButton("Сохранить")
        save_btn.setObjectName("primaryButton")
        save_btn.clicked.connect(self.save)
        btn_row.addWidget(save_btn)
        outer.addLayout(btn_row)

        self.load()

    def add_card(self, data: dict) -> AccountCard:
        card = AccountCard(data)
        card.remove_requested.connect(self.remove_card)
        self.scout_group.addButton(card.scout_radio)
        self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)
        self.cards.append(card)
        return card

    def remove_card(self, card: AccountCard):
        self.scout_group.removeButton(card.scout_radio)
        self.cards_layout.removeWidget(card)
        card.setParent(None)
        card.deleteLater()
        self.cards.remove(card)

    def load(self):
        if not os.path.exists(self.config_path):
            self.hour_spin.setValue(10)
            self.minute_spin.setValue(0)
            self.second_spin.setValue(0)
            return

        with open(self.config_path, encoding="utf-8") as f:
            cfg = json.load(f)

        t = cfg.get("time", {})
        self.hour_spin.setValue(t.get("hour", 10))
        self.minute_spin.setValue(t.get("minute", 0))
        self.second_spin.setValue(t.get("second", 0))

        for acc in cfg.get("accounts", []):
            self.add_card(acc)

    def save(self) -> bool:
        errors = []
        accounts = []
        scout_count = 0

        for card in self.cards:
            data = card.to_dict()
            if not data["email"] or not data["password"]:
                errors.append("у аккаунта пустой email или пароль")
            if data["scout"]:
                scout_count += 1
            accounts.append(data)

        if not accounts:
            errors.append("нет ни одного аккаунта")
        if scout_count != 1:
            errors.append(f"нужен ровно 1 scout-аккаунт, отмечено: {scout_count}")

        if errors:
            self.status_label.setText("Ошибка: " + "; ".join(errors))
            self.status_label.setStyleSheet(f"color: {theme.RED};")
            return False

        cfg = {
            "time": {
                "hour": self.hour_spin.value(),
                "minute": self.minute_spin.value(),
                "second": self.second_spin.value(),
            },
            "accounts": accounts,
        }
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)

        self.status_label.setText("Сохранено")
        self.status_label.setStyleSheet(f"color: {theme.GREEN};")
        return True
