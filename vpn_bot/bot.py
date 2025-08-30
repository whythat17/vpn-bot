import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from config import BOT_TOKEN
from users import register_user, subscribe_user, check_subscription, load_users


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    print(f"📥 /start от пользователя {user_id}")
    register_user(user_id)
    await update.message.reply_text(
        "👋 Привет! Я бот для доступа к VPN.\n\n👉 Введите /subscribe для подписки."
    )

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    print(f"📥 /subscribe от пользователя {user_id}")
    subscribe_user(user_id, days=7)
    await update.message.reply_text(
        "✅ Вы подписались на 7 дней!\nВведите /vpn для получения конфигурации."
    )

async def vpn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    print(f"📥 /vpn от пользователя {user_id}")

    if check_subscription(user_id):
        file_path = os.path.join("vpn_configs", "default.ovpn")
        if os.path.exists(file_path):
            await update.message.reply_document(
                document=open(file_path, "rb"),
                filename="myvpn.ovpn",
                caption="🔐 Ваш конфигурационный файл VPN"
            )
            print(f"📤 Конфиг отправлен пользователю {user_id}")
        else:
            await update.message.reply_text("❗️ Конфигурационный файл не найден.")
            print("⚠️ Файл default.ovpn не найден в vpn_configs/")
    else:
        await update.message.reply_text("⛔ У вас нет активной подписки. Введите /subscribe.")
        print(f"⛔ Нет подписки у пользователя {user_id}")

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"❓ Неизвестная команда: {update.message.text}")
    await update.message.reply_text("⚠️ Неизвестная команда. Используйте /start, /subscribe или /vpn.")

if __name__ == '__main__':
    print("📦 Загружаем пользователей...")
    load_users()

    print("🚀 Запуск бота...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("subscribe", subscribe))
    app.add_handler(CommandHandler("vpn", vpn))
    app.add_handler(MessageHandler(filters.COMMAND, unknown))

# Команда /buy — выставляет счёт на 5 USDT за 7 дней
@bot.message_handler(commands=['buy'])
def buy(message):
    chat_id = message.chat.id
    price = 5.0  # стоимость в USDT
    try:
        url, invoice_id = create_invoice(amount=price, asset="USDT",
                                         description="VPN подписка на 7 дней",
                                         payload=str(chat_id))  # прикрепим chat_id в payload
        bot.send_message(
            chat_id,
            f"💳 Счёт на <b>{price} USDT</b> создан.\n\n"
            f"🔗 Оплатить: {url}\n"
            f"🧾 Номер счёта: <code>{invoice_id}</code>\n\n"
            f"После оплаты отправьте команду:\n"
            f"/check {invoice_id}"
        )
    except Exception as e:
        bot.send_message(chat_id, f"❌ Ошибка при создании счёта:\n<code>{e}</code>")

# Команда /check <invoice_id> — проверяет статус
@bot.message_handler(commands=['check'])
def check(message):
    chat_id = message.chat.id
    parts = message.text.split()
    if len(parts) != 2:
        bot.send_message(chat_id, "Использование: <code>/check invoice_id</code>")
        return
    invoice_id = parts[1]
    try:
        status = get_invoice_status(invoice_id)
        if status == "paid":
            activate_subscription(chat_id, days=7)
            bot.send_message(chat_id, "✅ Оплата получена! Подписка активирована на 7 дней.")
        elif status == "active":
            bot.send_message(chat_id, "🕓 Счёт пока не оплачен. Если оплатили только что — подождите минуту и повторите /check.")
        elif status == "expired":
            bot.send_message(chat_id, "⌛ Счёт истёк. Введите /buy, чтобы создать новый.")
        else:
            bot.send_message(chat_id, f"ℹ️ Статус счёта: {status}")
    except Exception as e:
        bot.send_message(chat_id, f"❌ Ошибка при проверке счёта:\n<code>{e}</code>")

# Пример проверки подписки перед выдачей VPN-конфига
@bot.message_handler(commands=['vpn'])
def vpn(message):
    chat_id = message.chat.id
    if is_subscription_active(chat_id):
        # тут отправь реальный .ovpn/.conf или ссылку
        bot.send_message(chat_id, "🔐 Ваша подписка активна. (Тут отправим VPN-конфиг)")
    else:
        bot.send_message(chat_id, "❗ Подписка не активна. Создайте счёт командой /buy")


    app.run_polling()
