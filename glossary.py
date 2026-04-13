GLOSSARY = [
    # 🔹 Основные разделы
    {"word": "Learning", "ru": "Обучение", "desc": "Раздел для изучения тем"},
    {"word": "Practice", "ru": "Практика", "desc": "Раздел для тренировки навыков"},
    {"word": "Advanced", "ru": "Продвинутый", "desc": "Дополнительные функции (премиум)"},
    {"word": "Settings", "ru": "Настройки", "desc": "Изменение параметров бота"},
    {"word": "Glossary", "ru": "Глоссарий", "desc": "Список слов для навигации"},

    # 🔹 Learning
    {"word": "Explain", "ru": "Объяснить", "desc": "Понять тему с примерами"},
    {"word": "Summary", "ru": "Кратко", "desc": "Короткий конспект темы"},

    # 🔹 Practice
    {"word": "Quiz", "ru": "Тест", "desc": "Ответы на вопросы по теме"},
    {"word": "Practice task", "ru": "Практика", "desc": "Задания для тренировки"},

    # 🔹 Advanced
    {"word": "Chat", "ru": "Чат", "desc": "Общение на английском"},
    {"word": "Fix sentence", "ru": "Исправить предложение", "desc": "Проверка ошибок"},
    {"word": "Voice", "ru": "Голос", "desc": "Голосовое взаимодействие"},

    # 🔹 Навигация
    {"word": "Back", "ru": "Назад", "desc": "Вернуться в меню"},
    {"word": "Menu", "ru": "Меню", "desc": "Главный экран"},
    {"word": "Cancel", "ru": "Отмена", "desc": "Прервать действие"},
    {"word": "Help", "ru": "Помощь", "desc": "Инструкция по боту"},

    # 🔹 Уровни
    {"word": "Level", "ru": "Уровень", "desc": "Сложность обучения"},
    {"word": "Beginner", "ru": "Начинающий", "desc": "Базовый уровень"},
    {"word": "Intermediate", "ru": "Средний", "desc": "Средний уровень"},
    {"word": "Advanced level", "ru": "Продвинутый уровень", "desc": "Сложный уровень"},

    # 🔹 Действия
    {"word": "Choose", "ru": "Выбери", "desc": "Сделать выбор"},
    {"word": "Type", "ru": "Ввести", "desc": "Написать текст"},
    {"word": "Topic", "ru": "Тема", "desc": "О чем ты хочешь узнать"},
    {"word": "Answer", "ru": "Ответ", "desc": "Результат от бота"},

    # 🔹 Системные
    {"word": "Thinking", "ru": "Думаю", "desc": "Бот обрабатывает запрос"},
    {"word": "Error", "ru": "Ошибка", "desc": "Что-то пошло не так"},
    {"word": "Premium", "ru": "Премиум", "desc": "Платные функции"},
]

def format_glossary():
    text = "📚 Glossary | Глоссарий\n\n"

    for item in GLOSSARY:
        text += f"• {item['word']} — {item['ru']}\n"
        text += f"  {item['desc']}\n\n"

    text += "💡 Tip: Use /start to return to menu"
    return text