import asyncio
import logging
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, Message, PreCheckoutQuery
from dotenv import load_dotenv

from ai_client import ask_ai
from database.db import SessionLocal, engine, ensure_user_progress_columns
from database.models import Base, User, VocabWord
from glossary import glossary_menu, glossary_text
from level_tests import get_level_test
from modes import MODES
from motivation import get_phrase
from prompts import (
    make_practice_check_prompt,
    make_practice_task_prompt,
    make_roadmap_check_prompt,
    make_roadmap_lesson_prompt,
    make_roadmap_review_prompt,
    make_user_prompt,
    make_vocab_words_prompt,
)
from roadmap import ROADMAP, get_current_topic, update_progress

ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

BOT_TOKEN = (os.getenv("BOT_TOKEN") or "").strip()
ADMIN_TELEGRAM_ID = (os.getenv("TELEGRAM_ADMIN_ID") or "").strip()
PREMIUM_PAYMENT_TEXT = (os.getenv("PREMIUM_PAYMENT_TEXT") or "Способ оплаты уточняется у администратора.").strip()
YOOKASSA_SHOP_ID = (os.getenv("YOOKASSA_SHOP_ID") or "").strip()
YOOKASSA_SECRET_KEY = (os.getenv("YOOKASSA_SECRET_KEY") or "").strip()
YOOKASSA_RETURN_URL = (os.getenv("YOOKASSA_RETURN_URL") or "https://t.me/").strip()
PREMIUM_PRICE_RUB = (os.getenv("PREMIUM_PRICE_RUB") or "299.00").strip()
PREMIUM_STARS_PRICE = int((os.getenv("PREMIUM_STARS_PRICE") or "150").strip())

DEFAULT_LEVEL = "A1"
DEFAULT_WORDS_PER_DAY = 5
DAILY_VOCAB_HOUR = 10
RECENT_VOCAB_HISTORY_LIMIT = 80
FREE_DAILY_AI_LIMIT = 5
FREE_MAX_WORDS_PER_DAY = 3
PREMIUM_MAX_WORDS_PER_DAY = 10
DEFAULT_PREMIUM_DAYS = 30
ROADMAP_REVIEW_INTERVAL = 3

LEVELS = [
    ("A1", "A1 Beginner lvl 1"),
    ("A2", "A2 Beginner lvl 2"),
    ("B1", "B1 Intermediate lvl 1"),
    ("B2", "B2 Intermediate lvl 2"),
    ("C1", "C1 Advanced lvl 1"),
    ("C2", "C2 Advanced lvl 2"),
]
LEVEL_LABELS = dict(LEVELS)
LEGACY_LEVELS = {
    "Beginner": "A1",
    "Intermediate": "B1",
    "Advanced": "C1",
}


def normalize_level(level: str | None) -> str:
    if not level:
        return DEFAULT_LEVEL

    level = level.strip()
    return LEGACY_LEVELS.get(level, level if level in LEVEL_LABELS else DEFAULT_LEVEL)


def level_label(level: str | None) -> str:
    return LEVEL_LABELS[normalize_level(level)]


def get_user(user_id: int) -> User | None:
    db = SessionLocal()
    try:
        return db.query(User).filter(User.telegram_id == user_id).first()
    finally:
        db.close()


def today_key() -> str:
    return datetime.now().date().isoformat()


def is_admin(user_id: int | None) -> bool:
    if user_id is None or not ADMIN_TELEGRAM_ID:
        return False
    return str(user_id) == ADMIN_TELEGRAM_ID


def is_yookassa_configured() -> bool:
    return bool(YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY)


def object_value(obj, key: str):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def is_premium_user(user: User | None) -> bool:
    if not user or not user.premium_until:
        return False

    try:
        premium_until = datetime.strptime(user.premium_until, "%Y-%m-%d").date()
    except ValueError:
        return False

    return premium_until >= datetime.now().date()


def is_premium(user_id: int) -> bool:
    return is_premium_user(get_user(user_id))


def get_premium_status_text(user_id: int) -> str:
    user = get_user(user_id)
    if is_premium_user(user):
        return f"Premium до {user.premium_until}"
    return "Free"


def get_ai_usage_text(user_id: int) -> str:
    user = get_user(user_id)
    if is_premium_user(user):
        return "без лимита"

    count = 0
    if user and user.ai_requests_date == today_key() and user.ai_requests_count:
        count = user.ai_requests_count

    remaining = max(FREE_DAILY_AI_LIMIT - count, 0)
    return f"{remaining}/{FREE_DAILY_AI_LIMIT} AI-запросов сегодня"


def get_free_plan_text() -> str:
    return (
        "Free:\n"
        f"• {FREE_DAILY_AI_LIMIT} AI-запросов в день\n"
        "• Explain, Summary, Quiz, Practice\n"
        "• Roadmap доступен, но тратит AI-запросы\n"
        f"• Vocabulary до {FREE_MAX_WORDS_PER_DAY} слов в день\n"
        "• Глоссарий, профиль, уровень и помощь без лимита\n"
        "• Chat и Voice недоступны"
    )


def get_premium_plan_text() -> str:
    return (
        "Premium:\n"
        "• AI-запросы без дневного лимита\n"
        "• Explain, Summary, Quiz, Practice без лимита\n"
        "• Roadmap без лимита\n"
        f"• Vocabulary до {PREMIUM_MAX_WORDS_PER_DAY} слов в день\n"
        "• Chat и Voice\n"
        "• приоритет для новых функций"
    )


def consume_ai_request(user_id: int) -> tuple[bool, int]:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == user_id).first()
        if not user:
            return False, 0

        if is_premium_user(user):
            return True, -1

        today = today_key()
        if user.ai_requests_date != today:
            user.ai_requests_date = today
            user.ai_requests_count = 0

        if (user.ai_requests_count or 0) >= FREE_DAILY_AI_LIMIT:
            return False, 0

        user.ai_requests_count = (user.ai_requests_count or 0) + 1
        remaining = max(FREE_DAILY_AI_LIMIT - user.ai_requests_count, 0)
        db.commit()
        return True, remaining
    finally:
        db.close()


def grant_premium(user_id: int, days: int = DEFAULT_PREMIUM_DAYS) -> str | None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == user_id).first()
        if not user:
            return None

        base_date = datetime.now().date()
        if is_premium_user(user):
            base_date = datetime.strptime(user.premium_until, "%Y-%m-%d").date()

        user.premium_until = (base_date + timedelta(days=days)).isoformat()
        db.commit()
        return user.premium_until
    finally:
        db.close()


def save_pending_yookassa_payment(user_id: int, payment_id: str, confirmation_url: str) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == user_id).first()
        if user:
            user.pending_yookassa_payment_id = payment_id
            user.pending_yookassa_payment_url = confirmation_url
            db.commit()
    finally:
        db.close()


def get_pending_yookassa_payment(user_id: int) -> tuple[str, str]:
    user = get_user(user_id)
    if not user:
        return "", ""
    return user.pending_yookassa_payment_id or "", user.pending_yookassa_payment_url or ""


def clear_pending_yookassa_payment(user_id: int) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == user_id).first()
        if user:
            user.pending_yookassa_payment_id = ""
            user.pending_yookassa_payment_url = ""
            db.commit()
    finally:
        db.close()


def save_telegram_payment_charge(user_id: int, charge_id: str) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == user_id).first()
        if user:
            user.last_telegram_payment_charge_id = charge_id
            db.commit()
    finally:
        db.close()


def create_yookassa_payment_sync(user_id: int) -> tuple[str, str, str]:
    if not is_yookassa_configured():
        raise RuntimeError("YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY are not configured.")

    try:
        from yookassa import Configuration, Payment
    except ImportError as exc:
        raise RuntimeError("Package yookassa is not installed. Run: pip install yookassa") from exc

    Configuration.configure(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY)
    payment = Payment.create(
        {
            "amount": {
                "value": PREMIUM_PRICE_RUB,
                "currency": "RUB",
            },
            "capture": True,
            "confirmation": {
                "type": "redirect",
                "return_url": YOOKASSA_RETURN_URL,
            },
            "description": f"English Hub Premium {DEFAULT_PREMIUM_DAYS} days",
            "metadata": {
                "telegram_id": str(user_id),
                "product": "premium",
                "days": str(DEFAULT_PREMIUM_DAYS),
            },
        },
        str(uuid4()),
    )
    confirmation = object_value(payment, "confirmation") or {}
    confirmation_url = object_value(confirmation, "confirmation_url")
    if not confirmation_url:
        raise RuntimeError("YooKassa did not return confirmation_url.")

    return object_value(payment, "id"), object_value(payment, "status"), confirmation_url


def get_yookassa_payment_status_sync(payment_id: str) -> str:
    if not is_yookassa_configured():
        raise RuntimeError("YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY are not configured.")

    try:
        from yookassa import Configuration, Payment
    except ImportError as exc:
        raise RuntimeError("Package yookassa is not installed. Run: pip install yookassa") from exc

    Configuration.configure(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY)
    payment = Payment.find_one(payment_id)
    return object_value(payment, "status") or ""


def premium_limit_text() -> str:
    return (
        "Дневной лимит Free закончился.\n\n"
        f"{get_free_plan_text()}\n\n"
        f"{get_premium_plan_text()}"
    )


def get_level(user_id: int) -> str:
    user = get_user(user_id)
    if user and user.level:
        return normalize_level(user.level)
    return DEFAULT_LEVEL


def get_words_per_day(user_id: int) -> int | None:
    user = get_user(user_id)
    return user.words_per_day if user else None


def get_current_topic_number(user_id: int) -> int:
    user = get_user(user_id)
    if not user or user.current_topic_index is None:
        return 1
    return user.current_topic_index + 1


def get_roadmap_status_text(user_id: int) -> str:
    user = get_user(user_id)
    if not user:
        return "не начат"
    if is_roadmap_review_due(user):
        return "повторение"
    return f"тема {get_current_topic_number(user_id)}"


def format_topic_title(topic: str) -> str:
    return topic.replace(" and ", " & ").capitalize()


def progress_bar(done: int, total: int, width: int = 10) -> str:
    if total <= 0:
        return "□" * width
    filled = round((done / total) * width)
    return "■" * filled + "□" * (width - filled)


def is_roadmap_review_due(user: User) -> bool:
    current_index = max(user.current_topic_index or 0, 0)
    review_index = max(user.roadmap_review_index or 0, 0)
    return current_index > 0 and current_index - review_index >= ROADMAP_REVIEW_INTERVAL


def get_roadmap_review_topics(user: User) -> list[str]:
    level = normalize_level(user.level)
    topics = ROADMAP.get(level, [])
    current_index = min(max(user.current_topic_index or 0, 0), len(topics))
    review_index = min(max(user.roadmap_review_index or 0, 0), current_index)
    return topics[review_index:current_index]


def split_roadmap_lesson(text: str) -> dict:
    sections = {"theory_1": "", "theory_2": "", "practice": ""}
    current = None

    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        marker = line.upper()
        if marker == "===THEORY_1===":
            current = "theory_1"
            continue
        if marker == "===THEORY_2===":
            current = "theory_2"
            continue
        if marker == "===PRACTICE===":
            current = "practice"
            continue
        if current:
            sections[current] += raw_line + "\n"

    for key, value in sections.items():
        sections[key] = value.strip()

    if not any(sections.values()):
        sections["theory_1"] = text.strip()

    return sections


def split_practice_questions(text: str) -> list[str]:
    matches = re.findall(
        r"(?ms)^\s*\d{1,2}[\).:-]\s+(.*?)(?=^\s*\d{1,2}[\).:-]\s+|\Z)",
        text or "",
    )
    questions = [match.strip() for match in matches if match.strip()]
    if questions:
        return questions[:5]

    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    return lines[:5] if lines else [text.strip()]


def format_practice_question(question: str, index: int, total: int) -> str:
    return f"Практика {index + 1}/{total}\n\n{question}"


def format_roadmap_answers(answers: list[dict]) -> str:
    parts = []
    for index, item in enumerate(answers, start=1):
        question = item.get("question", "").strip()
        answer = item.get("answer", "").strip()
        parts.append(f"{index}. Task: {question}\nStudent answer: {answer}")
    return "\n\n".join(parts)


def get_roadmap_snapshot(user: User) -> dict:
    level = normalize_level(user.level)
    topics = ROADMAP.get(level, [])
    total = len(topics)
    raw_index = user.current_topic_index or 0
    current_index = max(raw_index, 0)
    done = min(current_index, total)
    current_topic = topics[current_index] if current_index < total else None
    next_topics = topics[current_index + 1:current_index + 6] if current_topic else []
    percent = round((done / total) * 100) if total else 0
    review_due = is_roadmap_review_due(user)
    review_topics = get_roadmap_review_topics(user) if review_due else []

    return {
        "level": level,
        "label": level_label(level),
        "topics": topics,
        "total": total,
        "done": done,
        "current_index": current_index,
        "current_topic": current_topic,
        "next_topics": next_topics,
        "percent": percent,
        "review_due": review_due,
        "review_topics": review_topics,
    }


def build_roadmap_text(user_id: int) -> str:
    user = get_user(user_id)
    if not user:
        return "Пользователь не найден. Нажмите /start."

    snapshot = get_roadmap_snapshot(user)
    total = snapshot["total"]
    done = snapshot["done"]

    if not snapshot["current_topic"]:
        return (
            "🗺 План обучения\n\n"
            f"Уровень: {snapshot['label']}\n"
            f"Прогресс: {done}/{total} тем • 100%\n"
            f"{progress_bar(done, total)}\n\n"
            "✅ План уровня завершён. Можно сменить уровень в профиле и продолжить."
        )

    if snapshot["review_due"]:
        review_lines = "\n".join(
            f"• {format_topic_title(topic)}"
            for topic in snapshot["review_topics"]
        )
        return (
            "🗺 План обучения\n\n"
            f"Уровень: {snapshot['label']}\n"
            f"Прогресс: {done}/{total} тем • {snapshot['percent']}%\n"
            f"{progress_bar(done, total)}\n\n"
            "Сейчас: повторение\n"
            f"{review_lines}\n\n"
            "Почему это важно:\n"
            "После нескольких новых тем бот возвращает старые темы, чтобы они закрепились, а не просто пролетели мимо.\n\n"
            "Формат урока:\n"
            "1. Теория 1 — смысл\n"
            "2. Теория 2 — частые ошибки\n"
            "3. Практика — 5 заданий"
        )

    next_lines = "\n".join(
        f"{snapshot['current_index'] + offset + 1}. {format_topic_title(topic)}"
        for offset, topic in enumerate(snapshot["next_topics"], start=1)
    )
    if not next_lines:
        next_lines = "Это последняя тема уровня."

    return (
        "🗺 План обучения\n\n"
        f"Уровень: {snapshot['label']}\n"
        f"Прогресс: {done}/{total} тем • {snapshot['percent']}%\n"
        f"{progress_bar(done, total)}\n\n"
        "Текущий шаг:\n"
        f"{snapshot['current_index'] + 1}. {format_topic_title(snapshot['current_topic'])}\n\n"
        "Следующие темы:\n"
        f"{next_lines}\n\n"
        "Как это работает:\n"
        "1. Теория 1 — смысл темы.\n"
        "2. Теория 2 — как использовать и где ошибаются.\n"
        "3. Практика — 5 заданий.\n"
        f"4. Каждые {ROADMAP_REVIEW_INTERVAL} темы — повторение."
    )


def menu_back_label() -> str:
    return "◀️ Главное меню"


def cancel_label() -> str:
    return "✖️ Отмена"


def mode_prompt_text(mode: str) -> str:
    prompts = {
        "explain": (
            "📘 Объяснение темы\n"
            "Напишите тему, которую хотите понять.\n\n"
            "Примеры:\n"
            "• Present Simple\n"
            "• difference between much and many\n"
            "• how to use should\n\n"
            "После объяснения я дам мини-задание и смогу проверить ваш ответ."
        ),
        "summary": (
            "📝 Краткий конспект\n"
            "Напишите тему, и я соберу короткую шпаргалку.\n\n"
            "Примеры:\n"
            "• Past Simple\n"
            "• articles a/an/the\n"
            "• phrasal verbs with get"
        ),
        "quiz": (
            "🧩 Мини-тест\n"
            "Напишите тему, и я сделаю 5 вопросов без ответов заранее.\n\n"
            "Примеры:\n"
            "• Present Perfect\n"
            "• prepositions of place\n"
            "• conditionals"
        ),
        "practice": (
            "✍️ Практика с проверкой\n"
            "Напишите тему, и я дам 5 заданий. Потом вы отправите ответы, а я проверю.\n\n"
            "Примеры:\n"
            "• to be\n"
            "• comparatives\n"
            "• job interview phrases"
        ),
        "chat": (
            "💬 Чат-тренировка\n"
            "Напишите ситуацию для диалога.\n\n"
            "Примеры:\n"
            "• small talk at work\n"
            "• airport conversation\n"
            "• job interview"
        ),
    }
    return prompts.get(mode, "✍️ Напишите тему, с которой хотите поработать.")


def build_main_menu_text(user_id: int) -> str:
    level = level_label(get_level(user_id))
    words_per_day = get_words_per_day(user_id)
    words_text = f"{words_per_day} в день" if words_per_day else "не настроено"
    roadmap_status = get_roadmap_status_text(user_id)
    plan = get_premium_status_text(user_id)
    ai_usage = get_ai_usage_text(user_id)

    return (
        "✨ English Hub\n"
        "Выберите действие ниже. Самый простой старт — «Объяснить тему» или «План обучения».\n\n"
        "Ваш прогресс\n"
        f"• Тариф: {plan}\n"
        f"• AI: {ai_usage}\n"
        f"• Уровень: {level}\n"
        f"• Словарь: {words_text}\n"
        f"• План обучения: {roadmap_status}\n\n"
        f"💡 {get_phrase()}"
    )


def build_learning_menu_text() -> str:
    return (
        "📘 Обучение\n"
        "Здесь можно разобрать тему или получить короткую шпаргалку.\n\n"
        "• Объяснить тему — урок + мини-задание\n"
        "• Конспект — короткая выжимка\n"
        f"• Слова на день — до {FREE_MAX_WORDS_PER_DAY} слов в Free"
    )


def build_practice_menu_text() -> str:
    return (
        "🧠 Практика\n"
        "Здесь бот даёт задания и проверяет ваши ответы.\n\n"
        "• Мини-тест — 5 вопросов по теме\n"
        "• Практика — 5 заданий с проверкой"
    )


def build_advanced_menu_text() -> str:
    return (
        "🚀 Продвинутые режимы\n"
        "Выберите формат тренировки.\n\n"
        "• План обучения — пошаговые темы по уровню\n"
        "• Чат-тренировка — диалог по ситуации\n"
        "• Голос — скоро"
    )


def build_settings_menu_text(user_id: int) -> str:
    level = level_label(get_level(user_id))
    words_per_day = get_words_per_day(user_id)
    words_text = f"{words_per_day} в день" if words_per_day else "не настроено"
    plan = get_premium_status_text(user_id)
    ai_usage = get_ai_usage_text(user_id)

    return (
        "⚙️ Профиль и настройки\n"
        "Ваши текущие параметры обучения.\n\n"
        f"• Тариф: {plan}\n"
        f"• AI: {ai_usage}\n"
        f"• Уровень: {level}\n"
        f"• Словарь: {words_text}\n\n"
        f"{get_free_plan_text() if not is_premium(user_id) else get_premium_plan_text()}\n\n"
        "Здесь можно поменять уровень и открыть справку."
    )


def build_premium_text(user_id: int) -> str:
    status = get_premium_status_text(user_id)
    ai_usage = get_ai_usage_text(user_id)
    yookassa_text = f"{PREMIUM_PRICE_RUB} RUB через ЮKassa" if is_yookassa_configured() else "ЮKassa не настроена"

    return (
        "💎 Premium\n"
        f"Статус: {status}\n"
        f"AI сегодня: {ai_usage}\n\n"
        f"{get_free_plan_text()}\n\n"
        f"{get_premium_plan_text()}\n\n"
        f"Telegram Stars: {PREMIUM_STARS_PRICE} ⭐\n"
        f"Карта: {yookassa_text}\n"
        f"Оплата: {PREMIUM_PAYMENT_TEXT}\n\n"
        "Выберите удобный способ оплаты ниже."
    )


def main_menu(user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📘 Объяснить тему", callback_data="mode_explain"),
            InlineKeyboardButton(text="📝 Конспект", callback_data="mode_summary"),
        ],
        [
            InlineKeyboardButton(text="🧩 Мини-тест", callback_data="mode_quiz"),
            InlineKeyboardButton(text="✍️ Практика", callback_data="mode_practice"),
        ],
        [
            InlineKeyboardButton(text="🗺 План обучения", callback_data="mode_roadmap"),
            InlineKeyboardButton(text="✨ Слова на день", callback_data="vocab_settings"),
        ],
        [InlineKeyboardButton(text="💎 Premium", callback_data="premium")],
        [
            InlineKeyboardButton(text="⚙️ Профиль", callback_data="menu_settings"),
            InlineKeyboardButton(text="❔ Помощь", callback_data="help"),
        ],
        [
            InlineKeyboardButton(text="📖 Глоссарий", callback_data="glossary"),
            InlineKeyboardButton(text="📂 Разделы", callback_data="menu_learning"),
        ],
    ])


def learning_menu(user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📘 Объяснить тему", callback_data="mode_explain"),
            InlineKeyboardButton(text="📝 Конспект", callback_data="mode_summary"),
        ],
        [InlineKeyboardButton(text="✨ Слова на день", callback_data="vocab_settings")],
        [InlineKeyboardButton(text=menu_back_label(), callback_data="back_main")],
    ])


def practice_menu(user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🧩 Мини-тест", callback_data="mode_quiz"),
            InlineKeyboardButton(text="✍️ Практика", callback_data="mode_practice"),
        ],
        [InlineKeyboardButton(text=menu_back_label(), callback_data="back_main")],
    ])


def advanced_menu(user_id: int):
    def lock(text: str, key: str) -> str:
        if MODES[key]["premium"] and not is_premium(user_id):
            return f"{text} 🔒"
        return text

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=lock("💬 Чат-тренировка", "chat"), callback_data="mode_chat"),
            InlineKeyboardButton(text=lock("🗺 План обучения", "roadmap"), callback_data="mode_roadmap"),
        ],
        [InlineKeyboardButton(text=lock("🎤 Голос скоро", "voice"), callback_data="mode_voice")],
        [InlineKeyboardButton(text=menu_back_label(), callback_data="back_main")],
    ])


def settings_menu(user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎯 Уровень", callback_data="change_level"),
            InlineKeyboardButton(text="❔ Помощь", callback_data="help"),
        ],
        [InlineKeyboardButton(text="💎 Premium", callback_data="premium")],
        [InlineKeyboardButton(text=menu_back_label(), callback_data="back_main")],
    ])


def premium_kb():
    rows = [
        [InlineKeyboardButton(text="⭐ Оплатить Stars", callback_data="premium_stars")],
    ]
    if is_yookassa_configured():
        rows.append([InlineKeyboardButton(text="💳 Оплатить картой", callback_data="premium_yookassa")])
        rows.append([InlineKeyboardButton(text="🔄 Проверить оплату картой", callback_data="premium_check")])
    rows.append([InlineKeyboardButton(text="🧾 Ручная проверка", callback_data="premium_request")])
    rows.append([InlineKeyboardButton(text=menu_back_label(), callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def roadmap_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ Начать урок", callback_data="roadmap_start")],
        [InlineKeyboardButton(text="🔄 Сбросить прогресс", callback_data="roadmap_reset_confirm")],
        [InlineKeyboardButton(text=menu_back_label(), callback_data="back_main")],
    ])


def roadmap_reset_confirm_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, сбросить", callback_data="roadmap_reset"),
            InlineKeyboardButton(text="✖️ Нет", callback_data="mode_roadmap"),
        ],
        [InlineKeyboardButton(text=menu_back_label(), callback_data="back_main")],
    ])


def roadmap_lesson_step_kb(next_text: str, next_callback: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=next_text, callback_data=next_callback)],
        [InlineKeyboardButton(text=cancel_label(), callback_data="cancel")],
        [InlineKeyboardButton(text=menu_back_label(), callback_data="back_main")],
    ])


def yookassa_payment_kb(confirmation_url: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Перейти к оплате", url=confirmation_url)],
        [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data="premium_check")],
        [InlineKeyboardButton(text=menu_back_label(), callback_data="back_main")],
    ])


def cancel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=cancel_label(), callback_data="cancel")],
    ])


def after_explain_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Дать ещё практику по теме", callback_data="practice")],
        [InlineKeyboardButton(text="✨ Слова на день", callback_data="vocab_settings")],
        [InlineKeyboardButton(text=menu_back_label(), callback_data="back_main")],
    ])


def level_kb(current: str):
    current = normalize_level(current)
    rows = []
    for code, label in LEVELS:
        prefix = "✅ " if current == code else ""
        rows.append([InlineKeyboardButton(text=f"{prefix}{label}", callback_data=f"set_level:{code}")])

    rows.append([InlineKeyboardButton(text=menu_back_label(), callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def level_change_confirm_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🧪 Пройти тест", callback_data="level_test_yes"),
            InlineKeyboardButton(text="✖️ Отмена", callback_data="level_test_cancel"),
        ],
    ])


def level_question_kb(question: dict):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=option, callback_data=f"level_answer:{index}")]
        for index, option in enumerate(question["options"])
    ])


def vocab_count_kb(user_id: int, current_value: int | None = None):
    rows = []
    row = []
    max_words = PREMIUM_MAX_WORDS_PER_DAY if is_premium(user_id) else FREE_MAX_WORDS_PER_DAY

    for value in range(3, 11):
        prefix = "✅ " if current_value == value else ""
        suffix = "" if value <= max_words else " 🔒"
        row.append(InlineKeyboardButton(text=f"{prefix}{value}{suffix}", callback_data=f"set_vocab_count:{value}"))
        if len(row) == 4:
            rows.append(row)
            row = []

    if row:
        rows.append(row)

    rows.append([InlineKeyboardButton(text=menu_back_label(), callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


class Registration(StatesGroup):
    name = State()
    birthdate = State()
    frequency = State()


class StudyFlow(StatesGroup):
    waiting_topic = State()
    waiting_practice_answer = State()
    viewing_roadmap_lesson = State()
    waiting_roadmap_answer = State()


class LevelChangeFlow(StatesGroup):
    confirming = State()
    testing = State()


async def delete_later(msg: Message, delay: int = 10):
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except Exception:
        pass


async def notify_bot_started(bot: Bot) -> None:
    if not ADMIN_TELEGRAM_ID:
        logging.info("TELEGRAM_ADMIN_ID is not set. Startup notification skipped.")
        return

    try:
        admin_id = int(ADMIN_TELEGRAM_ID)
    except ValueError:
        logging.warning("TELEGRAM_ADMIN_ID must be numeric. Startup notification skipped.")
        return

    try:
        me = await bot.get_me()
        msg = await bot.send_message(admin_id, f"Bot @{me.username or me.first_name} started successfully.")
        asyncio.create_task(delete_later(msg, 5))
    except Exception as exc:
        logging.exception("Failed to send startup notification: %s", exc)


async def main():
    logging.basicConfig(level=logging.INFO)
    Base.metadata.create_all(bind=engine)
    ensure_user_progress_columns()

    if not BOT_TOKEN:
        raise RuntimeError(f"BOT_TOKEN is missing. Env file: {ENV_PATH}")

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    async def show_main_menu(message: Message, state: FSMContext):
        await state.clear()
        await message.answer(
            build_main_menu_text(message.from_user.id),
            reply_markup=main_menu(message.from_user.id),
        )

    async def show_help(message: Message):
        await message.answer(
            "❔ Как пользоваться\n\n"
            "1. Нажмите кнопку в главном меню.\n"
            "2. Если бот просит тему, напишите её обычным текстом.\n"
            "3. Если бот дал задание, отправьте ответ одним сообщением.\n\n"
            "Что выбрать:\n"
            "• Объяснить тему — когда хотите понять правило\n"
            "• Конспект — когда нужна короткая шпаргалка\n"
            "• Мини-тест — когда хотите проверить себя\n"
            "• Практика — когда хотите задания с проверкой\n"
            "• План обучения — когда не знаете, что учить дальше\n"
            "• Слова на день — ежедневный словарь\n\n"
            "Команды: /start, /help, /cancel, /premium"
        )

    async def cancel_action(message: Message, state: FSMContext, user_id: int | None = None):
        menu_user_id = user_id or message.from_user.id
        await state.clear()
        await message.answer(
            "✖️ Действие отменено.\n\n" + build_main_menu_text(menu_user_id),
            reply_markup=main_menu(menu_user_id),
        )

    async def change_level_action(message: Message, user_id: int):
        current = get_level(user_id)
        await message.answer(
            f"🎯 Уровень\n\nСейчас: {level_label(current)}\n\nВыберите новый уровень. После выбора бот предложит короткий тест.",
            reply_markup=level_kb(current),
        )

    async def show_premium(message: Message, user_id: int):
        await message.answer(build_premium_text(user_id), reply_markup=premium_kb())

    async def show_roadmap(message: Message, user_id: int):
        await message.answer(build_roadmap_text(user_id), reply_markup=roadmap_kb())

    async def reset_roadmap_progress(message: Message, user_id: int):
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.telegram_id == user_id).first()
            if not user:
                await message.answer("Пользователь не найден. Нажмите /start.")
                return

            user.current_topic_index = 0
            user.roadmap_review_index = 0
            user.last_result = ""
            db.commit()
        finally:
            db.close()

        await message.answer("🔄 Прогресс плана обучения сброшен.", reply_markup=roadmap_kb())
        await message.answer(build_roadmap_text(user_id), reply_markup=roadmap_kb())

    async def send_stars_invoice(bot: Bot, user_id: int):
        payload = f"premium_stars:{user_id}:{uuid4().hex[:16]}"
        await bot.send_invoice(
            chat_id=user_id,
            title=f"Premium на {DEFAULT_PREMIUM_DAYS} дней",
            description="Безлимитные AI-объяснения, проверка практики и roadmap.",
            payload=payload,
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label="Premium", amount=PREMIUM_STARS_PRICE)],
        )

    async def create_yookassa_payment(message: Message, user_id: int):
        if not is_yookassa_configured():
            await message.answer(
                "ЮKassa пока не настроена. Добавьте YOOKASSA_SHOP_ID и YOOKASSA_SECRET_KEY в .env.",
                reply_markup=premium_kb(),
            )
            return

        try:
            payment_id, status, confirmation_url = await asyncio.to_thread(create_yookassa_payment_sync, user_id)
        except Exception as exc:
            logging.exception("Failed to create YooKassa payment: %s", exc)
            await message.answer(f"Не получилось создать платеж ЮKassa: {exc}", reply_markup=premium_kb())
            return

        save_pending_yookassa_payment(user_id, payment_id, confirmation_url)
        await message.answer(
            f"💳 Платеж создан.\nСтатус: {status}\nСумма: {PREMIUM_PRICE_RUB} RUB\n\nПосле оплаты вернитесь в бот и нажмите «Проверить оплату».",
            reply_markup=yookassa_payment_kb(confirmation_url),
        )

    async def check_yookassa_payment(message: Message, user_id: int):
        payment_id, confirmation_url = get_pending_yookassa_payment(user_id)
        if not payment_id:
            await message.answer("Активного платежа ЮKassa нет. Создайте новый платеж.", reply_markup=premium_kb())
            return

        try:
            status = await asyncio.to_thread(get_yookassa_payment_status_sync, payment_id)
        except Exception as exc:
            logging.exception("Failed to check YooKassa payment: %s", exc)
            await message.answer(f"Не получилось проверить платеж ЮKassa: {exc}", reply_markup=premium_kb())
            return

        if status == "succeeded":
            premium_until = grant_premium(user_id, DEFAULT_PREMIUM_DAYS)
            clear_pending_yookassa_payment(user_id)
            await message.answer(
                f"✅ Оплата прошла. Premium активирован до {premium_until}.",
                reply_markup=main_menu(user_id),
            )
            return

        if status == "canceled":
            clear_pending_yookassa_payment(user_id)
            await message.answer("Платеж отменен. Можно создать новый платеж.", reply_markup=premium_kb())
            return

        await message.answer(
            f"Платеж пока не завершен.\nСтатус: {status}",
            reply_markup=yookassa_payment_kb(confirmation_url) if confirmation_url else premium_kb(),
        )

    async def ensure_ai_quota(message: Message, user_id: int) -> bool:
        allowed, remaining = consume_ai_request(user_id)
        if allowed:
            if remaining >= 0 and remaining <= 1:
                await message.answer(f"ℹ️ Осталось AI-запросов сегодня: {remaining}/{FREE_DAILY_AI_LIMIT}.")
            return True

        await message.answer(premium_limit_text(), reply_markup=premium_kb())
        return False

    async def notify_admin_about_premium_request(bot: Bot, message: Message, requester):
        if not ADMIN_TELEGRAM_ID:
            await message.answer(
                "Заявка зафиксирована, но TELEGRAM_ADMIN_ID не настроен. Администратору нужно добавить его в .env.",
                reply_markup=main_menu(requester.id),
            )
            return

        username = f"@{requester.username}" if requester.username else "без username"
        text = (
            "💎 Premium request\n\n"
            f"User ID: {requester.id}\n"
            f"Name: {requester.full_name}\n"
            f"Username: {username}\n\n"
            f"Выдать доступ: /grant_premium {requester.id} {DEFAULT_PREMIUM_DAYS}"
        )

        try:
            await bot.send_message(int(ADMIN_TELEGRAM_ID), text)
            await message.answer(
                "✅ Заявка отправлена администратору. После проверки оплаты Premium будет включен.",
                reply_markup=main_menu(requester.id),
            )
        except Exception as exc:
            logging.exception("Failed to send premium request to admin: %s", exc)
            await message.answer(
                "Не получилось отправить заявку администратору. Попробуйте позже.",
                reply_markup=main_menu(requester.id),
            )

    async def send_level_question(message: Message, state: FSMContext):
        data = await state.get_data()
        questions = data["level_questions"]
        index = data["level_index"]
        question = questions[index]
        await message.answer(
            f"🧪 Вопрос {index + 1}/5\n\n{question['question']}",
            reply_markup=level_question_kb(question),
        )

    def normalize_vocab_key(word: str) -> str:
        return (word or "").strip().lower()

    def parse_vocab_entries(text: str) -> list[dict]:
        entries = []
        for raw_line in (text or "").splitlines():
            line = raw_line.strip()
            if not line or "|" not in line:
                continue

            parts = [part.strip(" -\t") for part in line.split("|")]
            if len(parts) < 4:
                continue

            word, translation, example, example_translation = parts[:4]
            if not word or not translation:
                continue

            entries.append({
                "word": word,
                "translation": translation,
                "example": example,
                "example_translation": example_translation,
            })
        return entries

    def format_vocab_entries(entries: list[dict]) -> str:
        blocks = []
        for index, entry in enumerate(entries, start=1):
            blocks.append(
                f"{index}. {entry['word']} — {entry['translation']}\n"
                f"   {entry['example']}\n"
                f"   {entry['example_translation']}"
            )
        return "\n\n".join(blocks)

    def filter_vocab_entries(entries: list[dict], recent_words: list[str], target_count: int) -> list[dict]:
        recent_keys = {normalize_vocab_key(word) for word in recent_words}
        seen_keys = set()
        result = []

        for entry in entries:
            key = normalize_vocab_key(entry["word"])
            if not key or key in recent_keys or key in seen_keys:
                continue

            seen_keys.add(key)
            result.append(entry)
            if len(result) >= target_count:
                break

        return result

    async def show_vocab_settings(message: Message, user_id: int):
        current_value = get_words_per_day(user_id) or DEFAULT_WORDS_PER_DAY
        max_words = PREMIUM_MAX_WORDS_PER_DAY if is_premium(user_id) else FREE_MAX_WORDS_PER_DAY
        await message.answer(
            "✨ Настройка словаря\n"
            "Выберите, сколько новых слов присылать каждый день.\n"
            f"Free: до {FREE_MAX_WORDS_PER_DAY} слов в день.\n"
            f"Premium: до {PREMIUM_MAX_WORDS_PER_DAY} слов в день.\n"
            f"Ваш максимум сейчас: {max_words}.",
            reply_markup=vocab_count_kb(user_id, current_value),
        )

    async def send_vocab_words(bot: Bot, user_id: int, force: bool = False):
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.telegram_id == user_id).first()
            if not user or not user.words_per_day:
                return False

            today = today_key()
            if not force and user.last_vocab_sent_date == today:
                return False

            user_is_premium = is_premium_user(user)
            level_code = user.level
            level = level_label(level_code)
            count = user.words_per_day
            recent_words = [
                item.word
                for item in db.query(VocabWord)
                .filter(VocabWord.telegram_id == user_id)
                .order_by(VocabWord.id.desc())
                .limit(RECENT_VOCAB_HISTORY_LIMIT)
                .all()
            ]
        finally:
            db.close()

        if not user_is_premium:
            allowed, _ = consume_ai_request(user_id)
            if not allowed:
                if force:
                    await bot.send_message(user_id, premium_limit_text(), reply_markup=premium_kb())
                return False

        raw_text = ask_ai(
            make_vocab_words_prompt(level, count + 5, recent_words),
            level,
            "vocabulary",
        )
        parsed_entries = parse_vocab_entries(raw_text)
        final_entries = filter_vocab_entries(parsed_entries, recent_words, count)
        if not final_entries:
            return False

        await bot.send_message(
            user_id,
            f"✨ Daily vocabulary\nУровень: {level}\nСлов сегодня: {len(final_entries)}\n\n{format_vocab_entries(final_entries)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=menu_back_label(), callback_data="back_main")],
            ]),
        )

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.telegram_id == user_id).first()
            if user:
                user.last_vocab_sent_date = today
                for entry in final_entries:
                    db.add(VocabWord(
                        telegram_id=user_id,
                        level=level_code,
                        word=entry["word"],
                        translation=entry["translation"],
                        example=entry["example"],
                        example_translation=entry["example_translation"],
                        sent_date=today,
                    ))
                db.commit()
            return True
        finally:
            db.close()

    async def vocab_daily_loop(bot: Bot):
        while True:
            try:
                now = datetime.now()
                if now.hour >= DAILY_VOCAB_HOUR:
                    db = SessionLocal()
                    users = db.query(User).all()
                    db.close()

                    for user in users:
                        try:
                            await send_vocab_words(bot, user.telegram_id)
                        except Exception as exc:
                            logging.exception("Failed to send daily vocabulary to %s: %s", user.telegram_id, exc)
            except Exception as exc:
                logging.exception("Vocabulary daily loop failed: %s", exc)

            await asyncio.sleep(3600)

    async def send_practice_task(message: Message, state: FSMContext, answer: str, topic: str, level: str, mode: str):
        await state.update_data(
            topic=topic,
            mode=mode,
            practice_task=answer,
            practice_topic=topic,
            practice_level=level,
            practice_mode=mode,
        )
        await state.set_state(StudyFlow.waiting_practice_answer)
        await message.answer(answer)
        await message.answer(
            "✍️ Напишите ответы одним сообщением, например: 1) ... 2) ... 3) ... 4) ... 5) ...\nЯ проверю и дам короткий фидбэк.",
            reply_markup=cancel_kb(),
        )

    async def check_practice_answer(message: Message, state: FSMContext, user_answer: str):
        data = await state.get_data()
        task = data.get("practice_task")
        topic = data.get("practice_topic", "")
        level = data.get("practice_level") or level_label(get_level(message.from_user.id))
        mode = data.get("practice_mode", "practice")

        if not task:
            await state.clear()
            await message.answer(
                "Задание потерялось. Попробуйте начать практику заново.",
                reply_markup=main_menu(message.from_user.id),
            )
            return

        prompt = make_practice_check_prompt(topic, level, task, user_answer, mode)
        if not await ensure_ai_quota(message, message.from_user.id):
            await state.clear()
            return

        msg = await message.answer("🤖 Проверяю ответы...")
        asyncio.create_task(delete_later(msg, 5))
        feedback = ask_ai(prompt, level, "practice_check")
        await state.clear()
        await message.answer(feedback, reply_markup=main_menu(message.from_user.id))

    def parse_roadmap_result(answer: str) -> bool:
        first_line = (answer or "").splitlines()[0].strip().lower()
        return "result: correct" in first_line

    async def send_roadmap_lesson(message: Message, state: FSMContext, user_id: int):
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.telegram_id == user_id).first()
            if not user:
                await state.clear()
                await message.answer("User not found. Please use /start first.")
                return

            review_due = is_roadmap_review_due(user)
            review_topics = get_roadmap_review_topics(user) if review_due else []
            topic = "review: " + ", ".join(review_topics) if review_due else get_current_topic(user)
            level = level_label(user.level)
            simplify = user.last_result in {"wrong_twice", "review_wrong"}
        finally:
            db.close()

        if not topic:
            await state.clear()
            await message.answer("✅ План обучения завершён.", reply_markup=roadmap_kb())
            return

        if not await ensure_ai_quota(message, user_id):
            await state.clear()
            return

        if review_due:
            lesson = ask_ai(make_roadmap_review_prompt(review_topics, level, simplify), level, "roadmap_review")
            roadmap_kind = "review"
            title = "Повторение: " + ", ".join(format_topic_title(topic) for topic in review_topics)
        else:
            lesson = ask_ai(make_roadmap_lesson_prompt(topic, level, simplify), level, "roadmap")
            roadmap_kind = "topic"
            title = format_topic_title(topic)

        sections = split_roadmap_lesson(lesson)
        theory_1 = sections["theory_1"] or lesson
        theory_2 = sections["theory_2"]
        practice_task = sections["practice"] or lesson
        await state.update_data(
            roadmap_topic=topic,
            roadmap_lesson=lesson,
            roadmap_theory_1=theory_1,
            roadmap_theory_2=theory_2,
            roadmap_practice_task=practice_task,
            roadmap_kind=roadmap_kind,
            roadmap_lesson_step="theory_1",
        )
        await state.set_state(StudyFlow.viewing_roadmap_lesson)
        await message.answer(f"🗺 Урок плана: {title}")
        next_text = "➡️ Дальше" if theory_2 else "🧠 К практике"
        next_callback = "roadmap_theory_2" if theory_2 else "roadmap_practice"
        theory_title = "Теория 1/2" if theory_2 else "Теория"
        await message.answer(
            f"{theory_title}\n\n{theory_1}",
            reply_markup=roadmap_lesson_step_kb(next_text, next_callback),
        )

    async def send_roadmap_theory_2(message: Message, state: FSMContext, user_id: int):
        data = await state.get_data()
        theory_2 = data.get("roadmap_theory_2")

        if not data.get("roadmap_practice_task"):
            await state.clear()
            await message.answer("Состояние урока потеряно. Запустите план обучения снова.", reply_markup=main_menu(user_id))
            return

        if not theory_2:
            await send_roadmap_practice(message, state, user_id)
            return

        await state.update_data(roadmap_lesson_step="theory_2")
        await state.set_state(StudyFlow.viewing_roadmap_lesson)
        await message.answer(
            f"Теория 2/2\n\n{theory_2}",
            reply_markup=roadmap_lesson_step_kb("🧠 К практике", "roadmap_practice"),
        )

    async def send_roadmap_practice(message: Message, state: FSMContext, user_id: int):
        data = await state.get_data()
        practice_task = data.get("roadmap_practice_task")

        if not practice_task:
            await state.clear()
            await message.answer("Состояние урока потеряно. Запустите план обучения снова.", reply_markup=main_menu(user_id))
            return

        questions = split_practice_questions(practice_task)
        await state.set_state(StudyFlow.waiting_roadmap_answer)
        await state.update_data(
            roadmap_lesson_step="practice",
            roadmap_practice_questions=questions,
            roadmap_practice_index=0,
            roadmap_practice_answers=[],
        )
        await message.answer(f"Практика: {len(questions)} заданий. Отвечайте по одному сообщению.")
        await message.answer(
            format_practice_question(questions[0], 0, len(questions)),
            reply_markup=cancel_kb(),
        )

    async def check_roadmap_answer(message: Message, state: FSMContext, user_answer: str):
        data = await state.get_data()
        topic = data.get("roadmap_topic")
        lesson = data.get("roadmap_lesson")
        practice_task = data.get("roadmap_practice_task") or lesson
        roadmap_kind = data.get("roadmap_kind", "topic")

        if not topic or not lesson:
            await state.clear()
            await message.answer(
                "Состояние roadmap потеряно. Запустите его снова.",
                reply_markup=main_menu(message.from_user.id),
            )
            return

        if not get_user(message.from_user.id):
            await state.clear()
            await message.answer("User not found. Please use /start first.")
            return

        if not await ensure_ai_quota(message, message.from_user.id):
            await state.clear()
            return

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
            if not user:
                await state.clear()
                await message.answer("User not found. Please use /start first.")
                return

            level = level_label(user.level)
            review = ask_ai(make_roadmap_check_prompt(topic, level, practice_task, user_answer), level, "roadmap_check")
            result = parse_roadmap_result(review)
            if roadmap_kind == "review":
                if result:
                    user.roadmap_review_index = user.current_topic_index or 0
                    user.last_result = "review_correct"
                else:
                    user.last_result = "review_wrong"
            else:
                update_progress(user, result)
            db.commit()
        finally:
            db.close()

        await state.clear()
        await message.answer(review)
        await message.answer(build_roadmap_text(message.from_user.id), reply_markup=roadmap_kb())

    async def explain_level_errors(wrong_answers: list[dict], target_level: str) -> str:
        details = "\n".join(
            f"- Topic: {item['topic']}\n  Question: {item['question']}\n  User answer: {item['selected_answer']}\n  Correct answer: {item['correct_answer']}"
            for item in wrong_answers
        )
        prompt = f"""
Student tried to switch to {level_label(target_level)} and made mistakes.

Explain briefly in Russian what went wrong.
Name the topics the student should review.
Be supportive, but say that it is too early to change level now.

Mistakes:
{details}
"""
        return ask_ai(prompt, level_label(target_level), "level_test")

    async def finish_level_test(call: CallbackQuery, state: FSMContext):
        data = await state.get_data()
        target_level = data["pending_level"]
        questions = data["level_questions"]
        answers = data["level_answers"]
        score = 0
        wrong_answers = []

        for question, selected_index in zip(questions, answers):
            if selected_index == question["correct_index"]:
                score += 1
            else:
                wrong_answers.append({
                    "topic": question["topic"],
                    "question": question["question"],
                    "selected_answer": question["options"][selected_index],
                    "correct_answer": question["answer"],
                })

        if score == 5:
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.telegram_id == call.from_user.id).first()
                if user:
                    user.level = target_level
                    user.current_topic_index = 0
                    user.last_result = ""
                    db.commit()
            finally:
                db.close()

            await state.clear()
            await call.message.answer(
                f"✅ Тест пройден: {score}/5\nУровень изменен на {level_label(target_level)}.",
                reply_markup=main_menu(call.from_user.id),
            )
            return

        topics = ", ".join(sorted({item["topic"] for item in wrong_answers}))
        mistakes_text = "\n".join(
            f"- {item['topic']}: ваш ответ — {item['selected_answer']} | правильный — {item['correct_answer']}"
            for item in wrong_answers
        )
        if not await ensure_ai_quota(call.message, call.from_user.id):
            await state.clear()
            return

        explanation = await explain_level_errors(wrong_answers, target_level)
        await state.clear()
        await call.message.answer(
            f"Результат: {score}/5\n\n"
            "Пока рано менять уровень.\n"
            f"Стоит повторить: {topics}\n\n"
            f"Ошибки:\n{mistakes_text}\n\n"
            f"{explanation}",
            reply_markup=main_menu(call.from_user.id),
        )

    @dp.message(Registration.name)
    async def reg_name(message: Message, state: FSMContext):
        name = (message.text or "").strip()
        if not name:
            await message.answer("Введите имя.")
            return

        if not re.match(r"^[A-Za-zА-Яа-яЁё]+$", name):
            await message.answer("Имя должно содержать только буквы.")
            return

        if len(name) > 20:
            await message.answer("Имя слишком длинное.")
            return

        await state.update_data(name=name)
        await state.set_state(Registration.birthdate)
        await message.answer("Введите дату рождения в формате 01.01.2000")

    @dp.message(Registration.birthdate)
    async def reg_birth(message: Message, state: FSMContext):
        text = (message.text or "").strip()
        try:
            birthdate = datetime.strptime(text, "%d.%m.%Y")
            if birthdate > datetime.now():
                await message.answer("Дата не может быть из будущего.")
                return
            if birthdate.year < 1900:
                await message.answer("Введите реальную дату.")
                return
        except Exception:
            await message.answer("Введите дату в формате 01.01.2000")
            return

        await state.update_data(birthdate=text)
        await state.set_state(Registration.frequency)
        await message.answer(
            "Как часто хотите заниматься?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📅 Каждый день", callback_data="freq_daily")],
                [InlineKeyboardButton(text="📘 3 раза в неделю", callback_data="freq_3")],
                [InlineKeyboardButton(text="🕊 1 раз в неделю", callback_data="freq_1")],
            ]),
        )

    @dp.callback_query(Registration.frequency, lambda c: c.data and c.data.startswith("freq_"))
    async def reg_freq(call: CallbackQuery, state: FSMContext):
        freq = call.data.replace("freq_", "")
        data = await state.get_data()
        name = data.get("name")
        birthdate = data.get("birthdate")

        if not name or not birthdate:
            await state.clear()
            await call.message.answer("Registration data was lost. Please start again with /start.")
            return

        db = SessionLocal()
        try:
            user = User(
                telegram_id=call.from_user.id,
                name=name,
                birthday=birthdate,
                frequency=freq,
                level=DEFAULT_LEVEL,
                current_topic_index=0,
                roadmap_review_index=0,
                last_result="",
                words_per_day=None,
                last_vocab_sent_date="",
                premium_until="",
                ai_requests_date="",
                ai_requests_count=0,
                pending_yookassa_payment_id="",
                pending_yookassa_payment_url="",
                last_telegram_payment_charge_id="",
            )
            db.add(user)
            db.commit()
        finally:
            db.close()

        await state.clear()
        await call.message.edit_text(
            f"✨ Добро пожаловать, {name}!\n\n"
            f"Стартовый уровень: {level_label(DEFAULT_LEVEL)}\n"
            "Откройте меню ниже и выберите нужный блок.",
            reply_markup=main_menu(call.from_user.id),
        )

    @dp.message(CommandStart())
    async def start(message: Message, state: FSMContext):
        if get_user(message.from_user.id):
            await show_main_menu(message, state)
        else:
            await state.set_state(Registration.name)
            await message.answer("Привет. Как тебя зовут?")

    @dp.message(Command("help"))
    async def help_cmd(message: Message):
        await show_help(message)

    @dp.message(Command("cancel"))
    async def cancel_cmd(message: Message, state: FSMContext):
        await cancel_action(message, state)

    @dp.message(Command("change_level"))
    async def change_level_cmd(message: Message):
        await change_level_action(message, message.from_user.id)

    @dp.message(Command("premium"))
    async def premium_cmd(message: Message):
        await show_premium(message, message.from_user.id)

    @dp.message(Command("grant_premium"))
    async def grant_premium_cmd(message: Message):
        if not is_admin(message.from_user.id):
            await message.answer("Эта команда доступна только администратору.")
            return

        parts = (message.text or "").split()
        if len(parts) < 2:
            await message.answer(f"Формат: /grant_premium USER_ID DAYS\nПример: /grant_premium 123456789 {DEFAULT_PREMIUM_DAYS}")
            return

        try:
            target_user_id = int(parts[1])
            days = int(parts[2]) if len(parts) > 2 else DEFAULT_PREMIUM_DAYS
        except ValueError:
            await message.answer("USER_ID и DAYS должны быть числами.")
            return

        if days <= 0:
            await message.answer("DAYS должен быть больше 0.")
            return

        premium_until = grant_premium(target_user_id, days)
        if not premium_until:
            await message.answer("Пользователь не найден. Он должен сначала открыть /start.")
            return

        await message.answer(f"✅ Premium выдан пользователю {target_user_id} до {premium_until}.")
        try:
            await bot.send_message(target_user_id, f"💎 Premium активирован до {premium_until}.")
        except Exception as exc:
            logging.exception("Failed to notify premium user %s: %s", target_user_id, exc)

    @dp.pre_checkout_query()
    async def pre_checkout_query(query: PreCheckoutQuery):
        payload = query.invoice_payload or ""
        if payload.startswith("premium_stars:"):
            await bot.answer_pre_checkout_query(query.id, ok=True)
            return

        await bot.answer_pre_checkout_query(
            query.id,
            ok=False,
            error_message="Неизвестный платеж. Попробуйте создать счет заново.",
        )

    @dp.message(lambda message: message.successful_payment is not None)
    async def successful_payment(message: Message):
        payment = message.successful_payment
        payload = payment.invoice_payload or ""
        if not payload.startswith("premium_stars:"):
            return

        premium_until = grant_premium(message.from_user.id, DEFAULT_PREMIUM_DAYS)
        save_telegram_payment_charge(message.from_user.id, payment.telegram_payment_charge_id)
        await message.answer(
            f"✅ Оплата Stars прошла. Premium активирован до {premium_until}.",
            reply_markup=main_menu(message.from_user.id),
        )

    @dp.callback_query()
    async def cb(call: CallbackQuery, state: FSMContext):
        data = call.data
        if not data:
            await call.answer()
            return

        if data == "help":
            await show_help(call.message)

        elif data == "premium":
            await show_premium(call.message, call.from_user.id)

        elif data == "premium_stars":
            await send_stars_invoice(bot, call.from_user.id)

        elif data == "premium_yookassa":
            await create_yookassa_payment(call.message, call.from_user.id)

        elif data == "premium_check":
            await check_yookassa_payment(call.message, call.from_user.id)

        elif data == "premium_request":
            await notify_admin_about_premium_request(bot, call.message, call.from_user)

        elif data == "roadmap_start":
            await send_roadmap_lesson(call.message, state, call.from_user.id)

        elif data == "roadmap_theory_2":
            await send_roadmap_theory_2(call.message, state, call.from_user.id)

        elif data == "roadmap_practice":
            await send_roadmap_practice(call.message, state, call.from_user.id)

        elif data == "roadmap_reset_confirm":
            await call.message.answer(
                "Сбросить план обучения на первую тему текущего уровня?",
                reply_markup=roadmap_reset_confirm_kb(),
            )

        elif data == "roadmap_reset":
            await state.clear()
            await reset_roadmap_progress(call.message, call.from_user.id)

        elif data == "cancel":
            await cancel_action(call.message, state, call.from_user.id)

        elif data == "level_test_cancel":
            await state.clear()
            await call.message.edit_text(build_main_menu_text(call.from_user.id), reply_markup=main_menu(call.from_user.id))

        elif data == "level_test_yes":
            state_data = await state.get_data()
            target_level = state_data.get("pending_level")
            if not target_level:
                await state.clear()
                await call.message.answer("Сначала выберите уровень.", reply_markup=main_menu(call.from_user.id))
                return

            await state.set_state(LevelChangeFlow.testing)
            await state.update_data(level_questions=get_level_test(target_level), level_index=0, level_answers=[])
            await call.message.edit_text(f"🧪 Тест на уровень {level_label(target_level)}")
            await send_level_question(call.message, state)

        elif data.startswith("level_answer:"):
            state_data = await state.get_data()
            questions = state_data.get("level_questions")
            index = state_data.get("level_index", 0)
            if not questions or index >= len(questions):
                await state.clear()
                await call.message.answer("Состояние теста потеряно.", reply_markup=main_menu(call.from_user.id))
                return

            selected_index = int(data.split(":", 1)[1])
            answers = state_data.get("level_answers", [])
            answers.append(selected_index)
            index += 1
            await state.update_data(level_answers=answers, level_index=index)
            await call.message.edit_reply_markup(reply_markup=None)

            if index >= len(questions):
                await finish_level_test(call, state)
            else:
                await send_level_question(call.message, state)

        elif data == "vocab_settings":
            await state.clear()
            await show_vocab_settings(call.message, call.from_user.id)

        elif data.startswith("set_vocab_count:"):
            value = int(data.split(":", 1)[1])
            if value < 3 or value > 10:
                await call.answer("Выберите число от 3 до 10.")
                return

            if not is_premium(call.from_user.id) and value > FREE_MAX_WORDS_PER_DAY:
                await call.message.answer(
                    f"🔒 В Free доступно до {FREE_MAX_WORDS_PER_DAY} слов в день. Больше — в Premium.",
                    reply_markup=premium_kb(),
                )
                return

            db = SessionLocal()
            try:
                user = db.query(User).filter(User.telegram_id == call.from_user.id).first()
                if not user:
                    await call.message.answer("User not found. Please use /start first.")
                    return

                user.words_per_day = value
                user.last_vocab_sent_date = ""
                db.commit()
            finally:
                db.close()

            await call.message.answer(
                f"✨ Словарь настроен: {value} слов в день.\n"
                "Самый комфортный темп для большинства — 5-7 слов в день."
            )
            await send_vocab_words(bot, call.from_user.id, force=True)

        elif data.startswith("mode_"):
            mode = data.replace("mode_", "")
            if MODES[mode]["premium"] and not is_premium(call.from_user.id):
                await call.message.answer("🔒 Этот режим доступен только в Premium.", reply_markup=premium_kb())
                return

            if mode == "voice":
                await call.message.answer(
                    "🎤 Голосовой режим пока готовится.\n\nСейчас можно пользоваться текстовыми режимами: объяснение, практика, тесты и план обучения.",
                    reply_markup=main_menu(call.from_user.id),
                )
                return

            if mode == "roadmap":
                await show_roadmap(call.message, call.from_user.id)
                return

            await state.update_data(mode=mode)
            await state.set_state(StudyFlow.waiting_topic)
            msg = await call.message.edit_text(mode_prompt_text(mode), reply_markup=cancel_kb())
            asyncio.create_task(delete_later(msg, 30))

        elif data == "change_level":
            await change_level_action(call.message, call.from_user.id)

        elif data == "noop":
            await call.answer()

        elif data == "menu_learning":
            await call.message.edit_text(build_learning_menu_text(), reply_markup=learning_menu(call.from_user.id))

        elif data == "menu_practice":
            await call.message.edit_text(build_practice_menu_text(), reply_markup=practice_menu(call.from_user.id))

        elif data == "menu_advanced":
            await call.message.edit_text(build_advanced_menu_text(), reply_markup=advanced_menu(call.from_user.id))

        elif data == "menu_settings":
            await call.message.edit_text(build_settings_menu_text(call.from_user.id), reply_markup=settings_menu(call.from_user.id))

        elif data == "back_main":
            await state.clear()
            await call.message.edit_text(build_main_menu_text(call.from_user.id), reply_markup=main_menu(call.from_user.id))

        elif data == "glossary":
            await call.message.edit_text("📖 Глоссарий\nВыберите раздел:", reply_markup=glossary_menu())

        elif data.startswith("glossary_"):
            category = data.replace("glossary_", "")
            await call.message.edit_text(glossary_text(category), reply_markup=glossary_menu())

        elif data == "practice":
            state_data = await state.get_data()
            topic = state_data.get("topic")
            level = level_label(get_level(call.from_user.id))

            if not topic:
                await call.message.answer("Тема потерялась. Попробуйте снова.", reply_markup=main_menu(call.from_user.id))
                return

            practice_prompt = make_practice_task_prompt(topic, level)
            if not await ensure_ai_quota(call.message, call.from_user.id):
                await state.clear()
                return

            answer = ask_ai(practice_prompt, level, "practice")
            await send_practice_task(call.message, state, answer, topic, level, "practice")

        elif data.startswith("set_level:"):
            level = normalize_level(data.split(":", 1)[1])
            await state.set_state(LevelChangeFlow.confirming)
            await state.update_data(pending_level=level)
            await call.message.edit_text(
                f"🎯 Хотите сменить уровень на {level_label(level)}?\n\nМожно подтвердить сразу и пройти короткий тест.",
                reply_markup=level_change_confirm_kb(),
            )

    @dp.message(StudyFlow.waiting_topic)
    async def topic_input(message: Message, state: FSMContext):
        topic = (message.text or "").strip()
        if not topic:
            data = await state.get_data()
            await message.answer(mode_prompt_text(data.get("mode", "explain")), reply_markup=cancel_kb())
            return

        data = await state.get_data()
        mode = data.get("mode", "explain")
        level = level_label(get_level(message.from_user.id))
        if not await ensure_ai_quota(message, message.from_user.id):
            await state.clear()
            return

        msg = await message.answer("🤖 Думаю...")
        asyncio.create_task(delete_later(msg, 5))
        prompt = make_user_prompt(topic, mode, level)

        try:
            answer = ask_ai(prompt, level, mode)
        except Exception as exc:
            await state.clear()
            await message.answer(f"Ошибка: {exc}")
            await message.answer(build_main_menu_text(message.from_user.id), reply_markup=main_menu(message.from_user.id))
            return

        await state.update_data(topic=topic, mode=mode)
        if mode == "explain":
            await state.update_data(
                practice_task=answer,
                practice_topic=topic,
                practice_level=level,
                practice_mode="explain",
            )
            await state.set_state(StudyFlow.waiting_practice_answer)
            await message.answer(answer, reply_markup=after_explain_kb())
            await message.answer(
                "✍️ В конце урока есть мини-задание. Отправьте ответ одним сообщением, и я его проверю.\n\nЕсли хотите просто выйти, нажмите «Главное меню».",
                reply_markup=cancel_kb(),
            )
        elif mode in {"quiz", "practice"}:
            await send_practice_task(message, state, answer, topic, level, mode)
        else:
            await state.clear()
            await message.answer(answer, reply_markup=main_menu(message.from_user.id))

    @dp.message(StudyFlow.waiting_practice_answer)
    async def practice_answer_input(message: Message, state: FSMContext):
        user_answer = (message.text or "").strip()
        if not user_answer:
            await message.answer("Напишите ответ текстом одним сообщением. Если передумали, нажмите «Отмена».", reply_markup=cancel_kb())
            return

        await check_practice_answer(message, state, user_answer)

    @dp.message(StudyFlow.viewing_roadmap_lesson)
    async def roadmap_theory_input(message: Message, state: FSMContext):
        data = await state.get_data()
        step = data.get("roadmap_lesson_step")
        if step == "theory_1" and data.get("roadmap_theory_2"):
            await message.answer(
                "Сейчас мы на теории. Нажмите «Дальше», потом перейдём к практике.",
                reply_markup=roadmap_lesson_step_kb("➡️ Дальше", "roadmap_theory_2"),
            )
        elif data.get("roadmap_practice_task"):
            await message.answer(
                "Теория уже открыта. Нажмите «К практике», чтобы перейти к заданиям.",
                reply_markup=roadmap_lesson_step_kb("🧠 К практике", "roadmap_practice"),
            )
        else:
            await state.clear()
            await message.answer("Состояние урока потеряно. Запустите план обучения снова.", reply_markup=main_menu(message.from_user.id))

    @dp.message(StudyFlow.waiting_roadmap_answer)
    async def roadmap_answer_input(message: Message, state: FSMContext):
        user_answer = (message.text or "").strip()
        if not user_answer:
            await message.answer("Напишите ответ на текущее задание. Если передумали, нажмите «Отмена».", reply_markup=cancel_kb())
            return

        data = await state.get_data()
        questions = data.get("roadmap_practice_questions") or [data.get("roadmap_practice_task", "")]
        index = data.get("roadmap_practice_index", 0)
        answers = data.get("roadmap_practice_answers", [])

        if index >= len(questions):
            await check_roadmap_answer(message, state, user_answer)
            return

        answers.append({
            "question": questions[index],
            "answer": user_answer,
        })
        index += 1

        if index < len(questions):
            await state.update_data(
                roadmap_practice_index=index,
                roadmap_practice_answers=answers,
            )
            await message.answer(
                format_practice_question(questions[index], index, len(questions)),
                reply_markup=cancel_kb(),
            )
            return

        await state.update_data(
            roadmap_practice_index=index,
            roadmap_practice_answers=answers,
        )
        await message.answer("Готово, проверяю все ответы вместе.")
        await check_roadmap_answer(message, state, format_roadmap_answers(answers))

    asyncio.create_task(vocab_daily_loop(bot))
    await notify_bot_started(bot)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
