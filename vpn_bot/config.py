# vpn_bot/config.py
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CRYPTOBOT_TOKEN = os.getenv("CRYPTOBOT_TOKEN")

# Параметры подписки/оплаты
PRICE_USDT = float(os.getenv("PRICE_USDT", "5"))
SUB_DAYS = int(os.getenv("SUB_DAYS", "7"))

# Тестовый режим и владелец
DEV_MODE = os.getenv("DEV_MODE", "false").lower() in ("1", "true", "yes", "on")
OWNER_ID = int(os.getenv("OWNER_ID", "0")) if os.getenv("OWNER_ID") else None

missing = []
if not BOT_TOKEN:
    missing.append("BOT_TOKEN")
if not CRYPTOBOT_TOKEN:
    missing.append("CRYPTOBOT_TOKEN")
if missing:
    raise RuntimeError(
        "Не найдены переменные в .env: " + ", ".join(missing) +
        ". Создай/проверь файл .env на основе .env.example"
    )
