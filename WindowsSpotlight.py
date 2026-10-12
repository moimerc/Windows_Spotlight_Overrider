import json
import os
import shutil
import subprocess
import time
import sys
from datetime import datetime, date

# ============================================================
# Configuration
# ============================================================
DOWNLOAD_DIR = r"C:\Path\To\Your\Archive\Folder"

# Windows Lock Screen cache path (Replace YOUR_USER_SID with your actual SID)
READONLY_DIR = r"C:\ProgramData\Microsoft\Windows\SystemData\<YOUR_USER_SID>\ReadOnly"

# Log file path
LOG_FILE = os.path.join(DOWNLOAD_DIR, "bing_lock_screen_log.txt")

API_MAX_RETRIES = 8          # Maximum API retry attempts
API_RETRY_DELAY = 45         # Delay between retries in seconds
CURL_API_TIMEOUT = 20        # API call timeout
CURL_IMG_TIMEOUT = 90        # Image download timeout (UHD may take longer)
RUN_ONCE_PER_DAY = True      # Limit execution to once per day


def log_message(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except OSError:
        pass


def flush_dns():
    """Flush DNS cache to resolve potential network errors (curl code 6)"""
    try:
        subprocess.run(
            ["ipconfig", "/flushdns"],
            capture_output=True, timeout=10
        )
        log_message("DNS cache flushed.")
        time.sleep(2)
    except Exception as e:
        log_message(f"Failed to flush DNS: {e}")


def already_ran_today():
    if not os.path.exists(DOWNLOAD_DIR):
        return False
    today_prefix = f"bing_{date.today().strftime('%Y%m%d')}_"
    for f in os.listdir(DOWNLOAD_DIR):
        if f.startswith(today_prefix) and f.lower().endswith(".jpg"):
            return True
    return False


def fetch_bing_image_url():
    url = "https://www.bing.com/HPImageArchive.aspx?format=js&idx=0&n=1&mkt=en-US"

    for attempt in range(API_MAX_RETRIES):
        try:
            result = subprocess.run(
                ["curl.exe", "-sf", "--max-time", str(CURL_API_TIMEOUT),
                 "-A", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                 url],
                capture_output=True, text=True, timeout=CURL_API_TIMEOUT + 10
            )

            if result.returncode != 0:
                # Flush DNS and retry if DNS resolution fails (code 6)
                if result.returncode == 6:
                    log_message(f"API DNS failed (Attempt {attempt+1}/{API_MAX_RETRIES}) → Flushing DNS")
                    flush_dns()
                raise RuntimeError(f"curl exit code {result.returncode}")

            if not result.stdout.strip():
                raise ValueError("Empty API response.")

            data = json.loads(result.stdout)
            urlbase = data["images"][0]["urlbase"]
            log_message(f"Bing API request successful (Attempt {attempt + 1})")
            return urlbase

        except Exception as e:
            log_message(f"API request failed (Attempt {attempt + 1}/{API_MAX_RETRIES}): {e}")
            if attempt < API_MAX_RETRIES - 1:
                time.sleep(API_RETRY_DELAY)

    return None


def download_image(urlbase, save_path):
    suffixes = ["_UHD.jpg", "_1920x1080.jpg"]

    for suffix in suffixes:
        image_url = "https://www.bing.com" + urlbase + suffix
        log_message(f"Attempting download: {suffix}")

        for attempt in range(3):  # Max 3 attempts per resolution
            try:
                result = subprocess.run(
                    ["curl.exe", "-sf", "--max-time", str(CURL_IMG_TIMEOUT),
                     "-o", save_path,
                     "-A", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                     image_url],
                    capture_output=True, text=True, timeout=CURL_IMG_TIMEOUT + 15
                )

                if result.returncode == 0 and os.path.exists(save_path) and os.path.getsize(save_path) > 10000:
                    log_message(f"Download successful: {os.path.basename(save_path)}")
                    return True

                if result.returncode == 6:
                    log_message(f"Download DNS failed ({suffix}) → Flushing DNS")
                    flush_dns()
                else:
                    log_message(f"Download failed ({suffix}): exit code {result.returncode}")

            except Exception as e:
                log_message(f"Download exception ({suffix}): {e}")

            if attempt < 2:
                time.sleep(10)

    return False


def replace_cache_images(source_image):
    if not os.path.exists(READONLY_DIR):
        log_message(f"ReadOnly directory not found: {READONLY_DIR}")
        return False

    replaced = 0
    for folder_name in os.listdir(READONLY_DIR):
        if not folder_name.startswith("LockScreen_"):
            continue

        cache_dir = os.path.join(READONLY_DIR, folder_name)
        if not os.path.isdir(cache_dir):
            continue

        log_message(f"Processing cache folder: {cache_dir}")
        for file in os.listdir(cache_dir):
            if not file.lower().endswith((".jpg", ".jpeg", ".png")):
                continue

            target_file = os.path.join(cache_dir, file)
            try:
                subprocess.run(["attrib", "-r", target_file], capture_output=True)
                shutil.copy2(source_image, target_file)
                replaced += 1
                log_message(f"  Cache replaced successfully: {folder_name}\\{file}")
            except Exception as e:
                log_message(f"  Cache replacement failed ({folder_name}\\{file}): {e}")

    return replaced > 0


def main():
    log_message("=== Lock Screen Cache Override & Archiving Started ===")

    if RUN_ONCE_PER_DAY and already_ran_today():
        log_message("Already ran today. Skipping execution.")
        log_message("=== Task Finished (Skipped) ===\n")
        return 0

    # Short delay to ensure network readiness upon boot/unlock
    time.sleep(5)

    urlbase = fetch_bing_image_url()
    if not urlbase:
        log_message("Final API request failed. Returning exit code 1 for scheduler retry.")
        return 1

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_image_path = os.path.join(DOWNLOAD_DIR, f"bing_{timestamp}.jpg")

    if not download_image(urlbase, new_image_path):
        log_message("Image download failed. Returning exit code 1 for scheduler retry.")
        return 1

    if not replace_cache_images(new_image_path):
        log_message("Cache replacement failed.")
        return 1

    subprocess.run(["taskkill", "/f", "/im", "LockApp.exe"], capture_output=True)
    log_message("LockApp.exe terminated. New image will display on Win+L.")
    log_message("=== Task Completed ===\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())