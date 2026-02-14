from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def kb_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔎 Анализ", callback_data="menu:analyze")],
        [InlineKeyboardButton("📊 Savings (до/после)", callback_data="menu:savings")],
        [InlineKeyboardButton("🎮 Демо", callback_data="menu:demo")],
        [InlineKeyboardButton("🔒 Privacy", callback_data="menu:privacy")],
        [InlineKeyboardButton("⭐ Feedback", callback_data="menu:feedback")],
    ])

def kb_back_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Назад", callback_data="nav:back"),
         InlineKeyboardButton("🏁 В меню", callback_data="nav:menu")]
    ])

def kb_city():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Алматы", callback_data="onb:city:almaty"),
         InlineKeyboardButton("Астана", callback_data="onb:city:astana")],
        [InlineKeyboardButton("Шымкент", callback_data="onb:city:shymkent"),
         InlineKeyboardButton("Караганда", callback_data="onb:city:karaganda")],
        [InlineKeyboardButton("Другое (ввести текстом)", callback_data="onb:city:other")],
        [InlineKeyboardButton("🏁 В меню", callback_data="nav:menu")]
    ])

def kb_home():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Квартира", callback_data="onb:home:flat"),
         InlineKeyboardButton("Дом", callback_data="onb:home:house")],
        [InlineKeyboardButton("Не знаю/смешано", callback_data="onb:home:unknown")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="nav:back"),
         InlineKeyboardButton("🏁 В меню", callback_data="nav:menu")]
    ])

def kb_heating():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Центральное", callback_data="onb:heat:central"),
         InlineKeyboardButton("Газ", callback_data="onb:heat:gas")],
        [InlineKeyboardButton("Электрическое", callback_data="onb:heat:electric"),
         InlineKeyboardButton("Не знаю", callback_data="onb:heat:unknown")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="nav:back"),
         InlineKeyboardButton("🏁 В меню", callback_data="nav:menu")]
    ])

def kb_people():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1", callback_data="onb:people:1"),
         InlineKeyboardButton("2", callback_data="onb:people:2")],
        [InlineKeyboardButton("3–4", callback_data="onb:people:3-4"),
         InlineKeyboardButton("5+", callback_data="onb:people:5+")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="nav:back"),
         InlineKeyboardButton("🏁 В меню", callback_data="nav:menu")]
    ])

def kb_yes_no(prefix: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Да", callback_data=f"{prefix}:yes"),
         InlineKeyboardButton("Нет", callback_data=f"{prefix}:no")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="nav:back"),
         InlineKeyboardButton("🏁 В меню", callback_data="nav:menu")]
    ])

def kb_period():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Последние 30 дней", callback_data="period:last30"),
         InlineKeyboardButton("Предыдущие 30 дней", callback_data="period:prev30")],
        [InlineKeyboardButton("Выбрать даты", callback_data="period:custom")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="nav:back"),
         InlineKeyboardButton("🏁 В меню", callback_data="nav:menu")]
    ])

def kb_value_mode():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Ввести кВт*ч", callback_data="valmode:kwh"),
         InlineKeyboardButton("Ввести сумму (₸)", callback_data="valmode:money")],
        [InlineKeyboardButton("Ввести оба", callback_data="valmode:both")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="nav:back"),
         InlineKeyboardButton("🏁 В меню", callback_data="nav:menu")]
    ])

def kb_privacy_actions():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🧹 Сбросить данные", callback_data="privacy:reset")],
        [InlineKeyboardButton("🏁 В меню", callback_data="nav:menu")]
    ])

def kb_actions_followup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Я сделал(а) действие 1", callback_data="actdone:1")],
        [InlineKeyboardButton("✅ Я сделал(а) действие 2", callback_data="actdone:2")],
        [InlineKeyboardButton("✅ Я сделал(а) действие 3", callback_data="actdone:3")],
        [InlineKeyboardButton("📊 Посчитать экономию", callback_data="nav:savings")],
        [InlineKeyboardButton("🔁 Новый анализ", callback_data="nav:analyze")],
        [InlineKeyboardButton("🏁 В меню", callback_data="nav:menu")]
    ])

def kb_feedback_stars():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1", callback_data="fb:1"),
         InlineKeyboardButton("2", callback_data="fb:2"),
         InlineKeyboardButton("3", callback_data="fb:3"),
         InlineKeyboardButton("4", callback_data="fb:4"),
         InlineKeyboardButton("5", callback_data="fb:5")],
        [InlineKeyboardButton("🏁 В меню", callback_data="nav:menu")]
    ])
