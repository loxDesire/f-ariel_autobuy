#!/usr/bin/env python3
"""
Ultra-fast async bot для f-ariel.ru
Vs старый код:
  - aiohttp (async I/O, нет GIL) вместо requests
  - параллельный логин всех аккаунтов
  - 3 параллельных опросчика товара вместо 1 (каждые ~17ms)
  - wait_for_msk: busy-wait последние 500ms для точности до мс
  - add+checkout всех аккаунтов одновременно через asyncio.gather
"""
import asyncio
import json
import os
import socket
import sys
import time
from datetime import datetime, timedelta

import ntplib
import pytz
import aiohttp
from yarl import URL

from core.envfile import telegram_from_env


def _quiet_exception_handler(loop, context):
    """
    ProactorEventLoop (дефолт на Windows) при частых запросах и закрытии
    сокетов сыплет в лог "Exception in callback ... ConnectionResetError
    [WinError 10054]" — сам опрос при этом продолжает работать нормально
    (add_product уже ловит все исключения сам), просто шумит в логе.
    Глушим конкретно этот безобидный случай, остальное — как обычно.
    """
    exc = context.get("exception")
    if isinstance(exc, ConnectionResetError):
        return
    loop.default_exception_handler(context)

CSRF_TOKEN = "4900d0a19b6894a4a514e9ff3afcc2c0"
BASE = "https://f-ariel.ru"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:142.0) Gecko/20100101 Firefox/142.0",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "x-csrf-token": CSRF_TOKEN,
}

POLL_WORKERS = 3   # параллельных опросчика на каждый аккаунт
POLL_SLEEP   = 0.05 / POLL_WORKERS  # ~17ms stagger между воркерами

# Логинимся один раз — дальше всё время те же cookies (сессия переживает
# падение сайта), перелогина во время опроса нет. Опрос — до победного:
# сайт лежит — запросы всё равно идут, пока товар не добавится и не пройдёт checkout.
LOGIN_RETRY_DELAY = 1.0    # режим "сразу": пауза между попытками первого логина, если сайт лежит
ADD_TIMEOUT = 1.5          # секунд ждём ответ на add-product: зависший сайт не держит воркер дольше
                           # (меньше не ставить — под нагрузкой дропа сайт может отвечать медленно)
RETRY_SLEEP = 0.2          # пауза между повторами add/checkout после сигнала, пока сайт не отвечает

MODE_SCHEDULED = "scheduled"  # ждать время дропа из config["time"], потом опрос
MODE_NOW = "now"              # начать опрос сразу после логина, без ожидания

MSK = pytz.timezone("Europe/Moscow")


# ─── вывод ────────────────────────────────────────────────────────────────────

BANNER = r"""
 █████╗ ██████╗ ██╗███████╗██╗     ██████╗  ██████╗ ████████╗
██╔══██╗██╔══██╗██║██╔════╝██║     ██╔══██╗██╔═══██╗╚══██╔══╝
███████║██████╔╝██║█████╗  ██║     ██████╔╝██║   ██║   ██║
██╔══██║██╔══██╗██║██╔══╝  ██║     ██╔══██╗██║   ██║   ██║
██║  ██║██║  ██║██║███████╗███████╗██████╔╝╚██████╔╝   ██║
╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚══════╝╚══════╝╚═════╝  ╚═════╝    ╚═╝
""".strip("\n")
CREDITS = "tg - @xdesire"

# ARIEL_TUI=1 — бота запустил TUI: каждая строка идёт как "@@<вид>@@<текст>",
# TUI сам раскрашивает и раскладывает по панелям. В терминале — цвета ANSI,
# в остальных случаях (pipe, файл) — простой текст.
_TUI = os.environ.get("ARIEL_TUI") == "1"
_COLOR = (not _TUI) and sys.stdout.isatty() and not os.environ.get("NO_COLOR")

# Виды строк лога:
#   head — заголовки, info — обычное, req — запрос отправлен (->),
#   resp — ответ без успеха (<-), ok — успешный запрос (логин и т.п.),
#   win — главное: товар в корзине / заказ оформлен, warn — повторы/ожидание,
#   err — ошибки, tg — уведомления Telegram
def _fg(hex_color: str, bold: bool = False) -> str:
    """Цвет текста truecolor из #rrggbb."""
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return f"\033[{'1;' if bold else ''}38;2;{r};{g};{b}m"


# Палитра «Сакура» (та же, что в TUI — tui/theme.py)
_ANSI = {
    "head": _fg("#ffa6c9", bold=True), "info": _fg("#e6e8ff"), "req": _fg("#5a6190"),
    "resp": _fg("#8a90c0"), "ok": _fg("#7ef0c3"), "win": _fg("#7ef0c3", bold=True),
    "warn": _fg("#ffd3a1"), "err": _fg("#ff7a85"), "tg": _fg("#a5b4fc"),
}
_TIME_COLOR = _fg("#454b78")
_BANNER_GRADIENT = ["#ffc4dc", "#ffa6c9", "#f3a9d6", "#dcaee6", "#c0b2f4", "#a5b4fc"]
_RESET = "\033[0m"

# Если задан (например TUI использует Account напрямую) — строки лога уходят
# в эту функцию (kind, text), а не в stdout.
LOG_SINK = None


def log(text: str, kind: str = "info"):
    if LOG_SINK is not None:
        LOG_SINK(kind, text)
        return
    ts = datetime.now(MSK).strftime("%H:%M:%S.%f")[:-3]
    if _TUI:
        print(f"@@{kind}@@{ts} {text}", flush=True)
    elif _COLOR:
        print(f"{_TIME_COLOR}{ts}{_RESET} {_ANSI.get(kind, '')}{text}{_RESET}", flush=True)
    else:
        print(f"{ts} {text}", flush=True)


def print_banner():
    if _TUI or LOG_SINK is not None:
        return  # у TUI своя шапка
    if _COLOR:
        # градиент по строкам баннера: от сакуры к лаванде
        for line, color in zip(BANNER.splitlines(), _BANNER_GRADIENT):
            print(f"{_fg(color, bold=True)}{line}{_RESET}")
        print(f"{_fg('#5a6190')}{CREDITS}{_RESET}\n", flush=True)
    else:
        print(BANNER)
        print(CREDITS + "\n", flush=True)


def _site_message(d) -> str:
    """Что сайт написал в ответе (message/errors) — коротко, одной строкой."""
    if not isinstance(d, dict):
        return str(d)[:120]
    msg = d.get("message") or d.get("errors") or ""
    if isinstance(msg, (dict, list)):
        msg = json.dumps(msg, ensure_ascii=False)
    return str(msg).replace("\n", " ")[:120]


# ─── Telegram ─────────────────────────────────────────────────────────────────

TELEGRAM = {"enabled": False, "bot_token": "", "chat_id": "", "api_base": "https://api.telegram.org",
            "name": ""}
_tg_tasks = set()


def _tg_url(cfg: dict, method: str) -> str:
    base = (cfg.get("api_base") or "https://api.telegram.org").rstrip("/")
    return f"{base}/bot{cfg['bot_token']}/{method}"


def instance_name(cfg: dict = None) -> str:
    """Имя этой программы в сообщениях — чтобы в общей группе было видно, кто купил."""
    cfg = cfg or TELEGRAM
    return (cfg.get("name") or "").strip() or socket.gethostname()


async def send_telegram(text: str, cfg: dict = None) -> bool:
    """
    sendMessage через api_base — это api.telegram.org или URL своего
    Cloudflare Worker (если Telegram заблокирован). chat_id — личный чат
    или группа (id группы отрицательный). Никогда не бросает.
    """
    cfg = cfg or TELEGRAM
    if not (cfg.get("enabled") and cfg.get("bot_token") and cfg.get("chat_id")):
        return False
    text = f"[{instance_name(cfg)}] {text}"
    chat_id = cfg["chat_id"]
    try:
        async with aiohttp.ClientSession() as s:
            for _ in range(2):
                async with s.post(
                    _tg_url(cfg, "sendMessage"),
                    json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as r:
                    d = await r.json(content_type=None)
                if d.get("ok"):
                    log("tg: уведомление отправлено", "tg")
                    return True
                # группа стала супергруппой — у неё новый id, Telegram его подсказывает
                new_id = (d.get("parameters") or {}).get("migrate_to_chat_id")
                if new_id and new_id != chat_id:
                    log(f"tg: группа сменила id на {new_id} — обнови chat_id в настройках", "warn")
                    chat_id = new_id
                    continue
                log(f"tg: Telegram ответил ошибкой: {d.get('description') or d}", "warn")
                break
    except Exception as e:
        log(f"tg: не отправилось: {type(e).__name__}: {e}", "warn")
    return False


async def find_telegram_chats(cfg: dict) -> list:
    """
    Чаты, где бот недавно видел сообщения (getUpdates): так узнаём id группы —
    добавь бота в группу, напиши там что угодно и вызови это.
    Возвращает [{"id", "title", "type"}], бросает при ошибке.
    """
    async with aiohttp.ClientSession() as s:
        async with s.get(_tg_url(cfg, "getUpdates"),
                         timeout=aiohttp.ClientTimeout(total=10)) as r:
            d = await r.json(content_type=None)
    if not d.get("ok"):
        raise RuntimeError(d.get("description") or str(d))
    chats = {}
    for upd in d.get("result", []):
        for key in ("message", "edited_message", "channel_post", "my_chat_member"):
            chat = (upd.get(key) or {}).get("chat")
            if chat:
                title = chat.get("title") or " ".join(
                    filter(None, [chat.get("first_name"), chat.get("last_name")])) or chat.get("username", "")
                chats[chat["id"]] = {"id": chat["id"], "title": title, "type": chat.get("type", "")}
    return list(chats.values())


def notify(text: str):
    """Уведомление в Telegram в фоне — бот его не ждёт и не падает из-за него."""
    if not TELEGRAM.get("enabled"):
        return
    task = asyncio.create_task(send_telegram(text))
    _tg_tasks.add(task)
    task.add_done_callback(_tg_tasks.discard)


async def flush_notifications(timeout: float = 6):
    if _tg_tasks:
        await asyncio.wait(list(_tg_tasks), timeout=timeout)


def _full_link(link: str) -> str:
    return link if link.startswith("http") else f"{BASE}{link}"


class Account:
    def __init__(self, email: str, password: str, product_ids: list,
                 proxy: str = None):
        self.email = email
        self.password = password
        self.proxy = proxy or None
        self.product_ids = product_ids
        self.session: aiohttp.ClientSession = None
        self.order_link = None
        self.consecutive_errors = 0   # ошибок сети/сервера подряд в add_product
        self.name = email.split("@")[0]  # коротко для лога

    async def open(self):
        # ssl=False убран из коннектора (устарело в aiohttp 3.9+),
        # передаём ssl=False на уровне каждого запроса
        connector = aiohttp.TCPConnector(limit=20, ttl_dns_cache=300)
        self.session = aiohttp.ClientSession(
            headers=HEADERS,
            connector=connector,
            trust_env=False,
        )
        # Имитируем принятие cookie-policy
        self.session.cookie_jar.update_cookies({"policy": "true"}, URL(BASE))

    async def close(self):
        if self.session:
            await self.session.close()

    async def login(self) -> bool:
        kw = dict(ssl=False, proxy=self.proxy)
        t0 = time.monotonic()
        log(f"-> [{self.name}] login", "req")
        try:
            async with self.session.get(
                BASE, timeout=aiohttp.ClientTimeout(total=10), **kw
            ):
                pass

            async with self.session.get(
                f"{BASE}/api/v1/auth/login/modal",
                timeout=aiohttp.ClientTimeout(total=10), **kw
            ):
                pass

            async with self.session.post(
                f"{BASE}/api/v1/auth/login",
                json={"email": self.email, "password": self.password, "captcha": ""},
                timeout=aiohttp.ClientTimeout(total=15), **kw,
            ) as r:
                d = await r.json(content_type=None)
                ok = bool(d.get("success")) or r.status == 200
                dt = time.monotonic() - t0
                if ok:
                    log(f"<- [{self.name}] OK login  {self.email}  {dt:.2f}s", "ok")
                else:
                    log(f"<- [{self.name}] FAIL login  {self.email}  {dt:.2f}s: {_site_message(d)}", "err")
                return ok
        except Exception as e:
            dt = time.monotonic() - t0
            log(f"<- [{self.name}] ERR login  {self.email}  {dt:.2f}s: {type(e).__name__}: {e}", "err")
            return False

    async def add_product(self, product_id: str, stats: dict = None, tag: str = "") -> bool:
        tag = tag or self.name
        t0 = time.monotonic()
        log(f"-> [{tag}] add-product id={product_id}", "req")
        try:
            async with self.session.post(
                f"{BASE}/api/v2/checkout/add-product",
                json={"identifier": product_id},
                ssl=False, proxy=self.proxy,
                timeout=aiohttp.ClientTimeout(total=ADD_TIMEOUT),
            ) as r:
                d = await r.json(content_type=None)
                ok = d.get("success") is True
                self.consecutive_errors = 0
                if stats is not None:
                    stats["ok" if ok else "clean_fail"] += 1
                dt = time.monotonic() - t0
                if ok:
                    log(f"<- [{tag}] {r.status} {dt:.2f}s OK добавлен id={product_id}", "ok")
                else:
                    log(f"<- [{tag}] {r.status} {dt:.2f}s нет: {_site_message(d) or 'success=false'}", "resp")
                return ok
        except Exception as e:
            self.consecutive_errors += 1
            if stats is not None:
                stats["errors"] += 1
                stats["last_error"] = f"{type(e).__name__}: {e}"
            dt = time.monotonic() - t0
            log(f"<- [{tag}] ERR {dt:.2f}s {type(e).__name__}: {e}", "err")
            return False

    async def add_products(self, product_ids: list) -> list:
        """
        Добавляет товары ПОСЛЕДОВАТЕЛЬНО (не через gather):
        add-product мутирует общую корзину сессии, параллельные
        запросы на одной сессии рискуют затереть друг друга.
        Сайт не отвечает (ошибка сети/5xx) — повторяем этот товар, пока сайт
        не ответит; честный ответ "не добавлено" — идём к следующему.
        """
        results = []
        for pid in product_ids:
            while True:
                ok = await self.add_product(pid)
                if ok or self.consecutive_errors == 0:
                    break
                await asyncio.sleep(RETRY_SLEEP)
            if not ok:
                log(f"  FAIL add {self.email} id={pid}", "err")
            results.append(ok)
        return results

    async def checkout(self) -> bool:
        """Повторяем, пока заказ не оформится (или сайт не ответит rejected)."""
        attempt = 0
        while True:
            attempt += 1
            t0 = time.monotonic()
            log(f"-> [{self.name}] checkout #{attempt}", "req")
            try:
                async with self.session.post(
                    f"{BASE}/api/v2/checkout/",
                    ssl=False, proxy=self.proxy,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as r:
                    d = await r.json(content_type=None)
                    dt = time.monotonic() - t0
                    ok = d.get("success") is True
                    if ok:
                        link = d.get("data", {}).get("link", "?")
                        # API отдаёт success:true даже когда заказ отклонён
                        # (например нет в наличии к моменту финализации) —
                        # это видно только по самой ссылке (/checkout/rejected/)
                        if "rejected" in link:
                            self.order_link = link  # в историю: видно, что заказ отклонён
                            log(f"<- [{self.name}] {r.status} {dt:.2f}s REJECTED checkout {self.email} -> {link}", "err")
                            return False
                        self.order_link = link
                        log(f"<- [{self.name}] {r.status} {dt:.2f}s OK checkout {self.email} -> {link}", "win")
                        notify(f"✅ Заказ оформлен! ({self.email})\n{_full_link(link)}")
                        return True
                    log(f"<- [{self.name}] {r.status} {dt:.2f}s FAIL checkout #{attempt}: {_site_message(d) or d}", "err")
            except Exception as e:
                dt = time.monotonic() - t0
                log(f"<- [{self.name}] ERR checkout #{attempt} {dt:.2f}s: {type(e).__name__}: {e}", "err")
            await asyncio.sleep(RETRY_SLEEP)


async def poll_worker(acc: Account, product_id, wid: int, start: float, max_wait,
                       found: asyncio.Event, stats: dict, winner: dict):
    """
    Один воркер одного аккаунта опрашивает СВОЙ product_id. found — общий
    сигнал НА ВСЕ аккаунты и всех их воркеров разом: как только кто-нибудь
    (любой воркер любого аккаунта) поймал товар — все остальные воркеры всех
    аккаунтов сразу останавливаются, а winner запоминает, кто и что поймал.

    Сайт упал — воркер не останавливается и продолжает слать запросы с теми
    же cookies, пока товар не добавится. max_wait=None — без лимита по времени.
    """
    i = 0
    while not found.is_set():
        if max_wait is not None and time.monotonic() - start > max_wait:
            return
        i += 1
        # Проверяем ещё раз ПЕРЕД запросом, чтобы не добавить лишний раз
        if found.is_set():
            return
        if await acc.add_product(product_id, stats, tag=f"{acc.name} w{wid} #{i}"):
            if not found.is_set():  # только первый во всём пуле считается
                elapsed = time.monotonic() - start
                log(f"++ [{acc.email}] w{wid} poll#{i} t={elapsed:.3f}s -> ADDED (id={product_id})", "win")
                winner["acc"] = acc
                winner["pid"] = product_id
                found.set()
            return
        await asyncio.sleep(POLL_SLEEP)


# ─── helpers ──────────────────────────────────────────────────────────────────

NTP_SERVERS = ["pool.ntp.org", "time.cloudflare.com", "time.google.com", "time.windows.com"]


def get_ntp_offset(servers: list = None, quiet: bool = False) -> float:
    """
    Разница (истинное время - системные часы) в секундах, БЕЗ изменения
    системных часов и без прав администратора/root — работает одинаково
    на Windows/macOS/Linux. Пробует несколько NTP-серверов по очереди (один
    может быть недоступен из-за DNS/сети), при отказе всех возвращает 0
    (используем системные часы как есть). quiet — без вывода в лог.
    """
    say = (lambda *a: None) if quiet else log
    client = ntplib.NTPClient()
    for server in servers or NTP_SERVERS:
        try:
            response = client.request(server, version=3, timeout=5)
            offset = response.offset
            say(f"NTP offset: {offset:+.3f}s (сервер {server})")
            return offset
        except Exception as e:
            say(f"NTP {server} error: {e}", "warn")
    say("NTP sync error: все серверы недоступны — используем системные часы без поправки", "warn")
    return 0.0


def save_history_record(accounts: list, ready: list, success: int):
    record = {
        "timestamp": datetime.now(MSK).isoformat(),
        "accounts": [
            {
                "email": a.email,
                "product_ids": a.product_ids,
                "order_link": a.order_link,
            }
            for a in accounts
        ],
        "success_count": success,
        "ready_count": len(ready),
    }
    with open("history.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


REFRESH_MARGIN = 180      # секунд до дропа: обновляем логин (куки) всех аккаунтов
NTP_RESYNC_INTERVAL = 600  # секунд: пока есть время — переопрашиваем NTP, компенсируя дрейф часов


def seconds_until_msk(h: int, m: int, s: int, offset: float = 0.0) -> float:
    now = datetime.now(MSK) + timedelta(seconds=offset)
    target = now.replace(hour=h, minute=m, second=s, microsecond=0)
    if now >= target:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def wait_for_msk(h: int, m: int, s: int, offset: float = 0.0):
    now = datetime.now(MSK) + timedelta(seconds=offset)
    target = now.replace(hour=h, minute=m, second=s, microsecond=0)
    if now >= target:
        target += timedelta(days=1)

    remaining = (target - now).total_seconds()
    log(f"ждём {remaining:.1f}s до {h:02d}:{m:02d}:{s:02d} MSK ...", "warn")

    if remaining > 0.6:
        time.sleep(remaining - 0.5)          # грубое ожидание

    # Busy-wait последние 500ms — точность до мс
    while True:
        current = datetime.now(MSK) + timedelta(seconds=offset)
        if (target - current).total_seconds() <= 0:
            break
        time.sleep(0.001)

    log("GO!", "head")


MODE_ALIASES = {
    "now": MODE_NOW, "--now": MODE_NOW, "сразу": MODE_NOW, "2": MODE_NOW,
    "time": MODE_SCHEDULED, "--time": MODE_SCHEDULED, "scheduled": MODE_SCHEDULED,
    "время": MODE_SCHEDULED, "1": MODE_SCHEDULED,
}


def choose_mode(cfg_mode: str) -> str:
    """
    Режим выбирается при старте, независимо от config.json:
      1) аргумент командной строки: now / time (или --now / --time);
      2) иначе, если запущено в терминале — спрашиваем; Enter = из конфига;
      3) иначе (запуск из TUI, stdin не терминал) — mode из конфига.
    """
    for arg in sys.argv[1:]:
        if arg.lower() in MODE_ALIASES:
            return MODE_ALIASES[arg.lower()]

    if sys.stdin is not None and sys.stdin.isatty():
        default = "сразу" if cfg_mode == MODE_NOW else "ко времени"
        while True:
            try:
                answer = input(
                    f"Режим: 1 — ко времени, 2 — сразу [Enter = {default}, из конфига]: "
                ).strip().lower()
            except EOFError:
                return cfg_mode
            if not answer:
                return cfg_mode
            if answer in MODE_ALIASES:
                return MODE_ALIASES[answer]
            print("  введи 1 (ко времени) или 2 (сразу)")

    return cfg_mode


# ─── main ─────────────────────────────────────────────────────────────────────

async def run():
    asyncio.get_running_loop().set_exception_handler(_quiet_exception_handler)
    print_banner()

    with open("config.json", encoding="utf-8") as f:
        cfg = json.load(f)

    TELEGRAM.update(cfg.get("telegram") or {})
    TELEGRAM.update(telegram_from_env())  # токен/chat id/Worker из .env важнее config.json

    cfg_mode = cfg.get("mode", MODE_SCHEDULED)
    if cfg_mode not in (MODE_SCHEDULED, MODE_NOW):
        log(f"config error: неизвестный mode={cfg_mode!r} (нужен {MODE_SCHEDULED!r} или {MODE_NOW!r}) — выход", "err")
        return
    mode = choose_mode(cfg_mode)

    h = cfg["time"]["hour"]
    m = cfg["time"]["minute"]
    s = cfg["time"]["second"]

    # API принимает число, не строку ("388" → 388)
    def coerce(pid):
        return int(pid) if str(pid).isdigit() else pid

    accounts = []
    for a in cfg["accounts"]:
        pids = [coerce(p) for p in a.get("product_ids") or []]
        accounts.append(Account(a["email"], a["password"], pids, a.get("proxy") or None))

    # Аккаунт без product_ids нечего покупать — в работе не участвует
    usable = []
    for a in accounts:
        if a.product_ids:
            usable.append(a)
        else:
            log(f"{a.email}: пустой product_ids — аккаунт пропущен", "warn")

    if not usable:
        log("config error: ни у одного аккаунта нет product_ids — выход", "err")
        return

    accounts = usable

    when = "СРАЗУ" if mode == MODE_NOW else f"{h:02d}:{m:02d}:{s:02d} MSK"
    log(f"═══ FAST BOT │ аккаунтов: {len(accounts)} │ режим: {when} ═══", "head")
    for a in accounts:
        log(f"  {a.email}: products={a.product_ids}" + (f"  proxy={a.proxy}" if a.proxy else ""))
    if TELEGRAM.get("enabled"):
        log("Telegram-уведомления: включены", "tg")

    # Режим "сразу": время дропа не нужно — NTP не опрашиваем
    ntp_offset = get_ntp_offset() if mode == MODE_SCHEDULED else 0.0

    # Открываем сессии
    await asyncio.gather(*[a.open() for a in accounts])

    # Логин ВСЕХ аккаунтов параллельно. Кто не вошёл (сайт лежит, сеть) — не
    # выкидываем: такие аккаунты логинятся снова, пока не получится, и только
    # потом начинают опрос. Бот не завершается, пока игрушка не куплена.
    log(f"Логин {len(accounts)} аккаунтов параллельно...", "head")
    login_ok = await asyncio.gather(*[a.login() for a in accounts])
    needs_login = {a for a, ok in zip(accounts, login_ok) if not ok}
    for a in needs_login:
        log(f"{a.email}: логин не прошёл — будем повторять до успеха", "warn")
    log(f"{len(accounts) - len(needs_login)}/{len(accounts)} вошли")

    # Если до дропа больше REFRESH_MARGIN — ждём кусками по NTP_RESYNC_INTERVAL,
    # каждый раз переопрашивая NTP (часы могут дрейфовать за часы ожидания),
    # пока не останется T-3мин, потом обновляем сессии (куки истекают через 2
    # часа). Если уже изначально ближе — ничего не трогаем.
    remaining = seconds_until_msk(h, m, s, ntp_offset)
    if mode == MODE_SCHEDULED and remaining > REFRESH_MARGIN:
        log(f"до дропа {remaining:.0f}s — ждём с пересверкой NTP каждые {NTP_RESYNC_INTERVAL}s", "warn")
        while True:
            remaining = seconds_until_msk(h, m, s, ntp_offset)
            if remaining <= REFRESH_MARGIN:
                break
            chunk = min(NTP_RESYNC_INTERVAL, remaining - REFRESH_MARGIN)
            await asyncio.sleep(chunk)
            ntp_offset = get_ntp_offset()
            remaining = seconds_until_msk(h, m, s, ntp_offset)
            log(f"пересверка NTP: офсет={ntp_offset:+.3f}s, до дропа {remaining:.0f}s", "warn")

        # Не обновилась сессия — работаем со старыми cookies (они обычно живы);
        # кто вообще не входил — продолжит попытки входа уже во время опроса
        log(f"Обновляем сессии (повторный логин) {len(accounts)} аккаунтов...", "head")
        refresh_ok = await asyncio.gather(*[a.login() for a in accounts])
        for a, ok in zip(accounts, refresh_ok):
            if ok:
                needs_login.discard(a)
            elif a not in needs_login:
                log(f"{a.email}: сессию обновить не удалось — продолжаем со старыми cookies", "warn")

    # Ждём нужного времени (в режиме "сразу" — не ждём)
    if mode == MODE_SCHEDULED:
        wait_for_msk(h, m, s, ntp_offset)
    else:
        log("режим СРАЗУ — начинаем опрос без ожидания", "warn")

    poll_stats = {"ok": 0, "clean_fail": 0, "errors": 0, "last_error": None}

    async def buy_until_success(acc: Account) -> bool:
        """
        Круг: ловим первый товар аккаунта (POLL_WORKERS воркеров) -> добавляем
        остальные его товары -> оформляем. Заказ не прошёл (rejected) — новый
        круг. Аккаунт останавливается только когда заказ оформлен.
        """
        attempt = 0
        while acc in needs_login:
            attempt += 1
            await asyncio.sleep(LOGIN_RETRY_DELAY)
            log(f"повторный логин {acc.email} попытка #{attempt}", "warn")
            if await acc.login():
                needs_login.discard(acc)

        round_no = 0
        while True:
            round_no += 1
            acc.order_link = None
            found = asyncio.Event()
            winner = {"acc": None, "pid": None}
            start = time.monotonic()
            await asyncio.gather(*[
                poll_worker(acc, acc.product_ids[0], wid, start, None, found, poll_stats, winner)
                for wid in range(POLL_WORKERS)
            ])
            rest = [p for p in acc.product_ids if p != winner["pid"]]
            if rest:
                await acc.add_products(rest)
            if await acc.checkout():
                save_history_record([acc], [acc], 1)
                return True
            save_history_record([acc], [acc], 0)
            log(f"{acc.email}: заказ не прошёл — снова ловим товар (круг #{round_no + 1})", "warn")

    log(f"Опрос: {POLL_WORKERS} воркера x {len(accounts)} аккаунт(ов), до покупки ...", "head")
    await asyncio.gather(*[buy_until_success(acc) for acc in accounts])
    log(f"═══ куплено: {len(accounts)}/{len(accounts)} ═══", "win")

    for a in accounts:
        await a.close()
    await flush_notifications()


RESTART_DELAY = 5  # секунд: пауза перед автоперезапуском после неожиданной ошибки


if __name__ == "__main__":
    # Бот завершается сам только когда всё куплено (или при ошибке конфига).
    # Неожиданная ошибка — не выход, а перезапуск через RESTART_DELAY секунд.
    while True:
        try:
            asyncio.run(run())
            break
        except KeyboardInterrupt:
            log("Stopped", "warn")
            break
        except Exception as e:
            import traceback
            log(f"Fatal: {type(e).__name__}: {e}", "err")
            traceback.print_exc()
            log(f"перезапуск через {RESTART_DELAY}s ...", "warn")
            try:
                time.sleep(RESTART_DELAY)
            except KeyboardInterrupt:
                log("Stopped", "warn")
                break
