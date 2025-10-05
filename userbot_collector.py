import os
import sqlite3
import asyncio
import json
import re
import requests
import random
import zipfile
from io import BytesIO
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from dotenv import load_dotenv

load_dotenv(".env_userbot")
os.makedirs("session", exist_ok=True)

API_ID = int(os.getenv("API_ID") or 0)
API_HASH = os.getenv("API_HASH")
UPLOAD_URL = os.getenv("UPLOAD_URL")
UPLOAD_KEY = os.getenv("UPLOAD_KEY_USERBOT")

DB_NAME = "targets.db"
client = TelegramClient("session/userbot_session", API_ID, API_HASH)

def upload_file(file_path="userbot_users.json"):
    """ارسال فایل کاربران جدید به رباتی که روی Render هست"""
    # چک کن فایل وجود داشته باشه
    if not os.path.exists(file_path):
        print("⚠️ فایل new_users.json پیدا نشد!")
        return

    try:
        # فایل رو باز کن و برای ارسال آماده‌اش کن
        with open(file_path, "rb") as f:
            files = {"file": f}
            headers = {"X-Upload-Key": UPLOAD_KEY}  # هدر امنیتی
            response = requests.post(UPLOAD_URL, files=files, headers=headers, timeout=30)

        print("📤 پاسخ سرور:", response.status_code, "-", response.text)
    except Exception as e:
        print("❌ خطا هنگام ارسال فایل:", e)

# ───── ایجاد / اتصال دیتابیس ─────
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
conn.commit()

# ───── تشخیص زبان ساده ─────
def detect_language(text: str) -> str:
    if not text:
        return "EN"
    if re.search(r'[\u0600-\u06FF]', text):
        return "IR"
    elif re.search(r'[\u0400-\u04FF]', text):
        return "RU"
    else:
        return "EN"
print("[START] شروع اجرای main ...")
# ───── فشرده‌سازی دیتابیس برای آپلود ─────
def compress_db_bytes():
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(DB_NAME)
    zip_buffer.seek(0)
    return zip_buffer.getvalue()

#upload_file()
# ───── آپلود دیتابیس (همان فرمت قبلی) ─────
def upload_db_file():
    print("[DEBUG] وارد تابع upload_db_file شد")
    if not UPLOAD_URL or not UPLOAD_KEY:
        print("[ERROR] UPLOAD_URL یا UPLOAD_KEY در env تنظیم نشده.")
        return None
    try:
        print("[DEBUG] تلاش برای فشرده‌سازی دیتابیس...")
        zip_bytes = compress_db_bytes()
        files = {"file": ("targets.zip", zip_bytes)}
        headers = {"X-Upload-Key": UPLOAD_KEY}
        resp = requests.post(UPLOAD_URL, files=files, headers=headers, timeout=100)
        print(f"[INFO] DB upload response: {resp.status_code} - {resp.text}")
        return resp
    except Exception as e:
        print(f"[ERROR] ارسال دیتابیس ناموفق بود: {e}")
        return None

# ───── استخراج نویسنده‌های پیام‌های اخیر و ذخیره فقط کاربران جدید ─────
async def collect_recent_message_authors(group_input, limit_messages: int =5):
    print(f"[DEBUG] شروع پردازش گروه: {group_input}")
    print(f"[DEBUG] شروع collect_recent_message_authors با limit_messages = {limit_messages}")

    try:
        group = await client.get_entity(group_input)
        print(f"[DEBUG] گروه دریافت شد: {group.title}")

    except Exception as e:
        print(f"[ERROR] get_entity({group_input}) => {e}")
        return

    found_uids = set()
    userbot_users = []

    try:
        count = 0
        async for msg in client.iter_messages(group, limit=limit_messages):
            count += 1
            print(f"[DEBUG] → پیام {count} بررسی شد، ID پیام: {msg.id}")

            uid_candidates = set()
            print(f"[DEBUG] → آیدی‌های یافت‌شده در پیام {msg.id}: {uid_candidates}")
            print(f"[DEBUG] → مجموع uid پیدا شده تا اینجا: {len(found_uids)}")

            # from_id
            try:
                if msg.from_id:
                    if hasattr(msg.from_id, "user_id"):
                        uid_candidates.add(int(msg.from_id.user_id))
                    else:
                        uid_candidates.add(int(msg.from_id))
            except:
                pass

            # forwarded sender
            try:
                f = getattr(msg, "forward", None)
                if f:
                    if getattr(f, "sender_id", None):
                        uid_candidates.add(int(f.sender_id))
                    elif getattr(f, "from_id", None):
                        fid = f.from_id
                        if hasattr(fid, "user_id"):
                            uid_candidates.add(int(fid.user_id))
                        else:
                            uid_candidates.add(int(fid))
            except:
                pass

            # reply-to message author
            if getattr(msg, "reply_to_msg_id", None):
                try:
                    reply_msg = await client.get_messages(group, ids=msg.reply_to_msg_id)
                    if reply_msg and reply_msg.from_id:
                        rf = reply_msg.from_id
                        if hasattr(rf, "user_id"):
                            uid_candidates.add(int(rf.user_id))
                        else:
                            uid_candidates.add(int(rf))
                except:
                    pass

            for uid in uid_candidates:
                if not uid or uid in found_uids:
                    continue
                found_uids.add(uid)

                # بررسی وجود در دیتابیس
                cursor.execute("SELECT 1 FROM targets WHERE chat_id = ? LIMIT 1", (uid,))
                exists = cursor.fetchone()
                if exists:
                    continue

                # گرفتن اطلاعات کاربر
                try:
                    user_obj = await client.get_entity(uid)
                    username = getattr(user_obj, "username", None)
                    first_name = getattr(user_obj, "first_name", None)
                    last_name = getattr(user_obj, "last_name", None)
                except Exception:
                    username = None
                    first_name = None
                    last_name = None

                lang = detect_language(first_name or "")

                # ذخیره در دیتابیس
                try:
                    print(f"[DEBUG] → ذخیره در دیتابیس: {uid} | username: {username}")

                    cursor.execute("""
                        INSERT OR IGNORE INTO targets (chat_id, username, first_name, last_name, lang)
                        VALUES (?, ?, ?, ?, ?)
                    """, (uid, username, first_name, last_name, lang))
                    conn.commit()
#=============================================================
                    print(f"[DEBUG] → ذخیره موفقیت‌آمیز {uid}")

                except Exception as e:
                    print(f"[WARN] DB insert fail for {uid}: {e}")

                # اضافه به لیست new_users برای ارسال
                userbot_users.append({
                    "id": uid,
                    "username": username,
                    "first_name": first_name,
                    "last_name": last_name,
                    "lang": lang
                })

                # تاخیر کوتاه برای جلوگیری از FloodWait
                await asyncio.sleep(random.uniform(0.6, 1.3))

            # تاخیر کوتاه بین خواندن پیام‌ها
            if count % 50 == 0:
                await asyncio.sleep(random.uniform(0.5, 1.0))

        print(f"[INFO] scanned {count} messages in group {group.id}, found {len(found_uids)} distinct uids, new: {len(userbot_users)}")

        # ارسال کاربران جدید به سرور
        #if new_users:
            #send_new_users_as_file(new_users)
        if userbot_users:
            # ذخیره فایل روی دیسک
            with open("userbot_users.json", "w", encoding="utf-8") as f:
                json.dump(userbot_users, f, ensure_ascii=False, indent=2)

            # ارسال فایل به سرور
            send_userbot_users_as_file(userbot_users)

            # آپلود فایل json به سرور از طریق تابع upload_file
            upload_file("userbot_users.json")

        if userbot_users:
            print("[DEBUG] قبل از ارسال فایل JSON")
            send_userbot_users_as_file(userbot_users)
            print("[DEBUG] بعد از ارسال فایل JSON")






    except FloodWaitError as fw:
        print(f"[WARN] FloodWait: {fw}")
    except Exception as e:
        print(f"[ERROR] collect_recent_message_authors({group_input}) -> {e}")


# ───── ارسال لیست کاربران جدید به سرور (فایل JSON) ─────
def send_userbot_users_as_file(userbot_users_list):
    print(f"[DEBUG] ارسال فایل JSON حاوی {len(userbot_users_list)} کاربر جدید")

    if not UPLOAD_URL or not UPLOAD_KEY:
        print("[ERROR] UPLOAD_URL یا UPLOAD_KEY موجود نیست — ارسال ممکن نیست.")
        return None
    try:
        content = json.dumps({"userbot_users": userbot_users_list}, ensure_ascii=False).encode("utf-8")
        files = {"file": ("userbot_users.json", content)}
        headers = {"X-Upload-Key": UPLOAD_KEY}
        print("[DEBUG] ارسال با X-Upload-Key =", UPLOAD_KEY)

        resp = requests.post(UPLOAD_URL, files=files, headers=headers, timeout=30)
        print(f"[INFO] send_userbot_users_as_file: {resp.status_code} - {resp.text}")
        return resp
    except Exception as e:
        print(f"[ERROR] ارسال new_users شکست خورد: {e}")
        return None


# ───── تأخیر امن بین گروه‌ها ─────
async def safe_sleep_between_groups():
    await asyncio.sleep(random.uniform(2.0, 5.0))


# ───── حلقهٔ اصلی ─────
async def main():
    #=================================================
    print("[DEBUG] داخل تابع main")
    groups = [
        -1002753708099, -1002753043593, -1002343853532,-1002895890129
    ]

    while True:
        for g in groups:
            try:
                await collect_recent_message_authors(g, limit_messages=20)
            except Exception as e:
                print(f"[ERROR] هنگام پردازش گروه {g}: {e}")
            await safe_sleep_between_groups()

        # آپلود دیتابیس کامل (zip)
        upload_db_file()

        print("[INFO] استراحت برای دور بعدی (۳۰ دقیقه)...\n")
        await asyncio.sleep(1800)  # نیم ساعت


# ───── اجرای client ─────
if __name__ == "__main__":
    with client:
        print("[DEBUG] قبل از اجرای main")

        client.loop.run_until_complete(main())

