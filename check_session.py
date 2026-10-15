#!/usr/bin/env python3
"""
Проверка: переживает ли сессия бота падение сайта.

  python check_session.py                 # первый аккаунт из config.json
  python check_session.py --email a@b.ru  # конкретный аккаунт

Логинится так же, как бот (Account из run_fast), находит признак "залогинен"
(сравнивает ответы залогиненной и анонимной сессии), потом каждые
CHECK_INTERVAL секунд проверяет сайт. Когда сайт падает и поднимается —
делает запрос СО СТАРЫМИ cookies и пишет вердикт: сессия жива или потеряна.
Ничего не покупает и не добавляет в корзину — только GET-запросы.
Остановка — Ctrl+C.
"""
import asyncio
import json
import sys
import time
from datetime import datetime

import aiohttp
from yarl import URL

from run_fast import BASE, Account, _quiet_exception_handler

CHECK_INTERVAL = 2      # секунд между проверками
REQUEST_TIMEOUT = 5     # секунд ждём ответ на одну проверку
HEARTBEAT = 60          # раз во сколько секунд писать "всё ок", пока сайт работает

# Кандидаты на "страницу, которая отличается для залогиненного" — только GET
CANDIDATES = [
    "/",
    "/personal/",
    "/api/v1/auth/login/modal",
    "/api/v1/user",
    "/api/v1/auth/user",
    "/api/v2/checkout/",
]


def now() -> str:
    return datetime.now().strftime("%H:%M:%S")


def log(msg: str):
    print(f"[{now()}] {msg}", flush=True)


async def signature(session: aiohttp.ClientSession, path: str, proxy, markers: list):
    """
    Короткий "отпечаток" ответа: статус, куда редиректнуло, есть ли в теле
    признаки входа (email, "Выйти", logout), для JSON — success и ключи.
    Бросает исключение, если сайт не ответил; site_down=True при 5xx.
    """
    async with session.get(
        f"{BASE}{path}", ssl=False, proxy=proxy,
        timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
    ) as r:
        body = await r.text(errors="replace")
        sig = {
            "status": r.status,
            "final_path": r.url.path,
            "markers": {m: (m.lower() in body.lower()) for m in markers},
        }
        try:
            d = json.loads(body)
            if isinstance(d, dict):
                sig["json_keys"] = sorted(d.keys())
                sig["json_success"] = d.get("success")
        except ValueError:
            pass
        return sig, r.status >= 500


async def find_discriminators(acc: Account, markers: list) -> dict:
    """Пути, где ответ залогиненной сессии отличается от анонимной."""
    found = {}
    anon = aiohttp.ClientSession(
        headers=dict(acc.session.headers), trust_env=False,
    )
    # как у бота — отличие от залогиненной сессии только во входе
    anon.cookie_jar.update_cookies({"policy": "true"}, URL(BASE))
    try:
        for path in CANDIDATES:
            try:
                auth_sig, auth_down = await signature(acc.session, path, acc.proxy, markers)
                anon_sig, anon_down = await signature(anon, path, acc.proxy, markers)
            except Exception as e:
                log(f"  {path}: ошибка {type(e).__name__}: {e}")
                continue
            if auth_down or anon_down:
                log(f"  {path}: 5xx — пропускаем")
                continue
            if auth_sig != anon_sig:
                found[path] = {"auth": auth_sig, "anon": anon_sig}
                log(f"  {path}: ОТЛИЧАЕТСЯ -> подходит как признак входа")
            else:
                log(f"  {path}: одинаково для залогиненного и анонима")
    finally:
        await anon.close()
    return found


async def check(acc: Account, probes: dict, markers: list):
    """
    Возвращает ("down", err) | ("alive", None) | ("lost", None) | ("unclear", details).
    """
    results = {}
    for path, base in probes.items():
        try:
            sig, down = await signature(acc.session, path, acc.proxy, markers)
        except Exception as e:
            return "down", f"{type(e).__name__}: {e}"
        if down:
            return "down", f"HTTP {sig['status']} на {path}"
        if sig == base["auth"]:
            results[path] = "alive"
        elif sig == base["anon"]:
            results[path] = "lost"
        else:
            results[path] = f"unclear: {sig}"

    values = set(results.values())
    if values == {"alive"}:
        return "alive", None
    if values == {"lost"}:
        return "lost", None
    return "unclear", results


async def main():
    asyncio.get_running_loop().set_exception_handler(_quiet_exception_handler)

    with open("config.json", encoding="utf-8") as f:
        cfg = json.load(f)
    accounts = cfg["accounts"]
    if "--email" in sys.argv:
        email = sys.argv[sys.argv.index("--email") + 1]
        accounts = [a for a in accounts if a["email"] == email]
        if not accounts:
            print(f"аккаунт {email} не найден в config.json")
            return
    a = accounts[0]
    acc = Account(a["email"], a["password"], [], a.get("proxy") or None)
    markers = [acc.email, acc.email.replace("@", "%40"), "Выйти", "logout"]

    await acc.open()
    try:
        log(f"Логин {acc.email} (как бот)...")
        if not await acc.login():
            log("Логин не прошёл — проверь, открывается ли сайт и верен ли пароль")
            return

        log("Ищем признак входа (сравниваем с анонимной сессией):")
        probes = await find_discriminators(acc, markers)
        if not probes:
            log("Не нашёл ни одной страницы, которая отличается для залогиненного.")
            log("Либо логин на самом деле не прошёл, либо нужны другие страницы — пришли этот лог.")
            return

        log(f"Признаки входа: {', '.join(probes)}")
        log(f"Сессия жива. Следим за сайтом каждые {CHECK_INTERVAL}s — жди падения (Ctrl+C — стоп)\n")

        down_since = None
        last_heartbeat = time.monotonic()
        while True:
            state, info = await check(acc, probes, markers)

            if state == "down":
                if down_since is None:
                    down_since = time.monotonic()
                    log(f"!! САЙТ УПАЛ ({info}) — ждём, пока поднимется...")
            else:
                if down_since is not None:
                    dur = time.monotonic() - down_since
                    log(f"Сайт поднялся (лежал {dur:.0f}s). Проверка со СТАРЫМИ cookies:")
                    down_since = None
                    verdict_prefix = ">>> ПОСЛЕ ПАДЕНИЯ: "
                else:
                    verdict_prefix = ">>> БЕЗ ПАДЕНИЯ: "

                if state == "alive":
                    if verdict_prefix.startswith(">>> ПОСЛЕ"):
                        log(verdict_prefix + "СЕССИЯ ЖИВА — cookies не истекли")
                    elif time.monotonic() - last_heartbeat > HEARTBEAT:
                        log("  ok: сайт работает, сессия жива")
                        last_heartbeat = time.monotonic()
                elif state == "lost":
                    log(verdict_prefix + "СЕССИЯ ПОТЕРЯНА — сайт видит нас как незалогиненных")
                    log("Остановка: дальше следить этой сессией бессмысленно.")
                    return
                else:
                    log(verdict_prefix + f"НЕПОНЯТНО — ответ не как раньше: {info}")

            await asyncio.sleep(CHECK_INTERVAL)
    finally:
        await acc.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped")
