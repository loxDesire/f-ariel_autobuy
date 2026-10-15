"""Экран «Товары»: доступные на сайте товары и назначение их аккаунтам."""
from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Label, Select

from core.product_finder import fetch_available_products
from ..config_store import coerce_pid


class ProductsPane(Vertical):
    BINDINGS = [("l", "load", "Загрузить с сайта")]

    def __init__(self, **kw):
        super().__init__(**kw)
        self.products = []

    def compose(self) -> ComposeResult:
        with Horizontal(classes="button-row"):
            yield Button("Загрузить с сайта [l]", id="load", variant="primary")
            yield Label("Аккаунт:", classes="inline-label")
            yield Select([], id="account", prompt="выбери аккаунт", allow_blank=True)
        yield Label("Enter на товаре — добавить / убрать у выбранного аккаунта", classes="hint")
        table = DataTable(id="products-table", cursor_type="row", zebra_stripes=True)
        table.border_title = "Товары на сайте"
        yield table

    def on_mount(self):
        self.query_one(DataTable).add_columns("ID", "Название", "У аккаунтов")
        self.reload_accounts()

    def on_show(self):
        self.reload_accounts()

    def reload_accounts(self):
        select = self.query_one("#account", Select)
        current = select.value
        emails = [a.get("email", "") for a in self.app.store.accounts]
        select.set_options([(e, e) for e in emails])
        if current in emails:
            select.value = current
        elif emails:
            select.value = emails[0]
        self._render_table()

    def _render_table(self):
        table = self.query_one(DataTable)
        table.clear()
        for p in self.products:
            owners = [a.get("email", "").split("@")[0] for a in self.app.store.accounts
                      if coerce_pid(p["id"]) in [coerce_pid(x) for x in a.get("product_ids", [])]]
            table.add_row(str(p["id"]), Text(p.get("name") or "—"),
                          ", ".join(owners) if owners else "", key=str(p["id"]))

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "load":
            self.action_load()

    def action_load(self):
        self._load()

    @work(exclusive=True, group="products")
    async def _load(self):
        self.app.notify("Загружаю список товаров с сайта...")
        try:
            self.products = await fetch_available_products()
        except Exception as e:
            self.app.notify(f"Не удалось загрузить: {type(e).__name__}: {e}", severity="error")
            return
        self._render_table()
        self.app.notify(f"Найдено товаров: {len(self.products)}"
                        if self.products else "На сайте сейчас нет доступных товаров")

    def on_data_table_row_selected(self, event: DataTable.RowSelected):
        email = self.query_one("#account", Select).value
        acc = next((a for a in self.app.store.accounts if a.get("email") == email), None)
        if acc is None:
            self.app.notify("Сначала выбери аккаунт", severity="warning")
            return
        pid = coerce_pid(event.row_key.value)
        ids = [coerce_pid(x) for x in acc.get("product_ids", [])]
        if pid in ids:
            ids.remove(pid)
            msg = f"Товар {pid} убран у {email}"
        else:
            ids.append(pid)
            msg = f"Товар {pid} добавлен {email}"
        acc["product_ids"] = ids
        self.app.store.save()
        self._render_table()
        self.app.refresh_accounts()
        self.app.notify(msg)
