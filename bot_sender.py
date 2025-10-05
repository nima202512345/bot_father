import os
import json
import sqlite3
import logging
import asyncio
import random
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
UPLOAD_KEY_USERBOT = os.getenv("UPLOAD_KEY_USERBOT")
DB_NAME = "targets.db"

WEBHOOK_HOST = f"https://bot-father-nmpt.onrender.com"
WEBHOOK_PATH = f"/{API_TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
WEBAPP_HOST = "0.0.0.0"
WEBAPP_PORT = int(os.environ.get("PORT", 5000))

# تنظیمات لاگ‌گذاری
logging.basicConfig(
    level=logging.DEBUG,  # برای جزئیات بیشتر هنگام دیباگ
    format='[%(asctime)s] %(levelname)s:%(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

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

# تشخیص زبان پیام (fallback)
def detect_language(text: str) -> str:
    if re.search(r'[\u0600-\u06FF]', text):
        return "IR"
    elif re.search(r'[\u0400-\u04FF]', text):
        return "RU"
    else:
        return "EN"

# اد تبلیغات
ads_fa = [...]
ads_en = [...]
ads_ru = [...]

def get_random_ad(lang="IR"):
    if lang == "IR":
        return random.choice(ads_fa)
    elif lang == "EN":
        return random.choice(ads_en)
    elif lang == "RU":
        return random.choice(ads_ru)
    else:
        return random.choice(ads_fa)

@dp.message(Command("broadcast"))
async def cmd_broadcast(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        logger.warning(f"کاربر {message.from_user.id} اجازه اجرای /broadcast ندارد.")
        return

    args = message.text.split(" ", 2)
    if len(args) < 3:
        await message.reply(
            "فرمت درست: /broadcast LANG پیام\n"
            "مثال: /broadcast IR سلام\n"
            "برای پیام تصادفی: /broadcast IR RANDOM\n"
            "برای همه زبان‌ها و پیام تصادفی: /broadcast ALL RANDOM"
        )
        logger.info("فرمت پیام /broadcast اشتباه است.")
        return

    target_lang = args[1].upper()
    text = args[2].strip()

    if target_lang == "ALL":
        cursor.execute("SELECT chat_id, lang FROM targets")
        targets_data = cursor.fetchall()
        logger.info(f"ارسال به همه کاربران: تعداد {len(targets_data)} کاربر")
    else:
        cursor.execute("SELECT chat_id, lang FROM targets WHERE lang=?", (target_lang,))
        targets_data = cursor.fetchall()
        logger.info(f"ارسال به کاربران با زبان {target_lang}: تعداد {len(targets_data)} کاربر")

    if not targets_data:
        await message.reply("⚠️ هیچ کاربری برای این زبان پیدا نشد.")
        logger.info("کاربری برای ارسال پیام پیدا نشد.")
        return

    sent_count, failed_count = 0, 0

    for uid, lang in targets_data:
        msg_to_send = text
        if text.upper() == "RANDOM":
            msg_to_send = get_random_ad(lang)

        try:
            await bot.send_message(uid, msg_to_send[:4000])
            sent_count += 1
            logger.debug(f"پیام به {uid} ارسال شد.")
            await asyncio.sleep(0.5)
        except Exception as e:
            failed_count += 1
            logger.error(f"ارسال پیام به {uid} با خطا مواجه شد: {e}")
            cursor.execute(
                "INSERT OR REPLACE INTO failed_targets (chat_id, reason) VALUES (?, ?)",
                (uid, str(e))
            )
            conn.commit()

    await message.reply(f"✅ ارسال شد: {sent_count} موفق، {failed_count} ناموفق.")
    logger.info(f"پایان ارسال پیام: {sent_count} موفق، {failed_count} ناموفق.")

@dp.message(Command("status"))
async def cmd_status(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        logger.warning(f"کاربر {message.from_user.id} اجازه اجرای /status ندارد.")
        return
    cursor.execute("SELECT lang, COUNT(*) FROM targets GROUP BY lang")
    stats = cursor.fetchall()
    text = "📊 آمار کاربران بر اساس زبان:\n"
    for lang, count in stats:
        text += f"- {lang}: {count}\n"
    await message.reply(text)
    logger.info("آمار کاربران ارسال شد.")

async def dashboard(request):
    key = request.query.get("key")
    if key != DASHBOARD_KEY:
        logger.warning("دسترسی غیرمجاز به داشبورد دریافت شد.")
        return web.json_response({"error": "unauthorized"}, status=401)
    cursor.execute("SELECT chat_id, username, first_name, last_name, lang FROM targets")
    data = cursor.fetchall()
    targets = [{"chat_id": r[0], "username": r[1], "first_name": r[2], "last_name": r[3], "lang": r[4]} for r in data]
    logger.info("داده‌های داشبورد ارسال شد.")
    return web.json_response({"targets": targets})

async def health(request):
    return web.Response(text="ok")

async def on_startup(app):
    await bot.set_webhook(WEBHOOK_URL)
    logger.info("وبهوک تنظیم شد.")

async def on_shutdown(app):
    await bot.delete_webhook()
    logger.info("وبهوک حذف شد.")

routes = web.RouteTableDef()

async def upload_db(request):
    key = request.headers.get("X-Upload-Key")
    if key != UPLOAD_KEY:
        logger.warning("دسترسی غیرمجاز به آپلود DB دریافت شد.")
        return web.json_response({"error": "unauthorized"}, status=401)

    reader = await request.multipart()
    field = await reader.next()
    with open(DB_NAME, "wb") as f:
        while True:
            chunk = await field.read_chunk()
            if not chunk:
                break
            f.write(chunk)
    logger.info(f"فایل DB با موفقیت دریافت و ذخیره شد: {field.filename}")
    return web.json_response({"status": "ok", "message": f"{field.filename} saved"})

def merge_userbot_users_into_db():
    logger.info("شروع merge_userbot_users_into_db ...")
    try:
        with open("userbot_users.json", "r", encoding="utf-8") as f:
            users = json.load(f)
            logger.info(f"خواندن فایل userbot_users.json با تعداد کاربران: {len(users)}")

        new_count = 0

        for idx, user in enumerate(users):
            logger.debug(f"کاربر {idx+1}: {user}")
            chat_id = user.get("id")
            username = user.get("username")
            first_name = user.get("first_name")
            last_name = user.get("last_name")
            lang = user.get("lang") or detect_language(first_name or "")

            cursor.execute("SELECT 1 FROM targets WHERE chat_id = ?", (chat_id,))
            if cursor.fetchone():
                logger.info(f"کاربر {chat_id} قبلا وجود دارد. رد شد.")
                continue

            cursor.execute("""
                INSERT INTO targets (chat_id, username, first_name, last_name, lang)
                VALUES (?, ?, ?, ?, ?)
            """, (chat_id, username, first_name, last_name, lang))
            new_count += 1
            logger.info(f"کاربر {chat_id} با موفقیت اضافه شد.")

        conn.commit()
        logger.info(f"merge_userbot_users_into_db: {new_count} کاربر جدید اضافه شد.")
    except Exception as e:
        logger.error(f"خطا در merge_userbot_users_into_db: {e}")

@routes.post("/userbot_users")
async def userbot_users(request):
    key = request.headers.get("X-Upload-Key")
    if key != UPLOAD_KEY:
        logger.warning("دسترسی غیرمجاز به /userbot_users دریافت شد.")
        return web.Response(text="Invalid key", status=403)

    data = await request.post()
    if "file" not in data:
        logger.error("فایل در درخواست /userbot_users پیدا نشد.")
        return web.Response(text="Missing file", status=400)

    file = data["file"]
    with open("userbot_users.json", "wb") as f:
        f.write(file.file.read())

    logger.info("فایل userbot_users.json دریافت و ذخیره شد. شروع ادغام به دیتابیس.")
    merge_userbot_users_into_db()

    return web.Response(text="Main upload OK")

@routes.post("/user_upload")
async def user_upload(request):
    key = request.headers.get("X-Upload-Key")
    if key != UPLOAD_KEY_USERBOT:
        logger.warning("دسترسی غیرمجاز به /user_upload دریافت شد.")
        return web.Response(text="Invalid key", status=403)

    data = await request.post()
    if "file" not in data:
        logger.error("فایل در درخواست /user_upload پیدا نشد.")
        return web.Response(text="Missing file", status=400)

    file = data["file"]
    with open("userbot_users.json", "wb") as f:
        f.write(file.file.read())

    logger.info("فایل userbot_users.json از /user_upload دریافت و ذخیره شد.")
    return web.Response(text="Userbot upload OK")

def main():
    app = web.Application()
    app.add_routes(routes)
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, on_startup=on_startup, on_shutdown=on_shutdown)

    async def home(request):
        return web.Response(text="Bot is alive ✅")

    app.router.add_get("/", home)
    app.router.add_get("/dashboard", dashboard)
    app.router.add_post("/upload_db", upload_db)
    app.router.add_get("/health", health)

    logger.info(f"Starting web app on {WEBAPP_HOST}:{WEBAPP_PORT}")
    web.run_app(app, host=WEBAPP_HOST, port=WEBAPP_PORT)

if __name__ == "__main__":
    main()
