# vpn_bot/users.py
from __future__ import annotations
import json, os, tempfile
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

BASE_DIR = os.path.dirname(__file__)
USERS_FILE = os.path.join(BASE_DIR, "users.json")


@dataclass
class User:
    subscribed: bool = False
    subscription_start: Optional[str] = None  # ISO формат
    subscription_end: Optional[str] = None    # ISO формат


def _to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def load_users() -> Dict[int, User]:
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)
    users: Dict[int, User] = {}
    for k, v in raw.items():
        users[int(k)] = User(**v)
    return users


def save_users(users: Dict[int, User]) -> None:
    tmp_fd, tmp_path = tempfile.mkstemp(prefix="users_", suffix=".json", dir=BASE_DIR)
    os.close(tmp_fd)
    data = {str(uid): asdict(u) for uid, u in users.items()}
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, USERS_FILE)


def register_user(users: Dict[int, User], user_id: int) -> None:
    users.setdefault(user_id, User())
    save_users(users)


def activate_subscription(users: Dict[int, User], user_id: int, days: int) -> None:
    start = datetime.now(timezone.utc)
    end = start + timedelta(days=days)
    u = users.setdefault(user_id, User())
    u.subscribed = True
    u.subscription_start = _to_iso(start)
    u.subscription_end = _to_iso(end)
    save_users(users)


def is_subscription_active(users: Dict[int, User], user_id: int) -> bool:
    u = users.get(user_id)
    if not u or not u.subscription_end:
        return False
    end = datetime.fromisoformat(u.subscription_end)
    return datetime.now(timezone.utc) < end
