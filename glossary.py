from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def glossary_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📚 Learning", callback_data="glossary_learning")],
        [InlineKeyboardButton(text="🧠 Practice", callback_data="glossary_practice")],
        [InlineKeyboardButton(text="🚀 Premium", callback_data="glossary_premium")],
        [InlineKeyboardButton(text="⚙️ Navigation", callback_data="glossary_nav")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="back_main")]
    ])


def glossary_text(category: str):
    data = {
        "learning": (
            "📚 Learning\n\n"
            
            "📚 Explain\n\n"
            "Перевод: объяснить\n"
            "Ты вводишь тему, бот объясняет её\n"
            "Пример: Present Simple\n\n"

            "📝 Summary\n\n"
            "Перевод: кратко\n"
            "Бот делает короткий конспект\n"
            "Пример: Past Simple"
        ),

        "practice": (
            "🧠 Practice\n\n"

            "🧩 Quiz\n\n"
            "Перевод: тест\n"
            "Бот задаёт вопросы по теме\n\n"

            "🧠 Practice\n\n"
            "Перевод: практика\n"
            "Бот дает несколько заданий\n"
            "Пример: перевести предложение"
        ),

        "premium": (
            "🚀 Premium \n\n"

            "💬 Chat\n\n"
            "Перевод: чат\n"
            "Ты общаешься на английском\n\n"

            "✍️ Road map\n\n"
            "Перевод: Путевая карта\n"
            "Бот составляет карту изучения языка по вашему уровню языка\n\n"
            

            "🎤 Voice\n\n"
            "Перевод: голос\n"
            "Общение с ботом голосовыми сообщениями"
        ),

        "nav": (
            "⚙️ Navigation\n\n"

            "⬅️ Back — назад\n"
            "Вернуться в меню\n\n"

            "❌ Cancel — отмена\n"
            "Остановить действие\n\n"

            "❓ Help — помощь\n"
            "Показать инструкцию\n\n"

            "🎯 Level — уровень\n"
            "Выбрать сложность"
        )
    }

    return data.get(category, "Glossary")