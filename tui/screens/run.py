"""Экран «Запуск»: старт/стоп бота, таймер до дропа, полный лог и успешные."""
import asyncio
import os
import signal
import sys
import time
from collections import deque

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Digits, Label, RadioButton, RadioSet, RichLog, Static

from ..theme import CORAL, DIM, LAVENDER, MINT, MUTED, PEACH, SAKURA, TEXT, TIME
from ..timeutil import countdown_parts

# Стиль строки по виду (см. run_fast.log: @@<вид>@@<текст>)
KIND_STYLE = {
    "head": f"bold {SAKURA}",
    "info": TEXT,
    "req": DIM,
    "resp": MUTED,
    "ok": MINT,
    "win": f"bold {MINT}",
    "warn": PEACH,
    "err": CORAL,
    "tg": LAVENDER,
}
SUCCESS_KINDS = {"ok", "win"}
MAX_LOG_LINES = 5000


def parse_line(raw: str):
    """'@@kind@@HH:MM:SS.mmm текст' -> (kind, ts, text). Прочее — info без времени."""
    if raw.startswith("@@"):
        end = raw.find("@@", 2)
        if end > 0:
            kind = raw[2:end]
            rest = raw[end + 2:]
            ts, _, text = rest.partition(" ")
            return kind, ts, text
    return "info", "", raw


class RunPane(Vertical):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.proc: asyncio.subprocess.Process = None
        self.started_at = None
        self.req_times = deque()
        self.counters = {"req": 0, "resp": 0, "ok": 0, "err": 0}

    def compose(self) -> ComposeResult:
        with Horizontal(id="run-top"):
            with Vertical(id="run-controls", classes="panel"):
                yield Label("Режим", classes="panel-title")
                with RadioSet(id="mode"):
                    yield RadioButton("Ко времени", id="mode-scheduled")
                    yield RadioButton("Сразу", id="mode-now")
                with Horizontal(id="run-buttons"):
                    yield Button("Старт", id="start", variant="success")
                    yield Button("Стоп", id="stop", variant="error", disabled=True)
                    yield Button("Очистить", id="clear")
            with Vertical(id="run-timer", classes="panel"):
                yield Label("", id="timer-title", classes="panel-title")
                yield Digits("00:00:00", id="timer")
            with Vertical(id="run-status", classes="panel"):
                yield Label("Статус", classes="panel-title")
                yield Static("", id="status-text")
        with Horizontal(id="run-logs"):
            log_all = RichLog(id="log-all", max_lines=MAX_LOG_LINES, wrap=False)
            log_all.border_title = "Все запросы"
            yield log_all
            log_ok = RichLog(id="log-ok", wrap=True, min_width=20)
            log_ok.border_title = "Успешные"
            yield log_ok

    def on_mount(self):
        mode = self.app.store.data.get("mode", "scheduled")
        self.query_one("#mode-now" if mode == "now" else "#mode-scheduled", RadioButton).value = True
        self.set_interval(0.5, self.refresh_status)
        self.refresh_status()

    # ─── режим / таймер / статус ─────────────────────────────────────────

    @property
    def mode(self) -> str:
        return "now" if self.query_one("#mode-now", RadioButton).value else "scheduled"

    def refresh_status(self):
        h, m, s = self.app.store.drop_time
        title = self.query_one("#timer-title", Label)
        digits = self.query_one("#timer", Digits)
        if self.mode == "now":
            title.update("Режим СРАЗУ — без ожидания")
            if self.started_at:
                el = int(time.monotonic() - self.started_at)
                digits.update(f"{el // 3600:02d}:{el % 3600 // 60:02d}:{el % 60:02d}")
            else:
                digits.update("00:00:00")
        else:
            title.update(f"До дропа {h:02d}:{m:02d}:{s:02d} МСК")
            digits.update(countdown_parts(h, m, s, self.app.ntp_offset)[0])

        now = time.monotonic()
        while self.req_times and now - self.req_times[0] > 5:
            self.req_times.popleft()
        rps = len(self.req_times) / 5
        running = self.proc is not None and self.proc.returncode is None
        state = "[b $success]РАБОТАЕТ[/]" if running else "[b $text-muted]остановлен[/]"
        uptime = ""
        if running and self.started_at:
            el = int(now - self.started_at)
            uptime = f" · {el // 60:02d}:{el % 60:02d}"
        c = self.counters
        self.query_one("#status-text", Static).update(
            f"{state}{uptime}\n"
            f"запросов: [b]{c['req']}[/]  ({rps:.1f}/с)\n"
            f"ответ «нет»: {c['resp']}\n"
            f"[$success]успешных: {c['ok']}[/]   [$error]ошибок: {c['err']}[/]"
        )

    # ─── кнопки ──────────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "start":
            self.start_bot()
        elif event.button.id == "stop":
            self.stop_bot()
        elif event.button.id == "clear":
            self.query_one("#log-all", RichLog).clear()
            self.query_one("#log-ok", RichLog).clear()
            self.counters = {k: 0 for k in self.counters}
            self.req_times.clear()

    def start_bot(self):
        if self.proc is not None and self.proc.returncode is None:
            self.app.notify("Бот уже работает", severity="warning")
            return
        if not self.app.store.accounts:
            self.app.notify("Нет аккаунтов — добавь на вкладке «Аккаунты»", severity="error")
            return
        self.run_bot(self.mode)

    def stop_bot(self):
        if self.proc is None or self.proc.returncode is not None:
            return
        self._write("warn", "", "Остановка бота...")
        try:
            if sys.platform == "win32":
                self.proc.terminate()
            else:
                self.proc.send_signal(signal.SIGINT)  # бот завершится как по Ctrl+C
        except ProcessLookupError:
            return
        self.set_timer(3, self._kill_if_alive)

    def _kill_if_alive(self):
        if self.proc is not None and self.proc.returncode is None:
            self.proc.kill()

    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.returncode is None

    # ─── процесс бота ────────────────────────────────────────────────────

    @work(exclusive=True, group="bot")
    async def run_bot(self, mode: str):
        env = dict(os.environ, ARIEL_TUI="1", PYTHONUNBUFFERED="1", PYTHONUTF8="1")
        self.query_one("#start", Button).disabled = True
        self.query_one("#stop", Button).disabled = False
        self.query_one("#mode", RadioSet).disabled = True
        self.started_at = time.monotonic()
        self._write("head", "", f"Запуск бота: режим {'СРАЗУ' if mode == 'now' else 'ко времени'}")
        try:
            self.proc = await asyncio.create_subprocess_exec(
                sys.executable, os.path.join(self.app.project_dir, "run_fast.py"), mode,
                cwd=self.app.project_dir, env=env,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
            )
            while True:
                raw = await self.proc.stdout.readline()
                if not raw:
                    break
                kind, ts, text = parse_line(raw.decode("utf-8", errors="replace").rstrip("\n"))
                self._on_bot_line(kind, ts, text)
            code = await self.proc.wait()
            self._write("warn" if code == 0 else "err", "", f"Бот завершился (код {code})")
        except Exception as e:
            self._write("err", "", f"Не удалось запустить бота: {type(e).__name__}: {e}")
        finally:
            self.started_at = None
            if self.is_attached:  # TUI могли закрыть, пока бот работал — виджетов уже нет
                self.query_one("#start", Button).disabled = False
                self.query_one("#stop", Button).disabled = True
                self.query_one("#mode", RadioSet).disabled = False
                self.app.refresh_history()

    def _on_bot_line(self, kind: str, ts: str, text: str):
        if kind == "req":
            self.counters["req"] += 1
            self.req_times.append(time.monotonic())
        elif kind == "resp":
            self.counters["resp"] += 1
        elif kind in SUCCESS_KINDS:
            self.counters["ok"] += 1
        elif kind == "err":
            self.counters["err"] += 1
        self._write(kind, ts, text)
        if kind == "win":
            self.app.notify(text, title="Успех!", timeout=10)
            self.app.bell()

    def _write(self, kind: str, ts: str, text: str):
        style = KIND_STYLE.get(kind, TEXT)
        line = Text()
        if ts:
            line.append(ts + " ", style=TIME)
        line.append(text, style=style)
        self.query_one("#log-all", RichLog).write(line)
        if kind in SUCCESS_KINDS:
            ok_line = Text()
            if ts:
                ok_line.append(ts[:8] + " ", style=TIME)
            ok_line.append(text, style=style)
            self.query_one("#log-ok", RichLog).write(ok_line)
