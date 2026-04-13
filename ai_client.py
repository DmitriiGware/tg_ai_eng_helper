from groq import Groq
import os
from dotenv import load_dotenv
from prompts import SYSTEM_TUTOR

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def ask_ai(prompt: str, level: str = "Beginner", mode: str = "explain") -> str:
    """
    Основная функция запроса к ИИ

    :param prompt: готовый user prompt
    :param level: уровень пользователя
    :param mode: режим (explain / quiz / summary)
    """

    # 👉 Усиливаем system prompt динамически
    system_prompt = f"""
{SYSTEM_TUTOR}

Уровень ученика: {level}

Важно:
- Beginner → максимально просто
- Intermediate → добавь немного деталей
- Advanced → добавь нюансы и исключения

Режим: {mode}
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt.strip()},
                {"role": "user", "content": prompt.strip()}
            ],
            temperature=0.7,
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        # 👉 нормальная обработка ошибки
        return f"⚠️ AI error: {e}"