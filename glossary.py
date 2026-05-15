from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def glossary_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📘 Learning", callback_data="glossary_learning")],
        [InlineKeyboardButton(text="🧠 Practice", callback_data="glossary_practice")],
        [InlineKeyboardButton(text="🚀 Advanced", callback_data="glossary_premium")],
        [InlineKeyboardButton(text="🧭 Navigation", callback_data="glossary_nav")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="back_main")],
    ])


def glossary_text(category: str):
    data = {
        "learning": (
            "📘 Learning\n\n"
            "📘 Explain\n"
            "Бот объясняет тему простыми словами.\n"
            "Пример: Present Simple\n\n"
            "📝 Summary\n"
            "Бот делает короткий и удобный конспект.\n"
            "Пример: Past Simple\n\n"
            "✨ Vocabulary\n"
            "Бот присылает ежедневную подборку слов по вашему уровню."
        ),
        "practice": (
            "🧠 Practice\n\n"
            "🧩 Quiz\n"
            "Мини-тест по теме без ответов заранее.\n\n"
            "✍️ Practice\n"
            "Практические задания с последующей проверкой."
        ),
        "premium": (
            "🚀 Advanced\n\n"
            "💬 Chat\n"
            "Свободная практика и общение.\n\n"
            "🗺 Road map\n"
            "Пошаговое обучение по темам с адаптацией.\n\n"
            "🎤 Voice\n"
            "Голосовой формат взаимодействия."
        ),
        "nav": (
            "🧭 Navigation\n\n"
            "◀️ Главное меню — вернуться на главный экран\n"
            "✖️ Отмена — остановить текущее действие\n"
            "❔ Помощь — открыть краткую инструкцию\n"
            "🎯 Уровень — изменить текущий уровень"
        ),
    }

    return data.get(category, "📖 Glossary")
