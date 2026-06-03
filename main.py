import asyncio
import json
import logging
import os
import random
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
from database.models import Base, IrregularVerbHistory, RoadmapLessonCache, User, UserMistake, VocabWord
from glossary import glossary_menu, glossary_text
from level_tests import get_level_test
from modes import MODES
from motivation import get_phrase
from prompts import (
    make_chat_reply_prompt,
    make_chat_start_prompt,
    make_practice_check_prompt,
    make_practice_task_prompt,
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
DAILY_MISTAKE_HOUR = 18
DAILY_IRREGULAR_VERBS_HOUR = 19
DEFAULT_TIMEZONE_OFFSET = "+03:00"
DELIVERY_HOURS = list(range(8, 23))
TIMEZONE_OPTIONS = [
    ("-08:00", "Лос-Анджелес, Ванкувер"),
    ("-05:00", "Нью-Йорк, Торонто"),
    ("-03:00", "Буэнос-Айрес"),
    ("+00:00", "Лондон, Лиссабон"),
    ("+01:00", "Берлин, Париж, Рим"),
    ("+02:00", "Киев, Афины, Хельсинки"),
    ("+03:00", "Москва, Стамбул, Минск"),
    ("+04:00", "Дубай, Баку, Ереван"),
    ("+05:00", "Ташкент, Алматы"),
    ("+06:00", "Бишкек, Астана"),
    ("+07:00", "Бангкок, Джакарта"),
    ("+08:00", "Пекин, Сингапур"),
    ("+09:00", "Токио, Сеул"),
    ("+10:00", "Сидней"),
    ("+12:00", "Окленд"),
]
RECENT_VOCAB_HISTORY_LIMIT = 80
VOCAB_REVIEW_WORDS_COUNT = 8
VOCAB_REVIEW_INTERVAL_DAYS = 7
RECENT_IRREGULAR_VERBS_HISTORY_LIMIT = 60
IRREGULAR_VERBS_PER_DAY = 5
FREE_DAILY_AI_LIMIT = 5
FREE_MAX_WORDS_PER_DAY = 3
PREMIUM_MAX_WORDS_PER_DAY = 10
DEFAULT_PREMIUM_DAYS = 30
ROADMAP_REVIEW_INTERVAL = 3
ROADMAP_CACHE_VERSION = "v3"
ROADMAP_GENERATION_MAX_ATTEMPTS = 3
ROADMAP_MIN_THEORY_PAGES = 2
ROADMAP_MAX_THEORY_PAGES = 3
ROADMAP_MIN_THEORY_WORDS = 180
ROADMAP_MAX_THEORY_WORDS = 700
DAILY_GOAL_ERRORS_TARGET = 3
DAILY_GOAL_TOPICS_TARGET = 1
MASTERED_MISTAKES_PAGE_SIZE = 5
PLACEMENT_TEST_PLAN = [
    ("A1", 2),
    ("A2", 2),
    ("B1", 2),
    ("B2", 1),
    ("C1", 1),
]

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
IRREGULAR_VERBS = [
    ("be", "was/were", "been", "быть", "I was at home yesterday."),
    ("become", "became", "become", "становиться", "She became a doctor."),
    ("begin", "began", "begun", "начинать", "The lesson began at nine."),
    ("break", "broke", "broken", "ломать", "He broke his phone."),
    ("bring", "brought", "brought", "приносить", "Please bring your notebook."),
    ("buy", "bought", "bought", "покупать", "I bought a new book."),
    ("catch", "caught", "caught", "ловить; успевать", "We caught the bus."),
    ("choose", "chose", "chosen", "выбирать", "They chose the blue one."),
    ("come", "came", "come", "приходить", "She came home late."),
    ("do", "did", "done", "делать", "I did my homework."),
    ("drink", "drank", "drunk", "пить", "He drank some water."),
    ("drive", "drove", "driven", "водить", "My dad drove to work."),
    ("eat", "ate", "eaten", "есть", "We ate dinner together."),
    ("fall", "fell", "fallen", "падать", "The glass fell down."),
    ("feel", "felt", "felt", "чувствовать", "I felt tired."),
    ("find", "found", "found", "находить", "She found her keys."),
    ("forget", "forgot", "forgotten", "забывать", "I forgot his name."),
    ("get", "got", "got/gotten", "получать; становиться", "I got your message."),
    ("give", "gave", "given", "давать", "He gave me advice."),
    ("go", "went", "gone", "идти; ехать", "They went to the park."),
    ("grow", "grew", "grown", "расти", "The city grew fast."),
    ("have", "had", "had", "иметь", "We had a good day."),
    ("hear", "heard", "heard", "слышать", "I heard a strange sound."),
    ("keep", "kept", "kept", "хранить; держать", "She kept the ticket."),
    ("know", "knew", "known", "знать", "I knew the answer."),
    ("leave", "left", "left", "уходить; оставлять", "He left early."),
    ("lose", "lost", "lost", "терять", "I lost my wallet."),
    ("make", "made", "made", "делать; создавать", "She made breakfast."),
    ("meet", "met", "met", "встречать", "We met at school."),
    ("pay", "paid", "paid", "платить", "I paid by card."),
    ("put", "put", "put", "класть", "Put it on the table."),
    ("read", "read", "read", "читать", "I read the email."),
    ("run", "ran", "run", "бежать", "He ran very fast."),
    ("say", "said", "said", "сказать", "She said hello."),
    ("see", "saw", "seen", "видеть", "I saw him yesterday."),
    ("sell", "sold", "sold", "продавать", "They sold their car."),
    ("send", "sent", "sent", "отправлять", "I sent you a file."),
    ("sit", "sat", "sat", "сидеть", "We sat near the window."),
    ("sleep", "slept", "slept", "спать", "The baby slept well."),
    ("speak", "spoke", "spoken", "говорить", "He spoke English."),
    ("spend", "spent", "spent", "тратить; проводить время", "I spent two hours there."),
    ("stand", "stood", "stood", "стоять", "She stood by the door."),
    ("swim", "swam", "swum", "плавать", "They swam in the sea."),
    ("take", "took", "taken", "брать", "I took a taxi."),
    ("teach", "taught", "taught", "учить; преподавать", "My friend taught me chess."),
    ("tell", "told", "told", "рассказывать; говорить", "He told me the truth."),
    ("think", "thought", "thought", "думать", "I thought about it."),
    ("understand", "understood", "understood", "понимать", "She understood the rule."),
    ("wake", "woke", "woken", "просыпаться; будить", "I woke up early."),
    ("wear", "wore", "worn", "носить одежду", "He wore a black jacket."),
    ("win", "won", "won", "выигрывать", "Our team won the game."),
    ("write", "wrote", "written", "писать", "I wrote a short note."),
]


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


def now_key() -> str:
    return datetime.now().isoformat(timespec="seconds")


def parse_timezone_offset(offset: str | None) -> timedelta:
    offset = offset or DEFAULT_TIMEZONE_OFFSET
    match = re.match(r"^([+-])(\d{2}):(\d{2})$", offset)
    if not match:
        offset = DEFAULT_TIMEZONE_OFFSET
        match = re.match(r"^([+-])(\d{2}):(\d{2})$", offset)

    sign, hours, minutes = match.groups()
    delta = timedelta(hours=int(hours), minutes=int(minutes))
    return delta if sign == "+" else -delta


def user_local_datetime(user: User) -> datetime:
    return datetime.utcnow() + parse_timezone_offset(user.timezone_offset)


def user_local_today(user: User) -> str:
    return user_local_datetime(user).date().isoformat()


def ensure_daily_goal_state(user: User) -> str:
    today = user_local_today(user)
    if user.daily_goal_date != today:
        user.daily_goal_date = today
        user.daily_goal_errors_closed = 0
        user.daily_goal_topics_done = 0
    return today


def refresh_user_streak(user: User, today: str) -> None:
    if user.streak_last_date == today:
        return

    try:
        yesterday = (datetime.fromisoformat(today).date() - timedelta(days=1)).isoformat()
    except ValueError:
        yesterday = ""

    if user.streak_last_date == yesterday:
        user.streak_count = (user.streak_count or 0) + 1
    else:
        user.streak_count = 1
    user.streak_last_date = today


def visible_streak_count(user: User, today: str) -> int:
    if not user.streak_last_date:
        return 0
    if user.streak_last_date == today:
        return user.streak_count or 0

    try:
        yesterday = (datetime.fromisoformat(today).date() - timedelta(days=1)).isoformat()
    except ValueError:
        return 0
    if user.streak_last_date == yesterday:
        return user.streak_count or 0
    return 0


def record_daily_progress(user_id: int, errors_closed: int = 0, topics_done: int = 0) -> None:
    if errors_closed <= 0 and topics_done <= 0:
        return

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == user_id).first()
        if not user:
            return

        today = ensure_daily_goal_state(user)
        user.daily_goal_errors_closed = min(
            (user.daily_goal_errors_closed or 0) + max(errors_closed, 0),
            DAILY_GOAL_ERRORS_TARGET,
        )
        user.daily_goal_topics_done = min(
            (user.daily_goal_topics_done or 0) + max(topics_done, 0),
            DAILY_GOAL_TOPICS_TARGET,
        )
        refresh_user_streak(user, today)
        db.commit()
    finally:
        db.close()


def delivery_hour(value: int | None, default: int) -> int:
    if value is None:
        return default
    return value if 0 <= value <= 23 else default


def timezone_label(offset: str | None) -> str:
    offset = offset or DEFAULT_TIMEZONE_OFFSET
    for value, label in TIMEZONE_OPTIONS:
        if value == offset:
            return label
    return f"UTC{offset}"


def is_delivery_due(user: User, last_sent_date: str | None, target_hour: int) -> bool:
    local_now = user_local_datetime(user)
    return local_now.hour >= target_hour and last_sent_date != local_now.date().isoformat()


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
        "• Путь изучения, разбор темы, тренировка и шпаргалки\n"
        "• Путь изучения: готовые модули без расхода AI-запросов, новые темы тратят запрос\n"
        f"• Vocabulary до {FREE_MAX_WORDS_PER_DAY} слов в день\n"
        "• Глоссарий, профиль, уровень и помощь без лимита\n"
        "• Irregular verbs недоступны\n"
        "• Chat и Voice недоступны"
    )


def get_premium_plan_text() -> str:
    return (
        "Premium:\n"
        "• AI-запросы без дневного лимита\n"
        "• Разборы, тренировки и шпаргалки без лимита\n"
        "• Путь изучения без лимита\n"
        f"• Vocabulary до {PREMIUM_MAX_WORDS_PER_DAY} слов в день\n"
        f"• Irregular verbs: {IRREGULAR_VERBS_PER_DAY} неправильных глаголов в день\n"
        "• Чат-тренировка с AI-собеседником\n"
        "• Voice скоро\n"
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


def get_daily_goal_snapshot(user_id: int) -> dict:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == user_id).first()
        if not user:
            return {
                "streak": 0,
                "errors_closed": 0,
                "topics_done": 0,
                "date": today_key(),
            }

        today = ensure_daily_goal_state(user)
        db.commit()
        return {
            "streak": visible_streak_count(user, today),
            "errors_closed": user.daily_goal_errors_closed or 0,
            "topics_done": user.daily_goal_topics_done or 0,
            "date": today,
        }
    finally:
        db.close()


def build_daily_goal_text(user_id: int) -> str:
    snapshot = get_daily_goal_snapshot(user_id)
    errors_done = min(snapshot["errors_closed"], DAILY_GOAL_ERRORS_TARGET)
    topics_done = min(snapshot["topics_done"], DAILY_GOAL_TOPICS_TARGET)
    errors_marker = "✅" if errors_done >= DAILY_GOAL_ERRORS_TARGET else "▫️"
    topic_marker = "✅" if topics_done >= DAILY_GOAL_TOPICS_TARGET else "▫️"

    return (
        "Сегодняшняя цель\n"
        f"• Серия дней: {snapshot['streak']}\n"
        f"• {errors_marker} Закрыть ошибки: {errors_done}/{DAILY_GOAL_ERRORS_TARGET}\n"
        f"• {topic_marker} Пройти тему: {topics_done}/{DAILY_GOAL_TOPICS_TARGET}"
    )


def is_irregular_verbs_enabled(user_id: int) -> bool:
    user = get_user(user_id)
    return bool(user and user.irregular_verbs_enabled)


def get_delivery_settings(user_id: int) -> dict:
    user = get_user(user_id)
    if not user:
        return {
            "timezone_offset": DEFAULT_TIMEZONE_OFFSET,
            "vocab_hour": DAILY_VOCAB_HOUR,
            "mistake_hour": DAILY_MISTAKE_HOUR,
            "irregular_verbs_hour": DAILY_IRREGULAR_VERBS_HOUR,
        }

    return {
        "timezone_offset": user.timezone_offset or DEFAULT_TIMEZONE_OFFSET,
        "vocab_hour": delivery_hour(user.vocab_hour, DAILY_VOCAB_HOUR),
        "mistake_hour": delivery_hour(user.mistake_hour, DAILY_MISTAKE_HOUR),
        "irregular_verbs_hour": delivery_hour(user.irregular_verbs_hour, DAILY_IRREGULAR_VERBS_HOUR),
    }


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
    sections = {"theory_1": "", "theory_2": "", "theory_3": "", "quiz": ""}
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
        if marker == "===THEORY_3===":
            current = "theory_3"
            continue
        if marker in {"===QUIZ===", "===PRACTICE==="}:
            current = "quiz"
            continue
        if current:
            sections[current] += raw_line + "\n"

    for key, value in sections.items():
        sections[key] = value.strip()

    if not any(sections.values()):
        sections["theory_1"] = text.strip()

    return sections


def get_roadmap_theory_pages(sections: dict) -> list[str]:
    return [
        page
        for page in [sections.get("theory_1", ""), sections.get("theory_2", ""), sections.get("theory_3", "")]
        if page
    ]


def count_text_words(text: str) -> int:
    return len(re.findall(r"[A-Za-zА-Яа-яЁё]+", text or ""))


def russian_words(text: str) -> list[str]:
    return re.findall(r"[А-Яа-яЁё]+", text or "")


def sentence_count(text: str) -> int:
    sentences = [part.strip() for part in re.split(r"[.!?]+", text or "") if part.strip()]
    return max(len(sentences), 1)


def roadmap_complexity_limits(level: str) -> dict:
    level = normalize_level(level)
    limits = {
        "A1": {"avg_sentence_words": 18, "long_word_ratio": 0.18, "hard_terms": 2},
        "A2": {"avg_sentence_words": 20, "long_word_ratio": 0.22, "hard_terms": 3},
        "B1": {"avg_sentence_words": 24, "long_word_ratio": 0.28, "hard_terms": 5},
        "B2": {"avg_sentence_words": 30, "long_word_ratio": 0.36, "hard_terms": 8},
        "C1": {"avg_sentence_words": 38, "long_word_ratio": 0.45, "hard_terms": 12},
        "C2": {"avg_sentence_words": 45, "long_word_ratio": 0.55, "hard_terms": 16},
    }
    return limits.get(level, limits[DEFAULT_LEVEL])


def is_roadmap_text_too_complex(pages: list[str], level: str) -> tuple[bool, list[str]]:
    limits = roadmap_complexity_limits(level)
    hard_markers = [
        "инверси",
        "номинализац",
        "причаст",
        "герунд",
        "инфинитив",
        "пассив",
        "косвен",
        "условн",
        "сослагател",
        "перфект",
        "модальн",
        "аспект",
        "придаточ",
        "дискурс",
        "регистр",
    ]
    reasons = []

    for index, page in enumerate(pages, start=1):
        words_count = count_text_words(page)
        avg_sentence_words = words_count / sentence_count(page)
        ru_words = russian_words(page)
        long_ratio = (
            sum(1 for word in ru_words if len(word) >= 15) / max(len(ru_words), 1)
        )
        lower_page = page.lower()
        hard_terms_count = sum(1 for marker in hard_markers if marker in lower_page)

        if avg_sentence_words > limits["avg_sentence_words"]:
            reasons.append(
                f"теория {index}: слишком длинные предложения для {normalize_level(level)}"
            )
        if long_ratio > limits["long_word_ratio"]:
            reasons.append(
                f"теория {index}: слишком много сложных длинных слов для {normalize_level(level)}"
            )
        if hard_terms_count > limits["hard_terms"]:
            reasons.append(
                f"теория {index}: слишком много сложных грамматических терминов для {normalize_level(level)}"
            )

    return bool(reasons), reasons


def validate_roadmap_lesson(lesson: str, level: str) -> dict:
    sections = split_roadmap_lesson(lesson)
    theory_pages = get_roadmap_theory_pages(sections)
    quiz_questions = parse_roadmap_quiz(sections["quiz"])
    reasons = []

    if not (ROADMAP_MIN_THEORY_PAGES <= len(theory_pages) <= ROADMAP_MAX_THEORY_PAGES):
        reasons.append("нужно 2-3 страницы теории")

    for index, page in enumerate(theory_pages, start=1):
        words_count = count_text_words(page)
        if words_count < ROADMAP_MIN_THEORY_WORDS:
            reasons.append(f"теория {index}: слишком коротко, нужно подробнее")
        if words_count > ROADMAP_MAX_THEORY_WORDS:
            reasons.append(f"теория {index}: слишком длинно для одного сообщения")

    if not sections["quiz"]:
        reasons.append("нет блока QUIZ")
    if not quiz_questions:
        reasons.append("нет валидного теста с правильным ответом")

    too_complex, complexity_reasons = is_roadmap_text_too_complex(theory_pages, level)
    if too_complex:
        reasons.extend(complexity_reasons)

    return {
        "valid": not reasons,
        "reasons": reasons,
        "sections": sections,
        "theory_pages": theory_pages,
        "quiz_questions": quiz_questions,
    }


def is_clear_roadmap_quiz_question(question_text: str, options: list[str]) -> bool:
    question = re.sub(r"\s+", " ", (question_text or "").strip().lower())
    clean_options = [re.sub(r"\s+", " ", option.strip().lower()) for option in options]
    vague_patterns = [
        "о ком говорится",
        "мужчина или женщина",
        "кто это",
        "что выбрать",
        "угадай",
    ]
    if any(pattern in question for pattern in vague_patterns):
        return False

    generic_questions = {
        "choose the best option",
        "choose the correct option",
        "выберите правильный вариант",
        "какой вариант правильный",
    }
    if question in generic_questions and all(len(option.split()) <= 4 for option in clean_options):
        return False

    return True


def parse_roadmap_quiz(text: str) -> list[dict]:
    questions = []
    for block in re.findall(r"(?ms)^\s*Q\d+:\s*(.*?)(?=^\s*Q\d+:\s*|\Z)", text or ""):
        first_option = re.search(r"(?m)^\s*A[\).]\s+", block)
        if not first_option:
            continue

        question_text = block[:first_option.start()].strip()
        options = []
        option_labels = []
        for label, option in re.findall(
            r"(?ms)^\s*([A-D])[\).]\s*(.*?)(?=^\s*[A-D][\).]\s+|^\s*ANSWER:\s*|\Z)",
            block,
        ):
            option_labels.append(label.upper())
            option = re.sub(r"(?mis)\n\s*EXPLANATION:\s*.*$", "", option).strip()
            options.append(option)

        answer_match = re.search(r"(?mi)^\s*ANSWER:\s*([A-D])\s*$", block)
        explanation_match = re.search(r"(?mis)^\s*EXPLANATION:\s*(.*?)\s*$", block)

        if not question_text or len(options) != 4 or not answer_match:
            continue
        if not is_clear_roadmap_quiz_question(question_text, options):
            continue

        correct_label = answer_match.group(1).upper()
        if correct_label not in option_labels:
            continue

        questions.append({
            "question": question_text,
            "options": options,
            "correct_index": option_labels.index(correct_label),
            "explanation": explanation_match.group(1).strip() if explanation_match else "",
        })

    return questions[:2]


def roadmap_quiz_kb(question: dict):
    labels = ["A", "B", "C", "D"]
    rows = [
        [InlineKeyboardButton(text=labels[index], callback_data=f"roadmap_quiz_answer:{index}")]
        for index, option in enumerate(question["options"])
    ]
    rows.append([InlineKeyboardButton(text=cancel_label(), callback_data="cancel")])
    rows.append([InlineKeyboardButton(text=menu_back_label(), callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def format_roadmap_quiz_question(question: dict, index: int, total: int) -> str:
    labels = ["A", "B", "C", "D"]
    options = "\n".join(
        f"{labels[option_index]}) {option}"
        for option_index, option in enumerate(question["options"])
    )
    return f"Тест {index + 1}/{total}\n\n{question['question']}\n\n{options}"


def build_roadmap_quiz_summary(questions: list[dict], answers: list[int]) -> tuple[str, bool]:
    total = len(questions)
    score = 0
    lines = []

    for index, question in enumerate(questions):
        selected_index = answers[index] if index < len(answers) else -1
        correct_index = question["correct_index"]
        is_correct = selected_index == correct_index
        if is_correct:
            score += 1

        selected = question["options"][selected_index] if 0 <= selected_index < len(question["options"]) else "нет ответа"
        correct = question["options"][correct_index]
        status = "✅" if is_correct else "❌"
        lines.append(
            f"{status} {index + 1}. {question['question']}\n"
            f"Ваш ответ: {selected}\n"
            f"Правильно: {correct}\n"
            f"{question.get('explanation', '').strip()}"
        )

    passed = total > 0 and score == total
    title = f"✅ Тест пройден: {score}/{total}" if passed else f"Нужно повторить: {score}/{total}"
    summary = title + "\n\n" + "\n\n".join(lines)
    return summary, passed


def build_roadmap_wrong_answer_text(question: dict, selected_index: int) -> str:
    labels = ["A", "B", "C", "D"]
    options = question.get("options") or []
    correct_index = question["correct_index"]
    selected = options[selected_index] if 0 <= selected_index < len(options) else "нет ответа"
    correct = options[correct_index] if 0 <= correct_index < len(options) else ""
    selected_label = labels[selected_index] if 0 <= selected_index < len(labels) else "?"
    correct_label = labels[correct_index] if 0 <= correct_index < len(labels) else "?"
    explanation = (question.get("explanation") or "").strip()
    explanation_text = f"\n\nПочему так:\n{explanation}" if explanation else ""

    return (
        "❌ Здесь ошибка, лучше вернуться к теории.\n\n"
        f"Вопрос:\n{question['question']}\n\n"
        f"Ваш ответ: {selected_label}) {selected}\n"
        f"Правильно: {correct_label}) {correct}"
        f"{explanation_text}\n\n"
        "Что делаем дальше?"
    )


def build_roadmap_cache_key(level: str, lesson_type: str, topic: str, simplify: bool) -> str:
    normalized_topic = re.sub(r"\s+", " ", (topic or "").strip().lower())
    return f"{ROADMAP_CACHE_VERSION}:{normalize_level(level)}:{lesson_type}:{int(simplify)}:{normalized_topic}"


def get_cached_roadmap_lesson(level: str, lesson_type: str, topic: str, simplify: bool) -> str | None:
    cache_key = build_roadmap_cache_key(level, lesson_type, topic, simplify)
    db = SessionLocal()
    try:
        cached = db.query(RoadmapLessonCache).filter(RoadmapLessonCache.cache_key == cache_key).first()
        if not cached:
            return None

        cached.use_count = (cached.use_count or 0) + 1
        cached.last_used_at = now_key()
        content = cached.content
        db.commit()
        return content
    finally:
        db.close()


def save_cached_roadmap_lesson(level: str, lesson_type: str, topic: str, simplify: bool, content: str) -> None:
    if not content:
        return

    cache_key = build_roadmap_cache_key(level, lesson_type, topic, simplify)
    db = SessionLocal()
    try:
        cached = db.query(RoadmapLessonCache).filter(RoadmapLessonCache.cache_key == cache_key).first()
        if cached:
            cached.content = content
            cached.last_used_at = now_key()
            db.commit()
            return

        now = now_key()
        db.add(RoadmapLessonCache(
            cache_key=cache_key,
            level=normalize_level(level),
            topic=topic,
            lesson_type=lesson_type,
            simplify=1 if simplify else 0,
            content=content,
            created_at=now,
            last_used_at=now,
            use_count=0,
        ))
        db.commit()
    finally:
        db.close()


def encode_options(options: list[str] | None) -> str:
    if not options:
        return ""
    return json.dumps(options, ensure_ascii=False)


def decode_options(options_text: str | None) -> list[str]:
    if not options_text:
        return []
    try:
        data = json.loads(options_text)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def save_user_mistake(
    user_id: int,
    level: str,
    source: str,
    topic: str,
    question: str,
    correct_answer: str = "",
    explanation: str = "",
    options: list[str] | None = None,
) -> None:
    question = (question or "").strip()
    if not question:
        return

    db = SessionLocal()
    try:
        existing = (
            db.query(UserMistake)
            .filter(
                UserMistake.telegram_id == user_id,
                UserMistake.question == question,
                UserMistake.status == "active",
            )
            .first()
        )
        if existing:
            existing.level = normalize_level(level)
            existing.source = source
            existing.topic = topic
            existing.correct_answer = correct_answer
            existing.explanation = explanation
            existing.options = encode_options(options)
            existing.correct_streak = 0
            db.commit()
            return

        now = now_key()
        db.add(UserMistake(
            telegram_id=user_id,
            level=normalize_level(level),
            source=source,
            topic=topic,
            question=question,
            options=encode_options(options),
            correct_answer=correct_answer,
            explanation=explanation,
            status="active",
            seen_count=0,
            correct_streak=0,
            created_at=now,
            last_seen_at="",
        ))
        db.commit()
    finally:
        db.close()


def get_due_mistakes(user_id: int, limit: int = 5) -> list[dict]:
    db = SessionLocal()
    try:
        rows = (
            db.query(UserMistake)
            .filter(UserMistake.telegram_id == user_id, UserMistake.status == "active")
            .order_by(UserMistake.correct_streak.asc(), UserMistake.seen_count.asc(), UserMistake.id.asc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": row.id,
                "level": row.level,
                "source": row.source,
                "topic": row.topic,
                "question": row.question,
                "options": decode_options(row.options),
                "correct_answer": row.correct_answer,
                "explanation": row.explanation,
            }
            for row in rows
        ]
    finally:
        db.close()


def get_random_active_mistake(user_id: int) -> dict | None:
    mistakes = [
        mistake
        for mistake in get_due_mistakes(user_id, limit=50)
        if mistake.get("options")
    ]
    if not mistakes:
        return None
    return random.choice(mistakes)


def get_mistake_by_id(user_id: int, mistake_id: int) -> dict | None:
    db = SessionLocal()
    try:
        row = (
            db.query(UserMistake)
            .filter(
                UserMistake.id == mistake_id,
                UserMistake.telegram_id == user_id,
                UserMistake.status == "active",
            )
            .first()
        )
        if not row:
            return None

        return {
            "id": row.id,
            "level": row.level,
            "source": row.source,
            "topic": row.topic,
            "question": row.question,
            "options": decode_options(row.options),
            "correct_answer": row.correct_answer,
            "explanation": row.explanation,
            "correct_streak": row.correct_streak or 0,
        }
    finally:
        db.close()


def get_active_mistakes_count(user_id: int) -> int:
    db = SessionLocal()
    try:
        return (
            db.query(UserMistake)
            .filter(UserMistake.telegram_id == user_id, UserMistake.status == "active")
            .count()
        )
    finally:
        db.close()


def get_mastered_mistakes_count(user_id: int) -> int:
    db = SessionLocal()
    try:
        return (
            db.query(UserMistake)
            .filter(UserMistake.telegram_id == user_id, UserMistake.status == "mastered")
            .count()
        )
    finally:
        db.close()


def get_mastered_mistakes(user_id: int, page: int = 0, page_size: int = MASTERED_MISTAKES_PAGE_SIZE) -> list[dict]:
    page = max(page, 0)
    db = SessionLocal()
    try:
        rows = (
            db.query(UserMistake)
            .filter(UserMistake.telegram_id == user_id, UserMistake.status == "mastered")
            .order_by(UserMistake.last_seen_at.desc(), UserMistake.id.desc())
            .offset(page * page_size)
            .limit(page_size)
            .all()
        )
        return [
            {
                "topic": row.topic,
                "question": row.question,
                "correct_answer": row.correct_answer,
                "last_seen_at": row.last_seen_at,
            }
            for row in rows
        ]
    finally:
        db.close()


def update_mistake_result(mistake_id: int, is_correct: bool | None) -> tuple[int, str] | None:
    db = SessionLocal()
    try:
        mistake = db.query(UserMistake).filter(UserMistake.id == mistake_id).first()
        if not mistake:
            return None

        mistake.seen_count = (mistake.seen_count or 0) + 1
        mistake.last_seen_at = now_key()
        newly_mastered_user_id = None
        if is_correct is True:
            mistake.correct_streak = (mistake.correct_streak or 0) + 1
            was_mastered = mistake.status == "mastered"
            if mistake.correct_streak >= 2:
                mistake.status = "mastered"
                if not was_mastered:
                    newly_mastered_user_id = mistake.telegram_id
        elif is_correct is False:
            mistake.correct_streak = 0
        result = (mistake.correct_streak or 0, mistake.status)
        db.commit()
        if newly_mastered_user_id:
            record_daily_progress(newly_mastered_user_id, errors_closed=1)
        return result
    finally:
        db.close()


def mistake_training_kb(mistake: dict):
    options = mistake.get("options") or []
    if not options:
        return cancel_kb()

    labels = ["A", "B", "C", "D"]
    rows = [
        [InlineKeyboardButton(text=labels[index], callback_data=f"mistake_answer:{index}")]
        for index, _ in enumerate(options[:4])
    ]
    rows.append([InlineKeyboardButton(text=cancel_label(), callback_data="cancel")])
    rows.append([InlineKeyboardButton(text=menu_back_label(), callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def format_mistake_question(mistake: dict, index: int, total: int) -> str:
    options = mistake.get("options") or []
    topic = format_topic_title(mistake.get("topic") or "ошибка")
    text = f"✍️ Работа над ошибками {index + 1}/{total}\nТема: {topic}\n\n{mistake['question']}"
    if options:
        labels = ["A", "B", "C", "D"]
        options_text = "\n".join(f"{labels[i]}) {option}" for i, option in enumerate(options[:4]))
        text += f"\n\n{options_text}"
    return text


def format_mistake_reminder(mistake: dict) -> str:
    topic = format_topic_title(mistake.get("topic") or "ошибка")
    options = mistake.get("options") or []
    options_text = ""

    if options:
        labels = ["A", "B", "C", "D"]
        options_text = "\n\n" + "\n".join(
            f"{labels[index]}) {option}"
            for index, option in enumerate(options[:4])
        )

    return (
        "Пора исправлять ошибки!\n\n"
        f"Тема: {topic}\n\n"
        f"{mistake['question']}"
        f"{options_text}\n\n"
        "Выберите вариант. Если ответите правильно, это зачтётся как одна успешная проверка."
    )


def mistake_reminder_kb(mistake: dict):
    options = mistake.get("options") or []
    labels = ["A", "B", "C", "D"]
    rows = [
        [InlineKeyboardButton(text=labels[index], callback_data=f"daily_mistake_answer:{mistake['id']}:{index}")]
        for index, _ in enumerate(options[:4])
    ]
    rows.append([InlineKeyboardButton(text="✍️ Открыть тренировку", callback_data="mode_practice")])
    rows.append([InlineKeyboardButton(text=menu_back_label(), callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=[
        *rows,
    ])


def mistake_reminder_after_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Открыть тренировку", callback_data="mode_practice")],
        [InlineKeyboardButton(text=menu_back_label(), callback_data="back_main")],
    ])


def build_mistake_feedback(mistake: dict, is_correct: bool | None = None) -> str:
    if is_correct is True:
        return "✅ Верно."

    if is_correct is False:
        title = "❌ Пока нет. Вот как правильно."
    else:
        title = "Сверьте с исправлением и запомните правило."

    explanation = mistake.get("explanation") or "Повторите это место и попробуйте похожее задание позже."
    correct = mistake.get("correct_answer")
    correct_text = f"\nПравильно: {correct}" if correct else ""
    return f"{title}{correct_text}\n\nРазбор:\n{explanation}"


def build_mistake_result_text(mistake: dict, is_correct: bool, result: tuple[int, str] | None) -> str:
    base = build_mistake_feedback(mistake, is_correct)
    if not result:
        return base

    streak, status = result
    if status == "mastered":
        return (
            f"{base}\n\n"
            "Готово: ошибка исправлена и больше не будет попадаться в активной тренировке."
        )
    if is_correct:
        return (
            f"{base}\n\n"
            f"Зачёт: {streak}/2. Нужна ещё одна успешная проверка, и ошибка уйдёт из активных."
        )
    return (
        f"{base}\n\n"
        "Серия сброшена. Эта ошибка ещё появится в тренировке."
    )


def is_ai_check_correct(feedback: str) -> bool:
    first_line = next((line.strip().lower() for line in (feedback or "").splitlines() if line.strip()), "")
    return "result: correct" in first_line


def extract_json_object(text: str) -> dict | None:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def has_cyrillic(text: str) -> bool:
    return bool(re.search(r"[А-Яа-яЁё]", text or ""))


def parse_practice_bundle(raw_answer: str, topic: str) -> dict:
    data = extract_json_object(raw_answer) or {}
    raw_tasks = data.get("tasks") if isinstance(data.get("tasks"), list) else []
    tasks = []

    for raw_task in raw_tasks[:5]:
        if not isinstance(raw_task, dict):
            continue

        question = str(raw_task.get("question") or "").strip()
        correct_answer = str(raw_task.get("correct_answer") or "").strip()
        if not question or not correct_answer:
            continue

        options = raw_task.get("options") if isinstance(raw_task.get("options"), list) else []
        acceptable_answers = raw_task.get("acceptable_answers")
        if not isinstance(acceptable_answers, list):
            acceptable_answers = []

        clean_options = [str(option).strip() for option in options if str(option).strip()]
        clean_answers = [
            str(answer).strip()
            for answer in acceptable_answers
            if str(answer).strip()
        ]
        visible_text = " ".join([question, correct_answer, *clean_options, *clean_answers])
        if has_cyrillic(visible_text):
            continue

        tasks.append({
            "type": str(raw_task.get("type") or "practice").strip(),
            "question": question,
            "options": clean_options,
            "correct_answer": correct_answer,
            "acceptable_answers": clean_answers,
            "explanation": str(raw_task.get("explanation") or "").strip(),
        })

    return {
        "title": str(data.get("title") or f"✍️ Тренировка: {topic}").strip(),
        "tasks": tasks,
    }


def normalize_practice_answer(answer: str) -> str:
    answer = (answer or "").strip().lower().replace("ё", "е")
    answer = re.sub(r"[“”\"`]", "", answer)
    answer = re.sub(r"\s+", " ", answer)
    answer = re.sub(r"[.!?,;:]+$", "", answer)
    return answer.strip()


def practice_answer_matches(task: dict, user_answer: str) -> bool:
    answer = normalize_practice_answer(user_answer)
    if not answer:
        return False

    options = task.get("options") or []
    correct_answer = task.get("correct_answer") or ""
    if options:
        labels = ["a", "b", "c", "d"]
        cyrillic_labels = {"а": "a", "б": "b", "в": "c", "г": "d"}
        raw_label = (user_answer or "").strip().lower()
        raw_label = re.sub(r"[\).]$", "", raw_label)
        raw_label = cyrillic_labels.get(raw_label, raw_label)
        correct_normalized = normalize_practice_answer(correct_answer)
        correct_index = next(
            (
                index
                for index, option in enumerate(options[:4])
                if normalize_practice_answer(option) == correct_normalized
            ),
            None,
        )
        if correct_index is not None and raw_label == labels[correct_index]:
            return True

    variants = [correct_answer] + (task.get("acceptable_answers") or [])
    normalized_variants = {normalize_practice_answer(variant) for variant in variants if variant}
    if options:
        answer_without_label = re.sub(r"^[a-dа-г][\).]\s*", "", user_answer or "", flags=re.IGNORECASE)
        if normalize_practice_answer(answer_without_label) in normalized_variants:
            return True

    return answer in normalized_variants


def format_practice_task(task: dict, index: int, total: int, title: str) -> str:
    text = f"{title}\n\nЗадание {index + 1}/{total}\n\n{task['question']}"
    options = task.get("options") or []
    if options:
        labels = ["A", "B", "C", "D"]
        options_text = "\n".join(f"{labels[i]}) {option}" for i, option in enumerate(options[:4]))
        text += f"\n\n{options_text}"

    hint = "Введите букву или вариант ответа." if options else "Напишите короткий ответ."
    return f"{text}\n\n{hint}"


def build_practice_step_feedback(task: dict, is_correct: bool) -> str:
    if is_correct:
        return "✅ Верно."

    explanation = task.get("explanation") or "Посмотрите на правильный вариант и попробуйте заметить правило."
    return (
        "❌ Нужно поправить.\n\n"
        f"Правильно: {task['correct_answer']}\n\n"
        f"{explanation}"
    )


def build_practice_summary(topic: str, results: list[dict]) -> str:
    total = len(results)
    correct = sum(1 for result in results if result.get("is_correct"))
    lines = []
    for index, result in enumerate(results, start=1):
        status = "✅" if result.get("is_correct") else "❌"
        lines.append(f"{index}. {status} {result.get('question', 'задание')}")

    return (
        f"✅ Тренировка завершена: {topic}\n\n"
        f"Верно: {correct}/{total}\n\n"
        + "\n".join(lines)
        + "\n\nОшибки, если они были, сохранены для повторения."
    )


def build_placement_test() -> list[dict]:
    questions = []
    for level, count in PLACEMENT_TEST_PLAN:
        for question in get_level_test(level, count):
            question["test_level"] = level
            questions.append(question)
    return questions


def determine_placement_level(questions: list[dict], answers: list[int]) -> tuple[str, dict[str, int], dict[str, int]]:
    scores = {level: 0 for level, _ in PLACEMENT_TEST_PLAN}
    totals = {level: 0 for level, _ in PLACEMENT_TEST_PLAN}

    for question, selected_index in zip(questions, answers):
        level = question.get("test_level", "A1")
        totals[level] = totals.get(level, 0) + 1
        if selected_index == question["correct_index"]:
            scores[level] = scores.get(level, 0) + 1

    if scores.get("A1", 0) < 1:
        return "A1", scores, totals
    if scores.get("A2", 0) < 1:
        return "A1", scores, totals
    if scores.get("B1", 0) < 2:
        return "A2", scores, totals
    if scores.get("B2", 0) < 1:
        return "B1", scores, totals
    if scores.get("C1", 0) < 1:
        return "B2", scores, totals
    return "C1", scores, totals


def format_placement_scores(scores: dict[str, int], totals: dict[str, int]) -> str:
    return "\n".join(
        f"• {level}: {scores.get(level, 0)}/{totals.get(level, 0)}"
        for level, _ in PLACEMENT_TEST_PLAN
    )


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
            "🗺 Путь изучения\n\n"
            "Это основной путь бота: идёте по темам уровня, а ошибки потом попадают в тренировку.\n\n"
            f"Уровень: {snapshot['label']}\n"
            f"Прогресс: {done}/{total} тем • 100%\n"
            f"{progress_bar(done, total)}\n\n"
            "✅ Путь уровня завершён. Можно сменить уровень в профиле и продолжить."
        )

    if snapshot["review_due"]:
        review_lines = "\n".join(
            f"• {format_topic_title(topic)}"
            for topic in snapshot["review_topics"]
        )
        return (
            "🗺 Путь изучения\n\n"
            "Это основной путь бота: учим темы по порядку и возвращаем ошибки в тренировку.\n\n"
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
            "3. Тест — 1-2 вопроса с вариантами ответа"
        )

    next_lines = "\n".join(
        f"{snapshot['current_index'] + offset + 1}. {format_topic_title(topic)}"
        for offset, topic in enumerate(snapshot["next_topics"], start=1)
    )
    if not next_lines:
        next_lines = "Это последняя тема уровня."

    return (
        "🗺 Путь изучения\n\n"
        "Это основной путь бота: проходите темы по уровню, а тренировка потом повторяет ваши ошибки.\n\n"
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
        "3. Тест — 1-2 вопроса с вариантами ответа.\n"
        f"4. Каждые {ROADMAP_REVIEW_INTERVAL} темы — повторение."
    )


def build_roadmap_topics_text(user_id: int) -> str:
    user = get_user(user_id)
    if not user:
        return "Пользователь не найден. Нажмите /start."

    snapshot = get_roadmap_snapshot(user)
    topics = snapshot["topics"]
    done = snapshot["done"]
    current_index = snapshot["current_index"]

    if not topics:
        return f"🧭 Темы уровня {snapshot['label']}\n\nДля этого уровня пока нет списка тем."

    lines = []
    for index, topic in enumerate(topics):
        if index < done:
            marker = "✅"
        elif index == current_index and snapshot["current_topic"]:
            marker = "▶️"
        else:
            marker = "▫️"
        lines.append(f"{marker} {index + 1}. {format_topic_title(topic)}")

    return (
        f"🧭 Темы уровня {snapshot['label']}\n\n"
        f"Прогресс: {done}/{snapshot['total']} тем • {snapshot['percent']}%\n"
        f"{progress_bar(done, snapshot['total'])}\n\n"
        + "\n".join(lines)
    )


def menu_back_label() -> str:
    return "◀️ Главное меню"


def cancel_label() -> str:
    return "✖️ Отмена"


def mode_prompt_text(mode: str) -> str:
    prompts = {
        "explain": (
            "📘 Разбор темы\n"
            "Напишите конкретную тему или вопрос. Я объясню правило, покажу примеры и частые ошибки.\n\n"
            "Примеры:\n"
            "• Present Simple\n"
            "• difference between much and many\n"
            "• how to use should"
        ),
        "summary": (
            "📝 Шпаргалка\n"
            "Напишите тему, и я соберу короткую памятку без длинного урока.\n\n"
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
            "✍️ Тренировка\n"
            "Сначала я беру ваши сохранённые ошибки из пути изучения и прошлых заданий. Если ошибок пока нет, напишите тему для обычной тренировки.\n\n"
            "Примеры:\n"
            "• to be\n"
            "• comparatives\n"
            "• job interview phrases"
        ),
        "chat": (
            "💬 Чат-тренировка\n"
            "Premium-режим: живой учебный диалог с AI-собеседником.\n\n"
            "Напишите формат: ситуация, роль бота, ваша роль и что исправлять.\n\n"
            "Примеры:\n"
            "• Ситуация: airport. Ты сотрудник регистрации, я пассажир. Исправляй грамматику после каждой реплики.\n"
            "• Job interview. Ты HR, я кандидат. Задавай короткие вопросы уровня A2.\n"
            "• Small talk at work. Исправляй только грубые ошибки и предлагай более естественную фразу."
        ),
    }
    return prompts.get(mode, "✍️ Напишите тему, с которой хотите поработать.")


def build_main_menu_text(user_id: int) -> str:
    level = level_label(get_level(user_id))
    words_per_day = get_words_per_day(user_id)
    words_text = f"{words_per_day} в день" if words_per_day else "не настроено"
    irregular_text = "включены" if is_irregular_verbs_enabled(user_id) and is_premium(user_id) else "выключены"
    roadmap_status = get_roadmap_status_text(user_id)
    plan = get_premium_status_text(user_id)
    ai_usage = get_ai_usage_text(user_id)
    mastered_count = get_mastered_mistakes_count(user_id)

    return (
        "✨ English Hub\n"
        "Как учиться: «Путь изучения» — основной маршрут, «Тренировка» — повтор ваших ошибок, «Разбор темы» — помощь по конкретному вопросу.\n\n"
        "Ваш прогресс\n"
        f"• Тариф: {plan}\n"
        f"• AI: {ai_usage}\n"
        f"• Уровень: {level}\n"
        f"• Словарь: {words_text}\n"
        f"• Неправильные глаголы: {irregular_text}\n"
        f"• Путь изучения: {roadmap_status}\n"
        f"• Исправлено ошибок: {mastered_count}\n\n"
        f"{build_daily_goal_text(user_id)}\n\n"
        f"💡 {get_phrase()}"
    )


def build_learning_guide_text(user_id: int) -> str:
    mastered_count = get_mastered_mistakes_count(user_id)
    delivery = get_delivery_settings(user_id)
    zone_label = timezone_label(delivery["timezone_offset"])
    return (
        "ℹ️ Как учиться в этом боте\n\n"
        "0. Входная диагностика\n"
        "При первом запуске бот задаёт короткий тест и ставит стартовый уровень.\n\n"
        "1. Путь изучения\n"
        "Основной путь. Бот ведёт по темам уровня, даёт теорию и короткий тест.\n\n"
        "2. Тренировка\n"
        "Повторяет ваши старые ошибки из пути изучения, тестов и прошлых заданий. Это главный режим закрепления.\n"
        f"Уже исправлено ошибок: {mastered_count}.\n"
        f"Ошибка дня приходит после {delivery['mistake_hour']:02d}:00 по вашему местному времени ({zone_label}).\n\n"
        "3. Разбор темы\n"
        "Для разового вопроса: когда нужно понять конкретное правило или пример.\n\n"
        "4. Шпаргалка и слова\n"
        f"Помогают быстро вспомнить тему и расширить словарь. Раз в {VOCAB_REVIEW_INTERVAL_DAYS} дней бот предлагает проверку на {VOCAB_REVIEW_WORDS_COUNT} слов.\n\n"
        "5. Irregular verbs\n"
        "Premium-рассылка: каждый день 5 неправильных глаголов с формами и примером."
    )


def build_learning_menu_text() -> str:
    return (
        "📘 Обучение\n"
        "Здесь только объяснение и справочные материалы.\n\n"
        "• Разбор темы — понять правило и примеры\n"
        "• Шпаргалка — быстро освежить тему\n"
        f"• Слова на день — до {FREE_MAX_WORDS_PER_DAY} слов в Free"
    )


def build_practice_menu_text() -> str:
    return (
        "✍️ Тренировка\n"
        "Это режим закрепления, а не основной урок.\n\n"
        "• Работа над вашими ошибками — без нового AI-запроса\n"
        "• Если ошибок пока нет — обычная тренировка по теме\n"
        "• Путь изучения — теория и короткие тесты по уровню"
    )


def build_advanced_menu_text() -> str:
    return (
        "💎 Premium функции\n"
        "Здесь собраны функции, которые дают Premium-ценность, а не просто увеличивают лимиты.\n\n"
        "• Чат-тренировка — живой диалог с AI-собеседником\n"
        "• Irregular words — ежедневные неправильные глаголы\n"
        "• Голос — скоро"
    )


def build_settings_menu_text(user_id: int) -> str:
    level = level_label(get_level(user_id))
    words_per_day = get_words_per_day(user_id)
    words_text = f"{words_per_day} в день" if words_per_day else "не настроено"
    irregular_text = "включены" if is_irregular_verbs_enabled(user_id) and is_premium(user_id) else "выключены"
    plan = get_premium_status_text(user_id)
    ai_usage = get_ai_usage_text(user_id)
    delivery = get_delivery_settings(user_id)
    zone_label = timezone_label(delivery["timezone_offset"])

    return (
        "⚙️ Профиль и настройки\n"
        "Ваши текущие параметры обучения.\n\n"
        f"• Тариф: {plan}\n"
        f"• AI: {ai_usage}\n"
        f"• Уровень: {level}\n"
        f"• Словарь: {words_text}\n"
        f"• Irregular verbs: {irregular_text}\n"
        f"• Ваше время: {zone_label}\n"
        f"• Слова: {delivery['vocab_hour']:02d}:00\n"
        f"• Ошибки: {delivery['mistake_hour']:02d}:00\n\n"
        f"{build_daily_goal_text(user_id)}\n\n"
        f"{get_free_plan_text() if not is_premium(user_id) else get_premium_plan_text()}\n\n"
        "Здесь можно поменять уровень и открыть справку."
    )


def build_delivery_settings_text(user_id: int) -> str:
    delivery = get_delivery_settings(user_id)
    zone_label = timezone_label(delivery["timezone_offset"])
    return (
        "⏰ Рассылка\n\n"
        "Выберите город или регион с таким же временем, как у вас. Тогда бот будет присылать сообщения по вашему местному времени.\n\n"
        f"• Ваше время: {zone_label}\n"
        f"• Технически: UTC{delivery['timezone_offset']}\n"
        f"• Слова на день: {delivery['vocab_hour']:02d}:00\n"
        f"• Ошибка дня: {delivery['mistake_hour']:02d}:00\n"
        f"• Irregular verbs: {delivery['irregular_verbs_hour']:02d}:00"
    )


def build_mastered_mistakes_text(user_id: int, page: int = 0) -> str:
    total = get_mastered_mistakes_count(user_id)
    page = normalize_mastered_mistakes_page(page, total)
    if total == 0:
        return (
            "✅ Исправленные ошибки\n\n"
            "Пока здесь пусто.\n\n"
            "Ошибка попадёт сюда после двух успешных проверок: например, один раз в рассылке и ещё раз в тренировке."
        )

    mistakes = get_mastered_mistakes(user_id, page)
    lines = []
    for index, mistake in enumerate(mistakes, start=1):
        item_number = page * MASTERED_MISTAKES_PAGE_SIZE + index
        topic = format_topic_title(mistake["topic"] or "ошибка")
        correct = mistake["correct_answer"] or "исправлено"
        lines.append(
            f"{item_number}. {topic}\n"
            f"   {mistake['question']}\n"
            f"   Правильно: {correct}"
        )

    total_pages = mastered_mistakes_total_pages(total)
    return (
        "✅ Исправленные ошибки\n\n"
        f"Всего исправлено: {total}\n"
        f"Страница: {page + 1}/{total_pages}\n\n"
        + "\n\n".join(lines)
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
        [InlineKeyboardButton(text="🗺 Путь изучения", callback_data="mode_roadmap")],
        [InlineKeyboardButton(text="ℹ️ Как учиться", callback_data="learning_guide")],
        [
            InlineKeyboardButton(text="📘 Разбор темы", callback_data="mode_explain"),
            InlineKeyboardButton(text="✍️ Тренировка", callback_data="mode_practice"),
        ],
        [
            InlineKeyboardButton(text="📝 Шпаргалка", callback_data="mode_summary"),
            InlineKeyboardButton(text="✨ Слова на день", callback_data="vocab_settings"),
        ],
        [InlineKeyboardButton(text="💎 Premium", callback_data="premium")],
        [
            InlineKeyboardButton(text="⚙️ Профиль", callback_data="menu_settings"),
            InlineKeyboardButton(text="❔ Помощь", callback_data="help"),
        ],
        [
            InlineKeyboardButton(text="📖 Глоссарий", callback_data="glossary"),
            InlineKeyboardButton(text="💎 Premium функции", callback_data="menu_advanced"),
        ],
    ])


def learning_menu(user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📘 Разбор темы", callback_data="mode_explain"),
            InlineKeyboardButton(text="📝 Шпаргалка", callback_data="mode_summary"),
        ],
        [InlineKeyboardButton(text="✨ Слова на день", callback_data="vocab_settings")],
        [InlineKeyboardButton(text=menu_back_label(), callback_data="back_main")],
    ])


def practice_menu(user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Тренировка", callback_data="mode_practice")],
        [InlineKeyboardButton(text="🗺 Путь изучения", callback_data="mode_roadmap")],
        [InlineKeyboardButton(text="ℹ️ Как учиться", callback_data="learning_guide")],
        [InlineKeyboardButton(text=menu_back_label(), callback_data="back_main")],
    ])


def advanced_menu(user_id: int):
    def lock(text: str, key: str) -> str:
        if MODES[key]["premium"] and not is_premium(user_id):
            return f"{text} 🔒"
        return text

    irregular_label = "🔥 Irregular words" if is_premium(user_id) else "🔥 Irregular words 🔒"

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=lock("💬 Чат-тренировка", "chat"), callback_data="mode_chat"),
            InlineKeyboardButton(text=irregular_label, callback_data="irregular_verbs_settings"),
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
        [InlineKeyboardButton(text="⏰ Рассылка", callback_data="delivery_settings")],
        [InlineKeyboardButton(text="✅ Исправленные ошибки", callback_data="mastered_mistakes")],
        [InlineKeyboardButton(text="💎 Premium", callback_data="premium")],
        [InlineKeyboardButton(text=menu_back_label(), callback_data="back_main")],
    ])


def delivery_settings_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✨ Время словаря", callback_data="delivery_vocab_hour")],
        [InlineKeyboardButton(text="✍️ Время ошибок", callback_data="delivery_mistake_hour")],
        [InlineKeyboardButton(text="🔥 Время irregular verbs", callback_data="delivery_irregular_verbs_hour")],
        [InlineKeyboardButton(text="🌍 Часовой пояс", callback_data="delivery_timezone")],
        [InlineKeyboardButton(text="⚙️ Профиль", callback_data="menu_settings")],
        [InlineKeyboardButton(text=menu_back_label(), callback_data="back_main")],
    ])


def mastered_mistakes_total_pages(total: int) -> int:
    return max((total - 1) // MASTERED_MISTAKES_PAGE_SIZE + 1, 1)


def normalize_mastered_mistakes_page(page: int, total: int) -> int:
    total_pages = mastered_mistakes_total_pages(total)
    return min(max(page, 0), total_pages - 1)


def mastered_mistakes_kb(page: int, total: int):
    page = normalize_mastered_mistakes_page(page, total)
    total_pages = mastered_mistakes_total_pages(total)
    rows = []
    nav = []

    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"mastered_mistakes:{page - 1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="Вперёд ▶️", callback_data=f"mastered_mistakes:{page + 1}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton(text="⚙️ Профиль", callback_data="menu_settings")])
    rows.append([InlineKeyboardButton(text=menu_back_label(), callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def delivery_hour_kb(kind: str, current_hour: int):
    rows = []
    row = []
    for hour in DELIVERY_HOURS:
        prefix = "✅ " if hour == current_hour else ""
        row.append(InlineKeyboardButton(text=f"{prefix}{hour:02d}:00", callback_data=f"set_{kind}_hour:{hour}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="delivery_settings")])
    rows.append([InlineKeyboardButton(text=menu_back_label(), callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def delivery_timezone_kb(current_offset: str):
    rows = []
    for offset, label in TIMEZONE_OPTIONS:
        prefix = "✅ " if offset == current_offset else ""
        rows.append([InlineKeyboardButton(text=f"{prefix}{label}", callback_data=f"set_timezone:{offset}")])
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="delivery_settings")])
    rows.append([InlineKeyboardButton(text=menu_back_label(), callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
        [InlineKeyboardButton(text="🧭 Список тем", callback_data="roadmap_topics")],
        [InlineKeyboardButton(text="ℹ️ Как учиться", callback_data="learning_guide")],
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


def roadmap_wrong_answer_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📚 Перейти к теории", callback_data="roadmap_theory:0")],
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


def chat_training_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏁 Закончить чат", callback_data="chat_end")],
        [InlineKeyboardButton(text=menu_back_label(), callback_data="back_main")],
    ])


def vocab_review_invite_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧪 Начать проверку", callback_data="vocab_review_start")],
        [InlineKeyboardButton(text=menu_back_label(), callback_data="back_main")],
    ])


def vocab_review_question_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤔 Не помню", callback_data="vocab_review_skip")],
        [InlineKeyboardButton(text="✖️ Отмена проверки", callback_data="vocab_review_cancel")],
    ])


def after_explain_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Потренироваться по теме", callback_data="practice")],
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

    rows.append([InlineKeyboardButton(text="🧪 Проверить слова", callback_data="vocab_review_start")])
    rows.append([InlineKeyboardButton(text=menu_back_label(), callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


class Registration(StatesGroup):
    name = State()
    birthdate = State()
    frequency = State()
    placement = State()


class StudyFlow(StatesGroup):
    waiting_topic = State()
    waiting_chat_message = State()
    after_topic_result = State()
    waiting_practice_answer = State()
    waiting_mistake_answer = State()
    waiting_vocab_review_answer = State()
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

    async def show_help(message: Message, user_id: int | None = None):
        guide_user_id = user_id or message.from_user.id
        await message.answer(
            "❔ Как пользоваться\n\n"
            "1. Нажмите кнопку в главном меню.\n"
            "2. Если бот просит тему, напишите её обычным текстом.\n"
            "3. Если бот дал задание, выберите вариант кнопкой или отправьте ответ текстом.\n\n"
            f"{build_learning_guide_text(guide_user_id)}\n\n"
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
            f"🎯 Уровень\n\nСейчас: {level_label(current)}\n\nA1 включается сразу. Для уровней выше бот предложит короткий тест.",
            reply_markup=level_kb(current),
        )

    async def show_premium(message: Message, user_id: int):
        await message.answer(build_premium_text(user_id), reply_markup=premium_kb())

    async def show_roadmap(message: Message, user_id: int):
        await message.answer(build_roadmap_text(user_id), reply_markup=roadmap_kb())

    async def show_roadmap_topics(message: Message, user_id: int):
        await message.answer(build_roadmap_topics_text(user_id), reply_markup=roadmap_kb())

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

        await message.answer("🔄 Прогресс пути изучения сброшен.", reply_markup=roadmap_kb())
        await message.answer(build_roadmap_text(user_id), reply_markup=roadmap_kb())

    async def send_stars_invoice(bot: Bot, user_id: int):
        payload = f"premium_stars:{user_id}:{uuid4().hex[:16]}"
        await bot.send_invoice(
            chat_id=user_id,
            title=f"Premium на {DEFAULT_PREMIUM_DAYS} дней",
            description="Безлимитные AI-объяснения, проверка практики и путь изучения.",
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
        test_kind = data.get("test_kind")
        title = "Диагностика" if test_kind == "placement" else "Вопрос"
        await message.answer(
            f"🧪 {title} {index + 1}/{len(questions)}\n\n{question['question']}",
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

    def normalize_translation_answer(text: str) -> str:
        text = (text or "").strip().lower().replace("ё", "е")
        text = re.sub(r"[^\w\s,;/|-]+", " ", text, flags=re.UNICODE)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def translation_variants(text: str) -> set[str]:
        normalized = normalize_translation_answer(text)
        if not normalized:
            return set()

        parts = re.split(r"[,;/|]|\s+-\s+|\s+или\s+", normalized)
        variants = {part.strip() for part in parts if part.strip()}
        variants.add(normalized)
        return variants

    def is_vocab_translation_correct(expected: str, user_answer: str) -> bool:
        expected_variants = translation_variants(expected)
        answer_variants = translation_variants(user_answer)
        if not expected_variants or not answer_variants:
            return False

        for answer in answer_variants:
            for expected_value in expected_variants:
                if answer == expected_value:
                    return True
                if len(answer) >= 4 and len(expected_value) >= 4 and (
                    answer in expected_value or expected_value in answer
                ):
                    return True
        return False

    def get_vocab_review_words(user_id: int, limit: int = VOCAB_REVIEW_WORDS_COUNT) -> list[dict]:
        db = SessionLocal()
        try:
            rows = (
                db.query(VocabWord)
                .filter(VocabWord.telegram_id == user_id)
                .order_by(VocabWord.id.desc())
                .limit(RECENT_VOCAB_HISTORY_LIMIT)
                .all()
            )
            unique = []
            seen = set()
            for row in rows:
                key = normalize_vocab_key(row.word)
                if not key or key in seen:
                    continue

                seen.add(key)
                unique.append({
                    "word": row.word,
                    "translation": row.translation,
                    "example": row.example,
                })

            if len(unique) < limit:
                return []
            return random.sample(unique, limit)
        finally:
            db.close()

    def format_vocab_review_question(item: dict, index: int, total: int) -> str:
        return (
            f"🧪 Проверка слов {index + 1}/{total}\n\n"
            f"Слово: {item['word']}\n\n"
            "Введите перевод на русском."
        )

    def build_vocab_review_feedback(item: dict, is_correct: bool, user_answer: str) -> str:
        if is_correct:
            return f"✅ Верно: {item['word']} — {item['translation']}"

        answer_text = user_answer or "не помню"
        return (
            "❌ Не засчитано.\n\n"
            f"Ваш ответ: {answer_text}\n"
            f"Правильно: {item['translation']}\n"
            f"Пример: {item.get('example') or '—'}"
        )

    def build_vocab_review_summary(results: list[dict]) -> str:
        total = len(results)
        correct = sum(1 for result in results if result.get("is_correct"))
        skipped = sum(1 for result in results if result.get("skipped"))
        lines = []
        for index, result in enumerate(results, start=1):
            status = "✅" if result.get("is_correct") else "❌"
            lines.append(
                f"{index}. {status} {result['word']} — {result['translation']}"
            )

        return (
            "🧪 Проверка слов завершена\n\n"
            f"Верно: {correct}/{total}\n"
            f"Не вспомнили: {skipped}\n\n"
            + "\n".join(lines)
        )

    def is_vocab_review_due(user: User) -> bool:
        if not user.words_per_day:
            return False

        today = user_local_datetime(user).date()
        if not user.last_vocab_review_sent_date:
            return True

        try:
            last_sent = datetime.fromisoformat(user.last_vocab_review_sent_date).date()
        except ValueError:
            return True
        return (today - last_sent).days >= VOCAB_REVIEW_INTERVAL_DAYS

    def normalize_irregular_verb_key(verb: str) -> str:
        return (verb or "").strip().lower()

    def select_irregular_verbs(recent_verbs: list[str], count: int = IRREGULAR_VERBS_PER_DAY) -> list[tuple[str, str, str, str, str]]:
        recent_keys = {normalize_irregular_verb_key(verb) for verb in recent_verbs}
        available = [
            verb
            for verb in IRREGULAR_VERBS
            if normalize_irregular_verb_key(verb[0]) not in recent_keys
        ]
        if len(available) < count:
            available = IRREGULAR_VERBS[:]

        return random.sample(available, min(count, len(available)))

    def format_irregular_verbs(entries: list[tuple[str, str, str, str, str]]) -> str:
        blocks = []
        for index, (base, past, participle, translation, example) in enumerate(entries, start=1):
            blocks.append(
                f"{index}. {base} — {past} — {participle}\n"
                f"   {translation}\n"
                f"   {example}"
            )
        return "\n\n".join(blocks)

    async def show_vocab_settings(message: Message, user_id: int):
        current_value = get_words_per_day(user_id) or DEFAULT_WORDS_PER_DAY
        max_words = PREMIUM_MAX_WORDS_PER_DAY if is_premium(user_id) else FREE_MAX_WORDS_PER_DAY
        await message.answer(
            "✨ Настройка словаря\n"
            "Выберите, сколько новых слов присылать каждый день.\n"
            f"Раз в {VOCAB_REVIEW_INTERVAL_DAYS} дней бот предложит проверку: {VOCAB_REVIEW_WORDS_COUNT} слов, перевод вводится вручную.\n"
            f"Free: до {FREE_MAX_WORDS_PER_DAY} слов в день.\n"
            f"Premium: до {PREMIUM_MAX_WORDS_PER_DAY} слов в день.\n"
            f"Ваш максимум сейчас: {max_words}.",
            reply_markup=vocab_count_kb(user_id, current_value),
        )

    async def start_vocab_review(message: Message, state: FSMContext, user_id: int):
        words = get_vocab_review_words(user_id)
        if not words:
            await message.answer(
                f"Пока не хватает слов для проверки. Нужно минимум {VOCAB_REVIEW_WORDS_COUNT} слов из вашего словаря.",
                reply_markup=main_menu(user_id),
            )
            return

        await state.update_data(
            vocab_review_words=words,
            vocab_review_index=0,
            vocab_review_results=[],
        )
        await send_vocab_review_question(message, state, user_id)

    async def send_vocab_review_question(message: Message, state: FSMContext, user_id: int):
        data = await state.get_data()
        words = data.get("vocab_review_words") or []
        index = data.get("vocab_review_index", 0)
        if not words or index >= len(words):
            await finish_vocab_review(message, state, user_id)
            return

        await state.set_state(StudyFlow.waiting_vocab_review_answer)
        await message.answer(
            format_vocab_review_question(words[index], index, len(words)),
            reply_markup=vocab_review_question_kb(),
        )

    async def handle_vocab_review_answer(
        message: Message,
        state: FSMContext,
        user_id: int,
        user_answer: str = "",
        skipped: bool = False,
    ):
        data = await state.get_data()
        words = data.get("vocab_review_words") or []
        index = data.get("vocab_review_index", 0)
        results = data.get("vocab_review_results") or []
        if not words or index >= len(words):
            await finish_vocab_review(message, state, user_id)
            return

        item = words[index]
        is_correct = False if skipped else is_vocab_translation_correct(item["translation"], user_answer)
        results.append({
            "word": item["word"],
            "translation": item["translation"],
            "answer": user_answer,
            "is_correct": is_correct,
            "skipped": skipped,
        })

        await message.answer(build_vocab_review_feedback(item, is_correct, user_answer))
        await state.update_data(
            vocab_review_index=index + 1,
            vocab_review_results=results,
        )
        await send_vocab_review_question(message, state, user_id)

    async def finish_vocab_review(message: Message, state: FSMContext, user_id: int):
        data = await state.get_data()
        results = data.get("vocab_review_results") or []
        await state.clear()
        if not results:
            await message.answer("Проверка слов отменена.", reply_markup=main_menu(user_id))
            return

        await message.answer(build_vocab_review_summary(results), reply_markup=main_menu(user_id))

    async def show_irregular_verbs_settings(message: Message, user_id: int):
        if not is_premium(user_id):
            await message.answer(
                "🔒 Irregular verbs — Premium-функция.\n\n"
                f"В Premium бот будет присылать по {IRREGULAR_VERBS_PER_DAY} неправильных глаголов в день: base, past simple, past participle, перевод и пример.",
                reply_markup=premium_kb(),
            )
            return

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.telegram_id == user_id).first()
            if not user:
                await message.answer("User not found. Please use /start first.")
                return

            user.irregular_verbs_enabled = 1
            user.last_irregular_verbs_sent_date = ""
            db.commit()
            hour = delivery_hour(user.irregular_verbs_hour, DAILY_IRREGULAR_VERBS_HOUR)
        finally:
            db.close()

        await message.answer(
            "🔥 Irregular verbs включены.\n"
            f"Каждый день после {hour:02d}:00 по вашему времени бот будет присылать {IRREGULAR_VERBS_PER_DAY} неправильных глаголов.\n"
            "Первую подборку отправляю сейчас."
        )
        await send_irregular_verbs(bot, user_id, force=True)

    async def send_vocab_words(bot: Bot, user_id: int, force: bool = False):
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.telegram_id == user_id).first()
            if not user or not user.words_per_day:
                return False

            today = user_local_today(user)
            vocab_hour = delivery_hour(user.vocab_hour, DAILY_VOCAB_HOUR)
            if not force and not is_delivery_due(user, user.last_vocab_sent_date, vocab_hour):
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

    async def send_vocab_review_invite(bot: Bot, user_id: int) -> bool:
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.telegram_id == user_id).first()
            if not user or not is_vocab_review_due(user):
                return False

            target_hour = delivery_hour(user.vocab_hour, DAILY_VOCAB_HOUR)
            if not is_delivery_due(user, user.last_vocab_review_sent_date, target_hour):
                return False

            recent_words = (
                db.query(VocabWord)
                .filter(VocabWord.telegram_id == user_id)
                .order_by(VocabWord.id.desc())
                .limit(RECENT_VOCAB_HISTORY_LIMIT)
                .all()
            )
            unique_words = {normalize_vocab_key(item.word) for item in recent_words if normalize_vocab_key(item.word)}
            if len(unique_words) < VOCAB_REVIEW_WORDS_COUNT:
                return False

            today = user_local_today(user)
            user.last_vocab_review_sent_date = today
            db.commit()
        finally:
            db.close()

        await bot.send_message(
            user_id,
            "🧪 Пора проверить новые слова!\n\n"
            f"В тесте будет {VOCAB_REVIEW_WORDS_COUNT} слов из вашего словаря. Нужно ввести перевод вручную.\n"
            "Если слово не вспоминается, нажмите «Не помню».",
            reply_markup=vocab_review_invite_kb(),
        )
        return True

    async def send_irregular_verbs(bot: Bot, user_id: int, force: bool = False) -> bool:
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.telegram_id == user_id).first()
            if not user or not user.irregular_verbs_enabled:
                return False
            if not is_premium_user(user):
                return False

            today = user_local_today(user)
            target_hour = delivery_hour(user.irregular_verbs_hour, DAILY_IRREGULAR_VERBS_HOUR)
            if not force and not is_delivery_due(user, user.last_irregular_verbs_sent_date, target_hour):
                return False

            recent_verbs = [
                item.base_form
                for item in db.query(IrregularVerbHistory)
                .filter(IrregularVerbHistory.telegram_id == user_id)
                .order_by(IrregularVerbHistory.id.desc())
                .limit(RECENT_IRREGULAR_VERBS_HISTORY_LIMIT)
                .all()
            ]
        finally:
            db.close()

        entries = select_irregular_verbs(recent_verbs)
        if not entries:
            return False

        await bot.send_message(
            user_id,
            "🔥 Irregular verbs на сегодня\n"
            "Формы: base — past simple — past participle\n\n"
            f"{format_irregular_verbs(entries)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=menu_back_label(), callback_data="back_main")],
            ]),
        )

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.telegram_id == user_id).first()
            if user:
                user.last_irregular_verbs_sent_date = today
                for base, _, _, _, _ in entries:
                    db.add(IrregularVerbHistory(
                        telegram_id=user_id,
                        base_form=base,
                        sent_date=today,
                    ))
                db.commit()
            return True
        finally:
            db.close()

    async def send_daily_mistake(bot: Bot, user_id: int) -> bool:
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.telegram_id == user_id).first()
            if not user:
                return False

            today = user_local_today(user)
            mistake_hour = delivery_hour(user.mistake_hour, DAILY_MISTAKE_HOUR)
            if not is_delivery_due(user, user.last_mistake_sent_date, mistake_hour):
                return False
        finally:
            db.close()

        mistake = get_random_active_mistake(user_id)
        if not mistake:
            return False

        await bot.send_message(
            user_id,
            format_mistake_reminder(mistake),
            reply_markup=mistake_reminder_kb(mistake),
        )

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.telegram_id == user_id).first()
            if user:
                user.last_mistake_sent_date = user_local_today(user)
                db.commit()
            return True
        finally:
            db.close()

    async def vocab_daily_loop(bot: Bot):
        while True:
            try:
                db = SessionLocal()
                users = db.query(User).all()
                db.close()

                for user in users:
                    try:
                        await send_vocab_words(bot, user.telegram_id)
                        await send_vocab_review_invite(bot, user.telegram_id)
                    except Exception as exc:
                        logging.exception("Failed to send daily vocabulary to %s: %s", user.telegram_id, exc)
            except Exception as exc:
                logging.exception("Vocabulary daily loop failed: %s", exc)

            await asyncio.sleep(3600)

    async def mistake_daily_loop(bot: Bot):
        while True:
            try:
                db = SessionLocal()
                users = db.query(User).all()
                db.close()

                for user in users:
                    try:
                        await send_daily_mistake(bot, user.telegram_id)
                    except Exception as exc:
                        logging.exception("Failed to send daily mistake to %s: %s", user.telegram_id, exc)
            except Exception as exc:
                logging.exception("Mistake daily loop failed: %s", exc)

            await asyncio.sleep(3600)

    async def irregular_verbs_daily_loop(bot: Bot):
        while True:
            try:
                db = SessionLocal()
                users = db.query(User).all()
                db.close()

                for user in users:
                    try:
                        await send_irregular_verbs(bot, user.telegram_id)
                    except Exception as exc:
                        logging.exception("Failed to send daily irregular verbs to %s: %s", user.telegram_id, exc)
            except Exception as exc:
                logging.exception("Irregular verbs daily loop failed: %s", exc)

            await asyncio.sleep(3600)

    async def start_chat_training(message: Message, state: FSMContext, user_id: int, user_format: str, level: str):
        if not await ensure_ai_quota(message, user_id):
            await state.clear()
            return

        msg = await message.answer("🤖 Настраиваю диалог...")
        asyncio.create_task(delete_later(msg, 5))
        prompt = make_chat_start_prompt(user_format, level)

        try:
            answer = ask_ai(prompt, level, "chat")
        except Exception as exc:
            await state.clear()
            await message.answer(f"Ошибка: {exc}")
            await message.answer(build_main_menu_text(user_id), reply_markup=main_menu(user_id))
            return

        await state.update_data(
            mode="chat",
            chat_format=user_format,
            chat_level=level,
            chat_history=[{"role": "assistant", "text": answer}],
        )
        await state.set_state(StudyFlow.waiting_chat_message)
        await message.answer(answer, reply_markup=chat_training_kb())

    async def continue_chat_training(message: Message, state: FSMContext, user_id: int, user_message: str):
        data = await state.get_data()
        user_format = data.get("chat_format") or "Свободный диалог для практики английского."
        level = data.get("chat_level") or level_label(get_level(user_id))
        history = data.get("chat_history") or []

        if not await ensure_ai_quota(message, user_id):
            await state.clear()
            return

        msg = await message.answer("🤖 Отвечаю...")
        asyncio.create_task(delete_later(msg, 5))
        prompt = make_chat_reply_prompt(user_format, level, history, user_message)

        try:
            answer = ask_ai(prompt, level, "chat")
        except Exception as exc:
            await state.clear()
            await message.answer(f"Ошибка: {exc}")
            await message.answer(build_main_menu_text(user_id), reply_markup=main_menu(user_id))
            return

        history.append({"role": "user", "text": user_message})
        history.append({"role": "assistant", "text": answer})
        await state.update_data(chat_history=history[-10:])
        await message.answer(answer, reply_markup=chat_training_kb())

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

    async def start_generated_practice(message: Message, state: FSMContext, user_id: int, topic: str, level: str):
        if not await ensure_ai_quota(message, user_id):
            await state.clear()
            return

        msg = await message.answer("🤖 Собираю тренировку...")
        asyncio.create_task(delete_later(msg, 5))
        raw_answer = ask_ai(make_practice_task_prompt(topic, level), level, "practice")
        bundle = parse_practice_bundle(raw_answer, topic)
        tasks = bundle["tasks"]
        if len(tasks) < 5:
            await state.clear()
            await message.answer(
                "Не получилось собрать тренировку в нужном формате. Попробуйте ещё раз.",
                reply_markup=main_menu(user_id),
            )
            return

        await state.update_data(
            topic=topic,
            mode="practice",
            practice_user_id=user_id,
            practice_topic=topic,
            practice_level=level,
            practice_title=bundle["title"],
            practice_tasks=tasks,
            practice_index=0,
            practice_results=[],
            practice_task=None,
        )
        await send_practice_step(message, state)

    async def send_practice_step(message: Message, state: FSMContext):
        data = await state.get_data()
        tasks = data.get("practice_tasks") or []
        index = data.get("practice_index", 0)
        topic = data.get("practice_topic", "")
        title = data.get("practice_title") or f"✍️ Тренировка: {topic}"

        if not tasks or index >= len(tasks):
            results = data.get("practice_results") or []
            user_id = data.get("practice_user_id") or message.from_user.id
            await state.clear()
            await message.answer(build_practice_summary(topic, results), reply_markup=main_menu(user_id))
            return

        await state.set_state(StudyFlow.waiting_practice_answer)
        await message.answer(
            format_practice_task(tasks[index], index, len(tasks), title),
            reply_markup=cancel_kb(),
        )

    async def check_generated_practice_answer(message: Message, state: FSMContext, user_answer: str):
        data = await state.get_data()
        tasks = data.get("practice_tasks") or []
        index = data.get("practice_index", 0)
        topic = data.get("practice_topic", "")
        level = data.get("practice_level") or level_label(get_level(message.from_user.id))

        if not tasks or index >= len(tasks):
            await state.clear()
            await message.answer("Тренировка потерялась. Попробуйте начать заново.", reply_markup=main_menu(message.from_user.id))
            return

        task = tasks[index]
        is_correct = practice_answer_matches(task, user_answer)
        results = data.get("practice_results") or []
        results.append({
            "question": task["question"],
            "is_correct": is_correct,
        })

        if not is_correct:
            save_user_mistake(
                message.from_user.id,
                get_level(message.from_user.id),
                "practice",
                topic,
                task["question"],
                options=task.get("options") or None,
                correct_answer=task["correct_answer"],
                explanation=task.get("explanation") or "Повторите правильный вариант и попробуйте ещё раз позже.",
            )

        await message.answer(build_practice_step_feedback(task, is_correct))
        await state.update_data(
            practice_index=index + 1,
            practice_results=results,
            practice_level=level,
        )
        await send_practice_step(message, state)

    async def check_practice_answer(message: Message, state: FSMContext, user_answer: str):
        data = await state.get_data()
        if data.get("practice_tasks"):
            await check_generated_practice_answer(message, state, user_answer)
            return

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
        if not is_ai_check_correct(feedback):
            save_user_mistake(
                message.from_user.id,
                get_level(message.from_user.id),
                "practice",
                topic,
                task,
                correct_answer="Смотрите сохранённый разбор ниже.",
                explanation=feedback,
            )
        await state.clear()
        await message.answer(feedback, reply_markup=main_menu(message.from_user.id))

    async def send_mistake_training_question(message: Message, state: FSMContext):
        data = await state.get_data()
        mistakes = data.get("mistake_questions") or []
        index = data.get("mistake_index", 0)
        if not mistakes or index >= len(mistakes):
            await finish_mistake_training(message, state, message.from_user.id)
            return

        mistake = mistakes[index]
        await message.answer(
            format_mistake_question(mistake, index, len(mistakes)),
            reply_markup=mistake_training_kb(mistake),
        )

    async def start_mistake_training(message: Message, state: FSMContext, user_id: int) -> bool:
        mistakes = get_due_mistakes(user_id)
        if not mistakes:
            return False

        await state.update_data(
            mistake_questions=mistakes,
            mistake_index=0,
            mistake_results=[],
        )
        await state.set_state(StudyFlow.waiting_mistake_answer)
        await message.answer("✍️ Тренировка по вашим ошибкам. Эти задания уже сохранены, поэтому AI-запрос не тратится.")
        await send_mistake_training_question(message, state)
        return True

    async def finish_mistake_training(message: Message, state: FSMContext, user_id: int):
        data = await state.get_data()
        results = data.get("mistake_results") or []
        correct = sum(1 for item in results if item == "correct")
        reviewed = sum(1 for item in results if item == "reviewed")
        total = len(results)
        await state.clear()
        if total:
            await message.answer(
                f"✅ Тренировка завершена.\n"
                f"Верно с вариантами: {correct}/{total - reviewed}\n"
                f"Повторено текстовых ошибок: {reviewed}\n"
                "Ошибки, которые вы закрываете два раза подряд, уходят из активной тренировки.",
                reply_markup=main_menu(user_id),
            )
        else:
            await message.answer("Тренировка завершена.", reply_markup=main_menu(user_id))

    async def handle_mistake_answer(call: CallbackQuery, state: FSMContext):
        data = await state.get_data()
        mistakes = data.get("mistake_questions") or []
        index = data.get("mistake_index", 0)
        results = data.get("mistake_results") or []
        if not mistakes or index >= len(mistakes):
            await state.clear()
            await call.message.answer("Состояние тренировки потеряно.", reply_markup=main_menu(call.from_user.id))
            return

        mistake = mistakes[index]
        selected_index = int(call.data.split(":", 1)[1])
        options = mistake.get("options") or []
        correct_answer = mistake.get("correct_answer")
        is_correct = 0 <= selected_index < len(options) and options[selected_index] == correct_answer
        result = update_mistake_result(mistake["id"], is_correct)
        results.append("correct" if is_correct else "wrong")
        await call.message.edit_reply_markup(reply_markup=None)
        await call.message.answer(build_mistake_result_text(mistake, is_correct, result))

        index += 1
        await state.update_data(mistake_index=index, mistake_results=results)
        if index < len(mistakes):
            await send_mistake_training_question(call.message, state)
        else:
            await finish_mistake_training(call.message, state, call.from_user.id)

    async def handle_daily_mistake_answer(call: CallbackQuery):
        parts = call.data.split(":")
        if len(parts) != 3:
            await call.answer()
            return

        mistake_id = int(parts[1])
        selected_index = int(parts[2])
        mistake = get_mistake_by_id(call.from_user.id, mistake_id)
        if not mistake:
            await call.message.edit_reply_markup(reply_markup=None)
            await call.message.answer("Эта ошибка уже закрыта или больше не активна.", reply_markup=main_menu(call.from_user.id))
            return

        options = mistake.get("options") or []
        correct_answer = mistake.get("correct_answer")
        is_correct = 0 <= selected_index < len(options) and options[selected_index] == correct_answer
        result = update_mistake_result(mistake_id, is_correct)
        await call.message.edit_reply_markup(reply_markup=None)
        await call.message.answer(
            build_mistake_result_text(mistake, is_correct, result),
            reply_markup=mistake_reminder_after_kb(),
        )

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
            level_code = normalize_level(user.level)
            level = level_label(level_code)
            simplify = user.last_result in {"wrong_twice", "review_wrong"}
        finally:
            db.close()

        if not topic:
            await state.clear()
            await message.answer("✅ Путь изучения завершён.", reply_markup=roadmap_kb())
            return

        if review_due:
            roadmap_kind = "review"
            title = "Повторение: " + ", ".join(format_topic_title(topic) for topic in review_topics)
        else:
            roadmap_kind = "topic"
            title = format_topic_title(topic)

        cached_lesson = get_cached_roadmap_lesson(level_code, roadmap_kind, topic, simplify)
        lesson = cached_lesson
        validation = validate_roadmap_lesson(lesson, level_code) if lesson else None
        generated_new_lesson = False

        def build_generation_prompt(reasons: list[str] | None = None) -> str:
            if review_due:
                prompt = make_roadmap_review_prompt(review_topics, level, simplify)
            else:
                prompt = make_roadmap_lesson_prompt(topic, level, simplify)

            if reasons:
                prompt += (
                    "\n\nКонтроль качества: предыдущий модуль был отклонён.\n"
                    "Исправь эти проблемы в новой версии:\n"
                    + "\n".join(f"- {reason}" for reason in reasons[:6])
                    + "\n\nВерни полностью новый модуль в том же строгом формате."
                )
            return prompt

        if validation and not validation["valid"]:
            logging.warning("Cached roadmap lesson rejected: %s", "; ".join(validation["reasons"]))
            lesson = None

        if not lesson:
            if not await ensure_ai_quota(message, user_id):
                await state.clear()
                return

            previous_reasons = validation["reasons"] if validation else []
            for attempt in range(ROADMAP_GENERATION_MAX_ATTEMPTS):
                lesson = ask_ai(
                    build_generation_prompt(previous_reasons if previous_reasons else None),
                    level,
                    "roadmap_review" if review_due else "roadmap",
                )
                generated_new_lesson = True
                validation = validate_roadmap_lesson(lesson, level_code)
                if validation["valid"]:
                    break

                previous_reasons = validation["reasons"]
                logging.warning(
                    "Generated roadmap lesson rejected on attempt %s/%s: %s",
                    attempt + 1,
                    ROADMAP_GENERATION_MAX_ATTEMPTS,
                    "; ".join(previous_reasons),
                )

        if not validation or not validation["valid"]:
            await state.clear()
            reasons_text = "\n".join(f"• {reason}" for reason in (validation or {}).get("reasons", [])[:5])
            details = f"\n\nЧто не прошло:\n{reasons_text}" if reasons_text else ""
            await message.answer(
                "Не получилось собрать качественный урок. Попробуйте запустить путь изучения ещё раз."
                f"{details}",
                reply_markup=roadmap_kb(),
            )
            return

        sections = validation["sections"]
        theory_pages = validation["theory_pages"]
        quiz_questions = validation["quiz_questions"]

        if generated_new_lesson:
            save_cached_roadmap_lesson(level_code, roadmap_kind, topic, simplify, lesson)

        await state.update_data(
            roadmap_topic=topic,
            roadmap_lesson=lesson,
            roadmap_theory_pages=theory_pages,
            roadmap_quiz_questions=quiz_questions,
            roadmap_quiz_answers=[],
            roadmap_quiz_index=0,
            roadmap_kind=roadmap_kind,
            roadmap_lesson_step="theory",
            roadmap_theory_index=0,
        )
        await state.set_state(StudyFlow.viewing_roadmap_lesson)
        await message.answer(f"🗺 Урок пути изучения: {title}")
        await send_roadmap_theory_page(message, state, user_id, 0)

    async def send_roadmap_theory_page(message: Message, state: FSMContext, user_id: int, index: int):
        data = await state.get_data()
        pages = data.get("roadmap_theory_pages") or []

        if not pages or index >= len(pages):
            await state.clear()
            await message.answer("Состояние урока потеряно. Запустите путь изучения снова.", reply_markup=main_menu(user_id))
            return

        next_index = index + 1
        next_text = "➡️ Дальше" if next_index < len(pages) else "🧪 К тесту"
        next_callback = f"roadmap_theory:{next_index}" if next_index < len(pages) else "roadmap_quiz_start"
        await state.update_data(roadmap_lesson_step="theory", roadmap_theory_index=index)
        await state.set_state(StudyFlow.viewing_roadmap_lesson)
        await message.answer(
            f"Теория {index + 1}/{len(pages)}\n\n{pages[index]}",
            reply_markup=roadmap_lesson_step_kb(next_text, next_callback),
        )

    async def send_roadmap_quiz_question(message: Message, state: FSMContext, user_id: int):
        data = await state.get_data()
        questions = data.get("roadmap_quiz_questions") or []
        index = data.get("roadmap_quiz_index", 0)

        if not questions or index >= len(questions):
            await state.clear()
            await message.answer("Состояние урока потеряно. Запустите путь изучения снова.", reply_markup=main_menu(user_id))
            return

        await state.set_state(StudyFlow.waiting_roadmap_answer)
        await state.update_data(
            roadmap_lesson_step="quiz",
            roadmap_quiz_index=index,
        )
        await message.answer(
            format_roadmap_quiz_question(questions[index], index, len(questions)),
            reply_markup=roadmap_quiz_kb(questions[index]),
        )

    async def finish_roadmap_quiz(message: Message, state: FSMContext, user_id: int):
        data = await state.get_data()
        topic = data.get("roadmap_topic")
        roadmap_kind = data.get("roadmap_kind", "topic")
        questions = data.get("roadmap_quiz_questions") or []
        answers = data.get("roadmap_quiz_answers") or []
        summary, result = build_roadmap_quiz_summary(questions, answers)

        if not topic or not questions:
            await state.clear()
            await message.answer(
                "Состояние пути изучения потеряно. Запустите его снова.",
                reply_markup=main_menu(user_id),
            )
            return

        if not get_user(user_id):
            await state.clear()
            await message.answer("User not found. Please use /start first.")
            return

        topic_completed = False
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.telegram_id == user_id).first()
            if not user:
                await state.clear()
                await message.answer("User not found. Please use /start first.")
                return

            for question, selected_index in zip(questions, answers):
                correct_index = question["correct_index"]
                if selected_index != correct_index:
                    save_user_mistake(
                        user_id,
                        user.level,
                        roadmap_kind,
                        topic,
                        question["question"],
                        correct_answer=question["options"][correct_index],
                        explanation=question.get("explanation", ""),
                        options=question.get("options", []),
                    )

            if roadmap_kind == "review":
                if result:
                    user.roadmap_review_index = user.current_topic_index or 0
                    user.last_result = "review_correct"
                else:
                    user.last_result = "review_wrong"
            else:
                update_progress(user, result)
                topic_completed = result
            db.commit()
        finally:
            db.close()

        if topic_completed:
            record_daily_progress(user_id, topics_done=1)

        await state.clear()
        await message.answer(summary)
        await message.answer(build_roadmap_text(user_id), reply_markup=roadmap_kb())

    async def handle_roadmap_quiz_answer(call: CallbackQuery, state: FSMContext):
        data = await state.get_data()
        topic = data.get("roadmap_topic")
        roadmap_kind = data.get("roadmap_kind", "topic")
        questions = data.get("roadmap_quiz_questions") or []
        index = data.get("roadmap_quiz_index", 0)
        answers = data.get("roadmap_quiz_answers") or []

        if not topic or not questions or index >= len(questions):
            await state.clear()
            await call.message.answer("Состояние теста потеряно. Запустите путь изучения снова.", reply_markup=main_menu(call.from_user.id))
            return

        selected_index = int(call.data.split(":", 1)[1])
        question = questions[index]
        correct_index = question["correct_index"]
        answers.append(selected_index)
        await call.message.edit_reply_markup(reply_markup=None)

        if selected_index != correct_index:
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.telegram_id == call.from_user.id).first()
                if not user:
                    await state.clear()
                    await call.message.answer("User not found. Please use /start first.")
                    return

                save_user_mistake(
                    call.from_user.id,
                    user.level,
                    roadmap_kind,
                    topic,
                    question["question"],
                    correct_answer=question["options"][correct_index],
                    explanation=question.get("explanation", ""),
                    options=question.get("options", []),
                )

                if roadmap_kind == "review":
                    user.last_result = "review_wrong"
                else:
                    update_progress(user, False)
                db.commit()
            finally:
                db.close()

            await state.update_data(
                roadmap_quiz_answers=answers,
                roadmap_quiz_index=index,
                roadmap_lesson_step="theory",
                roadmap_theory_index=0,
            )
            await state.set_state(StudyFlow.viewing_roadmap_lesson)
            await call.message.answer(
                build_roadmap_wrong_answer_text(question, selected_index),
                reply_markup=roadmap_wrong_answer_kb(),
            )
            return

        index += 1
        await state.update_data(roadmap_quiz_answers=answers, roadmap_quiz_index=index)
        if index < len(questions):
            await send_roadmap_quiz_question(call.message, state, call.from_user.id)
        else:
            await finish_roadmap_quiz(call.message, state, call.from_user.id)

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
                    "options": question["options"],
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
                    user.roadmap_review_index = 0
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
        for item in wrong_answers:
            save_user_mistake(
                call.from_user.id,
                target_level,
                "level_test",
                item["topic"],
                item["question"],
                correct_answer=item["correct_answer"],
                explanation=f"Ошибка в тесте уровня. Правильный ответ: {item['correct_answer']}",
                options=item["options"],
            )

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

    async def finish_placement_test(call: CallbackQuery, state: FSMContext):
        data = await state.get_data()
        questions = data.get("level_questions") or []
        answers = data.get("level_answers") or []
        level, scores, totals = determine_placement_level(questions, answers)

        for question, selected_index in zip(questions, answers):
            if selected_index != question["correct_index"]:
                save_user_mistake(
                    call.from_user.id,
                    question.get("test_level", level),
                    "placement",
                    question["topic"],
                    question["question"],
                    correct_answer=question["answer"],
                    explanation=f"Ошибка во входной диагностике. Правильный ответ: {question['answer']}",
                    options=question["options"],
                )

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.telegram_id == call.from_user.id).first()
            if user:
                user.level = level
                user.current_topic_index = 0
                user.roadmap_review_index = 0
                user.last_result = ""
                db.commit()
        finally:
            db.close()

        await state.clear()
        await call.message.answer(
            "✅ Диагностика завершена.\n\n"
            f"Стартовый уровень: {level_label(level)}\n\n"
            f"Результаты:\n{format_placement_scores(scores, totals)}\n\n"
            "Дальше лучше начать с «Пути изучения». Ошибки из диагностики уже добавлены в тренировку.",
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
                streak_count=0,
                streak_last_date="",
                daily_goal_date="",
                daily_goal_errors_closed=0,
                daily_goal_topics_done=0,
                words_per_day=None,
                last_vocab_sent_date="",
                last_vocab_review_sent_date="",
                last_mistake_sent_date="",
                irregular_verbs_enabled=0,
                last_irregular_verbs_sent_date="",
                timezone_offset=DEFAULT_TIMEZONE_OFFSET,
                vocab_hour=DAILY_VOCAB_HOUR,
                mistake_hour=DAILY_MISTAKE_HOUR,
                irregular_verbs_hour=DAILY_IRREGULAR_VERBS_HOUR,
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

        questions = build_placement_test()
        await state.set_state(Registration.placement)
        await state.update_data(
            level_questions=questions,
            level_index=0,
            level_answers=[],
            test_kind="placement",
        )
        await call.message.edit_text(
            f"✨ Добро пожаловать, {name}!\n\n"
            "Сейчас пройдём короткую диагностику: 8 вопросов с вариантами ответа.\n"
            "Это поможет поставить стартовый уровень и собрать первые темы для тренировки."
        )
        await send_level_question(call.message, state)

    @dp.message(CommandStart())
    async def start(message: Message, state: FSMContext):
        if get_user(message.from_user.id):
            await show_main_menu(message, state)
        else:
            await state.set_state(Registration.name)
            await message.answer("Привет. Как тебя зовут?")

    @dp.message(Command("help"))
    async def help_cmd(message: Message):
        await show_help(message, message.from_user.id)

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
            await show_help(call.message, call.from_user.id)

        elif data == "learning_guide":
            await call.message.answer(build_learning_guide_text(call.from_user.id), reply_markup=main_menu(call.from_user.id))

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

        elif data == "delivery_settings":
            await call.message.edit_text(
                build_delivery_settings_text(call.from_user.id),
                reply_markup=delivery_settings_kb(),
            )

        elif data == "mastered_mistakes" or data.startswith("mastered_mistakes:"):
            page = 0
            if ":" in data:
                try:
                    page = int(data.split(":", 1)[1])
                except ValueError:
                    page = 0
            total = get_mastered_mistakes_count(call.from_user.id)
            page = normalize_mastered_mistakes_page(page, total)
            await call.message.edit_text(
                build_mastered_mistakes_text(call.from_user.id, page),
                reply_markup=mastered_mistakes_kb(page, total),
            )

        elif data == "delivery_vocab_hour":
            delivery = get_delivery_settings(call.from_user.id)
            await call.message.edit_text(
                "✨ Выберите время прихода словаря.\nВремя считается по вашему часовому поясу.",
                reply_markup=delivery_hour_kb("vocab", delivery["vocab_hour"]),
            )

        elif data == "delivery_mistake_hour":
            delivery = get_delivery_settings(call.from_user.id)
            await call.message.edit_text(
                "✍️ Выберите время прихода ошибки дня.\nВремя считается по вашему часовому поясу.",
                reply_markup=delivery_hour_kb("mistake", delivery["mistake_hour"]),
            )

        elif data == "delivery_irregular_verbs_hour":
            if not is_premium(call.from_user.id):
                await call.message.answer("🔒 Irregular verbs доступны только в Premium.", reply_markup=premium_kb())
                return

            delivery = get_delivery_settings(call.from_user.id)
            await call.message.edit_text(
                "🔥 Выберите время прихода irregular verbs.\nВремя считается по вашему часовому поясу.",
                reply_markup=delivery_hour_kb("irregular_verbs", delivery["irregular_verbs_hour"]),
            )

        elif data == "delivery_timezone":
            delivery = get_delivery_settings(call.from_user.id)
            await call.message.edit_text(
                "🌍 Выберите город или регион, где сейчас такое же время, как у вас.\n\n"
                "Если вашего города нет, выберите ближайший похожий вариант.",
                reply_markup=delivery_timezone_kb(delivery["timezone_offset"]),
            )

        elif data.startswith("set_vocab_hour:"):
            hour = int(data.split(":", 1)[1])
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.telegram_id == call.from_user.id).first()
                if user:
                    user.vocab_hour = hour
                    db.commit()
            finally:
                db.close()
            await call.message.edit_text(build_delivery_settings_text(call.from_user.id), reply_markup=delivery_settings_kb())

        elif data.startswith("set_mistake_hour:"):
            hour = int(data.split(":", 1)[1])
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.telegram_id == call.from_user.id).first()
                if user:
                    user.mistake_hour = hour
                    db.commit()
            finally:
                db.close()
            await call.message.edit_text(build_delivery_settings_text(call.from_user.id), reply_markup=delivery_settings_kb())

        elif data.startswith("set_irregular_verbs_hour:"):
            hour = int(data.split(":", 1)[1])
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.telegram_id == call.from_user.id).first()
                if user:
                    user.irregular_verbs_hour = hour
                    db.commit()
            finally:
                db.close()
            await call.message.edit_text(build_delivery_settings_text(call.from_user.id), reply_markup=delivery_settings_kb())

        elif data.startswith("set_timezone:"):
            offset = data.split(":", 1)[1]
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.telegram_id == call.from_user.id).first()
                if user:
                    user.timezone_offset = offset
                    db.commit()
            finally:
                db.close()
            await call.message.edit_text(build_delivery_settings_text(call.from_user.id), reply_markup=delivery_settings_kb())

        elif data == "roadmap_start":
            await send_roadmap_lesson(call.message, state, call.from_user.id)

        elif data == "roadmap_topics":
            await show_roadmap_topics(call.message, call.from_user.id)

        elif data.startswith("roadmap_theory:"):
            theory_index = int(data.split(":", 1)[1])
            await send_roadmap_theory_page(call.message, state, call.from_user.id, theory_index)

        elif data == "roadmap_quiz_start":
            await state.update_data(roadmap_quiz_index=0, roadmap_quiz_answers=[])
            await send_roadmap_quiz_question(call.message, state, call.from_user.id)

        elif data.startswith("roadmap_quiz_answer:"):
            await handle_roadmap_quiz_answer(call, state)

        elif data.startswith("mistake_answer:"):
            await handle_mistake_answer(call, state)

        elif data.startswith("daily_mistake_answer:"):
            await handle_daily_mistake_answer(call)

        elif data == "roadmap_reset_confirm":
            await call.message.answer(
                "Сбросить путь изучения на первую тему текущего уровня?",
                reply_markup=roadmap_reset_confirm_kb(),
            )

        elif data == "roadmap_reset":
            await state.clear()
            await reset_roadmap_progress(call.message, call.from_user.id)

        elif data == "cancel":
            await cancel_action(call.message, state, call.from_user.id)

        elif data == "chat_end":
            await state.clear()
            await call.message.answer(
                "🏁 Чат-тренировка завершена.\n\nЛучше всего закрепить новые фразы через «Путь изучения» или тренировку ошибок.",
                reply_markup=main_menu(call.from_user.id),
            )

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
            await state.update_data(
                level_questions=get_level_test(target_level),
                level_index=0,
                level_answers=[],
                test_kind="level_change",
            )
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
                if state_data.get("test_kind") == "placement":
                    await finish_placement_test(call, state)
                else:
                    await finish_level_test(call, state)
            else:
                await send_level_question(call.message, state)

        elif data == "vocab_settings":
            await state.clear()
            await show_vocab_settings(call.message, call.from_user.id)

        elif data == "vocab_review_start":
            await state.clear()
            await start_vocab_review(call.message, state, call.from_user.id)

        elif data == "vocab_review_skip":
            await call.message.edit_reply_markup(reply_markup=None)
            await handle_vocab_review_answer(
                call.message,
                state,
                call.from_user.id,
                user_answer="",
                skipped=True,
            )

        elif data == "vocab_review_cancel":
            await state.clear()
            await call.message.edit_reply_markup(reply_markup=None)
            await call.message.answer("✖️ Проверка слов отменена.", reply_markup=main_menu(call.from_user.id))

        elif data == "irregular_verbs_settings":
            await state.clear()
            await show_irregular_verbs_settings(call.message, call.from_user.id)

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
                    "🎤 Голосовой режим пока готовится.\n\nСейчас можно пользоваться текстовыми режимами: объяснение, практика, тесты и путь изучения.",
                    reply_markup=main_menu(call.from_user.id),
                )
                return

            if mode == "roadmap":
                await show_roadmap(call.message, call.from_user.id)
                return

            if mode == "practice" and await start_mistake_training(call.message, state, call.from_user.id):
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

            await start_generated_practice(call.message, state, call.from_user.id, topic, level)

        elif data.startswith("set_level:"):
            level = normalize_level(data.split(":", 1)[1])
            if level == "A1":
                await state.clear()
                db = SessionLocal()
                try:
                    user = db.query(User).filter(User.telegram_id == call.from_user.id).first()
                    if not user:
                        await call.message.answer("User not found. Please use /start first.")
                        return

                    user.level = level
                    user.current_topic_index = 0
                    user.roadmap_review_index = 0
                    user.last_result = ""
                    db.commit()
                finally:
                    db.close()

                await call.message.edit_text(
                    f"✅ Уровень изменен на {level_label(level)}.\nПуть изучения начнётся с первой темы.",
                    reply_markup=main_menu(call.from_user.id),
                )
                return

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
        if mode == "practice":
            await start_generated_practice(message, state, message.from_user.id, topic, level)
            return
        if mode == "chat":
            if not is_premium(message.from_user.id):
                await state.clear()
                await message.answer("🔒 Чат-тренировка доступна только в Premium.", reply_markup=premium_kb())
                return
            await start_chat_training(message, state, message.from_user.id, topic, level)
            return

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
                practice_level=level,
            )
            await state.set_state(StudyFlow.after_topic_result)
            await message.answer(answer, reply_markup=after_explain_kb())
        elif mode in {"quiz", "practice"}:
            await send_practice_task(message, state, answer, topic, level, mode)
        else:
            await state.clear()
            await message.answer(answer, reply_markup=main_menu(message.from_user.id))

    @dp.message(StudyFlow.after_topic_result)
    async def after_topic_result_input(message: Message, state: FSMContext):
        await message.answer(
            "Выберите действие кнопкой: можно потренироваться по теме или вернуться в главное меню.",
            reply_markup=after_explain_kb(),
        )

    @dp.message(StudyFlow.waiting_chat_message)
    async def chat_training_input(message: Message, state: FSMContext):
        user_message = (message.text or "").strip()
        if not user_message:
            await message.answer("Напишите реплику для диалога текстом или завершите чат кнопкой.", reply_markup=chat_training_kb())
            return

        if not is_premium(message.from_user.id):
            await state.clear()
            await message.answer("🔒 Чат-тренировка доступна только в Premium.", reply_markup=premium_kb())
            return

        await continue_chat_training(message, state, message.from_user.id, user_message)

    @dp.message(StudyFlow.waiting_practice_answer)
    async def practice_answer_input(message: Message, state: FSMContext):
        user_answer = (message.text or "").strip()
        if not user_answer:
            await message.answer("Напишите ответ текстом одним сообщением. Если передумали, нажмите «Отмена».", reply_markup=cancel_kb())
            return

        await check_practice_answer(message, state, user_answer)

    @dp.message(StudyFlow.waiting_mistake_answer)
    async def mistake_answer_input(message: Message, state: FSMContext):
        data = await state.get_data()
        mistakes = data.get("mistake_questions") or []
        index = data.get("mistake_index", 0)
        results = data.get("mistake_results") or []
        if not mistakes or index >= len(mistakes):
            await state.clear()
            await message.answer("Состояние тренировки потеряно.", reply_markup=main_menu(message.from_user.id))
            return

        mistake = mistakes[index]
        if mistake.get("options"):
            await message.answer(
                "В этом задании нужно выбрать вариант кнопкой под вопросом.",
                reply_markup=mistake_training_kb(mistake),
            )
            return

        update_mistake_result(mistake["id"], None)
        results.append("reviewed")
        await message.answer(build_mistake_feedback(mistake, None))

        index += 1
        await state.update_data(mistake_index=index, mistake_results=results)
        if index < len(mistakes):
            await send_mistake_training_question(message, state)
        else:
            await finish_mistake_training(message, state, message.from_user.id)

    @dp.message(StudyFlow.waiting_vocab_review_answer)
    async def vocab_review_answer_input(message: Message, state: FSMContext):
        user_answer = (message.text or "").strip()
        if not user_answer:
            await message.answer(
                "Введите перевод текстом или нажмите «Не помню».",
                reply_markup=vocab_review_question_kb(),
            )
            return

        await handle_vocab_review_answer(message, state, message.from_user.id, user_answer=user_answer)

    @dp.message(StudyFlow.viewing_roadmap_lesson)
    async def roadmap_theory_input(message: Message, state: FSMContext):
        data = await state.get_data()
        pages = data.get("roadmap_theory_pages") or []
        index = data.get("roadmap_theory_index", 0)
        if not pages:
            await state.clear()
            await message.answer("Состояние урока потеряно. Запустите путь изучения снова.", reply_markup=main_menu(message.from_user.id))
            return

        next_index = index + 1
        next_text = "➡️ Дальше" if next_index < len(pages) else "🧪 К тесту"
        next_callback = f"roadmap_theory:{next_index}" if next_index < len(pages) else "roadmap_quiz_start"
        await message.answer(
            "Сейчас мы на теории. Нажмите кнопку под предыдущим сообщением, чтобы идти дальше.",
            reply_markup=roadmap_lesson_step_kb(next_text, next_callback),
        )

    @dp.message(StudyFlow.waiting_roadmap_answer)
    async def roadmap_answer_input(message: Message, state: FSMContext):
        await message.answer(
            "В этом модуле тест с вариантами ответа. Выберите вариант кнопкой под вопросом.",
            reply_markup=cancel_kb(),
        )

    asyncio.create_task(vocab_daily_loop(bot))
    asyncio.create_task(mistake_daily_loop(bot))
    asyncio.create_task(irregular_verbs_daily_loop(bot))
    await notify_bot_started(bot)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
