# vpn_bot/config.py
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CRYPTOBOT_TOKEN = os.getenv("CRYPTOBOT_TOKEN")

TG_BOT_USERNAME = "thatvpn_bot"

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

# ... существующие импорты и load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CRYPTOBOT_TOKEN = os.getenv("CRYPTOBOT_TOKEN")

PRICE_USDT = float(os.getenv("PRICE_USDT", "5"))
SUB_DAYS = int(os.getenv("SUB_DAYS", "7"))

DEV_MODE = os.getenv("DEV_MODE", "false").lower() in ("1", "true", "yes", "on")
OWNER_ID = int(os.getenv("OWNER_ID", "0")) if os.getenv("OWNER_ID") else None

# ↓↓↓ новое
SERVER_HOST = os.getenv("SERVER_HOST", "127.0.0.1")
SERVER_PORT = int(os.getenv("SERVER_PORT", "1194"))

# ... проверки missing как были

WG_ENDPOINT_HOST = os.getenv("WG_ENDPOINT_HOST", "127.0.0.1")
WG_ENDPOINT_PORT = int(os.getenv("WG_ENDPOINT_PORT", "51820"))
WG_ALLOWED_IPS = os.getenv("WG_ALLOWED_IPS", "0.0.0.0/0, ::/0")
WG_DNS = os.getenv("WG_DNS", "1.1.1.1")
WG_SERVER_PUBLIC_KEY = os.getenv("WG_SERVER_PUBLIC_KEY", "")

# --- WireGuard addressing (для клиентов) ---
# Пример: 10.66.0.X/32 — будут выдаваться адреса .2, .3, .4, ...
WG_ADDRESS_PREFIX = os.getenv("WG_ADDRESS_PREFIX", "10.66.0")
WG_ADDRESS_CIDR = int(os.getenv("WG_ADDRESS_CIDR", "32"))
WG_START_HOST = int(os.getenv("WG_START_HOST", "2"))  # с какого host-октета начинать
