"""Экран «Аккаунты»: список, редактирование, получатель и доставка."""
from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Label, RadioButton, RadioSet

from core import recipient_finder as rf
from ..config_store import coerce_pid
from ..theme import CORAL
from ..modals import ConfirmModal, FormModal

CDEK_SETUP_URL = "https://f-ariel.ru/profile/info/?add_recipient"


def account_form(acc: dict = None) -> list:
    acc = acc or {}
    return [
        ("email", "Email", acc.get("email", ""), False),
        ("password", "Пароль", acc.get("password", ""), True),
        ("proxy", "Прокси (необязательно), http://user:pass@host:port", acc.get("proxy") or "", False),
        ("product_ids", "Товары (id через запятую)",
         ", ".join(str(p) for p in acc.get("product_ids", [])), False),
    ]


def form_to_account(data: dict, old: dict = None) -> dict:
    acc = dict(old or {})  # незнакомые поля аккаунта сохраняем
    acc["email"] = data["email"]
    acc["password"] = data["password"]
    acc["proxy"] = data["proxy"] or None
    acc["product_ids"] = [coerce_pid(p) for p in data["product_ids"].replace(";", ",").split(",") if p.strip()]
    return acc


class AccountsPane(Vertical):
    BINDINGS = [
        ("a", "add", "Добавить"),
        ("e", "edit", "Изменить"),
        ("d", "delete", "Удалить"),
        ("o", "open", "Получатель/доставка"),
    ]

    def compose(self) -> ComposeResult:
        table = DataTable(id="accounts-table", cursor_type="row", zebra_stripes=True)
        table.border_title = "Аккаунты"
        yield table
        with Horizontal(classes="button-row"):
            yield Button("+ Добавить [a]", id="add", variant="success")
            yield Button("Изменить [e]", id="edit")
            yield Button("Получатель и доставка [o]", id="open", variant="primary")
            yield Button("Удалить [d]", id="delete", variant="error")

    def on_mount(self):
        table = self.query_one(DataTable)
        table.add_columns("#", "Email", "Пароль", "Прокси", "Товары")
        self.reload()

    def reload(self):
        table = self.query_one(DataTable)
        table.clear()
        for i, acc in enumerate(self.app.store.accounts, 1):
            table.add_row(
                str(i), acc.get("email", ""), "••••••" if acc.get("password") else "—",
                acc.get("proxy") or "—",
                ", ".join(str(p) for p in acc.get("product_ids", [])) or Text("нет", style=CORAL),
            )

    def _selected(self):
        table = self.query_one(DataTable)
        if not self.app.store.accounts or table.cursor_row is None:
            self.app.notify("Выбери аккаунт в таблице", severity="warning")
            return None, None
        idx = min(table.cursor_row, len(self.app.store.accounts) - 1)
        return idx, self.app.store.accounts[idx]

    def _save(self, msg: str):
        self.app.store.save()
        self.reload()
        self.app.notify(msg)

    def on_button_pressed(self, event: Button.Pressed):
        getattr(self, f"action_{event.button.id}")()

    def on_data_table_row_selected(self, event: DataTable.RowSelected):
        self.action_edit()

    def action_add(self):
        def done(data):
            if data and data["email"]:
                self.app.store.accounts.append(form_to_account(data))
                self._save(f"Аккаунт {data['email']} добавлен")
        self.app.push_screen(FormModal("Новый аккаунт", account_form()), done)

    def action_edit(self):
        idx, acc = self._selected()
        if acc is None:
            return

        def done(data):
            if data and data["email"]:
                self.app.store.accounts[idx] = form_to_account(data, acc)
                self._save("Аккаунт сохранён")
        self.app.push_screen(FormModal(f"Аккаунт {acc.get('email')}", account_form(acc)), done)

    def action_delete(self):
        idx, acc = self._selected()
        if acc is None:
            return

        def done(yes):
            if yes:
                self.app.store.accounts.pop(idx)
                self._save(f"Аккаунт {acc.get('email')} удалён")
        self.app.push_screen(ConfirmModal(f"Удалить аккаунт {acc.get('email')}?", yes="Удалить"), done)

    def action_open(self):
        _, acc = self._selected()
        if acc is not None:
            self.app.push_screen(RecipientModal(acc))


class RecipientModal(ModalScreen):
    """Как в GUI: войти в аккаунт, выбрать получателя и способ доставки."""
    BINDINGS = [("escape", "dismiss", "Закрыть"), ("r", "refresh", "Обновить")]

    def __init__(self, acc: dict):
        super().__init__()
        self.acc = acc
        self.recipients = []
        self.delivery = []

    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="dialog wide"):
            yield Label(f"Аккаунт {self.acc.get('email')}", classes="dialog-title")
            yield Label("Загрузка...", id="rc-status")
            yield Label("Получатель", classes="panel-title")
            yield Vertical(id="rc-recipients")
            with Horizontal(classes="dialog-buttons"):
                yield Button("Сделать выбранным", id="rc-apply-recipient", variant="primary")
                yield Button("+ Создать получателя", id="rc-create")
            yield Label("Способ доставки (самовывоз / пункт СДЭК)", classes="panel-title")
            yield Vertical(id="rc-delivery")
            with Horizontal(classes="dialog-buttons"):
                yield Button("Сделать выбранным", id="rc-apply-delivery", variant="primary")
                yield Button("+ Пункт СДЭК", id="rc-cdek")
            with Horizontal(classes="dialog-buttons"):
                yield Button("Обновить [r]", id="rc-refresh")
                yield Button("Закрыть", id="rc-close")

    def on_mount(self):
        self.action_refresh()

    # ─── запросы к сайту ─────────────────────────────────────────────────

    def _creds(self):
        return self.acc.get("email"), self.acc.get("password"), self.acc.get("proxy")

    def action_refresh(self):
        self._run(lambda: rf.check_account(*self._creds()))

    @work(exclusive=True, group="recipient")
    async def _run(self, coro_factory):
        status = self.query_one("#rc-status", Label)
        status.update("[$warning]Выполняется запрос к сайту...[/]")
        for b in self.query(Button):
            b.disabled = b.id != "rc-close"
        try:
            result = await coro_factory()
        finally:
            for b in self.query(Button):
                b.disabled = False
        if not result.get("ok"):
            status.update(f"[$error]Ошибка: {result.get('error')}[/]")
            return
        status.update("[$success]Готово[/]")
        self.recipients = result.get("recipients", [])
        self.delivery = result.get("delivery", [])
        await self._rebuild()

    async def _rebuild(self):
        rec_box = self.query_one("#rc-recipients", Vertical)
        await rec_box.remove_children()
        if not self.recipients:
            await rec_box.mount(Label("[$error]Получатель не создан[/]"))
        else:
            if not any(r.get("selected") for r in self.recipients):
                await rec_box.mount(Label("[$error]Получатель не выбран по умолчанию[/]"))
            await rec_box.mount(RadioSet(*[
                RadioButton(
                    Text(f'{r.get("name", "")} {r.get("last_name", "")} — {r.get("phone_number", "")}'),
                    value=bool(r.get("selected")),
                ) for r in self.recipients
            ], id="rc-recipient-set"))

        del_box = self.query_one("#rc-delivery", Vertical)
        await del_box.remove_children()
        if not self.delivery:
            await del_box.mount(Label("[$error]Способ доставки не настроен[/]"))
        else:
            if not any(d.get("selected") for d in self.delivery):
                await del_box.mount(Label("[$error]Способ доставки не выбран по умолчанию[/]"))
            buttons = []
            for d in self.delivery:
                address = d.get("address") or ""
                kind = d.get("type") or ""
                label = f'[{kind}] {d.get("name", "")}' + (f" — {address}" if address else "")
                buttons.append(RadioButton(Text(label), value=bool(d.get("selected"))))
            await del_box.mount(RadioSet(*buttons, id="rc-delivery-set"))

    def _pressed(self, set_id: str, items: list):
        try:
            idx = self.query_one(f"#{set_id}", RadioSet).pressed_index
        except Exception:
            idx = -1
        if idx < 0 or idx >= len(items):
            self.app.notify("Сначала отметь вариант в списке", severity="warning")
            return None
        return items[idx]

    def on_button_pressed(self, event: Button.Pressed):
        bid = event.button.id
        if bid == "rc-close":
            self.dismiss()
        elif bid == "rc-refresh":
            self.action_refresh()
        elif bid == "rc-apply-recipient":
            r = self._pressed("rc-recipient-set", self.recipients)
            if r:
                self._run(lambda: rf.select_recipient(*self._creds(), r.get("identifier")))
        elif bid == "rc-apply-delivery":
            d = self._pressed("rc-delivery-set", self.delivery)
            if d:
                self._run(lambda: rf.select_delivery(*self._creds(), d.get("type"), d.get("identifier")))
        elif bid == "rc-create":
            self._create_recipient()
        elif bid == "rc-cdek":
            self.app.notify(
                f"Добавление пункта СДЭК прямо из TUI появится, когда будет трейс запроса сайта. "
                f"Пока — добавь на сайте: {CDEK_SETUP_URL}, потом нажми «Обновить».",
                title="Пункт СДЭК", timeout=15,
            )

    def _create_recipient(self):
        fields = [
            ("name", "Имя", "", False),
            ("last_name", "Фамилия", "", False),
            ("phone_number", "Телефон", "", False),
        ]

        def done(data):
            if not data:
                return
            if not all(data.values()):
                self.app.notify("Заполни имя, фамилию и телефон", severity="error")
                return
            self._run(lambda: rf.create_recipient(
                *self._creds(), data["name"], data["last_name"], data["phone_number"]))
        self.app.push_screen(FormModal("Новый получатель", fields, ok_label="Создать"), done)
