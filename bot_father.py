import re
import asyncio
import logging
import sqlite3
import os
from aiogram import Bot, Dispatcher, Router, types, F
from dotenv import load_dotenv
from aiogram.types import Message
from aiogram.enums import ChatType
from aiogram.utils.markdown import hbold
from flask import Flask
import threading

# ───── تنظیمات کلی ─────
load_dotenv()  # بارگذاری متغیرهای .env

API_TOKEN = os.getenv("API_TOKEN")
admin_ids_str = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = list(map(int, admin_ids_str.split(','))) if admin_ids_str else []

# ───── لاگ ─────
logging.basicConfig(level=logging.INFO)

# ───── دیتابیس ─────
conn = sqlite3.connect("targets.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS targets (
    chat_id INTEGER PRIMARY KEY,
    chat_type TEXT,
    tags TEXT
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS failed_targets (
    chat_id INTEGER PRIMARY KEY,
    reason TEXT
)
""")
conn.commit()

# ───── تشخیص زبان ─────
def detect_language(text):
    if re.search(r'[\u0600-\u06FF]', text):
        return "IR"
    elif re.search(r'[\u0400-\u04FF]', text):
        return "RU"
    else:
        return "EN"

# ───── ذخیره آیدی کاربر ─────
def save_user(chat_id, chat_type, tag):
    cursor.execute(
        "INSERT OR IGNORE INTO targets (chat_id, chat_type, tags) VALUES (?, ?, ?)",
        (chat_id, chat_type, tag)
    )
    conn.commit()

# ───── شروع Aiogram 3 ─────
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# ───── ذخیره کاربران از پیام‌های گروه/خصوصی ─────
@router.message(F.text)
async def handle_all_messages(message: Message):
    user_id = message.from_user.id
    lang_tag = detect_language(message.text)
    chat_type = message.chat.type
    save_user(user_id, chat_type, lang_tag)
    print(f"[LOG] ذخیره شد: {user_id} ({lang_tag})")

# ───── ارسال پیام خصوصی به تگ خاص ─────
@router.message(F.text.startswith("/broadcast"))
async def broadcast_message(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("⛔️ دسترسی نداری")
        return

    args = message.text.split(" ", 2)
    if len(args) < 3:
        await message.reply("فرمت درست: /broadcast TAG پیام")
        return

    target_tag = args[1].upper()
    text = args[2]

    cursor.execute("SELECT chat_id FROM targets WHERE tags=?", (target_tag,))
    users = cursor.fetchall()

    success, failed = 0, 0

    for (chat_id,) in users:
        try:
            await bot.send_message(chat_id, text)
            success += 1
            await asyncio.sleep(0.5)
        except Exception as e:
            failed += 1
            cursor.execute(
                "INSERT OR REPLACE INTO failed_targets (chat_id, reason) VALUES (?, ?)",
                (chat_id, str(e))
            )
            conn.commit()

    await message.reply(f"✅ ارسال انجام شد: {success} موفق، {failed} ناموفق")

# ───── وضعیت کاربران ذخیره‌شده ─────
@router.message(F.text == "/status")
async def status_handler(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    cursor.execute("SELECT tags, COUNT(*) FROM targets GROUP BY tags")
    stats = cursor.fetchall()

    text = "📊 آمار کاربران:\n"
    for tag, count in stats:
        text += f"- {tag}: {count}\n"
    await message.reply(text)

# ───── سرور Flask برای داشبورد ساده ─────
app = Flask(__name__)

@app.route("/dashboard")
def dashboard():
    cursor.execute("SELECT chat_id, chat_type, tags FROM targets")
    data = cursor.fetchall()
    return {
        "users": [
            {"chat_id": row[0], "chat_type": row[1], "tag": row[2]}
            for row in data
        ]
    }

def run_flask():
    app.run(host="0.0.0.0", port=5000)

# ───── اجرای همزمان Aiogram و Flask ─────
async def main():
    threading.Thread(target=run_flask, daemon=True).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
