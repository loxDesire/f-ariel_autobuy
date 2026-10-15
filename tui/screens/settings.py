"""Экран «Настройки»: время дропа, режим по умолчанию, Telegram."""
from textual import work
from textual.app import ComposeResult
from rich.text import Text
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, RadioButton, RadioSet, Switch

import os

import run_fast
from core.envfile import TELEGRAM_KEYS, telegram_from_env, write_env


def _chat_id(value: str):
    """id чата числом (у групп отрицательный), иначе как есть (например @channel)."""
    v = value.strip()
    return int(v) if v.lstrip("-").isdigit() else v


class SettingsPane(VerticalScroll):
    def compose(self) -> ComposeResult:
        yield Label("Время дропа (МСК)", classes="panel-title")
        with Horizontal(classes="time-row"):
            yield Label("час", classes="inline-label")
            yield Input(id="t-hour", type="integer", max_length=2)
            yield Label("мин", classes="inline-label")
            yield Input(id="t-minute", type="integer", max_length=2)
            yield Label("сек", classes="inline-label")
            yield Input(id="t-second", type="integer", max_length=2)

        yield Label("Режим по умолчанию", classes="panel-title")
        with RadioSet(id="s-mode"):
            yield RadioButton("Ко времени", id="s-mode-scheduled")
            yield RadioButton("Сразу", id="s-mode-now")

        yield Label("Уведомления в Telegram", classes="panel-title")
        with Horizontal(classes="switch-row"):
            yield Switch(id="tg-enabled")
            yield Label("включены", classes="inline-label")
        yield Label("Токен бота (от @BotFather)", classes="field-label")
        yield Input(id="tg-token", password=True)
        yield Label("Chat ID — группа (кнопка «Найти группу») или личный чат (@userinfobot)",
                    classes="field-label")
        with Horizontal(classes="input-row"):
            yield Input(id="tg-chat")
            yield Button("Найти группу", id="tg-find")
        yield Label("Имя программы — видно в сообщениях, чтобы в общей группе было понятно, "
                    "кто купил (пусто = имя компьютера)", classes="field-label")
        yield Input(id="tg-name", placeholder=run_fast.instance_name({}))
        yield Label("API base — api.telegram.org или URL своего Cloudflare Worker "
                    "(если Telegram заблокирован, см. tools/tg-proxy-worker.js)", classes="field-label")
        yield Input(id="tg-api", placeholder="https://api.telegram.org")

        with Horizontal(classes="button-row"):
            yield Button("Сохранить", id="save", variant="success")
            yield Button("Отправить тест в Telegram", id="tg-test", variant="primary")
        yield Label("", id="s-config-path", classes="hint")

    def on_mount(self):
        store = self.app.store
        h, m, s = store.drop_time
        self.query_one("#t-hour", Input).value = str(h)
        self.query_one("#t-minute", Input).value = str(m)
        self.query_one("#t-second", Input).value = str(s)
        mode = store.data.get("mode", "scheduled")
        self.query_one("#s-mode-now" if mode == "now" else "#s-mode-scheduled", RadioButton).value = True
        tg = dict(store.telegram, **telegram_from_env(self._env_path))
        self.query_one("#tg-enabled", Switch).value = bool(tg.get("enabled"))
        self.query_one("#tg-token", Input).value = tg.get("bot_token", "")
        self.query_one("#tg-chat", Input).value = str(tg.get("chat_id", ""))
        self.query_one("#tg-api", Input).value = tg.get("api_base", "")
        self.query_one("#tg-name", Input).value = tg.get("name", "")
        self.query_one("#s-config-path", Label).update(
            f"Конфиг: {store.path}\nСекреты Telegram (токен, chat id, Worker): {self._env_path} — не попадает в git")

    @property
    def _env_path(self) -> str:
        return os.path.join(self.app.project_dir, ".env")

    def _telegram_from_form(self) -> dict:
        return {
            "enabled": self.query_one("#tg-enabled", Switch).value,
            "bot_token": self.query_one("#tg-token", Input).value.strip(),
            "chat_id": _chat_id(self.query_one("#tg-chat", Input).value),
            "api_base": self.query_one("#tg-api", Input).value.strip() or "https://api.telegram.org",
            "name": self.query_one("#tg-name", Input).value.strip(),
        }

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "save":
            self.save()
        elif event.button.id == "tg-test":
            self.send_test()
        elif event.button.id == "tg-find":
            self.find_group()

    def save(self):
        try:
            h = int(self.query_one("#t-hour", Input).value)
            m = int(self.query_one("#t-minute", Input).value)
            s = int(self.query_one("#t-second", Input).value)
            if not (0 <= h <= 23 and 0 <= m <= 59 and 0 <= s <= 59):
                raise ValueError
        except ValueError:
            self.app.notify("Время: час 0–23, минуты и секунды 0–59", severity="error")
            return
        data = self.app.store.data
        data["time"] = {"hour": h, "minute": m, "second": s}
        data["mode"] = "now" if self.query_one("#s-mode-now", RadioButton).value else "scheduled"
        tg = self._telegram_from_form()
        # секреты — в .env (в .gitignore), в config.json — только вкл/выкл и имя
        write_env({env_key: tg[field] for env_key, field in TELEGRAM_KEYS.items()}, self._env_path)
        for field in TELEGRAM_KEYS.values():
            data["telegram"].pop(field, None)
        data["telegram"].update(enabled=tg["enabled"], name=tg["name"])
        self.app.store.save()
        self.app.notify("Настройки сохранены")

    @work(exclusive=True, group="tg-test")
    async def send_test(self):
        cfg = dict(self._telegram_from_form(), enabled=True)
        if not cfg["bot_token"] or not cfg["chat_id"]:
            self.app.notify("Заполни токен и chat id", severity="error")
            return
        self.app.notify("Отправляю тестовое сообщение...")
        ok = await run_fast.send_telegram("✅ ARIELBOT: тестовое уведомление", cfg)
        if ok:
            self.app.notify("Дошло! Проверь Telegram")
        else:
            self.app.notify("Не отправилось — проверь токен, chat id и API base "
                            "(если Telegram заблокирован — нужен Cloudflare Worker)",
                            severity="error", timeout=10)

    @work(exclusive=True, group="tg-find")
    async def find_group(self):
        cfg = self._telegram_from_form()
        if not cfg["bot_token"]:
            self.app.notify("Сначала впиши токен бота", severity="error")
            return
        self.app.notify("Ищу чаты, где бот видел сообщения...")
        try:
            chats = await run_fast.find_telegram_chats(cfg)
        except Exception as e:
            self.app.notify(f"Не получилось: {type(e).__name__}: {e} — проверь токен и API base",
                            severity="error", timeout=10)
            return
        if not chats:
            self.app.notify("Бот пока не видел сообщений. Добавь его в группу, напиши там "
                            "что-нибудь и нажми ещё раз.", severity="warning", timeout=12)
            return

        def done(chat_id):
            if chat_id is not None:
                self.query_one("#tg-chat", Input).value = str(chat_id)
                self.app.notify("Chat ID подставлен — нажми «Сохранить» и «Отправить тест»")
        self.app.push_screen(ChatPickModal(chats), done)


class ChatPickModal(ModalScreen):
    """Выбор чата/группы из найденных через getUpdates."""
    BINDINGS = [("escape", "dismiss(None)", "Отмена")]
    TYPES = {"group": "группа", "supergroup": "группа", "private": "личный", "channel": "канал"}

    def __init__(self, chats: list):
        super().__init__()
        # группы первыми
        self.chats = sorted(chats, key=lambda c: c["type"] not in ("group", "supergroup"))

    def compose(self):
        with Vertical(classes="dialog"):
            yield Label("Куда слать уведомления?", classes="dialog-title")
            yield RadioSet(*[
                RadioButton(Text(f'{c["title"] or "без названия"}  ·  '
                                 f'{self.TYPES.get(c["type"], c["type"])}  ·  {c["id"]}'),
                            value=i == 0)
                for i, c in enumerate(self.chats)
            ], id="chat-set")
            with Horizontal(classes="dialog-buttons"):
                yield Button("Выбрать", id="pick", variant="primary")
                yield Button("Отмена", id="cancel")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "pick":
            idx = self.query_one("#chat-set", RadioSet).pressed_index
            self.dismiss(self.chats[idx]["id"] if 0 <= idx < len(self.chats) else None)
        else:
            self.dismiss(None)
