import requests
from config import CRYPTOBOT_TOKEN

API_URL = "https://pay.crypt.bot/api/"
HEADERS = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}

class CryptoPayError(Exception):
    pass

def get_me():
    """Проверка токена приложения (опционально). Возвращает dict с информацией об аппе."""
    url = API_URL + "getMe"
    resp = requests.get(url, headers=HEADERS).json()
    if not resp.get("ok"):
        raise CryptoPayError(resp)
    return resp["result"]

def create_invoice(amount: float, asset: str = "USDT", description: str = "VPN подписка на 7 дней",
                   payload: str | None = None, expires_in: int | None = None):
    """
    Создаёт счёт на оплату.
    Возвращает (invoice_url, invoice_id).
    """
    url = API_URL + "createInvoice"
    body = {
        "currency_type": "crypto",   # тип цены — крипто
        "asset": asset,              # валюта платежа (USDT/TON/BTC/…)
        "amount": str(amount),       # строкой, как требует API
        "description": description,
        "allow_comments": False,
        "allow_anonymous": True
    }
    if payload:
        body["payload"] = str(payload)   # любые твои данные (например user_id)
    if expires_in:
        body["expires_in"] = int(expires_in)

    resp = requests.post(url, json=body, headers=HEADERS).json()
    if not resp.get("ok"):
        raise CryptoPayError(resp)

    item = resp["result"]
    # Новые поля для ссылок — используем bot_invoice_url (pay_url — устарел)
    invoice_url = item.get("bot_invoice_url") or item.get("pay_url")
    return invoice_url, item["invoice_id"]

def get_invoice_status(invoice_id: int) -> str:
    """
    Возвращает статус счёта: active / paid / expired
    """
    url = API_URL + "getInvoices"
    params = {"invoice_ids": invoice_id}
    resp = requests.get(url, params=params, headers=HEADERS).json()
    if not resp.get("ok"):
        raise CryptoPayError(resp)
    items = resp["result"]["items"]
    if not items:
        raise CryptoPayError(f"Invoice {invoice_id} not found")
    return items[0]["status"]
