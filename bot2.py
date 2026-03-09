import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest

# --- КОНФИГУРАЦИЯ ---
TOKEN = "8594010470:AAEF5eeIfVlPNdsqZbH9fQM2Yc1iHhHOQ7U"
CHECK_INTERVAL = 60  # Как часто проверять обновления (в секундах)

bot = Bot(token=TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# --- РАБОТА С БАЗОЙ ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("monitor.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS targets 
                      (user_id INTEGER, username TEXT, last_data TEXT, watchers TEXT)''')
    conn.commit()
    conn.close()

def get_targets():
    conn = sqlite3.connect("monitor.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM targets")
    data = cursor.fetchall()
    conn.close()
    return data

def update_target_in_db(user_id, last_data, watchers):
    conn = sqlite3.connect("monitor.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE targets SET last_data = ?, watchers = ? WHERE user_id = ?", 
                   (str(last_data), str(watchers), user_id))
    conn.commit()
    conn.close()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
async def fetch_full_user_data(username: str):
    try:
        chat = await bot.get_chat(f"@{username}")
        photos = await bot.get_user_profile_photos(chat.id, limit=1)
        photo_id = photos.photos[0][0].file_id if photos.total_count > 0 else "None"
        
        return {
            "id": chat.id,
            "username": chat.username or "None",
            "first_name": chat.first_name or "None",
            "last_name": chat.last_name or "None",
            "bio": chat.bio or "None",
            "photo": photo_id,
            "is_premium": getattr(chat, 'is_premium', False)
        }
    except Exception:
        return None

def get_osint_links(username):
    return (
        f"🔍 **OSINT ссылки для @{username}:**\n"
        f"├ [Google](https://www.google.com/search?q={username})\n"
        f"├ [Insta](https://instagram.com/{username})\n"
        f"├ [TikTok](https://tiktok.com/@{username})\n"
        f"└ [Twitter](https://twitter.com/{username})"
    )

# --- ОБРАБОТЧИКИ КОМАНД ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("🛠 **Режим MAXIMUM активирован.**\n\n"
                         "• `/info @username` — получить досье\n"
                         "• `/watch @username` — начать слежку за изменениями")

@dp.message(Command("info"))
async def cmd_info(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        return await message.answer("Пример: `/info @durov`")
    
    target = args[1].replace("@", "").strip()
    data = await fetch_full_user_data(target)
    
    if not data:
        return await message.answer("❌ Пользователь не найден.")

    report = [
        f"📊 **ДОСЬЕ: @{target}**",
        f"🆔 ID: `{data['id']}`",
        f"👤 Имя: {data['first_name']}",
        f"👥 Фамилия: {data['last_name']}",
        f"📝 Bio: {data['bio']}",
        f"👑 Premium: {'✅' if data['is_premium'] else '❌'}",
        "---",
        get_osint_links(target)
    ]
    
    if data['photo'] != "None":
        await message.answer_photo(data['photo'], caption="\n".join(report), parse_mode="Markdown")
    else:
        await message.answer("\n".join(report), parse_mode="Markdown", disable_web_page_preview=True)

@dp.message(Command("watch"))
async def cmd_watch(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        return await message.answer("Пример: `/watch @username`")

    target_user = args[1].replace("@", "").strip()
    data = await fetch_full_user_data(target_user)

    if not data:
        return await message.answer("❌ Не могу найти этого пользователя.")

    conn = sqlite3.connect("monitor.db")
    cursor = conn.cursor()
    cursor.execute("SELECT watchers FROM targets WHERE user_id = ?", (data['id'],))
    row = cursor.fetchone()

    if row:
        watchers = eval(row[0])
        if message.chat.id not in watchers:
            watchers.append(message.chat.id)
            update_target_in_db(data['id'], data, watchers)
    else:
        cursor.execute("INSERT INTO targets VALUES (?, ?, ?, ?)", 
                       (data['id'], target_user, str(data), str([message.chat.id])))
    
    conn.commit()
    conn.close()
    await message.answer(f"👁 Слежка за @{target_user} установлена.")

# --- ФОНОВАЯ СЛЕЖКА ---
async def watchdog():
    while True:
        await asyncio.sleep(CHECK_INTERVAL)
        targets = get_targets()
        
        for user_id, username, last_data_str, watchers_str in targets:
            last_data = eval(last_data_str)
            watchers = eval(watchers_str)
            current_data = await fetch_full_user_data(username)

            if not current_data: continue

            changes = []
            fields = {"first_name": "Имя", "last_name": "Фамилия", "bio": "Bio", "username": "Ник"}
            
            for key, label in fields.items():
                if str(current_data[key]) != str(last_data[key]):
                    changes.append(f"🔹 {label}: `{last_data[key]}` ➡️ `{current_data[key]}`")
            
            if changes:
                update_target_in_db(user_id, current_data, watchers)
                text = f"🔔 **ИЗМЕНЕНИЕ ПРОФИЛЯ @{username}**\n\n" + "\n".join(changes)
                for chat_id in watchers:
                    try:
                        await bot.send_message(chat_id, text, parse_mode="Markdown")
                    except: pass

async def main():
    init_db()
    asyncio.create_task(watchdog())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
