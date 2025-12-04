# create_test_session.py
from telethon import TelegramClient
import asyncio

async def main():
    api_id = 2040  # Дефолтный
    api_hash = "b18441a1ff607e10a989891a5462e627"
    phone = input("Введи номер телефона (+7...): ")
    
    client = TelegramClient(f"test_{phone.replace('+', '')}", api_id, api_hash)
    await client.start(phone)
    
    me = await client.get_me()
    print(f"✅ Сессия создана! Файл: test_{phone.replace('+', '')}.session")
    print(f"Пользователь: {me.first_name}")
    
    await client.disconnect()

asyncio.run(main())
