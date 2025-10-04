import os
import sqlite3
import logging
import asyncio
import re
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiogram.filters import Command
from aiohttp import web
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv("API_TOKEN")
ADMIN_IDS = [7233837335 ,7696244446]
DASHBOARD_KEY = os.getenv("DASHBOARD_KEY")
UPLOAD_KEY = os.getenv("UPLOAD_KEY")
DB_NAME = "targets.db"

WEBHOOK_HOST = f"https://bot-father-nmpt.onrender.com"
WEBHOOK_PATH = f"/{API_TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
WEBAPP_HOST = "0.0.0.0"
WEBAPP_PORT = int(os.environ.get("PORT", 5000))

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# دیتابیس
conn = sqlite3.connect(DB_NAME, check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS targets (
    chat_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    lang TEXT
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS failed_targets (
    chat_id INTEGER PRIMARY KEY,
    reason TEXT
)
""")
conn.commit()

# دریافت فایل DB از userbot
async def upload_db(request):
    key = request.headers.get("Authorization")
    if key != UPLOAD_KEY:
        return web.json_response({"error": "unauthorized"}, status=401)

    reader = await request.multipart()
    field = await reader.next()
    with open(DB_NAME, "wb") as f:
        while True:
            chunk = await field.read_chunk()
            if not chunk:
                break
            f.write(chunk)
    return web.json_response({"status": "ok", "message": f"{field.filename} saved"})

# تشخیص زبان پیام (fallback)
def detect_language(text: str) -> str:
    if re.search(r'[\u0600-\u06FF]', text):
        return "IR"
    elif re.search(r'[\u0400-\u04FF]', text):
        return "RU"
    else:
        return "EN"

# Broadcast بر اساس زبان
@dp.message(Command("broadcast"))
async def cmd_broadcast(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    args = message.text.split(" ", 2)
    if len(args) < 3:
        await message.reply("فرمت درست: /broadcast LANG پیام\nمثال: /broadcast IR سلام")
        return

    target_lang = args[1].upper()
    text = args[2]

    cursor.execute("SELECT chat_id FROM targets WHERE lang=?", (target_lang,))
    targets = [row[0] for row in cursor.fetchall()]

    sent_count, failed_count = 0, 0
    for uid in targets:
        try:
            await bot.send_message(uid, text[:4000])
            sent_count += 1
            await asyncio.sleep(0.5)
        except Exception as e:
            failed_count += 1
            cursor.execute("INSERT OR REPLACE INTO failed_targets (chat_id, reason) VALUES (?, ?)", (uid, str(e)))
            conn.commit()

    await message.reply(f"✅ ارسال شد: {sent_count} موفق، {failed_count} ناموفق.")

# آمار کاربران
@dp.message(Command("status"))
async def cmd_status(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    cursor.execute("SELECT lang, COUNT(*) FROM targets GROUP BY lang")
    stats = cursor.fetchall()
    text = "📊 آمار کاربران بر اساس زبان:\n"
    for lang, count in stats:
        text += f"- {lang}: {count}\n"
    await message.reply(text)

# داشبورد امن
async def dashboard(request):
    key = request.query.get("key")
    if key != DASHBOARD_KEY:
        return web.json_response({"error": "unauthorized"}, status=401)
    cursor.execute("SELECT chat_id, username, first_name, last_name, lang FROM targets")
    data = cursor.fetchall()
    targets = [{"chat_id": r[0], "username": r[1], "first_name": r[2], "last_name": r[3], "lang": r[4]} for r in data]
    return web.json_response({"targets": targets})

# health endpoint
async def health(request):
    return web.Response(text="ok")

# وبهوک
async def on_startup(app):
    await bot.set_webhook(WEBHOOK_URL)
async def on_shutdown(app):
    await bot.delete_webhook()

def main():
    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, on_startup=on_startup, on_shutdown=on_shutdown)

    app.router.add_get("/dashboard", dashboard)
    app.router.add_post("/upload_db", upload_db)
    app.router.add_get("/health", health)

    web.run_app(app, host=WEBAPP_HOST, port=WEBAPP_PORT)

if __name__ == "__main__":
    main()
