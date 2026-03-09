"""
Команды модерации, настройки, callback-обработчики.
"""
from datetime import datetime, timedelta

from telegram import Update, ChatPermissions
from telegram.ext import ContextTypes

from config import OWNER_ID, MAX_WARNINGS, MUTE_DURATION
from database import Database
from filters import is_admin
from utils import mention
from keyboards.inline_keyboards import (
    mod_kb, done_kb,
    settings_main_kb, filter_kb, back_kb,
)

MUTE_PERM = ChatPermissions(can_send_messages=False)
UNMUTE_PERM = ChatPermissions(
    can_send_messages=True,
    can_send_other_messages=True,
    can_add_web_page_previews=True,
    can_send_polls=True,
    can_invite_users=True,
)


# ═══════════════════════════════════════════════
#  КОМАНДЫ
# ═══════════════════════════════════════════════

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
    await update.message.reply_text(
        f"🤖 <b>Привет, {update.effective_user.first_name}!</b>\n"
        f"Я — <b>Страж Порядка</b>.\n\n"
        f"🛡️ Я слежу за чистотой в чатах.\n"
        f"Добавь меня в группу и дай права админа,\n"
        f"затем используй /settings для настройки.\n\n"
        f"📋 <b>Возможности:</b>\n"
        f"  • 🔐 Капча при входе\n"
        f"  • 🤬 Фильтр мата\n"
        f"  • 🔗 Блокировка ссылок\n"
        f"  • ⏳ Антифлуд\n"
        f"  • ⚠️ Система предупреждений\n"
        f"  • 📊 Статистика\n\n"
        f"ℹ️ /help — список команд",
        parse_mode="HTML",
    )


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 <b>КОМАНДЫ БОТА</b>\n\n"
        "<b>👮 Модерация</b> (ответом на сообщение):\n"
        "<code>/warn [причина]</code> — предупредить\n"
        "<code>/ban  [причина]</code> — забанить\n"
        "<code>/mute [минуты]</code>  — заглушить\n"
        "<code>/unmute</code>          — снять мьют\n"
        "<code>/unban ID</code>        — разбанить\n\n"
        "<b>⚙️ Настройки:</b>\n"
        "<code>/settings</code>  — панель управления\n"
        "<code>/rules</code>     — правила чата\n"
        "<code>/setrules</code>  — установить правила\n"
        "<code>/addadmin</code>  — добавить админа\n"
        "<code>/deladmin</code>  — удалить админа\n\n"
        "<b>📊 Информация:</b>\n"
        "<code>/stats</code> — статистика чата\n",
        parse_mode="HTML",
    )


async def cmd_rules(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from handlers.welcome import DEFAULT_RULES

    db: Database = ctx.bot_data["db"]
    s = db.get_settings(update.effective_chat.id)
    await update.message.reply_text(
        s.get("rules") or DEFAULT_RULES,
        parse_mode="HTML",
    )


async def cmd_setrules(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, ctx):
        return
    text = update.message.text.split(None, 1)
    if len(text) < 2:
        await update.message.reply_text(
            "⚠️ <code>/setrules текст правил</code>", parse_mode="HTML"
        )
        return
    db: Database = ctx.bot_data["db"]
    db.set_rules(update.effective_chat.id, text[1])
    await update.message.reply_text(
        "✅ <b>Правила обновлены!</b>", parse_mode="HTML"
    )


# ── /warn ────────────────────────────────────────

async def cmd_warn(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, ctx):
        return
    if not update.message.reply_to_message:
        await update.message.reply_text(
            "⚠️ Ответьте на сообщение: <code>/warn [причина]</code>",
            parse_mode="HTML",
        )
        return

    target = update.message.reply_to_message.from_user
    cid = update.effective_chat.id
    db: Database = ctx.bot_data["db"]
    reason = " ".join(ctx.args) if ctx.args else "Нарушение правил"
    count = db.add_warn(target.id, cid, reason)
    db.log(cid, target.id, "manual_warn",
           f"by {update.effective_user.id}: {reason}")

    if count >= MAX_WARNINGS:
        try:
            await ctx.bot.ban_chat_member(cid, target.id)
            db.inc_stat(cid, "banned_count")
        except Exception:
            pass
        db.reset_warns(target.id, cid)
        text = (
            f"🔨 <b>Пользователь заблокирован!</b>\n\n"
            f"👤 {mention(target)} (<code>{target.id}</code>)\n"
            f"📛 Причина: <i>{reason}</i>\n"
            f"⚠️ Предупреждений: <b>{count}/{MAX_WARNINGS}</b>\n"
            f"🤖 Судья: <b>Страж Порядка</b>"
        )
    else:
        text = (
            f"⚠️ <b>Предупреждение!</b>\n\n"
            f"👤 {mention(target)} (<code>{target.id}</code>)\n"
            f"📛 Причина: <i>{reason}</i>\n"
            f"⚠️ Счёт: <b>{count}/{MAX_WARNINGS}</b>\n"
            f"👮 Выдал: {mention(update.effective_user)}"
        )
    await update.message.reply_text(text, parse_mode="HTML")


# ── /ban ─────────────────────────────────────────

async def cmd_ban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, ctx):
        return
    if not update.message.reply_to_message:
        await update.message.reply_text(
            "⚠️ Ответьте на сообщение: <code>/ban [причина]</code>",
            parse_mode="HTML",
        )
        return

    target = update.message.reply_to_message.from_user
    cid = update.effective_chat.id
    db: Database = ctx.bot_data["db"]
    reason = " ".join(ctx.args) if ctx.args else "Решение администратора"

    try:
        await ctx.bot.ban_chat_member(cid, target.id)
        db.inc_stat(cid, "banned_count")
        db.reset_warns(target.id, cid)
        db.log(cid, target.id, "ban",
               f"by {update.effective_user.id}: {reason}")

        await update.message.reply_text(
            f"🔨 <b>Пользователь заблокирован!</b>\n\n"
            f"👤 {mention(target)} (<code>{target.id}</code>)\n"
            f"📛 Причина: <i>{reason}</i>\n"
            f"👮 Забанил: {mention(update.effective_user)}\n"
            f"🤖 Судья: <b>Страж Порядка</b>",
            parse_mode="HTML",
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ Ошибка: <code>{e}</code>", parse_mode="HTML"
        )


# ── /unban ───────────────────────────────────────

async def cmd_unban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, ctx):
        return
    if not ctx.args:
        await update.message.reply_text(
            "⚠️ <code>/unban user_id</code>", parse_mode="HTML"
        )
        return
    try:
        tid = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("❌ Укажите числовой ID.")
        return

    cid = update.effective_chat.id
    db: Database = ctx.bot_data["db"]
    try:
        await ctx.bot.unban_chat_member(cid, tid)
        db.reset_warns(tid, cid)
        db.log(cid, tid, "unban", f"by {update.effective_user.id}")
        await update.message.reply_text(
            f"✅ <b>Разблокирован!</b>\n🆔 <code>{tid}</code>\n"
            f"👮 {mention(update.effective_user)}",
            parse_mode="HTML",
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ <code>{e}</code>", parse_mode="HTML"
        )


# ── /mute, /unmute ───────────────────────────────

async def cmd_mute(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, ctx):
        return
    if not update.message.reply_to_message:
        await update.message.reply_text(
            "⚠️ Ответьте на сообщение: <code>/mute [минуты]</code>",
            parse_mode="HTML",
        )
        return

    target = update.message.reply_to_message.from_user
    minutes = 60
    if ctx.args:
        try:
            minutes = int(ctx.args[0])
        except ValueError:
            pass

    until = datetime.now() + timedelta(minutes=minutes)
    cid = update.effective_chat.id
    try:
        await ctx.bot.restrict_chat_member(
            cid, target.id, permissions=MUTE_PERM, until_date=until
        )
        ctx.bot_data["db"].log(
            cid, target.id, "mute",
            f"{minutes}min by {update.effective_user.id}",
        )
        await update.message.reply_text(
            f"🔇 <b>Заглушён!</b>\n\n"
            f"👤 {mention(target)} (<code>{target.id}</code>)\n"
            f"⏱ {minutes} мин.\n"
            f"👮 {mention(update.effective_user)}",
            parse_mode="HTML",
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ <code>{e}</code>", parse_mode="HTML"
        )


async def cmd_unmute(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, ctx):
        return
    if not update.message.reply_to_message:
        await update.message.reply_text(
            "⚠️ Ответьте на сообщение: <code>/unmute</code>",
            parse_mode="HTML",
        )
        return

    target = update.message.reply_to_message.from_user
    cid = update.effective_chat.id
    try:
        await ctx.bot.restrict_chat_member(
            cid, target.id, permissions=UNMUTE_PERM
        )
        await update.message.reply_text(
            f"🔊 <b>Размьючен!</b>\n"
            f"👤 {mention(target)} (<code>{target.id}</code>)",
            parse_mode="HTML",
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ <code>{e}</code>", parse_mode="HTML"
        )


# ── /addadmin, /deladmin ─────────────────────────

async def cmd_addadmin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, ctx):
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ Ответьте на сообщение.")
        return

    t = update.message.reply_to_message.from_user
    cid = update.effective_chat.id
    db: Database = ctx.bot_data["db"]
    db.add_admin(t.id, cid)

    ctx.bot_data.setdefault("bot_admin_cache", {}).setdefault(cid, set()).add(t.id)

    await update.message.reply_text(
        f"✅ {mention(t)} добавлен в админы бота!", parse_mode="HTML"
    )


async def cmd_deladmin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, ctx):
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ Ответьте на сообщение.")
        return

    t = update.message.reply_to_message.from_user
    cid = update.effective_chat.id
    db: Database = ctx.bot_data["db"]
    db.del_admin(t.id, cid)

    cache = ctx.bot_data.get("bot_admin_cache", {}).get(cid, set())
    cache.discard(t.id)

    await update.message.reply_text(
        f"✅ {mention(t)} удалён из админов бота.", parse_mode="HTML"
    )


# ── /settings ────────────────────────────────────

async def cmd_settings(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        if "cfg_chat" not in ctx.user_data:
            await update.message.reply_text(
                "ℹ️ Сначала используйте /settings <b>в группе</b>.",
                parse_mode="HTML",
            )
            return
        title = ctx.user_data.get("cfg_title", "Чат")
    else:
        if not await is_admin(update, ctx):
            return
        ctx.user_data["cfg_chat"] = update.effective_chat.id
        ctx.user_data["cfg_title"] = update.effective_chat.title or "Чат"
        title = ctx.user_data["cfg_title"]

    text = (
        f"🤖 <b>Страж Порядка — Панель управления</b>\n\n"
        f"⚙️ Чат: <b>{title}</b>\n\n"
        f"Выберите раздел:"
    )

    if update.effective_chat.type != "private":
        try:
            await ctx.bot.send_message(
                update.effective_user.id,
                text,
                parse_mode="HTML",
                reply_markup=settings_main_kb(),
            )
            await update.message.reply_text(
                "📬 Настройки отправлены в ЛС!", parse_mode="HTML"
            )
        except Exception:
            await update.message.reply_text(
                "❌ Напишите мне в ЛС первым, потом повторите.",
                parse_mode="HTML",
            )
    else:
        await update.message.reply_text(
            text, parse_mode="HTML", reply_markup=settings_main_kb()
        )


# ── /stats ───────────────────────────────────────

async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, ctx):
        return

    cid = update.effective_chat.id
    db: Database = ctx.bot_data["db"]
    st = db.get_stats(cid)

    b, d, n, w = (
        st["banned_count"],
        st["deleted_count"],
        st["new_users"],
        st["warnings_count"],
    )
    mx = max(b, d, n, w, 1)

    def bar(v):
        f = int(v / mx * 12) if mx else 0
        return "█" * f + "░" * (12 - f)

    await update.message.reply_text(
        f"📊 <b>СТАТИСТИКА ЧАТА</b>\n\n"
        f"🔨 Забанено       <code>{b:>4}</code>  {bar(b)}\n"
        f"🗑 Удалено        <code>{d:>4}</code>  {bar(d)}\n"
        f"👥 Новых юзеров   <code>{n:>4}</code>  {bar(n)}\n"
        f"⚠️ Предупреждений <code>{w:>4}</code>  {bar(w)}\n",
        parse_mode="HTML",
    )


# ═══════════════════════════════════════════════
#  CALLBACK HANDLERS
# ═══════════════════════════════════════════════

async def settings_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data
    db: Database = ctx.bot_data["db"]
    cid = ctx.user_data.get("cfg_chat")

    if data == "noop":
        await q.answer()
        return

    # ── Главное меню ─────────────────────────────
    if data == "set_main":
        title = ctx.user_data.get("cfg_title", "Чат")
        await q.message.edit_text(
            f"🤖 <b>Страж Порядка — Панель управления</b>\n\n"
            f"⚙️ Чат: <b>{title}</b>\n\nВыберите раздел:",
            parse_mode="HTML",
            reply_markup=settings_main_kb(),
        )
        await q.answer()

    # ── Права ────────────────────────────────────
    elif data == "set_rights":
        if not cid:
            await q.answer("❌ Сначала /settings в группе", show_alert=True)
            return
        admins = db.get_admins(cid)
        lst = "\n".join(f"  • <code>{a}</code>" for a in admins) or (
            "  <i>Пока нет</i>"
        )
        await q.message.edit_text(
            f"👮‍♂️ <b>УПРАВЛЕНИЕ ПРАВАМИ</b>\n\n"
            f"📋 <b>Админы бота:</b>\n{lst}\n\n"
            f"<b>Добавить/удалить</b> (в чате, ответом на сообщение):\n"
            f"  <code>/addadmin</code>\n  <code>/deladmin</code>\n\n"
            f"<i>ℹ️ Telegram-админы чата имеют права автоматически.</i>",
            parse_mode="HTML",
            reply_markup=back_kb(),
        )
        await q.answer()

    # ── Фильтр ───────────────────────────────────
    elif data == "set_filter":
        if not cid:
            await q.answer("❌ Сначала /settings в группе", show_alert=True)
            return
        s = db.get_settings(cid)
        await q.message.edit_text(
            "🚦 <b>НАСТРОЙКИ СПАМ-ФИЛЬТРА</b>\n\n"
            "Нажмите кнопку для переключения:",
            parse_mode="HTML",
            reply_markup=filter_kb(cid, s),
        )
        await q.answer()

    # ── Статистика ───────────────────────────────
    elif data == "set_stats":
        if not cid:
            await q.answer("❌ Сначала /settings в группе", show_alert=True)
            return
        st = db.get_stats(cid)
        b, d, n, w = (
            st["banned_count"],
            st["deleted_count"],
            st["new_users"],
            st["warnings_count"],
        )
        mx = max(b, d, n, w, 1)

        def bar(v):
            f = int(v / mx * 12) if mx else 0
            return "█" * f + "░" * (12 - f)

        await q.message.edit_text(
            f"📊 <b>СТАТИСТИКА</b>\n\n"
            f"🔨 Забанено       <code>{b:>4}</code>  {bar(b)}\n"
            f"🗑 Удалено        <code>{d:>4}</code>  {bar(d)}\n"
            f"👥 Новые юзеры    <code>{n:>4}</code>  {bar(n)}\n"
            f"⚠️ Предупреждения <code>{w:>4}</code>  {bar(w)}\n",
            parse_mode="HTML",
            reply_markup=back_kb(),
        )
        await q.answer()

    # ── Помощь ───────────────────────────────────
    elif data == "set_help":
        await q.message.edit_text(
            "❓ <b>ПОМОЩЬ</b>\n\n"
            "<b>Страж Порядка</b> — бот-модератор.\n\n"
            "🔐 <b>Капча</b> — проверяет новых участников\n"
            "🤬 <b>Антимат</b> — удаляет нецензурную лексику\n"
            "🔗 <b>Антиссылки</b> — блокирует ссылки\n"
            "⏳ <b>Антифлуд</b> — защита от спама\n"
            "⚠️ <b>3 страйка</b> — автоматический бан\n\n"
            "Бот должен быть <b>админом</b> чата с правами\n"
            "на удаление сообщений и бан участников.",
            parse_mode="HTML",
            reply_markup=back_kb(),
        )
        await q.answer()

    # ── Тогглы ───────────────────────────────────
    elif data.startswith("tog_"):
        _, kind, cid_s = data.split("_", 2)
        cid_t = int(cid_s)
        col_map = {
            "mat": "antimat",
            "link": "antilinks",
            "flood": "antiflood",
            "cap": "captcha",
            "wel": "welcome",
        }
        col = col_map.get(kind)
        if col:
            new = db.toggle_setting(cid_t, col)
            label = {
                "antimat": "Антимат",
                "antilinks": "Антиссылки",
                "antiflood": "Антифлуд",
                "captcha": "Капча",
                "welcome": "Приветствие",
            }.get(col, col)
            st = "включён ✅" if new else "выключен ❌"
            await q.answer(f"{label}: {st}")

            s = db.get_settings(cid_t)
            await q.message.edit_reply_markup(
                reply_markup=filter_kb(cid_t, s)
            )


# ── Callback модерации ───────────────────────────

async def moderation_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data
    cid = q.message.chat_id
    db: Database = ctx.bot_data["db"]

    # Проверка прав
    tg = ctx.bot_data.get("tg_admin_cache", {}).get(cid, set())
    ba = ctx.bot_data.get("bot_admin_cache", {}).get(cid, set())
    if q.from_user.id not in tg and q.from_user.id not in ba and q.from_user.id != OWNER_ID:
        try:
            m = await ctx.bot.get_chat_member(cid, q.from_user.id)
            if m.status not in ("administrator", "creator"):
                await q.answer("❌ Только для админов!", show_alert=True)
                return
        except Exception:
            await q.answer("❌ Только для админов!", show_alert=True)
            return

    parts = data.split("_")

    # 🗑 Удалить
    if data.startswith("m_del_"):
        uid, mid = int(parts[2]), int(parts[3]) if len(parts) > 3 else 0
        if mid:
            try:
                await ctx.bot.delete_message(cid, mid)
            except Exception:
                pass
        db.inc_stat(cid, "deleted_count")
        await q.message.edit_reply_markup(reply_markup=done_kb("Удалено"))
        await q.answer("🗑 Удалено!")

    # ⏱ Тайм-аут
    elif data.startswith("m_to_"):
        uid = int(parts[2])
        try:
            await ctx.bot.restrict_chat_member(
                cid, uid,
                permissions=MUTE_PERM,
                until_date=datetime.now() + timedelta(seconds=MUTE_DURATION),
            )
            db.log(cid, uid, "timeout", f"by {q.from_user.id}")
            await q.message.edit_reply_markup(
                reply_markup=done_kb("Тайм-аут 1ч")
            )
            await q.answer("⏱ Тайм-аут выдан!")
        except Exception as e:
            await q.answer(f"❌ {e}", show_alert=True)

    # 🔨 Бан
    elif data.startswith("m_ban_"):
        uid = int(parts[2])
        try:
            await ctx.bot.ban_chat_member(cid, uid)
            db.inc_stat(cid, "banned_count")
            db.reset_warns(uid, cid
