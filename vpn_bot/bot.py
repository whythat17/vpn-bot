# vpn_bot/bot.py
import secrets
from aiohttp import web
import time
from datetime import datetime, timezone
import shutil
from pathlib import Path
import logging, os
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from vpn_bot.config import (
    BOT_TOKEN, PRICE_USDT, SUB_DAYS, DEV_MODE, OWNER_ID,
    SERVER_HOST, SERVER_PORT,
    WG_ENDPOINT_HOST, WG_ENDPOINT_PORT, WG_ALLOWED_IPS, WG_DNS, WG_SERVER_PUBLIC_KEY,
    WG_ADDRESS_PREFIX, WG_ADDRESS_CIDR, WG_START_HOST,
)
from vpn_bot.cryptopay import create_invoice, get_invoice_status
from vpn_bot.users import (
    load_users, register_user, activate_subscription, is_subscription_active, save_users,
    set_wg_profile, next_wg_address,
)
from vpn_bot.wg_utils import gen_wg_keypair

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("vpn_bot")

# Загружаем пользователей при старте
USERS = load_users()

# Пути к шаблонам и личным конфигам
CFG_DIR = Path(__file__).with_name("vpn_configs")
TEMPLATE_OVPN = CFG_DIR / "default.ovpn"
USER_CFG_DIR = CFG_DIR / "users"
USER_CFG_DIR.mkdir(parents=True, exist_ok=True)

TEMPLATE_WG = CFG_DIR / "default_wg.conf"
USER_WG_DIR = CFG_DIR / "users"
USER_WG_DIR.mkdir(parents=True, exist_ok=True)



# Простейший анти-спам: кулдаун 2 сек на пользователя
LAST_CALL: dict[int, float] = {}
COOLDOWN_SEC = 2.0

# Одноразовые коды для входа из приложения
TOKENS: dict[str, dict] = {}  # code -> {"user_id": int, "exp": float}
TOKEN_TTL_SEC = 600  # 10 минут

def create_login_code(user_id: int) -> str:
    code = f"{secrets.randbelow(1_000_000):06d}"  # 000000..999999
    TOKENS[code] = {"user_id": user_id, "exp": time.time() + TOKEN_TTL_SEC}
    return code

def take_token(code: str) -> dict | None:
    """Вернёт запись и удалит токен, если живой; иначе None."""
    data = TOKENS.pop(code, None)
    if not data:
        return None
    if data["exp"] < time.time():
        return None
    return data

def peek_token(code: str) -> dict | None:
    """Вернёт запись по коду, не удаляя её (для /api/validate)."""
    data = TOKENS.get(code)
    if not data:
        return None
    if data["exp"] < time.time():
        return None
    return data

def get_telegram_link_url() -> str:
    try:
        from vpn_bot.config import TG_BOT_USERNAME
        username = TG_BOT_USERNAME.strip()
        if username.startswith("@"):
            username = username[1:]
        if username:
            return f"https://t.me/{username}"
    except Exception:
        pass
    return "https://t.me/thatvpn_bot"



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

def ensure_user_config(user_id: int) -> Path:
    """
    Гарантирует, что у пользователя есть свой файл-конфиг.
    Если нет — рендерим из шаблона default.ovpn, подставляя плейсхолдеры.
    Возвращает путь к файлу.
    """
    dst = USER_CFG_DIR / f"{user_id}.ovpn"
    if dst.exists():
        return dst

    if not TEMPLATE_OVPN.exists():
        raise FileNotFoundError("Шаблон default.ovpn не найден в vpn_bot/vpn_configs/")

    # берём дату окончания подписки пользователя (если есть)
    u = USERS.get(user_id)
    sub_end = getattr(u, "subscription_end", None) or ""

    # читаем шаблон и подставляем значения
    text = TEMPLATE_OVPN.read_text(encoding="utf-8")
    placeholders = {
        "SERVER_HOST": SERVER_HOST,
        "SERVER_PORT": str(SERVER_PORT),
        "USER_ID": str(user_id),
        "SUB_END": sub_end,
    }
    for k, v in placeholders.items():
        text = text.replace(f"{{{{{k}}}}}", v)

    dst.write_text(text, encoding="utf-8")
    return dst

def ensure_user_wg_config(user_id: int) -> Path:
    """
    Для пользователя гарантирует наличие wg-ключей + адреса, рендерит .conf из шаблона.
    """
    dst = USER_WG_DIR / f"{user_id}.conf"
    # если файл уже есть, просто возвращаем
    if dst.exists():
        return dst
    if not TEMPLATE_WG.exists():
        raise FileNotFoundError("Шаблон default_wg.conf не найден в vpn_bot/vpn_configs/")

    # получаем/генерируем профиль
    u = USERS.setdefault(user_id, None)
    need_save = False
    if not u or not getattr(u, "wg_private_key", None) or not getattr(u, "wg_public_key", None):
        priv, pub = gen_wg_keypair()
        addr = next_wg_address(USERS, WG_ADDRESS_PREFIX, WG_ADDRESS_CIDR, start_host=WG_START_HOST)
        set_wg_profile(USERS, user_id, priv, pub, addr)
        need_save = True

    # перечитываем (на случай, если только что создали)
    u = USERS[user_id]
    sub_end = getattr(u, "subscription_end", "") or ""

    # готовим плейсхолдеры
    placeholders = {
        "USER_ID": str(user_id),
        "SUB_END": sub_end,
        "WG_ENDPOINT_HOST": WG_ENDPOINT_HOST,
        "WG_ENDPOINT_PORT": str(WG_ENDPOINT_PORT),
        "WG_ALLOWED_IPS": WG_ALLOWED_IPS,
        "WG_DNS": WG_DNS,
        "WG_SERVER_PUBLIC_KEY": WG_SERVER_PUBLIC_KEY,
        "CLIENT_PRIVATE_KEY": u.wg_private_key or "<MISSING_PRIV>",
        "CLIENT_ADDRESS": u.wg_address or "<MISSING_ADDR>",
    }

    text = TEMPLATE_WG.read_text(encoding="utf-8")
    for k, v in placeholders.items():
        text = text.replace(f"{{{{{k}}}}}", v)

    dst.write_text(text, encoding="utf-8")
    if need_save:
        save_users(USERS)
    return dst

async def app_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _throttle(update): return
    user_id = update.effective_user.id
    if not is_subscription_active(USERS, user_id):
        await update.message.reply_text("⛔ Нет активной подписки. Сначала /buy и /check (или /dev_paid).")
        return
    code = create_login_code(user_id)
    await update.message.reply_text(
        f"🔑 Код для входа в приложение: {code}\n"
        f"Действует {TOKEN_TTL_SEC // 60} мин.\n\n"
        f"В приложении введите этот код — оно скачает ваш конфиг автоматически."
    )


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
        "/vpn — получить VPN-конфиг\n"
        "/help — помощь и команды"
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
        try:
            ensure_user_wg_config(user_id)
        except Exception:
            log.exception("WG profile prepare failed on activation")
        try:
            ensure_user_config(user_id)
        except Exception as e:
            log.exception("Не удалось создать персональный конфиг")
        await update.message.reply_text("✅ Оплата получена! Подписка активирована.")
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
        try:
            cfg_path = ensure_user_config(user_id)  # берём персональный
        except FileNotFoundError:
            await update.message.reply_text("⚠️ Не найден шаблон default.ovpn. Положи файл в vpn_bot/vpn_configs/default.ovpn")
            return
        except Exception as e:
            log.exception("Ошибка при подготовке конфига")
            await update.message.reply_text("⚠️ Не удалось подготовить конфиг. Попробуйте позже.")
            return

        if cfg_path.exists():
            with cfg_path.open("rb") as f:
                await update.message.reply_document(
                    document=f,
                    filename=f"vpn_{user_id}.ovpn",
                    caption="🔐 Ваш персональный VPN-конфиг",
                )
        else:
            await update.message.reply_text("⚠️ Конфиг не найден. Попробуйте снова или напишите в поддержку.")
    else:
        await update.message.reply_text("⛔ У вас нет активной подписки. Создайте счёт командой /buy.")

async def vpn_wg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _throttle(update): return
    user_id = update.effective_user.id
    if not is_subscription_active(USERS, user_id):
        await update.message.reply_text("⛔ Нет активной подписки. Сначала /buy и /check (или /dev_paid).")
        return
    try:
        cfg_path = ensure_user_wg_config(user_id)
    except FileNotFoundError:
        await update.message.reply_text("⚠️ Не найден шаблон default_wg.conf. Положи его в vpn_bot/vpn_configs/")
        return
    except Exception:
        log.exception("WG prepare error")
        await update.message.reply_text("⚠️ Не удалось подготовить WG-конфиг. Попробуйте позже.")
        return

    with cfg_path.open("rb") as f:
        await update.message.reply_document(
            document=f,
            filename=f"wg_{user_id}.conf",
            caption="🔐 Ваш персональный WireGuard-конфиг (шаблон)",
        )



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

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _throttle(update): return
    await update.message.reply_text(
        "ℹ️ Помощь\n\n"
        "/buy — создать счёт на оплату\n"
        "/check <invoice_id> — проверить оплату (active/paid/expired)\n"
        "/status — показать статус подписки\n"
        "/vpn — получить VPN-конфиг (если подписка активна)\n\n"
        "/vpn_wg — получить WireGuard-конфиг (шаблон)\n"
        "DEV (только для владельца, если DEV_MODE=true):\n"
        "/dev_paid <invoice_id> — имитация оплаты\n"
         "/app_code - получить код для входа в приложение"
        "/grant <days> — выдать подписку на N дней"
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
    try:
        ensure_user_wg_config(user_id)
    except Exception:
        log.exception("WG profile prepare failed on activation")
    try:
        ensure_user_config(user_id)
    except Exception as e:
        log.exception("Не удалось создать персональный конфиг (dev_paid)")
    await update.message.reply_text("✅ (DEV) Оплата имитирована. Подписка активирована.")
    await update.message.reply_text("✅ (DEV) Оплата имитирована. Подписка активирована.")

async def grant(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _throttle(update): return
    if not DEV_MODE or update.effective_user.id != OWNER_ID:
        return
    args = context.args or []
    days = int(args[0]) if args else SUB_DAYS
    user_id = update.effective_user.id
    activate_subscription(USERS, user_id, days=days)
    try:
        ensure_user_wg_config(user_id)
    except Exception:
        log.exception("WG profile prepare failed on activation")
    try:
        ensure_user_config(user_id)
    except Exception as e:
        log.exception("Не удалось создать персональный конфиг (grant)")
    await update.message.reply_text(f"🎁 (DEV) Подписка выдана на {days} дн.")
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

async def check_subscriptions(context: ContextTypes.DEFAULT_TYPE):
    """
    Периодически проверяет users.json и отключает истёкшие подписки.
    Отправляет пользователю уведомление об окончании.
    """
    now = datetime.now(timezone.utc)
    changed = False
    expired_count = 0

    # USERS — глобальный dict[int, User]
    for uid, u in list(USERS.items()):
        end_iso = getattr(u, "subscription_end", None)
        if not end_iso:
            continue
        try:
            end = datetime.fromisoformat(end_iso)
        except Exception:
            continue

        # если подписка была активна и срок вышел
        if getattr(u, "subscribed", False) and now >= end:
            u.subscribed = False
            changed = True
            expired_count += 1
            # пробуем уведомить пользователя; игнорируем любые ошибки отправки
            try:
                await context.bot.send_message(
                    chat_id=uid,
                    text="⛔ Ваша подписка истекла. Чтобы продлить, используйте /buy."
                )
            except Exception:
                pass

    if changed:
        save_users(USERS)
        log.info(f"[job] auto-expired {expired_count} subscriptions")

# --- HTTP API для приложения ---
async def http_get_wg_config(request: web.Request) -> web.Response:
    code = request.query.get("code", "").strip()
    if not code:
        return web.Response(status=400, text="missing code")
    data = take_token(code)
    if not data:
        return web.Response(status=401, text="invalid or expired code")

    user_id = int(data["user_id"])
    if not is_subscription_active(USERS, user_id):
        return web.Response(status=403, text="subscription inactive")

    try:
        cfg_path = ensure_user_wg_config(user_id)
        txt = cfg_path.read_text(encoding="utf-8")
        return web.Response(status=200, text=txt, content_type="text/plain")
    except Exception as e:
        log.exception("HTTP config error")
        return web.Response(status=500, text=f"server error: {e}")

async def http_validate(request: web.Request) -> web.Response:
    """
    POST /api/validate
    Body: {"code":"123456"}
    Ответ: JSON {"ok": bool, "subscriptionActive": bool, "message": str}
    (код НЕ расходуем, чтобы его потом можно было использовать для /api/config)
    """
    try:
        data = await request.json()
    except Exception:
        return web.json_response(
            {"ok": False, "subscriptionActive": False, "message": "invalid json"},
            status=400,
        )

    code = str(data.get("code", "")).strip()
    if not code:
        return web.json_response(
            {"ok": False, "subscriptionActive": False, "message": "empty code"},
            status=400,
        )

    peek = peek_token(code)
    if not peek:
        return web.json_response(
            {"ok": False, "subscriptionActive": False, "message": "invalid or expired code"},
            status=200,
        )

    user_id = int(peek["user_id"])
    active = is_subscription_active(USERS, user_id)
    if not active:
        return web.json_response(
            {"ok": True, "subscriptionActive": False, "message": "subscription inactive"},
            status=200,
        )

    return web.json_response(
        {"ok": True, "subscriptionActive": True, "message": "OK"},
        status=200,
    )


async def http_get_config_plain(request: web.Request) -> web.Response:
    """
    GET /api/config?code=123456
    Отдаёт текст конфига (plain text). Здесь код РАСХОДУЕМ (одноразовый).
    """
    code = request.query.get("code", "").strip()
    if not code:
        return web.Response(status=400, text="missing code")

    data = take_token(code)  # <-- именно расходуем
    if not data:
        return web.Response(status=401, text="invalid or expired code")

    user_id = int(data["user_id"])
    if not is_subscription_active(USERS, user_id):
        return web.Response(status=403, text="subscription inactive")

    try:
        cfg_path = ensure_user_wg_config(user_id)
        txt = cfg_path.read_text(encoding="utf-8")
        return web.Response(status=200, text=txt, content_type="text/plain")
    except Exception as e:
        log.exception("HTTP config error")
        return web.Response(status=500, text=f"server error: {e}")


async def http_telegram_link(request: web.Request) -> web.Response:
    """
    GET /api/telegram-link
    Возвращает {"url":"https://t.me/thatvpn_bot"}
    """
    return web.json_response({"url": get_telegram_link_url()}, status=200)


async def start_http_api():
    app_http = web.Application()
    # Старый маршрут, который уже был:
    app_http.router.add_get("/api/v1/config/wg", http_get_wg_config)

    # Новые маршруты под Android-приложение:
    app_http.router.add_post("/api/validate", http_validate)
    app_http.router.add_get("/api/config", http_get_config_plain)
    app_http.router.add_get("/api/telegram-link", http_telegram_link)

    runner = web.AppRunner(app_http)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=8080)
    await site.start()
    log.info("HTTP API started on http://0.0.0.0:8080")


from telegram.ext import Application  # добавь к импортам сверху

async def _post_init(app: Application) -> None:
    # здесь event loop уже запущен и можно стартовать aiohttp
    app.create_task(start_http_api())


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(_post_init).build()


    app.add_error_handler(on_error)

    # основные команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CommandHandler("check", check))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("app_code", app_code))
    app.add_handler(CommandHandler("vpn_wg", vpn_wg))
    app.add_handler(CommandHandler("vpn", vpn))
    app.add_handler(CommandHandler("help", help_cmd))

    # DEV команды
    if DEV_MODE:
        app.add_handler(CommandHandler("dev_paid", dev_paid))
        app.add_handler(CommandHandler("grant", grant))

        # быстрая проверка подписок в DEV-режиме
        async def dev_checksubs(update: Update, context: ContextTypes.DEFAULT_TYPE):
            if update.effective_user.id != OWNER_ID:
                return
            await check_subscriptions(context)
            await update.message.reply_text("🔧 (DEV) Проверка подписок выполнена.")

        app.add_handler(CommandHandler("dev_checksubs", dev_checksubs))

    # unknown — СТРОГО ПОСЛЕДНИМ!
    app.add_handler(MessageHandler(filters.COMMAND, unknown))

    # планировщик: проверка подписок раз в час, первая через 60 секунд
    app.job_queue.run_repeating(
        check_subscriptions,
        interval=3600,
        first=60,
        name="sub_checker",
    )

    log.info("Бот запущен")
    app.run_polling()



if __name__ == "__main__":
    main()
