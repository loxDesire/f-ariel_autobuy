"""Экран «История»: прошлые запуски из history.jsonl."""
import json
import os
from datetime import datetime

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import DataTable, Static

from ..theme import CORAL, MINT


class HistoryPane(Vertical):
    BINDINGS = [("r", "reload", "Обновить")]

    def __init__(self, **kw):
        super().__init__(**kw)
        self.records = []

    def compose(self) -> ComposeResult:
        table = DataTable(id="history-table", cursor_type="row", zebra_stripes=True)
        table.border_title = "История запусков (r — обновить)"
        yield table
        detail = Static("", id="history-detail", classes="panel")
        detail.border_title = "Подробности"
        yield detail

    def on_mount(self):
        self.query_one(DataTable).add_columns("Когда (МСК)", "Итог", "Аккаунты", "Товары")
        self.action_reload()

    def action_reload(self):
        path = os.path.join(self.app.project_dir, "history.jsonl")
        self.records = []
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    try:
                        self.records.append(json.loads(line))
                    except ValueError:
                        pass
        self.records.reverse()  # новые сверху

        table = self.query_one(DataTable)
        table.clear()
        for i, rec in enumerate(self.records):
            try:
                when = datetime.fromisoformat(rec["timestamp"]).strftime("%d.%m %H:%M:%S")
            except (KeyError, ValueError):
                when = rec.get("timestamp", "?")
            ok, total = rec.get("success_count", 0), rec.get("ready_count", 0)
            result = Text(f"{ok}/{total}", style=MINT) if ok else Text(f"{ok}/{total}", style=CORAL)
            accounts = rec.get("accounts", [])
            emails = ", ".join(a.get("email", "").split("@")[0] for a in accounts)
            products = ", ".join(sorted({str(p) for a in accounts for p in a.get("product_ids", [])}))
            table.add_row(when, result, emails, products, key=str(i))
        self._show(0)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted):
        if event.row_key is not None:
            self._show(int(event.row_key.value))

    def _show(self, idx: int):
        detail = self.query_one("#history-detail", Static)
        if not self.records:
            detail.update("[$text-muted]Запусков пока не было[/]")
            return
        rec = self.records[idx]
        lines = [f"[b]{rec.get('timestamp')}[/]  успешно {rec.get('success_count')}/{rec.get('ready_count')}"]
        for a in rec.get("accounts", []):
            link = a.get("order_link")
            if link and "rejected" not in link:
                status = f"[$success]{link}[/]"
            elif link:
                status = f"[$error]{link}[/]"
            else:
                status = "[$text-muted]заказа нет[/]"
            lines.append(f"  {a.get('email')}  товары={a.get('product_ids')}  {status}")
        detail.update("\n".join(lines))
