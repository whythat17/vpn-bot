# VPN Bot (Telegram + CryptoBot)

Коммерческий VPN-бот с оплатой через **CryptoBot**, управлением подпиской и выдачей VPN-конфига **напрямую в диалог** (без телеграм-канала).

## Возможности
- `/buy` — создаёт счёт в CryptoBot (USDT).
- `/check <invoice_id>` — проверяет оплату и **активирует подписку**.
- `/vpn` — выдаёт файл `vpn.ovpn`, если подписка активна.
- `/status` — показывает статус подписки.
- DEV-режим (для тестов без реальной оплаты):  
  - `/dev_paid <invoice_id>` — имитация «оплачено».  
  - `/grant <days>` — вручную выдать подписку на N дней.

---

## Требования
- **Python 3.11** (рекомендуется)  
  `python-telegram-bot==20.7` официально поддерживает до 3.11.
- Аккаунт Telegram + бот от **@BotFather** (BOT_TOKEN).
- Приложение в **@CryptoBot** → Crypto Pay API (CRYPTOBOT_TOKEN).

---

## Установка (Windows, PowerShell)
```powershell
# 1) Клонировать репозиторий (или скачайте ZIP)
git clone https://github.com/whythat17/vpn-bot.git
cd vpn-bot

# 2) Создать виртуальное окружение на Python 3.11
py -3.11 -m venv .venv
.venv\Scripts\activate

# 3) Установить зависимости
pip install -r requirements.txt

macOS / Linux (аналогично):

python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt