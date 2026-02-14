import uuid
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler, ConversationHandler,
    ContextTypes, MessageHandler, filters
)

import texts
import keyboards as kb
from analytics import make_analysis, savings_calc
from config import get_token, APP_VERSION
from db import DB
from utils import (
    Period, clamp_reasonable_kwh, clamp_reasonable_money,
    parse_custom_period, parse_one_or_two_numbers,
    period_last30, period_prev30
)

# ---------- DB ----------
db = DB("data.db")

# ---------- FSM states ----------
(
    S_IDLE,
    S_ONB_CITY, S_ONB_CITY_TEXT, S_ONB_HOME, S_ONB_HEAT, S_ONB_PEOPLE, S_ONB_TARIFF, S_ONB_REMIND,
    S_ANALYZE_PERIOD_CUR, S_ANALYZE_PERIOD_CUSTOM_CUR, S_ANALYZE_VALMODE_CUR, S_ANALYZE_VALUES_CUR,
    S_ANALYZE_HAS_PREV, S_ANALYZE_PERIOD_PREV, S_ANALYZE_PERIOD_CUSTOM_PREV, S_ANALYZE_VALMODE_PREV, S_ANALYZE_VALUES_PREV,
    S_CTX_Q1, S_CTX_Q2, S_CTX_Q3,
    S_SHOW_RESULTS,
    S_SAVINGS_PERIOD, S_SAVINGS_PERIOD_CUSTOM, S_SAVINGS_VALMODE, S_SAVINGS_VALUES, S_SAVINGS_TARIFF,
    S_FEEDBACK_COMMENT
) = range(27)

def _session_id(context: ContextTypes.DEFAULT_TYPE) -> str:
    sid = context.user_data.get("session_id")
    if not sid:
        sid = uuid.uuid4().hex[:12]
        context.user_data["session_id"] = sid
    return sid

def _state_name(state: int) -> str:
    return str(state)

async def log_evt(update: Update, context: ContextTypes.DEFAULT_TYPE, event: str, payload=None, command=None, is_demo=0):
    user_id = update.effective_user.id
    db.log_event(
        user_id=user_id,
        session_id=_session_id(context),
        state=_state_name(context.user_data.get("state", S_IDLE)),
        event_name=event,
        command=command,
        payload=payload,
        is_demo=is_demo,
        app_version=APP_VERSION
    )

def user_profile(user_id: int) -> dict:
    return db.get_user(user_id) or {}

def is_onboarded(profile: dict) -> bool:
    return bool(profile.get("city") and profile.get("home_type") and profile.get("heating") and profile.get("people") is not None)

async def go_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["state"] = S_IDLE
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(texts.MENU_TEXT, reply_markup=kb.kb_menu())
    else:
        await update.message.reply_text(texts.MENU_TEXT, reply_markup=kb.kb_menu())
    return S_IDLE

# ---------- /help, /privacy (вне зависимости от состояния) ----------
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(texts.HELP_TEXT)
    await log_evt(update, context, "command_used", command="/help")

async def cmd_privacy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(texts.PRIVACY_TEXT, reply_markup=kb.kb_privacy_actions())
    await log_evt(update, context, "command_used", command="/privacy")

async def cb_privacy_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = update.effective_user.id
    db.reset_user_data(user_id)
    await q.edit_message_text("Готово: данные сброшены.", reply_markup=kb.kb_menu())
    await log_evt(update, context, "privacy_reset")

# ---------- Entry points ----------
async def start_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    print(f"START: uid={user_id} chat={chat_id} username={update.effective_user.username}")
    db.upsert_user(user_id, chat_id)

    context.user_data["state"] = S_ONB_CITY
    await update.message.reply_text(texts.START_TEXT)
    await update.message.reply_text(texts.ASK_CITY, reply_markup=kb.kb_city())
    await log_evt(update, context, "bot_start", command="/start")
    return S_ONB_CITY

async def analyze_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    db.upsert_user(user_id, chat_id)

    profile = user_profile(user_id)
    if not is_onboarded(profile):
        # мягко уходим в онбординг
        context.user_data["state"] = S_ONB_CITY
        await update.message.reply_text("Сначала короткий онбординг (до 1 минуты).")
        await update.message.reply_text(texts.ASK_CITY, reply_markup=kb.kb_city())
        await log_evt(update, context, "command_used", command="/analyze", payload={"redirect":"onboarding"})
        return S_ONB_CITY

    context.user_data["flow"] = "analyze"
    context.user_data["state"] = S_ANALYZE_PERIOD_CUR
    await update.message.reply_text(texts.ASK_PERIOD_CURRENT, reply_markup=kb.kb_period())
    await log_evt(update, context, "command_used", command="/analyze")
    return S_ANALYZE_PERIOD_CUR

async def savings_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    db.upsert_user(user_id, chat_id)

    profile = user_profile(user_id)
    if not is_onboarded(profile):
        context.user_data["state"] = S_ONB_CITY
        await update.message.reply_text("Сначала короткий онбординг (до 1 минуты).")
        await update.message.reply_text(texts.ASK_CITY, reply_markup=kb.kb_city())
        await log_evt(update, context, "command_used", command="/savings", payload={"redirect":"onboarding"})
        return S_ONB_CITY

    context.user_data["flow"] = "savings"
    context.user_data["state"] = S_SAVINGS_PERIOD
    await update.message.reply_text("Период (второе измерение)?", reply_markup=kb.kb_period())
    await log_evt(update, context, "command_used", command="/savings")
    return S_SAVINGS_PERIOD

async def demo_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await log_evt(update, context, "command_used", command="/demo", is_demo=1)

    # Демонстрация без FSM: просто выводим пример
    msgs = [
        "🎮 Демо: зимний скачок с электроотоплением.",
        "Текущий период: 30 дней, ввод: 980 кВт*ч и 52000 ₸",
        "Предыдущий период: 30 дней, ввод: 720 кВт*ч и 38000 ₸",
        "Контекст: холоднее = да, бойлер = да",
        "Результат: рост ~+36% по кВт*ч, причины: отопление/бойлер, Top-3: таймер, бойлер 55–60°C, уплотнение окон."
    ]
    for m in msgs:
        await update.message.reply_text(m)
    await update.message.reply_text(texts.MENU_TEXT, reply_markup=kb.kb_menu())
    return ConversationHandler.END

async def feedback_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["state"] = S_FEEDBACK_COMMENT
    await update.message.reply_text(texts.FEEDBACK_ASK, reply_markup=kb.kb_feedback_stars())
    await log_evt(update, context, "command_used", command="/feedback")
    return S_FEEDBACK_COMMENT

# ---------- Menu callbacks ----------
async def cb_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data

    if data == "menu:privacy":
        await q.edit_message_text(texts.PRIVACY_TEXT, reply_markup=kb.kb_privacy_actions())
        return S_IDLE

    if data == "menu:analyze":
        # имитируем /analyze
        context.user_data["state"] = S_ANALYZE_PERIOD_CUR
        await q.edit_message_text(texts.ASK_PERIOD_CURRENT, reply_markup=kb.kb_period())
        return S_ANALYZE_PERIOD_CUR

    if data == "menu:savings":
        context.user_data["state"] = S_SAVINGS_PERIOD
        await q.edit_message_text("Период (второе измерение)?", reply_markup=kb.kb_period())
        return S_SAVINGS_PERIOD

    if data == "menu:demo":
        await q.edit_message_text("Запустите /demo (демо отправляется сообщениями).", reply_markup=kb.kb_menu())
        return S_IDLE

    if data == "menu:feedback":
        context.user_data["state"] = S_FEEDBACK_COMMENT
        await q.edit_message_text(texts.FEEDBACK_ASK, reply_markup=kb.kb_feedback_stars())
        return S_FEEDBACK_COMMENT

    return S_IDLE

# ---------- Navigation callbacks ----------
async def cb_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data

    if data == "nav:menu":
        return await go_menu(update, context)

    if data == "nav:analyze":
        # быстрый старт нового анализа (если онбординг пройден)
        context.user_data["state"] = S_ANALYZE_PERIOD_CUR
        await q.edit_message_text(texts.ASK_PERIOD_CURRENT, reply_markup=kb.kb_period())
        return S_ANALYZE_PERIOD_CUR

    if data == "nav:savings":
        context.user_data["state"] = S_SAVINGS_PERIOD
        await q.edit_message_text("Период (второе измерение)?", reply_markup=kb.kb_period())
        return S_SAVINGS_PERIOD

    if data == "nav:back":
        # минималистичный “назад”: возвращаем в меню, чтобы не усложнять MVP
        # (можно улучшить, сохраняя стек состояний)
        return await go_menu(update, context)

    return S_IDLE

# ---------- Onboarding callbacks & text ----------
async def cb_onb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    user_id = update.effective_user.id

    if data.startswith("onb:city:"):
        city = data.split(":")[-1]
        if city == "other":
            context.user_data["state"] = S_ONB_CITY_TEXT
            await q.edit_message_text("Введите город текстом (2–40 символов).", reply_markup=kb.kb_back_menu())
            return S_ONB_CITY_TEXT
        db.set_user_profile(user_id, city=city)
        context.user_data["state"] = S_ONB_HOME
        await q.edit_message_text(texts.ASK_HOME, reply_markup=kb.kb_home())
        return S_ONB_HOME

    if data.startswith("onb:home:"):
        home = data.split(":")[-1]
        db.set_user_profile(user_id, home_type=home)
        context.user_data["state"] = S_ONB_HEAT
        await q.edit_message_text(texts.ASK_HEATING, reply_markup=kb.kb_heating())
        return S_ONB_HEAT

    if data.startswith("onb:heat:"):
        heat = data.split(":")[-1]
        db.set_user_profile(user_id, heating=heat)
        context.user_data["state"] = S_ONB_PEOPLE
        await q.edit_message_text(texts.ASK_PEOPLE, reply_markup=kb.kb_people())
        return S_ONB_PEOPLE

    if data.startswith("onb:people:"):
        ppl = data.split(":")[-1]
        db.set_user_profile(user_id, people=ppl)
        context.user_data["state"] = S_ONB_TARIFF
        await q.edit_message_text(texts.ASK_KNOWS_TARIFF, reply_markup=kb.kb_yes_no("onb:tariff"))
        return S_ONB_TARIFF

    if data.startswith("onb:tariff:"):
        ans = data.split(":")[-1]
        db.set_user_profile(user_id, knows_tariff=1 if ans == "yes" else 0)
        context.user_data["state"] = S_ONB_REMIND
        await q.edit_message_text(texts.ASK_REMINDERS, reply_markup=kb.kb_yes_no("onb:remind"))
        return S_ONB_REMIND

    if data.startswith("onb:remind:"):
        ans = data.split(":")[-1]
        db.set_user_profile(user_id, reminders=1 if ans == "yes" else 0)
        context.user_data["state"] = S_IDLE
        await q.edit_message_text("Готово ✅", reply_markup=kb.kb_menu())
        await log_evt(update, context, "onboarding_done")
        return S_IDLE

    return S_IDLE

async def onb_city_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    txt = (update.message.text or "").strip()
    if len(txt) < 2 or len(txt) > 40:
        await update.message.reply_text("Похоже на некорректный ввод. Напишите город (2–40 символов).")
        return S_ONB_CITY_TEXT
    db.set_user_profile(user_id, city=txt)
    context.user_data["state"] = S_ONB_HOME
    await update.message.reply_text(texts.ASK_HOME, reply_markup=kb.kb_home())
    return S_ONB_HOME

# ---------- Period selection (analyze & savings) ----------
def _store_period(context: ContextTypes.DEFAULT_TYPE, key: str, p: Period):
    context.user_data[key] = {"start": p.start.isoformat(), "end": p.end.isoformat(), "days": p.days}

async def cb_period(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data

    state = context.user_data.get("state")

    if data == "period:last30":
        p = period_last30()
    elif data == "period:prev30":
        p = period_prev30()
    elif data == "period:custom":
        # переходим в ожидание текстового периода
        if state in (S_ANALYZE_PERIOD_CUR,):
            context.user_data["state"] = S_ANALYZE_PERIOD_CUSTOM_CUR
            await q.edit_message_text(texts.ASK_PERIOD_CUSTOM, reply_markup=kb.kb_back_menu())
            return S_ANALYZE_PERIOD_CUSTOM_CUR
        if state in (S_ANALYZE_PERIOD_PREV,):
            context.user_data["state"] = S_ANALYZE_PERIOD_CUSTOM_PREV
            await q.edit_message_text(texts.ASK_PERIOD_CUSTOM, reply_markup=kb.kb_back_menu())
            return S_ANALYZE_PERIOD_CUSTOM_PREV
        if state in (S_SAVINGS_PERIOD,):
            context.user_data["state"] = S_SAVINGS_PERIOD_CUSTOM
            await q.edit_message_text(texts.ASK_PERIOD_CUSTOM, reply_markup=kb.kb_back_menu())
            return S_SAVINGS_PERIOD_CUSTOM
        return state
    else:
        return state

    # сохранить период в зависимости от текущего шага
    if state == S_ANALYZE_PERIOD_CUR:
        _store_period(context, "cur_period", p)
        context.user_data["state"] = S_ANALYZE_VALMODE_CUR
        await q.edit_message_text(texts.ASK_VALUE_MODE, reply_markup=kb.kb_value_mode())
        return S_ANALYZE_VALMODE_CUR

    if state == S_ANALYZE_PERIOD_PREV:
        _store_period(context, "prev_period", p)
        context.user_data["state"] = S_ANALYZE_VALMODE_PREV
        await q.edit_message_text(texts.ASK_VALUE_MODE, reply_markup=kb.kb_value_mode())
        return S_ANALYZE_VALMODE_PREV

    if state == S_SAVINGS_PERIOD:
        _store_period(context, "second_period", p)
        context.user_data["state"] = S_SAVINGS_VALMODE
        await q.edit_message_text(texts.ASK_VALUE_MODE, reply_markup=kb.kb_value_mode())
        return S_SAVINGS_VALMODE

    return state

async def period_custom_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("state")
    p = parse_custom_period(update.message.text or "")
    if not p:
        await update.message.reply_text("Не понял формат. Пример: с 01.01.2026 по 31.01.2026")
        return state

    if state == S_ANALYZE_PERIOD_CUSTOM_CUR:
        _store_period(context, "cur_period", p)
        context.user_data["state"] = S_ANALYZE_VALMODE_CUR
        await update.message.reply_text(texts.ASK_VALUE_MODE, reply_markup=kb.kb_value_mode())
        return S_ANALYZE_VALMODE_CUR

    if state == S_ANALYZE_PERIOD_CUSTOM_PREV:
        _store_period(context, "prev_period", p)
        context.user_data["state"] = S_ANALYZE_VALMODE_PREV
        await update.message.reply_text(texts.ASK_VALUE_MODE, reply_markup=kb.kb_value_mode())
        return S_ANALYZE_VALMODE_PREV

    if state == S_SAVINGS_PERIOD_CUSTOM:
        _store_period(context, "second_period", p)
        context.user_data["state"] = S_SAVINGS_VALMODE
        await update.message.reply_text(texts.ASK_VALUE_MODE, reply_markup=kb.kb_value_mode())
        return S_SAVINGS_VALMODE

    return state

# ---------- Value mode ----------
async def cb_valmode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    mode = q.data.split(":")[-1]
    state = context.user_data.get("state")

    context.user_data["val_mode"] = mode

    if state == S_ANALYZE_VALMODE_CUR:
        context.user_data["state"] = S_ANALYZE_VALUES_CUR
        await q.edit_message_text(texts.ASK_ENTER_VALUES, reply_markup=kb.kb_back_menu())
        return S_ANALYZE_VALUES_CUR

    if state == S_ANALYZE_VALMODE_PREV:
        context.user_data["state"] = S_ANALYZE_VALUES_PREV
        await q.edit_message_text(texts.ASK_ENTER_VALUES, reply_markup=kb.kb_back_menu())
        return S_ANALYZE_VALUES_PREV

    if state == S_SAVINGS_VALMODE:
        context.user_data["state"] = S_SAVINGS_VALUES
        await q.edit_message_text(texts.ASK_ENTER_VALUES, reply_markup=kb.kb_back_menu())
        return S_SAVINGS_VALUES

    return state

def _normalize_values(mode: str, a: float, b_opt: float | None):
    """
    Возвращает (kwh, money) в зависимости от режима.
    """
    if mode == "kwh":
        return a, None
    if mode == "money":
        return None, a
    # both
    if b_opt is None:
        return None, None
    return a, b_opt

async def values_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("state")
    mode = context.user_data.get("val_mode", "both")

    parsed = parse_one_or_two_numbers(update.message.text or "")
    if not parsed:
        await update.message.reply_text("Нужны числа. Примеры: 250 или 12000 или 900 45000")
        return state

    a, b = parsed
    kwh, money = _normalize_values(mode, a, b)
    if mode == "both" and (kwh is None or money is None):
        await update.message.reply_text("Для режима «оба» введите два числа: кВт*ч и сумму (₸).")
        return state

    if kwh is not None:
        kwh, warn = clamp_reasonable_kwh(kwh)
        if warn:
            await update.message.reply_text(warn)

    if money is not None:
        money, warn = clamp_reasonable_money(money)
        if warn:
            await update.message.reply_text(warn)

    # Сохраняем в user_data
    if state == S_ANALYZE_VALUES_CUR:
        context.user_data["cur_values"] = {"kwh": kwh, "money": money}
        context.user_data["state"] = S_ANALYZE_HAS_PREV
        await update.message.reply_text(texts.ASK_PERIOD_PREV, reply_markup=kb.kb_yes_no("prev"))
        return S_ANALYZE_HAS_PREV

    if state == S_ANALYZE_VALUES_PREV:
        context.user_data["prev_values"] = {"kwh": kwh, "money": money}
        # контекстные вопросы
        context.user_data["state"] = S_CTX_Q1
        await update.message.reply_text(texts.CTX_Q1, reply_markup=kb.kb_yes_no("ctx:cold"))
        return S_CTX_Q1

    if state == S_SAVINGS_VALUES:
        context.user_data["second_values"] = {"kwh": kwh, "money": money}
        # если есть kWh и пользователь знает тариф — спросим тариф для денег
        prof = user_profile(update.effective_user.id)
        if prof.get("knows_tariff") == 1 and kwh is not None:
            context.user_data["state"] = S_SAVINGS_TARIFF
            await update.message.reply_text("Введите тариф ₸ за кВт*ч (например: 25). Или напишите 0, чтобы пропустить.")
            return S_SAVINGS_TARIFF

        # иначе сразу считаем
        return await do_savings(update, context)

    return state

# ---------- Prev period yes/no ----------
async def cb_prev_yesno(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    ans = q.data.split(":")[-1]
    if ans == "no":
        # Нет предыдущих данных -> всё равно задаём контекст и считаем без сравнения
        context.user_data["prev_values"] = {"kwh": None, "money": None}
        context.user_data["state"] = S_CTX_Q1
        await q.edit_message_text(texts.CTX_Q1, reply_markup=kb.kb_yes_no("ctx:cold"))
        return S_CTX_Q1

    # Да -> спросим период предыдущий
    context.user_data["state"] = S_ANALYZE_PERIOD_PREV
    await q.edit_message_text("Период (предыдущий)?", reply_markup=kb.kb_period())
    return S_ANALYZE_PERIOD_PREV

# ---------- Context yes/no ----------
async def cb_ctx(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data

    # ctx:cold:yes/no, ctx:boiler:yes/no, ctx:new:yes/no
    parts = data.split(":")
    key = parts[1]
    ans = parts[2]
    val = True if ans == "yes" else False

    ctx = context.user_data.get("ctx", {})
    if key == "cold":
        ctx["cold"] = val
        context.user_data["ctx"] = ctx
        context.user_data["state"] = S_CTX_Q2
        await q.edit_message_text(texts.CTX_Q2, reply_markup=kb.kb_yes_no("ctx:boiler"))
        return S_CTX_Q2

    if key == "boiler":
        ctx["boiler"] = val
        context.user_data["ctx"] = ctx
        context.user_data["state"] = S_CTX_Q3
        await q.edit_message_text(texts.CTX_Q3, reply_markup=kb.kb_yes_no("ctx:new"))
        return S_CTX_Q3

    if key == "new":
        ctx["new_appliance"] = val
        # Переходим к анализу
        return await do_analysis_from_context(update, context)

    return S_SHOW_RESULTS

async def do_analysis_from_context(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user_id = update.effective_user.id
    prof = user_profile(user_id)

    cur_p = context.user_data.get("cur_period")
    cur_v = context.user_data.get("cur_values", {})
    prev_p = context.user_data.get("prev_period")
    prev_v = context.user_data.get("prev_values", {})
    ctx = context.user_data.get("ctx", {})

    # Сохраним в БД (для MVP — фиксируем как current/prev)
    if cur_p:
        db.save_bill(
            user_id, "current",
            cur_p["start"], cur_p["end"], cur_p["days"],
            cur_v.get("kwh"), cur_v.get("money"), None
        )
    if prev_p and prev_v and (prev_v.get("kwh") is not None or prev_v.get("money") is not None):
        db.save_bill(
            user_id, "prev",
            prev_p["start"], prev_p["end"], prev_p["days"],
            prev_v.get("kwh"), prev_v.get("money"), None
        )

    res = make_analysis(
        profile=prof,
        ctx=ctx,
        now_kwh=cur_v.get("kwh"), prev_kwh=prev_v.get("kwh"),
        now_money=cur_v.get("money"), prev_money=prev_v.get("money")
    )

    # Сформируем короткий ответ
    lines = [res.headline, ""]
    lines.append("Вероятные причины:")
    for i, r in enumerate(res.reasons, 1):
        lines.append(f"{i}) {r}")

    lines.append("")
    lines.append("Top-3 действия на 1–2 дня:")
    for i, (title, why, how) in enumerate(res.actions, 1):
        lines.append(f"{i}) {title}\n— {why}\n— {how}")

    lines.append(texts.ANALYSIS_DISCLAIMER)

    context.user_data["last_top3"] = res.actions  # для отметок "сделал"
    context.user_data["state"] = S_SHOW_RESULTS

    await q.edit_message_text("\n".join(lines), reply_markup=kb.kb_actions_followup())
    await log_evt(update, context, "analysis_generated", payload=res.meta)
    return S_SHOW_RESULTS

# ---------- Mark action done / jump to savings ----------
async def cb_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    user_id = update.effective_user.id

    if data.startswith("actdone:"):
        idx = int(data.split(":")[-1]) - 1
        top3 = context.user_data.get("last_top3") or []
        if 0 <= idx < len(top3):
            title = top3[idx][0]
            db.add_action_done(user_id, f"top3_{idx+1}:{title}")
            await q.edit_message_text(f"Отмечено ✅: {title}\n\n{texts.MENU_TEXT}", reply_markup=kb.kb_menu())
            await log_evt(update, context, "action_marked_done", payload={"idx": idx+1, "title": title})
            return S_IDLE

    return S_SHOW_RESULTS

# ---------- Savings tariff + calc ----------
async def savings_tariff_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = (update.message.text or "").strip().replace(",", ".")
    try:
        tariff = float(txt)
        if tariff <= 0:
            tariff = None
    except ValueError:
        await update.message.reply_text("Введите число, например 25. Или 0, чтобы пропустить.")
        return S_SAVINGS_TARIFF

    context.user_data["tariff"] = tariff
    return await do_savings(update, context)

async def do_savings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    prof = user_profile(user_id)

    current = db.get_latest_bill(user_id, "current")
    if not current or current.get("kwh") is None:
        await update.message.reply_text(
            "Для savings нужен базовый период с кВт*ч. Сначала сделайте /analyze и введите кВт*ч.",
            reply_markup=kb.kb_menu()
        )
        return S_IDLE

    second_p = context.user_data.get("second_period")
    second_v = context.user_data.get("second_values", {})
    if not second_p or second_v.get("kwh") is None:
        await update.message.reply_text("Для savings нужен период и кВт*ч.")
        return S_IDLE

    tariff = context.user_data.get("tariff")
    # сохраним second
    db.save_bill(
        user_id, "second",
        second_p["start"], second_p["end"], second_p["days"],
        second_v.get("kwh"), second_v.get("money"), tariff
    )

    out = savings_calc(
        before_kwh=current["kwh"], before_days=int(current["days"]),
        after_kwh=second_v["kwh"], after_days=int(second_p["days"]),
        tariff=tariff
    )

    if not out["ok"]:
        await update.message.reply_text(out["msg"], reply_markup=kb.kb_menu())
        return S_IDLE

    pct = out["pct"]
    delta_kwh = out["delta_kwh"]
    msg_lines = []

    if pct > 2.0:
        msg_lines.append(f"✅ Экономия есть: примерно −{pct:.0f}%")
        msg_lines.append(f"≈ −{delta_kwh:.0f} кВт*ч за период")
    elif pct >= -2.0:
        msg_lines.append("➖ Почти без изменений (±2%).")
        msg_lines.append("Обычно это значит: эффект ещё не проявился или главная причина другая.")
    else:
        msg_lines.append(f"⚠️ Стало хуже: примерно +{abs(pct):.0f}%")
        msg_lines.append("Частые причины: похолодало/обогрев дольше, добавился прибор, перерасчёт.")

    if out["delta_money"] is not None:
        msg_lines.append(f"≈ {out['delta_money']:.0f} ₸ за период (по вашему тарифу)")

    msg_lines.append(f"\nДля самопроверки: было {out['before_per_day']:.1f} кВт*ч/день → стало {out['after_per_day']:.1f} кВт*ч/день.")
    await update.message.reply_text("\n".join(msg_lines), reply_markup=kb.kb_menu())
    await log_evt(update, context, "savings_calculated", payload={"pct": pct, "delta_kwh": delta_kwh, "tariff_used": tariff is not None})
    return S_IDLE

# ---------- Feedback ----------
async def cb_feedback_star(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    star = q.data.split(":")[-1]
    context.user_data["feedback_star"] = int(star)
    await q.edit_message_text(f"Оценка: {star}/5. Напишите 1–2 предложения (или '-' чтобы без комментария).")
    return S_FEEDBACK_COMMENT

async def feedback_comment_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    comment = (update.message.text or "").strip()
    star = context.user_data.get("feedback_star")
    if comment == "-":
        comment = ""
    await update.message.reply_text(texts.THANKS, reply_markup=kb.kb_menu())
    await log_evt(update, context, "feedback_submitted", payload={"star": star, "comment": comment[:400]})
    return S_IDLE

# ---------- Build app ----------
def build_app() -> Application:
    app = Application.builder().token(get_token()).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start_entry),
            CommandHandler("analyze", analyze_entry),
            CommandHandler("savings", savings_entry),
            CommandHandler("demo", demo_entry),
            CommandHandler("feedback", feedback_entry),
        ],
        states={
            S_IDLE: [
                CallbackQueryHandler(cb_menu, pattern=r"^menu:"),
                CallbackQueryHandler(cb_nav, pattern=r"^nav:"),
                CallbackQueryHandler(cb_privacy_reset, pattern=r"^privacy:reset$"),
            ],

            # Onboarding
            S_ONB_CITY: [CallbackQueryHandler(cb_onb, pattern=r"^onb:city:")],
            S_ONB_CITY_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, onb_city_text)],
            S_ONB_HOME: [CallbackQueryHandler(cb_onb, pattern=r"^onb:home:")],
            S_ONB_HEAT: [CallbackQueryHandler(cb_onb, pattern=r"^onb:heat:")],
            S_ONB_PEOPLE: [CallbackQueryHandler(cb_onb, pattern=r"^onb:people:")],
            S_ONB_TARIFF: [CallbackQueryHandler(cb_onb, pattern=r"^onb:tariff:")],
            S_ONB_REMIND: [CallbackQueryHandler(cb_onb, pattern=r"^onb:remind:")],

            # Analyze periods & values
            S_ANALYZE_PERIOD_CUR: [CallbackQueryHandler(cb_period, pattern=r"^period:")],
            S_ANALYZE_PERIOD_CUSTOM_CUR: [MessageHandler(filters.TEXT & ~filters.COMMAND, period_custom_text)],
            S_ANALYZE_VALMODE_CUR: [CallbackQueryHandler(cb_valmode, pattern=r"^valmode:")],
            S_ANALYZE_VALUES_CUR: [MessageHandler(filters.TEXT & ~filters.COMMAND, values_text)],

            S_ANALYZE_HAS_PREV: [CallbackQueryHandler(cb_prev_yesno, pattern=r"^prev:(yes|no)$")],
            S_ANALYZE_PERIOD_PREV: [CallbackQueryHandler(cb_period, pattern=r"^period:")],
            S_ANALYZE_PERIOD_CUSTOM_PREV: [MessageHandler(filters.TEXT & ~filters.COMMAND, period_custom_text)],
            S_ANALYZE_VALMODE_PREV: [CallbackQueryHandler(cb_valmode, pattern=r"^valmode:")],
            S_ANALYZE_VALUES_PREV: [MessageHandler(filters.TEXT & ~filters.COMMAND, values_text)],

            # Context
            S_CTX_Q1: [CallbackQueryHandler(cb_ctx, pattern=r"^ctx:cold:(yes|no)$")],
            S_CTX_Q2: [CallbackQueryHandler(cb_ctx, pattern=r"^ctx:boiler:(yes|no)$")],
            S_CTX_Q3: [CallbackQueryHandler(cb_ctx, pattern=r"^ctx:new:(yes|no)$")],

            # Result actions
            S_SHOW_RESULTS: [
                CallbackQueryHandler(cb_actions, pattern=r"^actdone:"),
                CallbackQueryHandler(cb_nav, pattern=r"^nav:"),
            ],

            # Savings
            S_SAVINGS_PERIOD: [CallbackQueryHandler(cb_period, pattern=r"^period:")],
            S_SAVINGS_PERIOD_CUSTOM: [MessageHandler(filters.TEXT & ~filters.COMMAND, period_custom_text)],
            S_SAVINGS_VALMODE: [CallbackQueryHandler(cb_valmode, pattern=r"^valmode:")],
            S_SAVINGS_VALUES: [MessageHandler(filters.TEXT & ~filters.COMMAND, values_text)],
            S_SAVINGS_TARIFF: [MessageHandler(filters.TEXT & ~filters.COMMAND, savings_tariff_text)],

            # Feedback
            S_FEEDBACK_COMMENT: [
                CallbackQueryHandler(cb_feedback_star, pattern=r"^fb:\d$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, feedback_comment_text),
            ],
        },
        fallbacks=[
            CommandHandler("help", cmd_help),
            CommandHandler("privacy", cmd_privacy),
            CallbackQueryHandler(cb_nav, pattern=r"^nav:"),
            CallbackQueryHandler(cb_privacy_reset, pattern=r"^privacy:reset$"),
        ],
        allow_reentry=True,
        per_message=False,  # важно для callback-кнопок в ConversationHandler, чтобы не ловить warning
    )

    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("privacy", cmd_privacy))
    app.add_handler(conv)

    app.add_handler(CallbackQueryHandler(cb_privacy_reset, pattern=r"^privacy:reset$"))

    return app

def main():
    app = build_app()
    print("Bot started.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
