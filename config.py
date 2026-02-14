import os

APP_VERSION = "mvp-0.1.0"

def get_token() -> str:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "Не найден TELEGRAM_BOT_TOKEN. "
            "Задайте переменную окружения TELEGRAM_BOT_TOKEN."
        )
    return token
