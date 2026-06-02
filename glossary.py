from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def glossary_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📘 Обучение", callback_data="glossary_learning")],
        [InlineKeyboardButton(text="🧠 Практика", callback_data="glossary_practice")],
        [InlineKeyboardButton(text="🚀 Продвинутые режимы", callback_data="glossary_premium")],
        [InlineKeyboardButton(text="🧭 Навигация", callback_data="glossary_nav")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="back_main")],
    ])


def glossary_text(category: str):
    data = {
        "learning": (
            "📘 Обучение\n\n"
            "📘 Объяснить тему\n"
            "Бот объясняет правило, даёт примеры и мини-задание.\n"
            "Пример: Present Simple\n\n"
            "📝 Конспект\n"
            "Бот делает короткую шпаргалку по теме.\n"
            "Пример: Past Simple\n\n"
            "✨ Слова на день\n"
            "Бот присылает ежедневную подборку слов по вашему уровню."
        ),
        "practice": (
            "🧠 Практика\n\n"
            "🧩 Мини-тест\n"
            "Мини-тест по теме без ответов заранее.\n\n"
            "✍️ Практика\n"
            "Практические задания с последующей проверкой."
        ),
        "premium": (
            "🚀 Продвинутые режимы\n\n"
            "🗺 Путь изучения\n"
            "Пошаговое обучение по темам с адаптацией.\n\n"
            "💬 Чат-тренировка\n"
            "Тренировка диалога по ситуации.\n\n"
            "🎤 Голос\n"
            "Голосовой формат, который будет подключен позже."
        ),
        "nav": (
            "🧭 Навигация\n\n"
            "◀️ Главное меню — вернуться на главный экран\n"
            "✖️ Отмена — остановить текущее действие\n"
            "❔ Помощь — открыть краткую инструкцию\n"
            "🎯 Уровень — изменить текущий уровень"
        ),
    }

    return data.get(category, "📖 Glossary")
