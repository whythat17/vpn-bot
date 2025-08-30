# vpn_bot/config.py
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CRYPTOBOT_TOKEN = os.getenv("CRYPTOBOT_TOKEN")

# Параметры подписки/оплаты
# Цена за период (в USDT) и длительность подписки (в днях)
PRICE_USDT = float(os.getenv("PRICE_USDT", "5"))
SUB_DAYS = int(os.getenv("SUB_DAYS", "7"))

# Валидация обязательных переменных
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
