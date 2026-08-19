"""
Проверка и управление получателем/способом доставки аккаунта на f-ariel.ru.

Эндпоинты подтверждены реальными трейсами запросов пользователя:
  GET  /api/v1/recipient/list                    -> {"success":true,"data":{"items":[...]}}
  GET  /api/v1/delivery/list                      -> {"success":true,"data":{"items":[...]}}
  POST /api/v1/recipient/create  {name,last_name,phone_number} (поля выведены
       из ответа API — эхо запроса; точное тело запроса не было в трейсе)
  POST /api/v1/recipient/{identifier}/select       -> без тела, id в пути (подтверждено трейсом)
  POST /api/v1/delivery/select   {"type": ..., "identifier": ...} (подтверждено
       трейсом тела запроса — байт в байт совпадает с Content-Length: 50)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import aiohttp
from run_fast import Account

BASE = "https://f-ariel.ru"
_TIMEOUT = aiohttp.ClientTimeout(total=10)


async def _fetch_list(acc: Account, path: str) -> list:
    try:
        async with acc.session.get(
            f"{BASE}{path}", ssl=False, proxy=acc.proxy, timeout=_TIMEOUT,
        ) as r:
            d = await r.json(content_type=None)
            if d.get("success"):
                return d.get("data", {}).get("items", [])
    except Exception:
        pass
    return []


async def _state(acc: Account) -> dict:
    recipients = await _fetch_list(acc, "/api/v1/recipient/list")
    delivery = await _fetch_list(acc, "/api/v1/delivery/list")
    return {"recipients": recipients, "delivery": delivery}


async def check_account(email: str, password: str, proxy: str = None) -> dict:
    acc = Account(email, password, [], proxy)
    await acc.open()
    try:
        if not await acc.login():
            return {"ok": False, "error": "Не удалось войти в аккаунт"}
        return {"ok": True, "error": None, **await _state(acc)}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    finally:
        await acc.close()


async def create_recipient(email, password, proxy, name, last_name, phone_number) -> dict:
    acc = Account(email, password, [], proxy)
    await acc.open()
    try:
        if not await acc.login():
            return {"ok": False, "error": "Не удалось войти в аккаунт"}
        async with acc.session.post(
            f"{BASE}/api/v1/recipient/create",
            json={"name": name, "last_name": last_name, "phone_number": phone_number},
            ssl=False, proxy=acc.proxy, timeout=_TIMEOUT,
        ) as r:
            resp = await r.json(content_type=None)
        if not resp.get("success"):
            return {"ok": False, "error": str(resp.get("message") or resp.get("errors") or resp)}
        return {"ok": True, "error": None, **await _state(acc)}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    finally:
        await acc.close()


async def select_recipient(email, password, proxy, recipient_identifier) -> dict:
    acc = Account(email, password, [], proxy)
    await acc.open()
    try:
        if not await acc.login():
            return {"ok": False, "error": "Не удалось войти в аккаунт"}
        async with acc.session.post(
            f"{BASE}/api/v1/recipient/{recipient_identifier}/select",
            ssl=False, proxy=acc.proxy, timeout=_TIMEOUT,
        ) as r:
            resp = await r.json(content_type=None)
        if not resp.get("success"):
            return {"ok": False, "error": str(resp)}
        return {"ok": True, "error": None, **await _state(acc)}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    finally:
        await acc.close()


async def select_delivery(email, password, proxy, delivery_type, delivery_identifier) -> dict:
    acc = Account(email, password, [], proxy)
    await acc.open()
    try:
        if not await acc.login():
            return {"ok": False, "error": "Не удалось войти в аккаунт"}
        async with acc.session.post(
            f"{BASE}/api/v1/delivery/select",
            json={"type": delivery_type, "identifier": delivery_identifier},
            ssl=False, proxy=acc.proxy, timeout=_TIMEOUT,
        ) as r:
            resp = await r.json(content_type=None)
        if not resp.get("success"):
            return {"ok": False, "error": str(resp)}
        return {"ok": True, "error": None, **await _state(acc)}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    finally:
        await acc.close()
