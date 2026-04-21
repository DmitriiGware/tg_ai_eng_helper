import asyncio
import logging
import os
import re
from dotenv import load_dotenv
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from prompts import make_user_prompt
from ai_client import ask_ai
from modes import MODES
from motivation import get_phrase
from glossary import glossary_menu, glossary_text
from datetime import datetime
from database.db import SessionLocal
from database.models import User
from database.db import engine
from database.models import Base

ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

BOT_TOKEN = (os.getenv("BOT_TOKEN") or "").strip()
ADMIN_TELEGRAM_ID = (os.getenv("TELEGRAM_ADMIN_ID") or "").strip()


#ПРОВЕРКА ПРЕМКИ

def is_premium(user_id: int) -> bool:
    return False

#УРОВЕНЬ ПОЛЬЗОВАТЕЛЯ

def get_level(user_id: int) -> str:
    db = SessionLocal()
    user = db.query(User).filter(User.telegram_id == user_id).first()
    db.close()

    if user and user.level:
        return user.level

    return "Beginner"


#МЕНЮ

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
        [InlineKeyboardButton(text="📚 Glossary | Глоссарий для новичков", callback_data="glossary")]
    ])

#МЕНЮ ОБУЧЕНИЯ

def learning_menu(user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📚 Explain", callback_data="mode_explain")],
        [InlineKeyboardButton(text="📝 Summary", callback_data="mode_summary")],
        [InlineKeyboardButton(text="⬅️ to Menu", callback_data="back_main")]
    ])

#МЕНЮ ПРАКТИКИ

def practice_menu(user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧩 Quiz", callback_data="mode_quiz")],
        [InlineKeyboardButton(text="🧠 Practice", callback_data="mode_practice")],
        [InlineKeyboardButton(text="⬅️ to Menu", callback_data="back_main")]
    ])

#РАСШИРЕННЫЙ ФУНКЦИОНАЛ

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
        ]
    ])

#МЕНЮ НАСТРОЕК

def settings_menu(user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎯 Change level", callback_data="change_level")],
        [InlineKeyboardButton(text="❓ Help", callback_data="help")],
        [InlineKeyboardButton(text="⬅️ to Menu", callback_data="back_main")]
    ])

#КНОПКА ОТМЕНЫ

def cancel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Cancel | Отмена", callback_data="cancel")]
    ])

#МЕНЮ ВЫБОРА

def level_kb(current: str):
    rows = [
        [InlineKeyboardButton(text=("✅ Beginner | Начинающий" if current == "Beginner" else "Beginner"), callback_data="set_level:Beginner")],
        [InlineKeyboardButton(text=("✅ Intermediate | Промежуточный" if current == "Intermediate" else "Intermediate"), callback_data="set_level:Intermediate")],
        [InlineKeyboardButton(text=("✅ Advanced | Продвинутый" if current == "Advanced" else "Advanced"), callback_data="set_level:Advanced")],
        [InlineKeyboardButton(text="⬅️ to Menu | Назад в меню", callback_data="back_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def delete_later(msg, delay=10):
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except:
        pass

#БЛОК ПОСЛЕ ОБЪЯСНЕНИЙ

def after_explain_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧠 Practice", callback_data="practice")],
        [InlineKeyboardButton(text="⬅️ to Menu", callback_data="back_menu")]
    ])

class Registration(StatesGroup):
    name = State()
    birthdate = State()
    frequency = State()

class StudyFlow(StatesGroup):
    waiting_topic = State()

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
        msg = await bot.send_message(
            admin_id,
            f"Bot @{me.username or me.first_name} started successfully."
        )

        asyncio.create_task(delete_later(msg, 5))

    except Exception as exc:
        logging.exception("Failed to send startup notification: %s", exc)

async def main():
    logging.basicConfig(level=logging.INFO)

    Base.metadata.create_all(bind=engine)

    if not BOT_TOKEN:
        raise RuntimeError(f"BOT_TOKEN is missing. Env file: {ENV_PATH}")

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    @dp.message(Registration.name)
    async def reg_name(message: Message, state: FSMContext):
        name = (message.text or "").strip()

        # ❌ пусто
        if not name:
            await message.answer("Введите имя 🙂")
            return

        # ❌ не буквы
        if not re.match(r"^[A-Za-zА-Яа-яЁё]+$", name):
            await message.answer("Имя должно содержать только буквы 🙂")
            return

        # ❌ слишком длинное
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

            # ❌ дата в будущем
            if birthdate > datetime.now():
                await message.answer("Дата не может быть из будущего 🙂")
                return

            # ❌ слишком старый (опционально)
            if birthdate.year < 1900:
                await message.answer("Введите реальную дату 🙂")
                return

        except:
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
            ])
        )

    @dp.callback_query(lambda c: c.data.startswith("freq_"))
    async def reg_freq(call: CallbackQuery, state: FSMContext):
        freq = call.data.replace("freq_", "")
        data = await state.get_data()

        #BD
        db = SessionLocal()

        user = User(
            telegram_id=call.from_user.id,
            name=data["name"],
            birthday=data["birthdate"],
            frequency=freq
        )

        db.add(user)
        db.commit()
        db.close()

        await state.clear()

        await call.message.edit_text(
            f"🔥 Готово, {data['name']}!\nНачинаем обучение 🚀\n\n"
            "🤖 I'm your AI Study Bot.\n\n"
            "I recommend that you first press or enter the command /help.\n"
            "Советую сначала нажать или ввести команду /help.\n\n"
            "You can choose a mode below and choose a type of learning.\n"
            "Вы можете выбрать режим и выбрать тип обучения.\n\n"
            "🎯 Current level: ""Beginner""\n"
            "If you don't know your level, try ""Beginner"" first.\n"
            "Если вы не знаете ваш уровень, начните с ""Beginner"".",
            reply_markup=main_menu(call.from_user.id)
        )




    async def show_main_menu(message: Message, state: FSMContext):
        await state.clear()
        await message.answer(
            "🏠 Main menu | Главное меню:" + "\n\n" + get_phrase(),
            reply_markup=main_menu(message.from_user.id)
        )

    async def show_help(message: Message):
        await message.answer(
            "🧠 How to use | Как пользоваться\n\n"
        "Все обучающие инструменты поделены на блоки,\nв каждом блоке есть несколько инструментов.\n\n"
        "📚 Learning — обучение\n"
        "🧠 Practice — Практика\n"
        "🚀 Premium — Премиум функции\n"
        "⚙️ Settings — настройки\n\n"

        "Commands | Команды:\n\n"
        "/start — меню\n"
        "/help — помощь\n"
        "/cancel — отмена\n"
        "/change_level — смена уровня\n\n"
        "Now Type /start | Далее напишите /start",
        )

    async def cancel_action(message: Message, state: FSMContext):
        await state.clear()
        await message.answer(
            "✅ Cancelled" + "\n\n" + get_phrase(),
            reply_markup=main_menu(message.from_user.id)
        )

    async def change_level_action(message: Message, user_id: int):
        current = get_level(user_id)
        await message.answer(
            f"🎯 Current level: {current}\nChoose your level:",
            reply_markup=level_kb(current)
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
            await message.answer(
                "Hello! What's your name?\nПривет! Как тебя зовут? 👋"
            )

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

        if data == "help":
            await show_help(call.message)


        elif data == "cancel":
            await cancel_action(call.message, state)


        elif data.startswith("mode_"):
            mode = data.replace("mode_", "")

            if MODES[mode]["premium"] and not is_premium(call.from_user.id):
                await call.message.answer("🔒 This mode is available in Premium\nЭто доступно только в премиуме")
                return

            await state.update_data(mode=mode)
            await state.set_state(StudyFlow.waiting_topic)
            ags = await call.message.edit_text("Type your topic | Введите вашу тему 👇", reply_markup=cancel_kb())

            asyncio.create_task(delete_later(ags, 30))


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
            await call.message.edit_text(
                "🏠 Main menu:" + "\n\n" + get_phrase(),
                reply_markup=main_menu(call.from_user.id)

            )

        elif data == "glossary":
            await call.message.edit_text(
                "📚 Glossary\nChoose a category:",
                reply_markup=glossary_menu()
            )

        elif data.startswith("glossary_"):
            category = data.replace("glossary_", "")

            await call.message.edit_text(
                glossary_text(category),
                reply_markup=glossary_menu()
            )

        elif data == "practice":
            data_state = await state.get_data()
            topic = data_state.get("topic")
            level = get_level(call.from_user.id)

            if not topic:
                await call.message.answer("❌ Topic lost, try again" + "\n\n" + get_phrase(), reply_markup=main_menu(call.from_user.id))
                return

            await call.message.answer("Practice time 🧠")

            practice_prompt = f"""
            Ты даёшь задания по английскому.

            Тема: {topic}
            Уровень: {level}

            Сделай РОВНО 3 задания:

            1. Translate (с русского на английский)
            2. Make a sentence (дай слова в скобках)
            3. Answer the question (вопрос на английском)

            Правила:
            - Не смешивай языки в одном предложении
            - Пиши чисто и понятно
            - НЕ давай ответы
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

            await state.clear()
            await call.message.answer(answer, reply_markup=main_menu(call.from_user.id))


        elif data.startswith("set_level:"):
            level = data.split(":", 1)[1]
            user_id = call.from_user.id
            db = SessionLocal()
            user = db.query(User).filter(User.telegram_id == user_id).first()

            if user:
                user.level = level
                db.commit()

            db.close()
            await call.message.edit_text(
                f"✅ Level set: {level}",
                reply_markup=main_menu(user_id)
            )


    @dp.message(StudyFlow.waiting_topic)
    async def topic_input(message: Message, state: FSMContext):
        topic = (message.text or "").strip()
        if not topic:
            await message.answer("Please type a topic 🙂" + "\n\n" + get_phrase(), reply_markup=cancel_kb())
            return

        data = await state.get_data()
        mode = data.get("mode", "explain")
        level = get_level(message.from_user.id)

        frf = await message.answer("Thinking… 🤖")

        asyncio.create_task(delete_later(frf, 5))

        prompt = make_user_prompt(topic, mode, level)

        try:
            answer = ask_ai(prompt, level, mode)
        except Exception as e:
            await state.clear()
            await message.answer(f"⚠️ Error: {e}")
            await message.answer("🏠 Main menu:" + "\n\n" + get_phrase(), reply_markup=main_menu(message.from_user.id))
            return

        await state.update_data(topic=topic, mode = mode)
        if mode == "explain":
            await message.answer(answer, reply_markup=after_explain_kb())
        else:
            await state.clear()
            await message.answer(answer, reply_markup=main_menu(message.from_user.id))

    await notify_bot_started(bot)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
