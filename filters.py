"""
Вспомогательные проверки прав.
Используются как обычные async-функции внутри хэндлеров.
"""
from telegram import Update
from telegram.ext import ContextTypes
from config import OWNER_ID


async def is_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat:
        return False
    if user.id == OWNER_ID:
        return True

    # Кэш Telegram-админов (обновляется раз в 5 мин)
    tg = ctx.bot_data.get("tg_admin_cache", {}).get(chat.id, set())
    if user.id in tg:
        return True

    # Кэш бот-админов
    bot = ctx.bot_data.get("bot_admin_cache", {}).get(chat.id, set())
    if user.id in bot:
        return True

    # Фолбэк — прямой запрос к API
    try:
        m = await ctx.bot.get_chat_member(chat.id, user.id)
        return m.status in ("administrator", "creator")
    except Exception:
        return False
