# vpn_bot/cryptopay.py
from typing import Optional, Tuple
import requests
from vpn_bot.config import CRYPTOBOT_TOKEN

API_URL = "https://pay.crypt.bot/api/"
HEADERS = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}


class CryptoPayError(Exception):
    pass


def get_me() -> dict:
    """Проверка токена приложения. Возвращает dict с инфой об аппе."""
    url = API_URL + "getMe"
    resp = requests.get(url, headers=HEADERS, timeout=15).json()
    if not resp.get("ok"):
        raise CryptoPayError(resp)
    return resp["result"]


def create_invoice(
    amount: float,
    asset: str = "USDT",
    description: str = "VPN подписка",
    payload: Optional[str] = None,
    expires_in: Optional[int] = 15 * 60,  # 15 минут
) -> Tuple[str, int]:
    """
    Создаёт счёт. Возвращает (invoice_url, invoice_id).
    """
    url = API_URL + "createInvoice"
    body = {
        "currency_type": "crypto",
        "asset": asset,
        "amount": str(amount),  # API требует строку
        "description": description,
        "allow_comments": False,
        "allow_anonymous": True,
    }
    if payload:
        body["payload"] = payload
    if expires_in:
        body["expires_in"] = expires_in

    resp = requests.post(url, json=body, headers=HEADERS, timeout=15).json()
    if not resp.get("ok"):
        raise CryptoPayError(resp)
    item = resp["result"]
    invoice_url = item.get("bot_invoice_url") or item.get("pay_url")
    return invoice_url, item["invoice_id"]


def get_invoice_status(invoice_id: int) -> str:
    """
    Получает статус счёта: active / paid / expired
    """
    url = API_URL + "getInvoices"
    params = {"invoice_ids": invoice_id}
    resp = requests.get(url, params=params, headers=HEADERS, timeout=15).json()
    if not resp.get("ok"):
        raise CryptoPayError(resp)
    items = resp["result"]["items"]
    if not items:
        raise CryptoPayError(f"Invoice {invoice_id} not found")
    return items[0]["status"]
