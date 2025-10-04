import os
import sqlite3
import asyncio
import re
import requests
from telethon import TelegramClient
from dotenv import load_dotenv

load_dotenv()

os.makedirs("session", exist_ok=True)

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
UPLOAD_URL = os.getenv("UPLOAD_URL")
UPLOAD_KEY = os.getenv("UPLOAD_KEY")

DB_NAME = "targets.db"
client = TelegramClient("session/userbot_session", API_ID, API_HASH)

# دیتابیس
conn = sqlite3.connect(DB_NAME)
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

# تشخیص زبان
def detect_language(text: str) -> str:
    if re.search(r'[\u0600-\u06FF]', text):
        return "IR"
    elif re.search(r'[\u0400-\u04FF]', text):
        return "RU"
    else:
        return "EN"

async def collect_members(group_input):
    try:
        group = await client.get_entity(group_input)  # تبدیل ID یا username به entity
        async for user in client.iter_participants(group):
                lang = detect_language(user.first_name or "")
                cursor.execute("""
                INSERT OR IGNORE INTO targets (chat_id, username, first_name, last_name, lang)
                VALUES (?, ?, ?, ?, ?)
                """, (user.id, user.username, user.first_name, user.last_name, lang))
                conn.commit()
                print(f"[INFO] Saved {user.id} @{user.username} [{lang}]")
    except Exception as e:
        print(f"[ERROR] {group_input} → {e}")

        #async def collect_members(group_link: str):
    #async for user in client.iter_participants(group_link):
        # زبان فرضی از نام کاربر یا username
        #lang = detect_language(user.first_name or "")
        #cursor.execute("""
        #INSERT OR IGNORE INTO targets (chat_id, username, first_name, last_name, lang)
        #VALUES (?, ?, ?, ?, ?)
        #""", (user.id, user.username, user.first_name, user.last_name, lang))
        #conn.commit()
        #print(f"[INFO] Saved {user.id} @{user.username} [{lang}]")

def upload_db():

    load_dotenv()
    UPLOAD_URL = os.getenv("UPLOAD_URL")
    UPLOAD_KEY = os.getenv("UPLOAD_KEY")

    if not UPLOAD_URL or not UPLOAD_KEY:
        print("[ERROR] اطلاعات فایل env ناقصه.")
        return

    try:
        with open("targets.db", "rb") as f:
            response = requests.post(
                UPLOAD_URL,
                files={"file": f},
                headers={"Authorization": f"Bearer {UPLOAD_KEY}"}
            )
        print(f"[INFO] DB upload response: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"[ERROR] ارسال دیتابیس ناموفق بود: {e}")


async def main():
    groups = [
        -1002753708099, -1002753043593# به صورت عددی
    ]
    #for g in groups:
        #await collect_members(g)
    while True:
        for g in groups:
            try:
                await collect_members(g)
            except Exception as e:
                print(f"[ERROR] هنگام پردازش گروه {g}: {e}")

        with open(DB_NAME, "rb") as f:
            resp = requests.post(
                UPLOAD_URL,
                headers={"Authorization": UPLOAD_KEY},
                files={"file": f}
            )
            print(f"[INFO] DB upload response: {resp.status_code} - {resp.text}")

        #try:
            #upload_db()  # بدون await چون sync هست
       # except Exception as e:
           # print(f"[ERROR] در ارسال دیتابیس: {e}")

        print("[INFO] در حال استراحت برای دور بعدی...\n")
        await asyncio.sleep(10)  # 30 دقیقه استراحت


     # آپلود دیتابیس به Bot
with open(DB_NAME, "rb") as f:
    resp = requests.post(
        UPLOAD_URL,
        headers={"Authorization": UPLOAD_KEY},
        files={"file": f}
        )
    print(f"[INFO] DB upload response: {resp.status_code} - {resp.text}")

with client:
    client.loop.run_until_complete(main())
