"""
Капча, приветствие, правила.
"""
from telegram import Update, ChatPermissions
from telegram.ext import ContextTypes

from database import Database
from keyboards.inline_keyboards import captcha_kb, rules_kb

DEFAULT_RULES = (
    "📜 <b>ПРАВИЛА ЧАТА</b>\n\n"
    "1️⃣ <b>Уважение</b> — не оскорбляем друг друга.\n"
    "2️⃣ <b>Реклама</b> — запрещена без согласования.\n"
    "3️⃣ <b>Мат</b> — фильтруй лексику.\n"
    "4️⃣ <b>Флуд</b> — не заливаем однотипными сообщениями.\n"
    "5️⃣ <b>Спам</b> — никакого спама и ботов.\n\n"
    "⚠️ <i>Нарушение правил ведёт к предупреждению и бану.</i>"
)

MUTE = ChatPermissions(can_send_messages=False)
UNMUTE = ChatPermissions(
    can_send_messages=True,
    can_send_other_messages=True,
    can_add_web_page_previews=True,
    can_send_polls=True,
    can_invite_users=True,
)


# ── Новый участник ───────────────────────────────

async def on_new_member(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    db: Database = ctx.bot_data["db"]
    chat_id = update.effective_chat.id

    for member in update.message.new_chat_members:
        # Если добавили самого бота — приветствие-инструкция
        if member.id == ctx.bot.id:
            await update.message.reply_text(
                "🛡️ <b>Страж Порядка активирован!</b>\n\n"
                "Дайте мне права администратора, затем\n"
                "используйте /settings для настройки.",
                parse_mode="HTML",
            )
            continue

        if member.is_bot:
            continue

        settings = db.get_settings(chat_id)
        db.inc_stat(chat_id, "new_users")

        if settings["captcha"]:
            # Мьют
            try:
                await ctx.bot.restrict_chat_member(
                    chat_id, member.id, permissions=MUTE
                )
            except Exception as e:
                print(f"[mute err] {e}")

            text = (
                f"👋 <b>Добро пожаловать, {member.first_name}!</b>\n\n"
                f"🛡️ Для доступа к чату:\n"
                f"  1. Прочитайте правила\n"
                f"  2. Нажмите «Я согласен»\n\n"
                f"⏳ <i>У вас 5 минут на прохождение проверки.</i>"
            )
            msg = await update.message.reply_text(
                text, parse_mode="HTML", reply_markup=captcha_kb(member.id)
            )

            # Авто-кик через 5 мин
            ctx.job_queue.run_once(
                _captcha_timeout,
                when=300,
                data={"chat_id": chat_id, "user_id": member.id,
                      "msg_id": msg.message_id},
                name=f"cap_{chat_id}_{member.id}",
            )

        elif settings["welcome"]:
            await update.message.reply_text(
                f"🎉 <b>Добро пожаловать, {member.first_name}!</b>\n"
                f"Ознакомься с правилами: /rules",
                parse_mode="HTML",
            )


async def _captcha_timeout(ctx: ContextTypes.DEFAULT_TYPE):
    d = ctx.job.data
    try:
        await ctx.bot.ban_chat_member(d["chat_id"], d["user_id"])
        await ctx.bot.unban_chat_member(d["chat_id"], d["user_id"])
        await ctx.bot.edit_message_text(
            chat_id=d["chat_id"],
            message_id=d["msg_id"],
            text=(
                "🔴 <b>Время вышло.</b>\n\n"
                "Пользователь не прошёл проверку и удалён."
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        print(f"[captcha timeout err] {e}")


# ── Callback-и капчи ────────────────────────────

async def captcha_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data
    db: Database = ctx.bot_data["db"]

    # ── Согласен ─────────────────────────────────
    if data.startswith("cap_ok_"):
        uid = int(data.split("_")[2])
        if q.from_user.id != uid:
            await q.answer("❌ Эта кнопка не для вас!", show_alert=True)
            return

        cid = q.message.chat_id

        try:
            await ctx.bot.restrict_chat_member(cid, uid, permissions=UNMUTE)
        except Exception as e:
            print(f"[unmute err] {e}")

        # Отмена таймера
        for job in ctx.job_queue.get_jobs_by_name(f"cap_{cid}_{uid}"):
            job.schedule_removal()

        await q.message.edit_text(
            f"✅ <b>{q.from_user.first_name}</b> прошёл проверку!\n\n"
            f"🎉 Добро пожаловать! Расскажи о себе 😊",
            parse_mode="HTML",
        )
        await q.answer("🎉 Добро пожаловать!")
        db.log(cid, uid, "captcha_ok")

    # ── Показать правила ─────────────────────────
    elif data.startswith("cap_rules_"):
        uid = int(data.split("_")[2])
        if q.from_user.id != uid:
            await q.answer("❌ Эта кнопка не для вас!", show_alert=True)
            return

        cid = q.message.chat_id
        s = db.get_settings(cid)
        rules = s.get("rules") or DEFAULT_RULES

        await q.message.edit_text(
            rules, parse_mode="HTML", reply_markup=rules_kb(uid)
        )
        await q.answer()

    # ── Назад ────────────────────────────────────
    elif data.startswith("cap_back_"):
        uid = int(data.split("_")[2])
        if q.from_user.id != uid:
            await q.answer("❌ Эта кнопка не для вас!", show_alert=True)
            return

        text = (
            f"👋 <b>Добро пожаловать, {q.from_user.first_name}!</b>\n\n"
            f"🛡️ Для доступа к чату:\n"
            f"  1. Прочитайте правила\n"
            f"  2. Нажмите «Я согласен»\n\n"
            f"⏳ <i>У вас 5 минут на прохождение проверки.</i>"
        )
        await q.message.edit_text(
            text, parse_mode="HTML", reply_markup=captcha_kb(uid)
        )
        await q.answer()
