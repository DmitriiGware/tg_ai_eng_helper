import asyncio
import logging
import os
import re
from datetime import datetime
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart, Command
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

DEFAULT_LEVEL = "A1"
DEFAULT_WORDS_PER_DAY = 5
DAILY_VOCAB_HOUR = 10
RECENT_VOCAB_HISTORY_LIMIT = 80
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


def is_premium(user_id: int) -> bool:
    return False


def get_level(user_id: int) -> str:
    db = SessionLocal()
    user = db.query(User).filter(User.telegram_id == user_id).first()
    db.close()

    if user and user.level:
        return normalize_level(user.level)

    return DEFAULT_LEVEL


def main_menu(user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📚 Learning", callback_data="menu_learning"),
            InlineKeyboardButton(text="🧠 Practice", callback_data="menu_practice"),
        ],
        [
            InlineKeyboardButton(text="🚀 Premium", callback_data="menu_advanced"),
            InlineKeyboardButton(text="⚙️ Settings", callback_data="menu_settings"),
        ],
        [InlineKeyboardButton(text="📚 Glossary | Глоссарий для новичков", callback_data="glossary")],
    ])


def learning_menu(user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📚 Explain", callback_data="mode_explain")],
        [InlineKeyboardButton(text="📝 Summary", callback_data="mode_summary")],
        [InlineKeyboardButton(text="⬅️ to Menu", callback_data="back_main")],
    ])


def practice_menu(user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧩 Quiz", callback_data="mode_quiz")],
        [InlineKeyboardButton(text="🧠 Practice", callback_data="mode_practice")],
        [InlineKeyboardButton(text="⬅️ to Menu", callback_data="back_main")],
    ])


def advanced_menu(user_id: int):
    def lock(text, key):
        if MODES[key]["premium"] and not is_premium(user_id):
            return text + " 🔒"
        return text

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=lock("💬 Chat", "chat"), callback_data="mode_chat"),
            InlineKeyboardButton(text=lock("✍️ Road map", "roadmap"), callback_data="mode_roadmap"),
        ],
        [
            InlineKeyboardButton(text=lock("🎤 Voice", "voice"), callback_data="mode_voice"),
            InlineKeyboardButton(text="⬅️ to Menu", callback_data="back_main"),
        ],
    ])


def settings_menu(user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎯 Change level", callback_data="change_level")],
        [InlineKeyboardButton(text="❓ Help", callback_data="help")],
        [InlineKeyboardButton(text="⬅️ to Menu", callback_data="back_main")],
    ])


def cancel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Cancel | Отмена", callback_data="cancel")],
    ])


async def delete_later(msg, delay=10):
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except Exception:
        pass


def after_explain_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧠 Practice", callback_data="practice")],
        [InlineKeyboardButton(text="⬅️ to Menu", callback_data="back_main")],
    ])


def level_kb(current: str):
    current = normalize_level(current)
    rows = []
    for code, label in LEVELS:
        prefix = "✅ " if current == code else ""
        rows.append([InlineKeyboardButton(text=f"{prefix}{label}", callback_data=f"set_level:{code}")])

    rows.append([InlineKeyboardButton(text="⬅️ to Menu | Назад в меню", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def level_change_confirm_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да", callback_data="level_test_yes")],
        [InlineKeyboardButton(text="Отмена", callback_data="level_test_cancel")],
    ])


def level_question_kb(question: dict):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=option, callback_data=f"level_answer:{index}")]
        for index, option in enumerate(question["options"])
    ])


def learning_menu(user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Explain", callback_data="mode_explain")],
        [InlineKeyboardButton(text="Summary", callback_data="mode_summary")],
        [InlineKeyboardButton(text="Vocabulary", callback_data="vocab_settings")],
        [InlineKeyboardButton(text="To menu", callback_data="back_main")],
    ])


def vocab_count_kb(current_value: int | None = None):
    rows = []
    row = []

    for value in range(3, 11):
        prefix = "OK " if current_value == value else ""
        row.append(InlineKeyboardButton(text=f"{prefix}{value}", callback_data=f"set_vocab_count:{value}"))
        if len(row) == 4:
            rows.append(row)
            row = []

    if row:
        rows.append(row)

    rows.append([InlineKeyboardButton(text="To menu", callback_data="back_main")])
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


async def notify_bot_started(bot: Bot) -> None:
    if not ADMIN_TELEGRAM_ID:
        logging.info("TELEGRAM_ADMIN_ID is not set. Startup notification skipped.")
        return

    try:
        admin_id = int(ADMIN_TELEGRAM_ID)
    except ValueError:
        logging.warning("TELEGRAM_ADMIN_ID must be a number. Startup notification skipped.")
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

    @dp.message(Registration.name)
    async def reg_name(message: Message, state: FSMContext):
        name = (message.text or "").strip()

        if not name:
            await message.answer("Введите имя 🙂")
            return

        if not re.match(r"^[A-Za-zА-Яа-яЁё]+$", name):
            await message.answer("Имя должно содержать только буквы 🙂")
            return

        if len(name) > 20:
            await message.answer("Слишком длинное имя 🙂")
            return

        await state.update_data(name=name)
        await state.set_state(Registration.birthdate)
        await message.answer("Enter your date of birth:\nВведите дату рождения: (01.01.2000)")

    @dp.message(Registration.birthdate)
    async def reg_birth(message: Message, state: FSMContext):
        text = (message.text or "").strip()

        try:
            birthdate = datetime.strptime(text, "%d.%m.%Y")
            if birthdate > datetime.now():
                await message.answer("Дата не может быть из будущего 🙂")
                return
            if birthdate.year < 1900:
                await message.answer("Введите реальную дату 🙂")
                return
        except Exception:
            await message.answer("Введите дату в формате 01.01.2000 🙂")
            return

        await state.update_data(birthdate=text)
        await state.set_state(Registration.frequency)
        await message.answer(
            "How often will you practice?\nКак часто ты будешь заниматься?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Каждый день", callback_data="freq_daily")],
                [InlineKeyboardButton(text="3 раза в неделю", callback_data="freq_3")],
                [InlineKeyboardButton(text="1 раз в неделю", callback_data="freq_1")],
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
        )
        db.add(user)
        db.commit()
        db.close()
        await state.clear()

        await call.message.edit_text(
            f"🔥 Готово, {name}!\nНачинаем обучение 🚀\n\n"
            "🤖 I'm your AI Study Bot.\n\n"
            "I recommend that you first press or enter the command /help.\n"
            "Советую сначала нажать или ввести команду /help.\n\n"
            "You can choose a mode below and choose a type of learning.\n"
            "Вы можете выбрать режим и тип обучения.\n\n"
            f"🎯 Current level: {level_label(DEFAULT_LEVEL)}\n"
            f"If you don't know your level, try {level_label(DEFAULT_LEVEL)} first.\n"
            f"Если вы не знаете ваш уровень, начните с {level_label(DEFAULT_LEVEL)}.",
            reply_markup=main_menu(call.from_user.id),
        )

    async def show_main_menu(message: Message, state: FSMContext):
        await state.clear()
        await message.answer("🏠 Main menu | Главное меню:" + "\n\n" + get_phrase(), reply_markup=main_menu(message.from_user.id))

    async def show_help(message: Message):
        await message.answer(
            "🧠 How to use | Как пользоваться\n\n"
            "Все обучающие инструменты поделены на блоки, в каждом блоке есть несколько инструментов.\n\n"
            "📚 Learning — обучение\n"
            "🧠 Practice — практика\n"
            "🚀 Premium — премиум функции\n"
            "⚙️ Settings — настройки\n\n"
            "Commands | Команды:\n\n"
            "/start — меню\n"
            "/help — помощь\n"
            "/cancel — отмена\n"
            "/change_level — смена уровня\n\n"
            "Now type /start | Далее напишите /start"
        )

    async def cancel_action(message: Message, state: FSMContext):
        await state.clear()
        await message.answer("✅ Cancelled" + "\n\n" + get_phrase(), reply_markup=main_menu(message.from_user.id))

    async def change_level_action(message: Message, user_id: int):
        current = get_level(user_id)
        await message.answer(
            f"🎯 Current level: {level_label(current)}\nChoose your level:",
            reply_markup=level_kb(current),
        )

    async def send_level_question(message: Message, state: FSMContext):
        data = await state.get_data()
        questions = data["level_questions"]
        index = data["level_index"]
        question = questions[index]
        await message.answer(
            f"Question {index + 1}/5\n\n{question['question']}",
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
        lines = []

        for index, entry in enumerate(entries, start=1):
            lines.append(
                f"{index}. {entry['word']} — {entry['translation']}\n"
                f"   {entry['example']}\n"
                f"   {entry['example_translation']}"
            )

        return "\n\n".join(lines)

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

    def save_vocab_entries(user_id: int, level: str, entries: list[dict]):
        if not entries:
            return

        db = SessionLocal()
        try:
            today = datetime.now().date().isoformat()
            for entry in entries:
                db.add(VocabWord(
                    telegram_id=user_id,
                    level=level,
                    word=entry["word"],
                    translation=entry["translation"],
                    example=entry["example"],
                    example_translation=entry["example_translation"],
                    sent_date=today,
                ))
            db.commit()
        finally:
            db.close()

    async def show_vocab_settings(message: Message, user_id: int):
        db = SessionLocal()
        user = db.query(User).filter(User.telegram_id == user_id).first()
        current_value = user.words_per_day if user and user.words_per_day else DEFAULT_WORDS_PER_DAY
        db.close()

        await message.answer(
            "Vocabulary setup.\n"
            "Choose how many new words you want per day.\n"
            f"Usually 5-7 words per day works best for steady progress. Recommended start: {DEFAULT_WORDS_PER_DAY}.",
            reply_markup=vocab_count_kb(current_value),
        )

    async def send_vocab_words(bot: Bot, user_id: int, force: bool = False):
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.telegram_id == user_id).first()
            if not user or not user.words_per_day:
                return False

            today = datetime.now().date().isoformat()
            if not force and user.last_vocab_sent_date == today:
                return False

            level = level_label(user.level)
            count = user.words_per_day
            recent_words = [
                item.word
                for item in db.query(VocabWord)
                .filter(VocabWord.telegram_id == user_id)
                .order_by(VocabWord.id.desc())
                .limit(RECENT_VOCAB_HISTORY_LIMIT)
                .all()
            ]
            requested_count = count + 5
            raw_text = ask_ai(make_vocab_words_prompt(level, requested_count, recent_words), level, "vocabulary")
            parsed_entries = parse_vocab_entries(raw_text)
            final_entries = filter_vocab_entries(parsed_entries, recent_words, count)

            if not final_entries:
                return False

            text = format_vocab_entries(final_entries)

            await bot.send_message(
                user_id,
                f"Daily vocabulary\nLevel: {level}\nWords today: {len(final_entries)}\n\n{text}",
            )
            user.last_vocab_sent_date = today
            db.commit()
            save_vocab_entries(user_id, user.level, final_entries)
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
            "Напишите ответы одним сообщением. Я проверю и дам короткий фидбэк.",
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

Задание, которое получил ученик:
{task}

Ответ ученика:
{user_answer}

Проверь ответ.
Формат:
1. Что верно
2. Что исправить
3. Правильный вариант, если есть ошибка
4. Короткий совет

Пиши понятно и поддерживающе.
"""
        msg = await message.answer("Проверяю ответы… 🤖")
        asyncio.create_task(delete_later(msg, 5))
        feedback = ask_ai(prompt, level, "practice_check")
        await state.clear()
        await message.answer(feedback, reply_markup=main_menu(message.from_user.id))

    def parse_roadmap_result(answer: str) -> bool:
        first_line = (answer or "").splitlines()[0].strip().lower()
        return "result: correct" in first_line

    async def send_roadmap_lesson(message: Message, state: FSMContext, user_id: int):
        db = SessionLocal()
        user = db.query(User).filter(User.telegram_id == user_id).first()

        if not user:
            db.close()
            await state.clear()
            await message.answer("User not found. Please use /start first.")
            return

        topic = get_current_topic(user)
        level = level_label(user.level)
        simplify = user.last_result == "wrong_twice"
        db.close()

        if not topic:
            await state.clear()
            await message.answer(
                "Roadmap completed. Great job.",
                reply_markup=main_menu(user_id),
            )
            return

        lesson = ask_ai(
            make_roadmap_lesson_prompt(topic, level, simplify),
            level,
            "roadmap",
        )

        await state.update_data(
            roadmap_topic=topic,
            roadmap_lesson=lesson,
        )
        await state.set_state(StudyFlow.waiting_roadmap_answer)
        await message.answer(f"Roadmap topic: {topic}")
        await message.answer(lesson)
        await message.answer(
            "Send your answer in one message.",
            reply_markup=cancel_kb(),
        )

    async def check_roadmap_answer(message: Message, state: FSMContext, user_answer: str):
        state_data = await state.get_data()
        topic = state_data.get("roadmap_topic")
        lesson = state_data.get("roadmap_lesson")

        if not topic or not lesson:
            await state.clear()
            await message.answer(
                "Roadmap state was lost. Start the roadmap again.",
                reply_markup=main_menu(message.from_user.id),
            )
            return

        db = SessionLocal()
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            db.close()
            await state.clear()
            await message.answer("User not found. Please use /start first.")
            return

        level = level_label(user.level)
        review = ask_ai(
            make_roadmap_check_prompt(topic, level, lesson, user_answer),
            level,
            "roadmap_check",
        )
        result = parse_roadmap_result(review)
        update_progress(user, result)
        db.commit()
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
            user = db.query(User).filter(User.telegram_id == call.from_user.id).first()
            if user:
                user.level = target_level
                user.current_topic_index = 0
                user.last_result = ""
                db.commit()
            db.close()
            await state.clear()
            await call.message.answer(
                f"✅ Test passed: {score}/5\nLevel changed to {level_label(target_level)}.",
                reply_markup=main_menu(call.from_user.id),
            )
            return

        topics = ", ".join(sorted({item["topic"] for item in wrong_answers}))
        mistakes_text = "\n".join(
            f"- {item['topic']}: your answer: {item['selected_answer']} | correct: {item['correct_answer']}"
            for item in wrong_answers
        )
        explanation = await explain_level_errors(wrong_answers, target_level)
        await state.clear()
        await call.message.answer(
            f"Result: {score}/5\n\n"
            "Кажется, вам еще рано менять уровень.\n"
            f"Посмотрите тему: {topics}\n\n"
            f"Errors:\n{mistakes_text}\n\n"
            f"{explanation}",
            reply_markup=main_menu(call.from_user.id),
        )

    @dp.message(CommandStart())
    async def start(message: Message, state: FSMContext):
        db = SessionLocal()
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        db.close()

        if user:
            await show_main_menu(message, state)
        else:
            await state.set_state(Registration.name)
            await message.answer("Hello! What's your name?\nПривет! Как тебя зовут? 👋")

    @dp.message(Command("help"))
    async def help_cmd(message: Message):
        await show_help(message)

    @dp.message(Command("cancel"))
    async def cancel_cmd(message: Message, state: FSMContext):
        await cancel_action(message, state)

    @dp.message(Command("change_level"))
    async def change_level_cmd(message: Message):
        await change_level_action(message, message.from_user.id)

    @dp.callback_query()
    async def cb(call: CallbackQuery, state: FSMContext):
        data = call.data
        if not data:
            await call.answer()
            return

        if data == "help":
            await show_help(call.message)

        elif data == "cancel":
            await cancel_action(call.message, state)

        elif data == "level_test_cancel":
            await state.clear()
            await call.message.edit_text("Level change cancelled.", reply_markup=main_menu(call.from_user.id))

        elif data == "level_test_yes":
            state_data = await state.get_data()
            target_level = state_data.get("pending_level")
            if not target_level:
                await state.clear()
                await call.message.answer("Level was not selected. Try again.", reply_markup=main_menu(call.from_user.id))
                return

            await state.set_state(LevelChangeFlow.testing)
            await state.update_data(level_questions=get_level_test(target_level), level_index=0, level_answers=[])
            await call.message.edit_text(f"Starting test for {level_label(target_level)}.")
            await send_level_question(call.message, state)

        elif data.startswith("level_answer:"):
            state_data = await state.get_data()
            questions = state_data.get("level_questions")
            index = state_data.get("level_index", 0)
            if not questions or index >= len(questions):
                await state.clear()
                await call.message.answer("Test state was lost. Try again.", reply_markup=main_menu(call.from_user.id))
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
                await call.answer("Choose a value from 3 to 10.")
                return

            db = SessionLocal()
            user = db.query(User).filter(User.telegram_id == call.from_user.id).first()
            if not user:
                db.close()
                await call.message.answer("User not found. Please use /start first.")
                return

            user.words_per_day = value
            user.last_vocab_sent_date = ""
            db.commit()
            db.close()

            await call.message.answer(
                f"Vocabulary goal saved: {value} words per day.\n"
                "Usually 5-7 words per day works best for steady progress.",
            )
            await send_vocab_words(bot, call.from_user.id, force=True)

        elif data.startswith("mode_"):
            mode = data.replace("mode_", "")
            if MODES[mode]["premium"] and not is_premium(call.from_user.id):
                await call.message.answer("🔒 This mode is available in Premium\nЭто доступно только в премиуме")
                return

            if mode == "roadmap":
                await send_roadmap_lesson(call.message, state, call.from_user.id)
                return

            await state.update_data(mode=mode)
            await state.set_state(StudyFlow.waiting_topic)
            msg = await call.message.edit_text("Type your topic | Введите вашу тему 👇", reply_markup=cancel_kb())
            asyncio.create_task(delete_later(msg, 30))

        elif data == "change_level":
            await change_level_action(call.message, call.from_user.id)

        elif data == "noop":
            await call.answer()

        elif data == "menu_learning":
            await call.message.edit_text("📚 Learning | Обучение" + "\n\n" + get_phrase(), reply_markup=learning_menu(call.from_user.id))

        elif data == "menu_practice":
            await call.message.edit_text("🧠 Practice | Практика" + "\n\n" + get_phrase(), reply_markup=practice_menu(call.from_user.id))

        elif data == "menu_advanced":
            await call.message.edit_text("🚀 Premium | Премиум" + "\n\n" + get_phrase(), reply_markup=advanced_menu(call.from_user.id))

        elif data == "menu_settings":
            await call.message.edit_text("⚙️ Settings | Настройки" + "\n\n" + get_phrase(), reply_markup=settings_menu(call.from_user.id))

        elif data == "back_main":
            await state.clear()
            await call.message.edit_text("🏠 Main menu:" + "\n\n" + get_phrase(), reply_markup=main_menu(call.from_user.id))

        elif data == "glossary":
            await call.message.edit_text("📚 Glossary\nChoose a category:", reply_markup=glossary_menu())

        elif data.startswith("glossary_"):
            category = data.replace("glossary_", "")
            await call.message.edit_text(glossary_text(category), reply_markup=glossary_menu())

        elif data == "practice":
            data_state = await state.get_data()
            topic = data_state.get("topic")
            level = level_label(get_level(call.from_user.id))

            if not topic:
                await call.message.answer("❌ Topic lost, try again" + "\n\n" + get_phrase(), reply_markup=main_menu(call.from_user.id))
                return

            await call.message.answer("Practice time 🧠")
            practice_prompt = f"""
Ты даешь задания по английскому.

Тема: {topic}
Уровень: {level}

Сделай ровно 3 задания:
1. Translate (с русского на английский)
2. Make a sentence (дай слова в скобках)
3. Answer the question (вопрос на английском)

Правила:
- Не смешивай языки в одном предложении
- Пиши чисто и понятно
- Не давай ответы
- Без лишнего текста

Формат:
🧠 Practice: {topic}

1. Translate:
...

2. Make a sentence:
(...)

3. Answer:
...
"""
            answer = ask_ai(practice_prompt, level, "practice")
            await send_practice_task(call.message, state, answer, topic, level, "practice")

        elif data.startswith("set_level:"):
            level = normalize_level(data.split(":", 1)[1])
            await state.set_state(LevelChangeFlow.confirming)
            await state.update_data(pending_level=level)
            await call.message.edit_text(
                f"Прежде чем сменить уровень на {level_label(level)}, вам предстоит пройти небольшой тест.",
                reply_markup=level_change_confirm_kb(),
            )
            return

    @dp.message(StudyFlow.waiting_topic)
    async def topic_input(message: Message, state: FSMContext):
        topic = (message.text or "").strip()
        if not topic:
            await message.answer("Please type a topic 🙂" + "\n\n" + get_phrase(), reply_markup=cancel_kb())
            return

        data = await state.get_data()
        mode = data.get("mode", "explain")
        level = level_label(get_level(message.from_user.id))
        msg = await message.answer("Thinking… 🤖")
        asyncio.create_task(delete_later(msg, 5))
        prompt = make_user_prompt(topic, mode, level)

        try:
            answer = ask_ai(prompt, level, mode)
        except Exception as e:
            await state.clear()
            await message.answer(f"⚠️ Error: {e}")
            await message.answer("🏠 Main menu:" + "\n\n" + get_phrase(), reply_markup=main_menu(message.from_user.id))
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
            await message.answer("Напишите ответы текстом, пожалуйста.", reply_markup=cancel_kb())
            return

        await check_practice_answer(message, state, user_answer)

    @dp.message(StudyFlow.waiting_roadmap_answer)
    async def roadmap_answer_input(message: Message, state: FSMContext):
        user_answer = (message.text or "").strip()
        if not user_answer:
            await message.answer("Please send your answer as text.", reply_markup=cancel_kb())
            return

        await check_roadmap_answer(message, state, user_answer)

    asyncio.create_task(vocab_daily_loop(bot))
    await notify_bot_started(bot)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
