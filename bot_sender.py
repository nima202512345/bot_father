import os
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

# Broadcast بر اساس زبا

# ===================== فارسی =====================
ads_fa = [
    "🎉 همه قرعه‌کشی‌ها یکجا!\nمیخوای هیچ قرعه‌کشی مهمی رو از دست ندی؟\nکانال ما همه قرعه‌کشی‌های تلگرام را جمع‌آوری کرده و مستقیم بهت اطلاع می‌دهد! 🏆\n\n✅ شرکت سریع و راحت\n✅ همه قرعه‌کشی‌ها یکجا\n✅ شانس برنده شدن بیشتر\n\n📌 [لینک کانال شما]",
    "سلام! 👋\nمیخوای با یک کلیک در قرعه‌کشی‌های تلگرام شرکت کنی و شانس برنده شدنت رو بالا ببری؟\nکانال ما همه قرعه‌کشی‌ها رو جمع کرده و بهت اطلاع می‌دهد! 🎁\n\n🔹 رایگان و آسان\n🔹 همه قرعه‌کشی‌ها یکجا\n🔹 هر هفته شانس برنده شدن\n\n📌 [لینک کانال شما]",
    "آیا NFT تلگرامی دوست داری ولی به خاطر گرون بودن نتونستی داشته باشی؟ 😢\nنگران نباش!\nکانال ما توی قرعه‌کشی‌ها شرکت کن و راحت کلی NFT و جوایز برنده شو! 🚀\n\n✅ بدون هزینه اضافی\n✅ شانس برنده شدن بالا\n✅ قرعه‌کشی‌های واقعی و معتبر\n\n📌 [لینک کانال شما]",
    "🎁 میخوای قرعه‌کشی‌ها رو از دست ندی؟\nکانال ما همه قرعه‌کشی‌های تلگرام را جمع کرده و مستقیم بهت اطلاع می‌دهد! 🏆\n📌 [لینک کانال شما]"
]

# ===================== انگلیسی =====================
ads_en = [
    "🎉 All Giveaways in One Place! Don't want to miss any important giveaway? Our channel collects all Telegram giveaways and notifies you directly! 🏆\n\n✅ Quick and easy participation\n✅ All giveaways in one place\n✅ Higher chances to win\n\n📌 [Your channel link]",
    "Hello! 👋 Want to join Telegram giveaways with one click and increase your winning chance? Our channel collects all giveaways and notifies you! 🎁\n\n🔹 Free and easy\n🔹 All giveaways in one place\n🔹 Weekly chances to win\n\n📌 [Your channel link]",
    "Do you want Telegram NFTs but couldn't get them due to high cost? 😢 Don't worry! Join our channel's giveaways and easily win NFTs and prizes! 🚀\n\n✅ No extra cost\n✅ High winning chances\n✅ Real and verified giveaways\n\n📌 [Your channel link]",
    "🎁 Don't miss any giveaways! Our channel collects all Telegram giveaways and notifies you directly! 🏆\n📌 [Your channel link]"
]

# ===================== روسی =====================
ads_ru = [
    "🎉 Все розыгрыши в одном месте! Не хочешь пропустить важные розыгрыши? Наш канал собирает все розыгрыши Telegram и уведомляет тебя напрямую! 🏆\n\n✅ Быстрое и легкое участие\n✅ Все розыгрыши в одном месте\n✅ Больше шансов на победу\n\n📌 [Ссылка на ваш канал]",
    "Привет! 👋 Хочешь участвовать в розыгрышах Telegram одним кликом и увеличить свои шансы на победу? Наш канал собирает все розыгрыши и уведомляет тебя! 🎁\n\n🔹 Бесплатно и легко\n🔹 Все розыгрыши в одном месте\n🔹 Еженедельные шансы на победу\n\n📌 [Ссылка на ваш канал]",
    "Хотите Telegram NFT, но не смогли получить из-за высокой цены? 😢 Не переживай! Участвуй в розыгрышах нашего канала и легко выигрывай NFT и призы! 🚀\n\n✅ Без дополнительных затрат\n✅ Высокие шансы на победу\n✅ Реальные и проверенные розыгрыши\n\n📌 [Ссылка на ваш канал]",
    "🎁 Не пропусти ни один розыгрыш! Наш канал собирает все розыгрыши Telegram и уведомляет тебя напрямую! 🏆\n📌 [Ссылка на ваш канал]"
]

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
        return

    args = message.text.split(" ", 2)
    if len(args) < 3:
        await message.reply(
            "فرمت درست: /broadcast LANG پیام\n"
            "مثال: /broadcast IR سلام\n"
            "برای پیام تصادفی: /broadcast IR RANDOM\n"
            "برای همه زبان‌ها و پیام تصادفی: /broadcast ALL RANDOM"
        )
        return

    target_lang = args[1].upper()
    text = args[2].strip()

    # تعیین کاربران هدف
    if target_lang == "ALL":
        # گرفتن تمام زبان‌ها
        cursor.execute("SELECT chat_id, lang FROM targets")
        targets_data = cursor.fetchall()
    else:
        cursor.execute("SELECT chat_id, lang FROM targets WHERE lang=?", (target_lang,))
        targets_data = cursor.fetchall()

    if not targets_data:
        await message.reply("⚠️ هیچ کاربری برای این زبان پیدا نشد.")
        return

    sent_count, failed_count = 0, 0

    for uid, lang in targets_data:
        msg_to_send = text

        # اگر متن RANDOM است، یکی از تبلیغ‌های همان زبان را انتخاب کن
        if text.upper() == "RANDOM":
            msg_to_send = get_random_ad(lang)

        try:
            await bot.send_message(uid, msg_to_send[:4000])
            sent_count += 1
            await asyncio.sleep(0.5)
        except Exception as e:
            failed_count += 1
            cursor.execute(
                "INSERT OR REPLACE INTO failed_targets (chat_id, reason) VALUES (?, ?)",
                (uid, str(e))
            )
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
#+++=============================================================
# ───── آپلود فایل از userbot یا از بات اصلی ─────
routes = web.RouteTableDef()

@routes.post("/upload")
async def upload(request):
    key = request.headers.get("X-Upload-Key")
    if key != os.getenv("UPLOAD_KEY"):
        return web.Response(text="Invalid key", status=403)

    data = await request.post()
    file = data["file"]
    with open("new_users.json", "wb") as f:
        f.write(file.file.read())

    return web.Response(text="Main upload OK")

@routes.post("/user_upload")
async def user_upload(request):
    key = request.headers.get("X-Upload-Key")
    if key != os.getenv("UPLOAD_KEY_USERBOT"):
        return web.Response(text="Invalid key", status=403)

    data = await request.post()
    file = data["file"]
    with open("userbot_users.json", "wb") as f:
        f.write(file.file.read())

    return web.Response(text="Userbot upload OK")

def main():
    app = web.Application()
    app.add_routes(routes)
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, on_startup=on_startup, on_shutdown=on_shutdown)


    async def home(request):
        return web.Response(text="Bot is alive ✅")

    app.router.add_get("/", home)

    # مسیر وبهوک برای دریافت آپدیت‌ها از تلگرام
    async def handle_webhook(request):
        data = await request.json()
        update = types.Update(**data)
        await dp.feed_update(bot, update)
        return web.Response(text="ok")



    app.router.add_get("/dashboard", dashboard)
    app.router.add_post("/upload_db", upload_db)
    app.router.add_get("/health", health)

    web.run_app(app, host=WEBAPP_HOST, port=WEBAPP_PORT)

if __name__ == "__main__":
    main()
