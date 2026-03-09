"""
Антимат · Антиссылки · Антифлуд.
"""
import time
from collections import defaultdict

from telegram import Update
from telegram.ext import ContextTypes

from config import OWNER_ID, MAX_WARNINGS, FLOOD_LIMIT, FLOOD_WINDOW
from database import Database
from utils import has_profanity, has_links, mention
from keyboards.inline_keyboards import mod_kb

# {(chat_id, user_id): [timestamp, ...]}
_flood: dict[tuple, list[float]] = defaultdict(list)


async def check_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.from_user:
        return

    user = msg.from_user
    cid = msg.chat_id

    # Пропускаем ботов
    if user.is_bot:
        return

    # Пропускаем админов (кэш без API-запросов)
    tg_adm = ctx.bot_data.get("tg_admin_cache", {}).get(cid, set())
    bot_adm = ctx.bot_data.get("bot_admin_cache", {}).get(cid, set())
    if user.id in tg_adm or user.id in bot_adm or user.id == OWNER_ID:
        return

    db: Database = ctx.bot_data["db"]
    s = db.get_settings(cid)
    text = msg.text or msg.caption or ""

    # 1) Мат
    if s["antimat"] and text:
        words = ctx.bot_data.get("banned_words", [])
        if has_profanity(text, words):
            await _violation(update, ctx, "profanity")
            return

    # 2) Ссылки
    if s["antilinks"]:
        if has_links(msg):
            await _violation(update, ctx, "links")
            return

    # 3) Флуд
    if s["antiflood"]:
        if _is_flood(cid, user.id):
            await _violation(update, ctx, "flood")
            return


# ── Помощники ────────────────────────────────────

def _is_flood(cid: int, uid: int) -> bool:
    key = (cid, uid)
    now = time.time()
    _flood[key] = [t for t in _flood[key] if now - t < FLOOD_WINDOW]
    _flood[key].append(now)
    return len(_flood[key]) > FLOOD_LIMIT


_V = {
    "profanity": {
        "reason": "Нецензурная лексика",
        "text": (
            "🟡 <b>Аккуратнее, {name}!</b>\n\n"
            "В чате запрещено использовать нецензурную лексику.\n"
        ),
    },
    "links": {
        "reason": "Запрещённые ссылки",
        "text": (
            "🟡 <b>Внимание, {name}!</b>\n\n"
            "Размещение ссылок запрещено без согласования с админом.\n"
        ),
    },
    "flood": {
        "reason": "Флуд",
        "text": (
            "⏳ <b>Пожалуйста, не спеши, {name}!</b>\n\n"
            "Ты пишешь слишком быстро. Подожди немного.\n"
        ),
    },
}


async def _violation(update: Update, ctx: ContextTypes.DEFAULT_TYPE, kind: str):
    msg = update.message
    user = msg.from_user
    cid = msg.chat_id
    db: Database = ctx.bot_data["db"]
    info = _V[kind]

    # Удаляем сообщение
    try:
        await msg.delete()
        db.inc_stat(cid, "deleted_count")
    except Exception:
        pass

    # Добавляем предупреждение
    count = db.add_warn(user.id, cid, info["reason"])
    db.log(cid, user.id, f"warn_{kind}", f"{count}/{MAX_WARNINGS}")

    if count >= MAX_WARNINGS:
        # Авто-бан
        try:
            await ctx.bot.ban_chat_member(cid, user.id)
            db.inc_stat(cid, "banned_count")
            db.log(cid, user.id, "auto_ban",
                   f"After {MAX_WARNINGS} warnings")
        except Exception:
            pass

        await ctx.bot.send_message(
            cid,
            f"🔨 <b>Пользователь</b> <code>{user.id}</code>"
            f" <b>заблокирован.</b>\n\n"
            f"👤 {mention(user)}\n"
            f"📛 Причина: <i>{info['reason']}</i>\n"
            f"⚠️ Предупреждений: {count}/{MAX_WARNINGS}\n"
            f"🤖 Судья: <b>Страж Порядка</b>",
            parse_mode="HTML",
        )
        db.reset_warns(user.id, cid)
    else:
        body = info["text"].format(name=user.first_name)
        body += (
            f"⚠️ Предупреждение: <b>{count}/{MAX_WARNINGS}</b>\n"
            f"<i>За {MAX_WARNINGS}-м предупреждением последует бан.</i>\n\n"
            f"🗑 <i>[Сообщение удалено]</i>"
        )
        await ctx.bot.send_message(
            cid, body, parse_mode="HTML",
            reply_markup=mod_kb(user.id, msg.message_id),
        )
