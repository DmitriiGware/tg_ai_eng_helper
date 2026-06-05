import re


LESSONS = {
    "past_simple": {
        "title": "Past Simple",
        "level": "A2",
        "aliases": [
            "past simple",
            "past simple regular",
            "past simple irregular verbs",
            "прошедшее время",
            "простое прошедшее",
        ],
        "steps": [
            {
                "id": 1,
                "type": "practice",
                "theory": "Past Simple используем, когда действие произошло и закончилось в прошлом.",
                "examples": [
                    "I watched TV yesterday.",
                    "She went to school last Monday.",
                ],
                "task": "Fill the gap: I ___ (buy) a phone yesterday.",
                "correct_answers": ["bought", "I bought a phone yesterday"],
                "short_explanation": "Правильно: bought. Buy -> bought - это неправильный глагол.",
            },
            {
                "id": 2,
                "type": "practice",
                "theory": "Для обычных глаголов в Past Simple чаще всего добавляем -ed.",
                "examples": [
                    "I clean my room every day.",
                    "I cleaned my room yesterday.",
                ],
                "task": "Fill the gap: She ___ (clean) her room yesterday.",
                "correct_answers": ["cleaned", "She cleaned her room yesterday"],
                "short_explanation": "Правильно: cleaned. Clean - обычный глагол, поэтому добавляем -ed.",
            },
            {
                "id": 3,
                "type": "practice",
                "theory": "В отрицании Past Simple используем did not / didn't, а глагол возвращается в обычную форму.",
                "examples": [
                    "I did not watch TV.",
                    "She didn't go to school.",
                ],
                "task": "Correct the mistake: I didn't bought coffee yesterday.",
                "correct_answers": ["I didn't buy coffee yesterday", "I did not buy coffee yesterday"],
                "short_explanation": "После didn't нужен обычный глагол: buy, не bought.",
            },
        ],
    },
    "present_simple": {
        "title": "Present Simple",
        "level": "A1",
        "aliases": [
            "present simple",
            "present simple negative",
            "present simple questions",
            "настоящее простое",
        ],
        "steps": [
            {
                "id": 1,
                "type": "practice",
                "theory": "Present Simple используем для привычек, фактов и регулярных действий.",
                "examples": [
                    "I drink coffee every morning.",
                    "They live in Moscow.",
                ],
                "task": "Choose the correct sentence for a daily habit.",
                "options": ["She likes tea.", "She like tea.", "She liking tea."],
                "correct_answers": ["She likes tea", "A"],
                "short_explanation": "С she/he/it в Present Simple добавляем -s: likes.",
            },
            {
                "id": 2,
                "type": "practice",
                "theory": "В отрицании с I/you/we/they используем don't + обычный глагол.",
                "examples": [
                    "I don't eat meat.",
                    "They don't work on Sunday.",
                ],
                "task": "Correct the mistake: I doesn't like milk.",
                "correct_answers": ["I don't like milk", "I do not like milk"],
                "short_explanation": "С I используем don't, а не doesn't.",
            },
            {
                "id": 3,
                "type": "practice",
                "theory": "В вопросах с you используем Do + you + verb.",
                "examples": [
                    "Do you speak English?",
                    "Do you like pizza?",
                ],
                "task": "Build the question: you / like / music",
                "correct_answers": ["Do you like music", "Do you like music?"],
                "short_explanation": "Вопрос строится так: Do you + verb.",
            },
        ],
    },
    "to_be": {
        "title": "To be",
        "level": "A1",
        "aliases": ["to be", "am is are", "глагол to be"],
        "steps": [
            {
                "id": 1,
                "type": "practice",
                "theory": "To be помогает сказать, кто человек, где он или какой он.",
                "examples": [
                    "I am a student.",
                    "She is happy.",
                ],
                "task": "Fill the gap: I ___ happy.",
                "correct_answers": ["am", "I am happy"],
                "short_explanation": "С I используем am.",
            },
            {
                "id": 2,
                "type": "practice",
                "theory": "С he, she, it используем is.",
                "examples": [
                    "He is tired.",
                    "It is cold.",
                ],
                "task": "Fill the gap: She ___ my friend.",
                "correct_answers": ["is", "She is my friend"],
                "short_explanation": "С she используем is.",
            },
            {
                "id": 3,
                "type": "practice",
                "theory": "С you, we, they используем are.",
                "examples": [
                    "You are right.",
                    "They are at home.",
                ],
                "task": "Fill the gap: They ___ ready.",
                "correct_answers": ["are", "They are ready"],
                "short_explanation": "С they используем are.",
            },
        ],
    },
    "articles": {
        "title": "Articles: a/an/the",
        "level": "A1",
        "aliases": ["articles", "a an the", "артикли"],
        "steps": [
            {
                "id": 1,
                "type": "practice",
                "theory": "A используем перед одним предметом, если слово начинается с согласного звука.",
                "examples": [
                    "a book",
                    "a phone",
                ],
                "task": "Fill the gap: I have ___ book.",
                "correct_answers": ["a", "I have a book"],
                "short_explanation": "Book начинается с согласного звука, поэтому a.",
            },
            {
                "id": 2,
                "type": "practice",
                "theory": "An используем перед одним предметом, если слово начинается с гласного звука.",
                "examples": [
                    "an apple",
                    "an old car",
                ],
                "task": "Fill the gap: I have ___ apple.",
                "correct_answers": ["an", "I have an apple"],
                "short_explanation": "Apple начинается с гласного звука, поэтому an.",
            },
            {
                "id": 3,
                "type": "practice",
                "theory": "The используем, когда мы говорим о конкретном или уже известном предмете.",
                "examples": [
                    "I have a dog. The dog is friendly.",
                    "Open the door.",
                ],
                "task": "Fill the gap: I have a cat. ___ cat is black.",
                "correct_answers": ["the", "The cat is black"],
                "short_explanation": "Во втором предложении cat уже известен, поэтому the.",
            },
        ],
    },
    "comparatives": {
        "title": "Comparatives",
        "level": "A2",
        "aliases": ["comparatives", "сравнительная степень"],
        "steps": [
            {
                "id": 1,
                "type": "practice",
                "theory": "Comparatives нужны, чтобы сравнить два предмета, человека или действия.",
                "examples": [
                    "This book is cheaper.",
                    "Anna is taller than Tom.",
                ],
                "task": "Fill the gap: This bag is ___ (cheap) than that bag.",
                "correct_answers": ["cheaper", "This bag is cheaper than that bag"],
                "short_explanation": "Cheap - короткое прилагательное, поэтому cheaper.",
            },
            {
                "id": 2,
                "type": "practice",
                "theory": "С длинными прилагательными часто используем more + adjective.",
                "examples": [
                    "This task is more difficult.",
                    "English is more interesting now.",
                ],
                "task": "Fill the gap: This lesson is ___ (interesting) than the last one.",
                "correct_answers": ["more interesting", "This lesson is more interesting than the last one"],
                "short_explanation": "Interesting длинное слово, поэтому more interesting.",
            },
        ],
    },
}


def normalize_lesson_text(text: str) -> str:
    text = (text or "").strip().lower().replace("ё", "е")
    text = re.sub(r"[^a-zа-я0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_answer(text: str) -> str:
    text = (text or "").strip().lower().replace("ё", "е")
    text = re.sub(r"[“”\"`]", "", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[.!?,;:]+$", "", text)
    return text.strip()


def check_answer(user_answer: str, correct_answers: list[str]) -> bool:
    normalized = normalize_answer(user_answer)
    if not normalized:
        return False

    normalized = re.sub(r"^[a-dа-г][\).]\s*", "", normalized)
    return normalized in {normalize_answer(answer) for answer in correct_answers if answer}


def find_static_lesson(topic: str, level: str | None = None) -> dict | None:
    normalized_topic = normalize_lesson_text(topic)
    normalized_level = (level or "").upper()[:2]

    for lesson in LESSONS.values():
        aliases = [lesson["title"], *lesson.get("aliases", [])]
        if normalized_level and lesson.get("level") and lesson["level"] != normalized_level:
            level_matches = lesson["level"] <= normalized_level
        else:
            level_matches = True

        if not level_matches:
            continue

        for alias in aliases:
            normalized_alias = normalize_lesson_text(alias)
            if normalized_alias and (
                normalized_alias == normalized_topic
                or normalized_alias in normalized_topic
                or normalized_topic in normalized_alias
            ):
                return lesson

    return None


def lesson_to_practice_bundle(lesson: dict) -> dict:
    tasks = []
    for step in lesson.get("steps", []):
        correct_answers = [str(answer).strip() for answer in step.get("correct_answers", []) if str(answer).strip()]
        if not correct_answers:
            continue

        tasks.append({
            "type": step.get("type", "practice"),
            "theory": step.get("theory", ""),
            "examples": step.get("examples", []),
            "question": step.get("task", ""),
            "options": step.get("options", []),
            "correct_answer": correct_answers[0],
            "acceptable_answers": correct_answers,
            "explanation": step.get("short_explanation", ""),
            "source": "static",
        })

    return {
        "title": f"✍️ Тренировка: {lesson.get('title', 'English')}",
        "topic": lesson.get("title", "English"),
        "tasks": tasks,
    }
