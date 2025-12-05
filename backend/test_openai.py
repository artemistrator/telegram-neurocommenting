import os
import asyncio
from openai import AsyncOpenAI

async def test():
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    print("🤖 Тест фильтрации (AI Classification)...")
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "user", 
            "content": """
Категории: вакансии, грузоперевозки, фриланс

Пост: "Ищу водителя на Газель, опыт от 3 лет"

Относится ли к категориям? Ответь: YES или NO
"""
        }],
        max_tokens=10
    )
    
    print(f"✓ AI ответил: {response.choices[0].message.content}")
    
    print("\n💬 Тест генерации коммента...")
    response2 = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Ты логист. Пиши технично, до 20 слов."},
            {"role": "user", "content": "Пост: Ищу грузоперевозки Москва-СПб\nНапиши коммент:"}
        ],
        max_tokens=50
    )
    
    print(f"✓ Сгенерирован коммент: {response2.choices[0].message.content}")

asyncio.run(test())