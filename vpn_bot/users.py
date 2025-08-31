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
    subscription_start: Optional[str] = None  # ISO
    subscription_end: Optional[str] = None    # ISO
    wg_private_key: Optional[str] = None
    wg_public_key: Optional[str] = None
    wg_address: Optional[str] = None  # например "10.66.0.2/32"


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

def assigned_wg_addresses(users: Dict[int, User]) -> set[str]:
    return {u.wg_address for u in users.values() if getattr(u, "wg_address", None)}

def next_wg_address(users: Dict[int, User], prefix: str, cidr: int, start_host: int = 2) -> str:
    """
    Ищет свободный адрес в подсети prefix.X/cidr, начиная с start_host.
    Пример: prefix="10.66.0", cidr=32 -> 10.66.0.2/32, 10.66.0.3/32, ...
    """
    used = assigned_wg_addresses(users)
    host = start_host
    while host < 255:  # простой линейный перебор
        candidate = f"{prefix}.{host}/{cidr}"
        if candidate not in used:
            return candidate
        host += 1
    raise RuntimeError("Не осталось свободных WG адресов в пуле")

def set_wg_profile(users: Dict[int, User], user_id: int, priv: str, pub: str, addr: str) -> None:
    u = users.setdefault(user_id, User())
    u.wg_private_key = priv
    u.wg_public_key = pub
    u.wg_address = addr
    save_users(users)



def is_subscription_active(users: Dict[int, User], user_id: int) -> bool:
    u = users.get(user_id)
    if not u or not u.subscription_end:
        return False
    end = datetime.fromisoformat(u.subscription_end)
    return datetime.now(timezone.utc) < end
