import asyncio
import aiohttp
from telethon import TelegramClient, events
import json
import os
import sys
# Импортируем новый класс клиента
from openai import AsyncOpenAI
from typing import List, Optional

# Установить кодировку для предотвращения UnicodeEncodeError
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ["PYTHONUNBUFFERED"] = "1"

# Загрузить конфигурацию
if not os.path.exists('config.json'):
    print("ERROR: config.json не найден", flush=True)
    exit(1)

with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

API_ID = int(config['telegram']['api_id'])
API_HASH = config['telegram']['api_hash']
SESSION = config['telegram'].get('session', 'telegram_session')
N8N_WEBHOOK = config.get('webhook_url', '')
MONITORED_CHATS = [chat['id'] for chat in config.get('monitored_chats', [])]

# Load OpenAI settings
openai_settings = config.get('openai', {})
AI_ENABLED = openai_settings.get('ai_enabled', False)
OPENAI_API_KEY = openai_settings.get('openai_api_key', '')
OPENAI_MODEL = openai_settings.get('openai_model', 'gpt-5-nano')
SYSTEM_PROMPT = openai_settings.get('system_prompt', 'Ты классификатор сообщений из чатов фрилансеров. Твоя задача — определить, содержит ли сообщение поиск исполнителя, вакансию или предложение работы. Если сообщение — это вопрос новичка, спам, реклама услуг или просто общение — возвращай false. Если это заказ/вакансия — возвращай true. Ответь ТОЛЬКО валидным JSON формата: {"relevant": true} или {"relevant": false}')
MIN_WORDS = openai_settings.get('min_words', 5)
USE_TRIGGERS = openai_settings.get('use_triggers', True)
TRIGGER_WORDS = openai_settings.get('trigger_words', [])

print("Мониторинг запущен", flush=True)
print(f"Чаты: {MONITORED_CHATS}", flush=True)
print(f"AI включен: {AI_ENABLED}", flush=True)
print(f"Trigger слова: {TRIGGER_WORDS}", flush=True)
print(f"Webhook: {N8N_WEBHOOK}", flush=True)

client = TelegramClient(SESSION, API_ID, API_HASH)

# Initialize OpenAI client using new v1 syntax
ai_client = None
if OPENAI_API_KEY:
    try:
        ai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    except Exception as e:
        print(f"Ошибка инициализации OpenAI клиента: {e}", flush=True)
else:
    print("OpenAI API key not configured", flush=True)


async def send_to_n8n(message_data):
    """Отправить в N8N вебхук"""
    # Send to N8N webhook (existing functionality)
    async with aiohttp.ClientSession() as session:
        try:
            print("Отправка в webhook...", flush=True)
            async with session.post(
                N8N_WEBHOOK,
                json=message_data,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    print('Отправлено в N8N', flush=True)
                else:
                    print(f'N8N вернул статус {resp.status}', flush=True)
                    text = await resp.text()
                    print(f'Ответ: {text}', flush=True)
        except Exception as e:
            print(f'Ошибка отправки в N8N: {e}', flush=True)
    
    # Send event to our own API (new functionality)
    try:
        async with aiohttp.ClientSession() as session:
            event_data = {
                "time": message_data["date"],
                "chat_name": message_data["chat_name"],
                "keywords": message_data["keywords_found"],
                "text_preview": message_data["text"][:100] if message_data["text"] else ""
            }
            # Send to our own API endpoint
            async with session.post(
                "http://localhost:8000/api/monitor/event",
                json=event_data,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    print('Событие отправлено в API', flush=True)
                else:
                    print(f'API вернул статус {resp.status}', flush=True)
    except Exception as e:
        print(f'Ошибка отправки события в API: {e}', flush=True)


async def check_with_openai(text: str) -> bool:
    print(f"[AI DEBUG] Entering check_with_openai", flush=True)
    
    if not ai_client:
        print("[AI DEBUG] Error: OpenAI client not initialized", flush=True)
        return False
    
    try:
        print(f"[AI DEBUG] Sending request to model {OPENAI_MODEL}...", flush=True)
        # New v1 syntax
        response = await ai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text}
            ],
            max_completion_tokens=100
        )
        
        result = response.choices[0].message.content
        print(f"[AI DEBUG] RAW RESPONSE: {result}", flush=True)
        
        if not result:
            return False
            
        result = result.strip()
        
        # Safe JSON parsing logic
        import json
        
        # Try finding JSON object
        start_idx = result.find('{')
        end_idx = result.rfind('}')
        
        if start_idx != -1 and end_idx != -1:
            json_str = result[start_idx:end_idx+1]
            try:
                result_json = json.loads(json_str)
                is_relevant = result_json.get("relevant", False)
                print(f"[AI DEBUG] Parsed JSON: {result_json} -> Relevant: {is_relevant}", flush=True)
                return is_relevant
            except json.JSONDecodeError:
                print(f"[AI DEBUG] JSON Decode Error on substring: {json_str}", flush=True)
        
        print("[AI DEBUG] Could not find valid JSON structure", flush=True)
        return False
            
    except Exception as e:
        print(f"[AI DEBUG] CRITICAL ERROR: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return False






# ВРЕМЕННО: Слушаем ВСЕ чаты, чтобы найти проблему
# Убрали chats=MONITORED_CHATS, чтобы слышать всё
@client.on(events.NewMessage(chats=MONITORED_CHATS))
async def handler(event):

    """Обработчик новых сообщений (DEBUG VERSION)"""
    text = event.message.text or ''
    chat_id = event.chat_id
    
    # 1. Сразу печатаем, что пришло сообщение (для отладки)
    # Это покажет, видит ли скрипт хоть что-то и какой РЕАЛЬНЫЙ ID у чата
    print(f"[DEBUG] Message from {chat_id}: {text[:50]}...", flush=True)

    # Если это не тот чат, который мы хотим мониторить - пропускаем (но после принта!)
    if chat_id not in MONITORED_CHATS:
        # Пробуем проверить вариант с -100 (супергруппы)
        # Если в конфиге -123, а приходит -100123
        # Преобразуем -1001234567890 -> -1234567890 для сравнения со старым форматом
        canonical_id = int(str(chat_id).replace('-100', '-'))
        
        # Если ни прямой ID, ни канонический не совпадают - выходим
        if chat_id not in MONITORED_CHATS and canonical_id not in MONITORED_CHATS:
            # print(f"[DEBUG] Skipped: chat {chat_id} is not monitored", flush=True)
            return 

    # Check if message meets minimum word count
    word_count = len(text.split())
    if word_count < MIN_WORDS:
        print(f"[DEBUG] Skipped: too short ({word_count} words)", flush=True)
        return
    
    # New logic: Check trigger words and AI filtering
    found_keywords = []
    should_process = False
    
    # Check trigger words if enabled
    if USE_TRIGGERS and TRIGGER_WORDS:
        text_lower = text.lower()
        found_keywords = [kw for kw in TRIGGER_WORDS if kw.lower() in text_lower]
        should_process = len(found_keywords) > 0
        if not should_process:
             print(f"[DEBUG] Skipped: no trigger words found", flush=True)
    else:
        should_process = True
    
    # If AI is enabled, apply additional filtering
    if should_process and AI_ENABLED:
        # If trigger words check passed or is disabled, check with AI
        print(f"[DEBUG] Sending to OpenAI...", flush=True) # ВИДИМ, что пошло в AI
        if USE_TRIGGERS and TRIGGER_WORDS:
            if found_keywords:
                should_process = await check_with_openai(text)
        else:
            should_process = await check_with_openai(text)
    elif not AI_ENABLED and USE_TRIGGERS and TRIGGER_WORDS:
        should_process = len(found_keywords) > 0
    elif not AI_ENABLED and not USE_TRIGGERS:
        should_process = True
    
    if should_process:
        print(f"Найдены ключевые слова: {found_keywords}", flush=True)
        print(f"Текст: {text[:100]}...", flush=True)
        
        chat = await event.get_chat()
        
        message_data = {
            'chat_id': event.chat_id,
            'chat_name': getattr(chat, 'title', None) or getattr(chat, 'first_name', 'Unknown'),
            'message_id': event.message.id,
            'text': text,
            'date': event.message.date.isoformat(),
            'sender_id': event.sender_id,
            'keywords_found': found_keywords
        }
        
        await send_to_n8n(message_data)
    else:
        print(f"[DEBUG] Result: Not relevant", flush=True)



def main():
    """Главная функция"""
    print('Подключено к Telegram', flush=True)
    print(f'Мониторинг чатов: {MONITORED_CHATS}', flush=True)
    print(f'AI включен: {AI_ENABLED}', flush=True)
    print(f'Trigger слова: {TRIGGER_WORDS}', flush=True)
    print('Ожидание сообщений...\n', flush=True)
    
    # Auto-reconnection loop
    while True:
        try:
            if not client.is_connected():
                print("Connecting...", flush=True)
                client.start()
            
            client.run_until_disconnected()
        except Exception as e:
            print(f"Monitor crashed: {e}. Restarting in 5s...", flush=True)
            import time
            time.sleep(5)


if __name__ == '__main__':
    main()
