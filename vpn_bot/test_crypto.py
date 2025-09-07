from vpn_bot.cryptopay import get_me, create_invoice

if __name__ == "__main__":
    print("Проверяю токен…")
    print(get_me())  # должен вернуть словарь с данными твоего приложения
    url, inv = create_invoice(1.0, "USDT", "Тестовый платёж 1 USDT")
    print("Ссылка на оплату:", url)
    print("Invoice ID:", inv)
