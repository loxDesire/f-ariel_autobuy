"""Чтение/запись config.json. Незнакомые ключи сохраняются как есть."""
import json
import os

DEFAULT_CONFIG = {
    "time": {"hour": 10, "minute": 59, "second": 50},
    "mode": "scheduled",
    "accounts": [],
    # токен, chat id и адрес Worker — в .env (см. core/envfile.py)
    "telegram": {"enabled": False, "name": ""},
}


def coerce_pid(pid):
    """API принимает число, не строку ("388" -> 388)."""
    s = str(pid).strip()
    return int(s) if s.isdigit() else s


class ConfigStore:
    def __init__(self, path: str):
        self.path = path
        self.data: dict = {}
        self.load()

    def load(self) -> dict:
        if os.path.exists(self.path):
            with open(self.path, encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            self.data = json.loads(json.dumps(DEFAULT_CONFIG))
        # недостающие разделы — из шаблона, существующие не трогаем
        for key, value in DEFAULT_CONFIG.items():
            if key not in self.data:
                self.data[key] = json.loads(json.dumps(value))
        for key, value in DEFAULT_CONFIG["telegram"].items():
            self.data["telegram"].setdefault(key, value)
        return self.data

    def save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    # удобные геттеры
    @property
    def accounts(self) -> list:
        return self.data["accounts"]

    @property
    def telegram(self) -> dict:
        return self.data["telegram"]

    @property
    def drop_time(self) -> tuple:
        t = self.data["time"]
        return t.get("hour", 0), t.get("minute", 0), t.get("second", 0)
