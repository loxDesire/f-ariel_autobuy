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
import time
from datetime import datetime, timedelta

import ntplib
import pytz
import aiohttp
from yarl import URL

CSRF_TOKEN = "4900d0a19b6894a4a514e9ff3afcc2c0"
BASE = "https://f-ariel.ru"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:142.0) Gecko/20100101 Firefox/142.0",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "x-csrf-token": CSRF_TOKEN,
}

POLL_WORKERS = 3   # параллельных опросчика на первый аккаунт
POLL_SLEEP   = 0.05 / POLL_WORKERS  # ~17ms stagger между воркерами


class Account:
    def __init__(self, email: str, password: str, product_ids: list,
                 proxy: str = None, scout: bool = False):
        self.email = email
        self.password = password
        self.proxy = proxy or None
        self.product_ids = product_ids
        self.scout = scout
        self.session: aiohttp.ClientSession = None
        self.order_link = None

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
                print(f"  {'OK' if ok else 'FAIL'} login  {self.email}")
                return ok
        except Exception as e:
            print(f"  ERR login  {self.email}: {type(e).__name__}: {e}")
            return False

    async def add_product(self, product_id: str) -> bool:
        try:
            async with self.session.post(
                f"{BASE}/api/v2/checkout/add-product",
                json={"identifier": product_id},
                ssl=False, proxy=self.proxy,
                timeout=aiohttp.ClientTimeout(total=5),
            ) as r:
                d = await r.json(content_type=None)
                return d.get("success") is True
        except Exception:
            return False

    async def add_products(self, product_ids: list) -> list:
        """
        Добавляет товары ПОСЛЕДОВАТЕЛЬНО (не через gather):
        add-product мутирует общую корзину сессии, параллельные
        запросы на одной сессии рискуют затереть друг друга.
        """
        results = []
        for pid in product_ids:
            ok = await self.add_product(pid)
            if not ok:
                print(f"  FAIL add {self.email} id={pid}")
            results.append(ok)
        return results

    async def checkout(self) -> bool:
        for attempt in range(2):
            try:
                async with self.session.post(
                    f"{BASE}/api/v2/checkout/",
                    ssl=False, proxy=self.proxy,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as r:
                    d = await r.json(content_type=None)
                    ok = d.get("success") is True
                    if ok:
                        link = d.get("data", {}).get("link", "?")
                        self.order_link = link
                        print(f"  OK checkout {self.email} -> {link}")
                        return True
                    err = d.get("errors") or d.get("message") or d
                    print(f"  FAIL checkout {self.email} attempt={attempt+1}: {err}")
            except Exception as e:
                print(f"  ERR checkout {self.email} attempt={attempt+1}: {e}")
            await asyncio.sleep(0.2)
        return False

    async def poll_until_added(self, product_id: str, max_wait: float = 120) -> bool:
        """
        3 параллельных воркера опрашивают товар.
        Первый успешный add -> event -> остальные останавливаются.
        """
        found = asyncio.Event()
        start = time.monotonic()

        async def worker(wid: int) -> bool:
            i = 0
            while not found.is_set():
                if time.monotonic() - start > max_wait:
                    return False
                i += 1
                # Проверяем ещё раз ПЕРЕД запросом, чтобы не добавить лишний раз
                if found.is_set():
                    return False
                if await self.add_product(product_id):
                    if not found.is_set():  # только первый воркер считается
                        elapsed = time.monotonic() - start
                        print(f"  ++ [{self.email}] w{wid} poll#{i} t={elapsed:.3f}s -> ADDED")
                        found.set()
                        return True
                    return False  # опоздал — другой воркер уже добавил
                await asyncio.sleep(POLL_SLEEP)
            return False

        results = await asyncio.gather(*[worker(i) for i in range(POLL_WORKERS)])
        return any(results)


# ─── helpers ──────────────────────────────────────────────────────────────────

NTP_SERVERS = ["pool.ntp.org", "time.cloudflare.com", "time.google.com", "time.windows.com"]


def get_ntp_offset(servers: list = None) -> float:
    """
    Разница (истинное время - системные часы) в секундах, БЕЗ изменения
    системных часов и без прав администратора/root — работает одинаково
    на Windows/macOS/Linux. Пробует несколько NTP-серверов по очереди (один
    может быть недоступен из-за DNS/сети), при отказе всех возвращает 0
    (используем системные часы как есть).
    """
    client = ntplib.NTPClient()
    for server in servers or NTP_SERVERS:
        try:
            response = client.request(server, version=3, timeout=5)
            offset = response.offset
            print(f"  NTP offset: {offset:+.3f}s (сервер {server})")
            return offset
        except Exception as e:
            print(f"  NTP {server} error: {e}")
    print("  NTP sync error: все серверы недоступны — используем системные часы без поправки")
    return 0.0


def save_history_record(accounts: list, ready: list, success: int):
    record = {
        "timestamp": datetime.now(pytz.timezone("Europe/Moscow")).isoformat(),
        "accounts": [
            {
                "email": a.email,
                "scout": a.scout,
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
    tz = pytz.timezone("Europe/Moscow")
    now = datetime.now(tz) + timedelta(seconds=offset)
    target = now.replace(hour=h, minute=m, second=s, microsecond=0)
    if now >= target:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def wait_for_msk(h: int, m: int, s: int, offset: float = 0.0):
    tz = pytz.timezone("Europe/Moscow")
    now = datetime.now(tz) + timedelta(seconds=offset)
    target = now.replace(hour=h, minute=m, second=s, microsecond=0)
    if now >= target:
        target += timedelta(days=1)

    remaining = (target - now).total_seconds()
    print(f"  waiting {remaining:.1f}s until {h:02d}:{m:02d}:{s:02d} MSK ...")

    if remaining > 0.6:
        time.sleep(remaining - 0.5)          # грубое ожидание

    # Busy-wait последние 500ms — точность до мс
    while True:
        current = datetime.now(tz) + timedelta(seconds=offset)
        if (target - current).total_seconds() <= 0:
            break
        time.sleep(0.001)

    print("  GO!")


# ─── main ─────────────────────────────────────────────────────────────────────

async def run():
    with open("config.json", encoding="utf-8") as f:
        cfg = json.load(f)

    h = cfg["time"]["hour"]
    m = cfg["time"]["minute"]
    s = cfg["time"]["second"]

    # API принимает число, не строку ("388" → 388)
    def coerce(pid):
        return int(pid) if str(pid).isdigit() else pid

    accounts = []
    scouts = []
    for a in cfg["accounts"]:
        pids = [coerce(p) for p in a.get("product_ids") or []]
        acc = Account(a["email"], a["password"], pids,
                      a.get("proxy") or None, a.get("scout", False))
        accounts.append(acc)
        if acc.scout:
            scouts.append(acc)

    if len(scouts) != 1:
        print(f"config error: нужен ровно 1 аккаунт со scout=true, найдено {len(scouts)} — выход")
        return
    scout = scouts[0]

    # Аккаунт без product_ids нечего покупать — в работе не участвует
    usable = []
    for a in accounts:
        if a.product_ids:
            usable.append(a)
        else:
            print(f"  {a.email}: пустой product_ids — аккаунт пропущен")

    if not usable:
        print("config error: ни у одного аккаунта нет product_ids — выход")
        return

    # Разведчику нужен товар для опроса. Если у scout из конфига товаров нет —
    # роль уходит следующему аккаунту ниже (если ниже некому — первому сверху).
    # Конфиг при этом не меняется, только текущий запуск.
    if not scout.product_ids:
        below = [a for a in accounts[accounts.index(scout) + 1:] if a.product_ids]
        scout.scout = False
        scout = below[0] if below else usable[0]
        scout.scout = True
        print(f"  scout без product_ids -> разведчиком назначен {scout.email}")

    accounts = usable

    print(f"=== FAST BOT | accounts={len(accounts)} | {h:02d}:{m:02d}:{s:02d} MSK ===")
    for a in accounts:
        print(f"  {a.email}{' [scout]' if a.scout else ''}: products={a.product_ids}")
    print()

    ntp_offset = get_ntp_offset()

    # Открываем сессии
    await asyncio.gather(*[a.open() for a in accounts])

    # Логин ВСЕХ аккаунтов параллельно
    print(f"Logging in {len(accounts)} accounts in parallel...")
    login_ok = await asyncio.gather(*[a.login() for a in accounts])
    ready = [a for a, ok in zip(accounts, login_ok) if ok]

    if not ready:
        print("No accounts ready, exiting")
        for a in accounts:
            await a.close()
        return

    print(f"{len(ready)}/{len(accounts)} ready\n")

    if scout not in ready:
        print(f"Scout {scout.email} не залогинился — выход")
        for a in accounts:
            await a.close()
        return

    # Если до дропа больше REFRESH_MARGIN — ждём кусками по NTP_RESYNC_INTERVAL,
    # каждый раз переопрашивая NTP (часы могут дрейфовать за часы ожидания),
    # пока не останется T-3мин, потом обновляем сессии (куки истекают через 2
    # часа). Если уже изначально ближе — ничего не трогаем.
    remaining = seconds_until_msk(h, m, s, ntp_offset)
    if remaining > REFRESH_MARGIN:
        print(f"  до дропа {remaining:.0f}s — ждём с пересверкой NTP каждые {NTP_RESYNC_INTERVAL}s")
        while True:
            remaining = seconds_until_msk(h, m, s, ntp_offset)
            if remaining <= REFRESH_MARGIN:
                break
            chunk = min(NTP_RESYNC_INTERVAL, remaining - REFRESH_MARGIN)
            await asyncio.sleep(chunk)
            ntp_offset = get_ntp_offset()
            remaining = seconds_until_msk(h, m, s, ntp_offset)
            print(f"  пересверка NTP: офсет={ntp_offset:+.3f}s, до дропа {remaining:.0f}s")

        print(f"Обновляем сессии (повторный логин) {len(ready)} аккаунтов...")
        refresh_ok = await asyncio.gather(*[a.login() for a in ready])
        ready = [a for a, ok in zip(ready, refresh_ok) if ok]

        if not ready:
            print("Ни один аккаунт не смог обновить сессию, exiting")
            for a in accounts:
                await a.close()
            return
        if scout not in ready:
            print(f"Scout {scout.email} не смог обновить сессию — выход")
            for a in accounts:
                await a.close()
            return

    # Ждём нужного времени
    wait_for_msk(h, m, s, ntp_offset)

    # Опрос со scout-аккаунта (3 параллельных воркера) по его первому товару —
    # это сигнал "дроп открылся", а не гонка за конкретным товаром
    poller = scout
    print(f"Polling ({POLL_WORKERS} workers) via {poller.email} ...")
    if not await poller.poll_until_added(poller.product_ids[0]):
        print("Timeout — product never available")
        for a in accounts:
            await a.close()
        return

    # Scout уже добавил свой первый товар -> добирает остаток списка и checkout
    # Остальные — весь свой список + checkout, всё параллельно
    async def scout_finish() -> bool:
        await poller.add_products(poller.product_ids[1:])
        return await poller.checkout()   # корзина заведомо не пуста

    async def add_all_then_checkout(acc: Account) -> bool:
        results = await acc.add_products(acc.product_ids)
        if not any(results):
            print(f"  SKIP checkout {acc.email}: ничего не добавилось")
            return False
        return await acc.checkout()

    tasks = [scout_finish()] + [add_all_then_checkout(a) for a in ready if a is not poller]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    success = sum(1 for r in results if r is True)

    print(f"\n=== {success}/{len(ready)} successful checkouts ===")

    save_history_record(accounts, ready, success)

    for a in accounts:
        await a.close()


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\nStopped")
    except Exception as e:
        import traceback
        print(f"\nFatal: {e}")
        traceback.print_exc()
