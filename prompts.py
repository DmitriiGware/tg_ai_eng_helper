SYSTEM_TUTOR = """
You are a friendly modern English tutor.

Rules:
- Explain simply, like a helpful teacher
- Avoid long textbook-style answers
- Write clearly and naturally
- Do not mix Russian and English in one sentence unless needed for examples

Default format:
1. Short explanation
2. Examples (English -> Russian)
"""


def make_user_prompt(topic: str, mode: str, level: str) -> str:
    topic = topic.strip()

    base = f"""
Topic: {topic}
Student level: {level}
"""

    if mode == "explain":
        return base + """
Explain the topic.

Include:
- a simple explanation
- 3-5 examples (English -> Russian)
"""

    if mode == "quiz":
        return base + """
Create a quiz:
- 5 questions
- do not give answers
- use different question types
"""

    if mode == "summary":
        return base + """
Create a short summary:
- keep it short and clear
- then give 5 key words with explanations
"""

    return base + "Help the student learn this topic."


def make_roadmap_lesson_prompt(topic: str, level: str, simplify: bool = False) -> str:
    simplify_block = ""
    if simplify:
        simplify_block = """
Объясни тему намного проще обычного.
- Используй короткие предложения
- Дай только 2 простых примера
- Дай 1 очень простое задание
"""

    return f"""
Тема: {topic}
Уровень ученика: {level}

Сделай короткий урок для roadmap.
- Пиши объяснение на русском
- Объясни кратко и понятно
- Дай 2-3 примера по теме
- Дай 1 задание для ответа ученика
- Не давай правильный ответ заранее

{simplify_block}
"""


def make_roadmap_check_prompt(topic: str, level: str, lesson: str, user_answer: str) -> str:
    return f"""
You are checking a student's English answer.

Topic: {topic}
Level: {level}

Lesson and task:
{lesson}

Student answer:
{user_answer}

Return strictly in this format:
RESULT: correct or incorrect
FEEDBACK: short feedback in Russian with what is right and what to fix
"""


def make_vocab_words_prompt(level: str, count: int, recent_words: list[str] | None = None) -> str:
    recent_block = ""
    if recent_words:
        recent_block = "Не используй эти слова повторно: " + ", ".join(recent_words)

    return f"""
Сделай ежедневную подборку слов по английскому.

Уровень ученика: {level}
Количество слов: {count}

Формат:
одна строка = слово | перевод | пример | перевод примера

Правила:
- слова должны подходить уровню
- слова должны быть полезными в повседневной речи
- без длинных объяснений
- без нумерации
- не добавляй текст до или после списка

{recent_block}
"""
