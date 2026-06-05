import os

from dotenv import load_dotenv
from groq import Groq

from prompts import SYSTEM_TUTOR

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

AI_MODE_FREE = "free_short"
AI_MODE_PREMIUM = "premium_detailed"

AI_MODE_SETTINGS = {
    AI_MODE_FREE: {
        "max_tokens": 120,
        "temperature": 0.1,
        "instructions": (
            "Режим free_short: ответ максимум 2-3 коротких предложения, "
            "без длинных примеров и без лишней теории."
        ),
    },
    AI_MODE_PREMIUM: {
        "max_tokens": 300,
        "temperature": 0.2,
        "instructions": (
            "Режим premium_detailed: ответ до 700-900 символов, правильный ответ, "
            "короткое объяснение ошибки, один пример и одно похожее задание."
        ),
    },
}


def ask_ai(prompt: str, level: str = "A1 Beginner lvl 1", mode: str = "explain") -> str:
    """
    Основная функция запроса к ИИ.

    :param prompt: готовый user prompt
    :param level: уровень пользователя
    :param mode: режим (explain / quiz / summary / practice / level_test)
    """

    level_guide = """
A1 Beginner lvl 1: very simple words and short examples.
A2 Beginner lvl 2: simple, with a bit more variety.
B1 Intermediate lvl 1: add more details and useful context.
B2 Intermediate lvl 2: use richer examples and natural phrasing.
C1 Advanced lvl 1: add nuance and exceptions.
C2 Advanced lvl 2: explain subtle differences and advanced usage.
"""

    mode_settings = AI_MODE_SETTINGS.get(mode, {})
    mode_instructions = mode_settings.get("instructions", "")
    temperature = mode_settings.get("temperature", 0.7)
    max_tokens = mode_settings.get("max_tokens")

    system_prompt = f"""
{SYSTEM_TUTOR}
{level_guide}

Уровень ученика: {level}
Режим: {mode}
{mode_instructions}
"""

    try:
        request = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": system_prompt.strip()},
                {"role": "user", "content": prompt.strip()},
            ],
            "temperature": temperature,
        }
        if max_tokens:
            request["max_tokens"] = max_tokens

        response = client.chat.completions.create(
            **request,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠️ AI error: {e}"
