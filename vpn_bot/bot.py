# vpn_bot/bot.py
import time
import logging, os
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from vpn_bot.config import BOT_TOKEN, PRICE_USDT, SUB_DAYS, DEV_MODE, OWNER_ID
from vpn_bot.cryptopay import create_invoice, get_invoice_status
from vpn_bot.users import (
    load_users,
    register_user,
    activate_subscription,
    is_subscription_active,
)

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("vpn_bot")

# Загружаем пользователей при старте
USERS = load_users()

# Простейший анти-спам: кулдаун 2 сек на пользователя
LAST_CALL: dict[int, float] = {}
COOLDOWN_SEC = 2.0

async def _throttle(update: Update) -> bool:
    """Возвращает True, если надо заблокировать обработку из-за кулдауна."""
    uid = update.effective_user.id if update.effective_user else 0
    now = time.time()
    last = LAST_CALL.get(uid, 0.0)
    if now - last < COOLDOWN_SEC:
        # молча игнорируем или отправляем мягкий ответ
        if update.message:
            await update.message.reply_text("⏳ Слишком часто. Подождите пару секунд.")
        return True
    LAST_CALL[uid] = now
    return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _throttle(update): return
    user_id = update.effective_user.id
    register_user(USERS, user_id)
    await update.message.reply_text(
          "👋 Привет! Я бот для доступа к VPN.\n\n"
          "Доступные команды:\n"
    "/buy — создать счёт на оплату\n"
    "/check <invoice_id> — проверить оплату\n"
    "/status — статус подписки\n"
    "/vpn — получить VPN-конфиг (если подписка активна)"
)



async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _throttle(update): return
    user_id = update.effective_user.id
    description = f"VPN подписка на {SUB_DAYS} дней"
    try:
        url, invoice_id = create_invoice(
            amount=PRICE_USDT,
            asset="USDT",
            description=description,
            payload=str(user_id),
            expires_in=15 * 60,  # 15 минут
        )
    except Exception as e:
        log.exception("Ошибка create_invoice")
        await update.message.reply_text(f"❌ Не удалось создать счёт: {e}")
        return

    await update.message.reply_text(
        f"💳 Счёт на *{PRICE_USDT} USDT* создан.\n\n"
        f"🔗 Оплатить: {url}\n"
        f"🧾 ID счёта: `{invoice_id}`\n\n"
        f"После оплаты отправьте:\n"
        f"`/check {invoice_id}`",
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )


async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _throttle(update): return
    args = context.args or []
    if len(args) != 1:
        await update.message.reply_text("Использование: `/check <invoice_id>`", parse_mode="Markdown")
        return

    invoice_id_raw = args[0].strip()
    if not invoice_id_raw.isdigit():
        await update.message.reply_text("❗ ID счёта должен быть числом. Пример: `/check 32714801`", parse_mode="Markdown")
        return

    user_id = update.effective_user.id
    # Идемпотентность: если уже активна — не дёргаем API
    if is_subscription_active(USERS, user_id):
        await update.message.reply_text("✅ Подписка уже активна. Используйте /vpn для получения конфига.")
        return

    try:
        status = get_invoice_status(int(invoice_id_raw))
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка проверки счёта: {e}")
        return

    if status == "paid":
        activate_subscription(USERS, user_id, days=SUB_DAYS)
        await update.message.reply_text("✅ Оплата получена! Подписка активирована.")
    elif status == "active":
        await update.message.reply_text("🕓 Счёт пока не оплачен. Если оплатили только что — подождите минуту и повторите /check.")
    elif status == "expired":
        await update.message.reply_text("⌛ Срок действия счёта истёк. Создайте новый командой /buy.")
    else:
        await update.message.reply_text(f"Статус счёта: {status}")



async def vpn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _throttle(update): return
    user_id = update.effective_user.id
    if is_subscription_active(USERS, user_id):
        cfg_dir = os.path.join(os.path.dirname(__file__), "vpn_configs")
        file_path = os.path.join(cfg_dir, "default.ovpn")
        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                await update.message.reply_document(
                    document=f,
                    filename="vpn.ovpn",
                    caption="🔐 Ваш VPN-конфиг",
                )
        else:
            await update.message.reply_text("⚠️ Конфиг не найден. Создайте файл vpn_bot/vpn_configs/default.ovpn")
    else:
        await update.message.reply_text("⛔ У вас нет активной подписки. Создайте счёт командой /buy.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _throttle(update): return
    user_id = update.effective_user.id
    u = USERS.get(user_id)
    if not u:
        await update.message.reply_text("Вы ещё не начинали. Наберите /start")
        return

    # если нет даты окончания — подписки нет
    if not u.subscription_end:
        await update.message.reply_text(
            "⚠️ Подписка не активна.\n"
            "Создайте счёт: /buy\n"
            "После оплаты — проверьте: /check <invoice_id>"
        )
        return

    try:
        end = datetime.fromisoformat(u.subscription_end)
    except Exception:
        await update.message.reply_text("Не удалось прочитать дату подписки. Попробуйте /buy заново.")
        return

    now = datetime.utcnow().replace(tzinfo=end.tzinfo)
    if now < end:
        until = end.strftime("%Y-%m-%d %H:%M UTC")
        await update.message.reply_text(
            "✅ Подписка активна.\n"
            f"Действует до: {until}\n\n"
            "Чтобы получить конфиг, отправьте: /vpn"
        )
    else:
        await update.message.reply_text(
            "⛔ Подписка истекла.\n"
            "Создайте новый счёт: /buy"
        )

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Неизвестная команда. Доступные: /buy, /check, /vpn, /status")


# --- DEV команды (работают только если DEV_MODE=True и пишет OWNER_ID) ---
async def dev_paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _throttle(update): return
    if not DEV_MODE or update.effective_user.id != OWNER_ID:
        return
    user_id = update.effective_user.id
    args = context.args or []
    if len(args) != 1:
        await update.message.reply_text("Использование (dev): /dev_paid <invoice_id>")
        return
    activate_subscription(USERS, user_id, days=SUB_DAYS)
    await update.message.reply_text("✅ (DEV) Оплата имитирована. Подписка активирована.")

async def grant(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _throttle(update): return
    if not DEV_MODE or update.effective_user.id != OWNER_ID:
        return
    args = context.args or []
    days = int(args[0]) if args else SUB_DAYS
    user_id = update.effective_user.id
    activate_subscription(USERS, user_id, days=days)
    await update.message.reply_text(f"🎁 (DEV) Подписка выдана на {days} дн.")

from telegram.error import TelegramError

async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    # Логируем любые исключения, но пользователю отвечаем мягко
    log.exception("Unhandled error", exc_info=context.error)
    try:
        if isinstance(update, Update) and update.message:
            await update.message.reply_text("⚠️ Ошибка на сервере. Попробуйте ещё раз через минуту.")
    except TelegramError:
        pass


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_error_handler(on_error)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CommandHandler("check", check))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("vpn", vpn))

    # DEV handlers
    if DEV_MODE:
        app.add_handler(CommandHandler("dev_paid", dev_paid))
        app.add_handler(CommandHandler("grant", grant))

    app.add_handler(MessageHandler(filters.COMMAND, unknown))

    log.info("Бот запущен")
    app.run_polling()


if __name__ == "__main__":
    main()
