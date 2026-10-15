"""
.env рядом с проектом — секреты, которые не должны попасть в git
(токен Telegram-бота, chat id, адрес Cloudflare Worker).

Формат: KEY=VALUE построчно, # — комментарий. Без зависимостей.
"""
import os

ENV_FILE = ".env"

# ключ в .env -> поле config["telegram"]
TELEGRAM_KEYS = {
    "TG_BOT_TOKEN": "bot_token",
    "TG_CHAT_ID": "chat_id",
    "TG_API_BASE": "api_base",
}


def read_env(path: str = ENV_FILE) -> dict:
    values = {}
    if not os.path.exists(path):
        return values
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def write_env(updates: dict, path: str = ENV_FILE):
    """Обновляет ключи в .env, сохраняя остальные строки и комментарии."""
    lines = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
    left = dict(updates)
    for i, line in enumerate(lines):
        key = line.partition("=")[0].strip()
        if "=" in line and not line.lstrip().startswith("#") and key in left:
            lines[i] = f"{key}={left.pop(key)}"
    lines += [f"{k}={v}" for k, v in left.items()]
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)  # секреты — только владельцу
    except OSError:
        pass


def telegram_from_env(path: str = ENV_FILE) -> dict:
    """Поля telegram из .env (только непустые)."""
    env = read_env(path)
    out = {}
    for env_key, field in TELEGRAM_KEYS.items():
        if env.get(env_key):
            value = env[env_key]
            if field == "chat_id" and value.lstrip("-").isdigit():
                value = int(value)
            out[field] = value
    return out
