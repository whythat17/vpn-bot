# users.py

import json
from datetime import datetime, timedelta

USERS_FILE = 'users.json'
users = {}  # глобальный словарь пользователей

def load_users():
    global users
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
            for user_id, data in raw_data.items():
                users[int(user_id)] = {
                    "subscribed": data["subscribed"],
                    "subscription_start": datetime.fromisoformat(data["subscription_start"]) if data["subscription_start"] else None,
                    "subscription_end": datetime.fromisoformat(data["subscription_end"]) if data["subscription_end"] else None
                }
        print(f"✅ Загружено пользователей: {len(users)}")
    except FileNotFoundError:
        print("⚠️ Файл users.json не найден. Будет создан при первом сохранении.")
        users = {}

def save_users():
    data = {}
    for user_id, info in users.items():
        data[str(user_id)] = {
            "subscribed": info["subscribed"],
            "subscription_start": info["subscription_start"].isoformat() if info["subscription_start"] else None,
            "subscription_end": info["subscription_end"].isoformat() if info["subscription_end"] else None
        }
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def register_user(user_id):
    if user_id not in users:
        users[user_id] = {
            "subscribed": False,
            "subscription_start": None,
            "subscription_end": None
        }
        print(f"👤 Новый пользователь зарегистрирован: {user_id}")
        save_users()

def subscribe_user(user_id, days=7):
    now = datetime.now()
    if user_id in users:
        users[user_id]["subscribed"] = True
        users[user_id]["subscription_start"] = now
        users[user_id]["subscription_end"] = now + timedelta(days=days)
        print(f"💳 Подписка оформлена: {user_id}, до {users[user_id]['subscription_end']}")
        save_users()

def check_subscription(user_id):
    if user_id in users:
        end = users[user_id]["subscription_end"]
        if end and datetime.now() < end:
            return True
    return False
