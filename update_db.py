import asyncio
import subprocess
import time

INTERVAL_HOURS = 6
USERBOT_SCRIPT = "userbot_collector.py"

def run_userbot():
    print("[INFO] اجرای userbot برای جمع‌آوری اعضا...")
    result = subprocess.run(["python3", USERBOT_SCRIPT], capture_output=True, text=True)
    if result.returncode == 0:
        print("[INFO] اجرا با موفقیت انجام شد.")
    else:
        print(f"[ERROR] خطا در اجرا:\n{result.stderr}")

def main():
    while True:
        run_userbot()
        print(f"[INFO] انتظار {INTERVAL_HOURS} ساعت قبل از اجرای بعدی...")
        time.sleep(INTERVAL_HOURS * 3600)

if __name__ == "__main__":
    main()
