"""Ариель Бот — TUI. Главное окно: шапка, боковое меню, экраны."""
import os
import threading

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import ContentSwitcher, Footer, Label, ListItem, ListView, Static

import run_fast
from .config_store import ConfigStore
from .modals import ConfirmModal
from .screens.accounts import AccountsPane
from .screens.history import HistoryPane
from .screens.products import ProductsPane
from .screens.run import RunPane
from .screens.settings import SettingsPane
from .theme import BANNER_GRADIENT, DIM, SAKURA, SAKURA_THEME
from .timeutil import countdown_parts, now_msk

VERSION = "2.0"

MENU = [
    ("run", "Запуск", "1"),
    ("accounts", "Аккаунты", "2"),
    ("products", "Товары", "3"),
    ("history", "История", "4"),
    ("settings", "Настройки", "5"),
    ("about", "О программе", "6"),
]


def banner_text() -> Text:
    text = Text()
    for line, color in zip(run_fast.BANNER.splitlines(), BANNER_GRADIENT):
        text.append(line + "\n", style=f"bold {color}")
    return text


class TopBar(Horizontal):
    def compose(self) -> ComposeResult:
        yield Label(Text.assemble(("ARIELBOT", f"bold {SAKURA}"),
                                  (" │ tg - @xdesire", DIM)),
                    id="brand")
        yield Label("", id="clock")

    def on_mount(self):
        self.set_interval(1, self.tick)
        self.tick()

    def tick(self):
        app = self.app
        h, m, s = app.store.drop_time
        left, _ = countdown_parts(h, m, s, app.ntp_offset)
        now = now_msk(app.ntp_offset).strftime("%H:%M:%S")
        state = "[$success]бот работает[/]" if app.run_pane.running else "[$text-muted]бот остановлен[/]"
        self.query_one("#clock", Label).update(
            f"{state} │ МСК [b]{now}[/] │ до дропа {h:02d}:{m:02d}:{s:02d}: [b $secondary]{left}[/]"
        )


class AboutPane(VerticalScroll):
    def compose(self) -> ComposeResult:
        yield Static(banner_text(), id="about-banner")
        yield Label("tg - @xdesire", id="about-credits")
        yield Static(
            f"Версия {VERSION}\n\n"
            "Бот для быстрой покупки лимитированных игрушек на f-ariel.ru\n"
            "сразу несколькими аккаунтами.\n\n"
            "[b]Клавиши[/]\n"
            "  1–6        разделы меню\n"
            "  s / x      старт / стоп бота\n"
            "  a e d o    аккаунты: добавить, изменить, удалить, получатель/доставка\n"
            "  l          загрузить товары с сайта\n"
            "  r          обновить (история, получатель)\n"
            "  esc        из поля ввода обратно в меню\n"
            "  ctrl+p     палитра команд\n"
            "  q          выход\n\n"
            f"[$text-muted]Папка: {self.app.project_dir}[/]",
            id="about-text",
        )


class ArielApp(App):
    TITLE = "ARIELBOT"
    CSS_PATH = "styles.tcss"
    BINDINGS = [
        *[Binding(key, f"show('{pane}')", label, show=False)
          for pane, label, key in MENU],
        Binding("s", "start", "Старт"),
        Binding("x", "stop", "Стоп"),
        Binding("q", "quit_app", "Выход"),
        Binding("escape", "focus_menu", "Меню", show=False),
    ]

    def __init__(self, project_dir: str):
        super().__init__()
        self.project_dir = project_dir
        self.store = ConfigStore(os.path.join(project_dir, "config.json"))
        self.ntp_offset = 0.0
        # Account/логин из run_fast пишут лог — в TUI это не должно ломать экран
        run_fast.LOG_SINK = lambda kind, text: None

    def compose(self) -> ComposeResult:
        yield TopBar(id="topbar")
        with Horizontal(id="body"):
            with Vertical(id="sidebar"):
                yield ListView(*[ListItem(Label(label), id=f"menu-{pane}") for pane, label, _ in MENU],
                               id="menu")
            with ContentSwitcher(initial="run", id="content"):
                yield RunPane(id="run")
                yield AccountsPane(id="accounts")
                yield ProductsPane(id="products")
                yield HistoryPane(id="history")
                yield SettingsPane(id="settings")
                yield AboutPane(id="about")
        yield Footer()

    def on_mount(self):
        self.register_theme(SAKURA_THEME)
        self.theme = "sakura"
        self.sync_ntp()

    def sync_ntp(self):
        # daemon-поток: если NTP недоступен, ожидание ответа не держит выход из TUI
        def worker():
            self.ntp_offset = run_fast.get_ntp_offset(quiet=True)
        threading.Thread(target=worker, daemon=True, name="ntp").start()

    @property
    def run_pane(self) -> RunPane:
        return self.query_one(RunPane)

    # ─── навигация ───────────────────────────────────────────────────────

    def on_list_view_selected(self, event: ListView.Selected):
        self.action_show(event.item.id.removeprefix("menu-"))

    def _focus_pane(self, pane: str):
        """
        Фокус на таблицу/кнопку раздела — чтобы сразу работали его клавиши
        (a, e, o, l...). Не в поле ввода: иначе цифры 1–6 напечатаются в поле.
        """
        widget = self.query_one(f"#{pane}")
        for selector in ("DataTable", "Button"):
            targets = widget.query(selector)
            if targets:
                targets.first().focus()
                return
        # в разделе нечего фокусировать (О программе) — в меню, а не в скрытый раздел
        self.query_one("#menu", ListView).focus()

    def on_list_view_highlighted(self, event: ListView.Highlighted):
        if event.item is not None:
            self.query_one(ContentSwitcher).current = event.item.id.removeprefix("menu-")

    def action_show(self, pane: str):
        self.query_one(ContentSwitcher).current = pane
        menu = self.query_one("#menu", ListView)
        menu.index = [p for p, _, _ in MENU].index(pane)
        self.call_after_refresh(self._focus_pane, pane)
        if pane == "history":
            self.refresh_history()

    def action_focus_menu(self):
        """Esc — из поля ввода обратно в меню, чтобы снова работали клавиши 1–6."""
        self.query_one("#menu", ListView).focus()

    def refresh_history(self):
        self.query_one(HistoryPane).action_reload()

    def refresh_accounts(self):
        self.query_one(AccountsPane).reload()

    # ─── бот ─────────────────────────────────────────────────────────────

    def action_start(self):
        self.action_show("run")
        self.run_pane.start_bot()

    def action_stop(self):
        self.run_pane.stop_bot()

    def action_quit_app(self):
        if not self.run_pane.running:
            self.exit()
            return

        def done(yes):
            if yes:
                self.run_pane.stop_bot()
                self.set_timer(1.5, self.exit)
        self.push_screen(ConfirmModal("Бот сейчас работает. Остановить его и выйти?",
                                      yes="Остановить и выйти"), done)


def main(project_dir: str):
    ArielApp(project_dir).run()
