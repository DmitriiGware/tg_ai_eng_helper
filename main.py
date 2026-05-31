import asyncio
import logging
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from dotenv import load_dotenv

from ai_client import ask_ai
from database.db import SessionLocal, engine, ensure_user_progress_columns
from database.models import Base, User, VocabWord
from glossary import glossary_menu, glossary_text
from level_tests import get_level_test
from modes import MODES
from motivation import get_phrase
from prompts import make_roadmap_check_prompt, make_roadmap_lesson_prompt, make_user_prompt, make_vocab_words_prompt
from roadmap import get_current_topic, update_progress

ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

BOT_TOKEN = (os.getenv("BOT_TOKEN") or "").strip()
ADMIN_TELEGRAM_ID = (os.getenv("TELEGRAM_ADMIN_ID") or "").strip()
PREMIUM_PAYMENT_TEXT = (os.getenv("PREMIUM_PAYMENT_TEXT") or "Способ оплаты уточняется у администратора.").strip()

DEFAULT_LEVEL = "A1"
DEFAULT_WORDS_PER_DAY = 5
DAILY_VOCAB_HOUR = 10
RECENT_VOCAB_HISTORY_LIMIT = 80
FREE_DAILY_AI_LIMIT = 5
DEFAULT_PREMIUM_DAYS = 30

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


def premium_limit_text() -> str:
    return (
        "Дневной лимит Free закончился.\n\n"
        "В Premium доступны безлимитные AI-объяснения, проверка ответов, roadmap, chat и voice."
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


def menu_back_label() -> str:
    return "◀️ Главное меню"


def cancel_label() -> str:
    return "✖️ Отмена"


def build_main_menu_text(user_id: int) -> str:
    level = level_label(get_level(user_id))
    words_per_day = get_words_per_day(user_id)
    words_text = f"{words_per_day} в день" if words_per_day else "не настроено"
    roadmap_step = get_current_topic_number(user_id)
    plan = get_premium_status_text(user_id)
    ai_usage = get_ai_usage_text(user_id)

    return (
        "✨ English Hub\n"
        "Ваш центр уроков и быстрых действий.\n\n"
        "📊 Сводка\n"
        f"• Тариф: {plan}\n"
        f"• AI: {ai_usage}\n"
        f"• Уровень: {level}\n"
        f"• Словарь: {words_text}\n"
        f"• Roadmap: тема {roadmap_step}\n\n"
        f"💡 {get_phrase()}"
    )


def build_learning_menu_text() -> str:
    return (
        "📘 Обучение\n"
        "Выберите, как хотите пройти материал.\n\n"
        "• Explain — быстро разобрать тему\n"
        "• Summary — получить короткий конспект\n"
        "• Vocabulary — ежедневные слова"
    )


def build_practice_menu_text() -> str:
    return (
        "🧠 Практика\n"
        "Блок для закрепления и ответов.\n\n"
        "• Quiz — мини-тест по теме\n"
        "• Practice — задания с проверкой"
    )


def build_advanced_menu_text() -> str:
    return (
        "🚀 Advanced\n"
        "Более глубокие режимы обучения.\n\n"
        "• Chat — свободная тренировка\n"
        "• Road map — пошаговый путь по темам\n"
        "• Voice — голосовой формат"
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
        "Здесь можно поменять уровень и открыть справку."
    )


def build_premium_text(user_id: int) -> str:
    status = get_premium_status_text(user_id)
    ai_usage = get_ai_usage_text(user_id)

    return (
        "💎 Premium\n"
        f"Статус: {status}\n"
        f"AI сегодня: {ai_usage}\n\n"
        "Что входит:\n"
        "• безлимитные AI-объяснения и конспекты\n"
        "• проверка практики без дневного лимита\n"
        "• roadmap без ограничений\n"
        "• доступ к Chat и Voice, когда они подключены\n"
        "• приоритет для новых функций\n\n"
        f"Оплата: {PREMIUM_PAYMENT_TEXT}\n\n"
        "Чтобы подключить Premium, оплатите доступ выбранным способом и нажмите кнопку ниже. "
        "Администратор проверит оплату и выдаст доступ."
    )


def main_menu(user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📘 Уроки", callback_data="menu_learning")],
        [
            InlineKeyboardButton(text="🧠 Практика", callback_data="menu_practice"),
            InlineKeyboardButton(text="🚀 Advanced", callback_data="menu_advanced"),
        ],
        [InlineKeyboardButton(text="💎 Premium", callback_data="premium")],
        [
            InlineKeyboardButton(text="⚙️ Профиль", callback_data="menu_settings"),
            InlineKeyboardButton(text="📖 Глоссарий", callback_data="glossary"),
        ],
    ])


def learning_menu(user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📘 Explain", callback_data="mode_explain"),
            InlineKeyboardButton(text="📝 Summary", callback_data="mode_summary"),
        ],
        [InlineKeyboardButton(text="✨ Vocabulary", callback_data="vocab_settings")],
        [InlineKeyboardButton(text=menu_back_label(), callback_data="back_main")],
    ])


def practice_menu(user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🧩 Quiz", callback_data="mode_quiz"),
            InlineKeyboardButton(text="✍️ Practice", callback_data="mode_practice"),
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
            InlineKeyboardButton(text=lock("💬 Chat", "chat"), callback_data="mode_chat"),
            InlineKeyboardButton(text=lock("🗺 Road map", "roadmap"), callback_data="mode_roadmap"),
        ],
        [InlineKeyboardButton(text=lock("🎤 Voice", "voice"), callback_data="mode_voice")],
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
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data="premium_request")],
        [InlineKeyboardButton(text=menu_back_label(), callback_data="back_main")],
    ])


def cancel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=cancel_label(), callback_data="cancel")],
    ])


def after_explain_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Перейти к практике", callback_data="practice")],
        [InlineKeyboardButton(text="✨ Vocabulary", callback_data="vocab_settings")],
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


def vocab_count_kb(current_value: int | None = None):
    rows = []
    row = []

    for value in range(3, 11):
        prefix = "✅ " if current_value == value else ""
        row.append(InlineKeyboardButton(text=f"{prefix}{value}", callback_data=f"set_vocab_count:{value}"))
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
            "• Уроки — объяснение, конспект и словарь\n"
            "• Практика — тесты и задания с проверкой\n"
            "• Advanced — roadmap, chat и voice\n"
            "• Premium — безлимитный AI-доступ\n"
            "• Профиль — уровень и быстрые настройки\n\n"
            "Команды:\n"
            "/start — открыть главное меню\n"
            "/help — показать помощь\n"
            "/cancel — отменить текущее действие\n"
            "/change_level — изменить уровень\n"
            "/premium — открыть Premium"
        )

    async def cancel_action(message: Message, state: FSMContext):
        await state.clear()
        await message.answer(
            "✖️ Действие отменено.\n\n" + build_main_menu_text(message.from_user.id),
            reply_markup=main_menu(message.from_user.id),
        )

    async def change_level_action(message: Message, user_id: int):
        current = get_level(user_id)
        await message.answer(
            f"🎯 Уровень пользователя\n\nСейчас: {level_label(current)}\n\nВыберите уровень вручную или пройдите тест после выбора.",
            reply_markup=level_kb(current),
        )

    async def show_premium(message: Message, user_id: int):
        await message.answer(build_premium_text(user_id), reply_markup=premium_kb())

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
        await message.answer(
            "✨ Настройка словаря\n"
            "Выберите, сколько новых слов хотите получать в день.\n"
            f"Рекомендуемый старт: {DEFAULT_WORDS_PER_DAY}. Самый удобный темп — 5-7 слов в день.",
            reply_markup=vocab_count_kb(current_value),
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
            "✍️ Напишите ответы одним сообщением. Я проверю и дам короткий фидбэк.",
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

        prompt = f"""
Ты проверяешь ответы ученика по английскому.

Тема: {topic}
Уровень: {level}
Тип задания: {mode}

Задание:
{task}

Ответ ученика:
{user_answer}

Проверь ответ.
Формат:
1. Что верно
2. Что исправить
3. Правильный вариант, если есть ошибка
4. Короткий совет
"""
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

            topic = get_current_topic(user)
            level = level_label(user.level)
            simplify = user.last_result == "wrong_twice"
        finally:
            db.close()

        if not topic:
            await state.clear()
            await message.answer("✅ Roadmap completed.", reply_markup=main_menu(user_id))
            return

        if not await ensure_ai_quota(message, user_id):
            await state.clear()
            return

        lesson = ask_ai(make_roadmap_lesson_prompt(topic, level, simplify), level, "roadmap")
        await state.update_data(roadmap_topic=topic, roadmap_lesson=lesson)
        await state.set_state(StudyFlow.waiting_roadmap_answer)
        await message.answer(f"🗺 Roadmap topic: {topic}")
        await message.answer(lesson)
        await message.answer("✍️ Отправьте ответ одним сообщением.", reply_markup=cancel_kb())

    async def check_roadmap_answer(message: Message, state: FSMContext, user_answer: str):
        data = await state.get_data()
        topic = data.get("roadmap_topic")
        lesson = data.get("roadmap_lesson")

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
            review = ask_ai(make_roadmap_check_prompt(topic, level, lesson, user_answer), level, "roadmap_check")
            result = parse_roadmap_result(review)
            update_progress(user, result)
            db.commit()
        finally:
            db.close()

        await message.answer(review)
        await send_roadmap_lesson(message, state, message.from_user.id)

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
                last_result="",
                words_per_day=None,
                last_vocab_sent_date="",
                premium_until="",
                ai_requests_date="",
                ai_requests_count=0,
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

        elif data == "premium_request":
            await notify_admin_about_premium_request(bot, call.message, call.from_user)

        elif data == "cancel":
            await cancel_action(call.message, state)

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

            if mode == "roadmap":
                await send_roadmap_lesson(call.message, state, call.from_user.id)
                return

            await state.update_data(mode=mode)
            await state.set_state(StudyFlow.waiting_topic)
            msg = await call.message.edit_text("✍️ Введите тему, с которой хотите поработать.", reply_markup=cancel_kb())
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

            practice_prompt = f"""
Ты даешь задания по английскому.

Тема: {topic}
Уровень: {level}

Сделай ровно 3 задания:
1. Translate
2. Make a sentence
3. Answer the question

Не давай ответы заранее.
"""
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
            await message.answer("Введите тему.", reply_markup=cancel_kb())
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
            await message.answer(answer, reply_markup=after_explain_kb())
        elif mode in {"quiz", "practice"}:
            await send_practice_task(message, state, answer, topic, level, mode)
        else:
            await state.clear()
            await message.answer(answer, reply_markup=main_menu(message.from_user.id))

    @dp.message(StudyFlow.waiting_practice_answer)
    async def practice_answer_input(message: Message, state: FSMContext):
        user_answer = (message.text or "").strip()
        if not user_answer:
            await message.answer("Напишите ответ текстом.", reply_markup=cancel_kb())
            return

        await check_practice_answer(message, state, user_answer)

    @dp.message(StudyFlow.waiting_roadmap_answer)
    async def roadmap_answer_input(message: Message, state: FSMContext):
        user_answer = (message.text or "").strip()
        if not user_answer:
            await message.answer("Напишите ответ текстом.", reply_markup=cancel_kb())
            return

        await check_roadmap_answer(message, state, user_answer)

    asyncio.create_task(vocab_daily_loop(bot))
    await notify_bot_started(bot)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
