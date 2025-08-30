import os
from dotenv import load_dotenv

print("📦 Загружаем .env файл...")
load_dotenv()

print("🔍 Список переменных окружения:")
for k, v in os.environ.items():
    if "TOKEN" in k or "BOT" in k:
        print(f"{k} = {v}")

BOT_TOKEN = os.getenv("BOT_TOKEN")
print(f"🎯 BOT_TOKEN из os.getenv: {BOT_TOKEN}")

if not BOT_TOKEN:
    raise ValueError("❌ Переменная BOT_TOKEN не найдена в .env файле!")

import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CRYPTOBOT_TOKEN = os.getenv("CRYPTOBOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не найден в .env")
if not CRYPTOBOT_TOKEN:
    raise RuntimeError("CRYPTOBOT_TOKEN не найден в .env")
