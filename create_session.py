from telethon import TelegramClient
import asyncio

async def create_session():
    """
    Скрипт для создания .session файлов локально
    
    Использование:
    1. Установите: pip install telethon
    2. Запустите: python create_session.py
    3. Следуйте инструкциям
    4. Загрузите полученный .session файл через UI
    """
    print("=" * 50)
    print("Создание Telegram Session файла")
    print("=" * 50)
    print()
    
    api_id = int(input("API ID: "))
    api_hash = input("API Hash: ")
    phone = input("Телефон (+7...): ")
    
    session_name = f"account_{phone.replace('+', '')}"
    
    print(f"\nСоздание сессии: {session_name}.session")
    print("Код будет отправлен в Telegram...")
    
    client = TelegramClient(session_name, api_id, api_hash)
    
    await client.start(phone)
    
    me = await client.get_me()
    print(f"\n✅ Сессия успешно создана!")
    print(f"📁 Файл: {session_name}.session")
    print(f"👤 Вы авторизованы как: {me.first_name}")
    
    if me.username:
        print(f"🔗 Username: @{me.username}")
    
    print("\nТеперь вы можете:")
    print("1. Создать CSV файл с данными аккаунта")
    print("2. Загрузить CSV + .session файл через UI")
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(create_session())
