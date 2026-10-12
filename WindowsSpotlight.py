import json
import os
import shutil
import subprocess
import time
import sys
from datetime import datetime, date

# ============================================================
# 설정
# ============================================================
DOWNLOAD_DIR = r"C:\Path\To\Your\Archive\Folder"

# Windows 잠금 화면 캐시 경로 (YOUR_USER_SID 부분을 본인 PC의 SID로 변경해야 합니다)
READONLY_DIR = r"C:\ProgramData\Microsoft\Windows\SystemData\<YOUR_USER_SID>\ReadOnly"
LOG_FILE = os.path.join(DOWNLOAD_DIR, "bing_lock_screen_log.txt")

API_MAX_RETRIES = 8          # API 호출 최대 재시도 횟수
API_RETRY_DELAY = 45         # 재시도 대기 시간 (초)
CURL_API_TIMEOUT = 20        # API 호출 타임아웃
CURL_IMG_TIMEOUT = 90        # 이미지 다운로드 타임아웃
RUN_ONCE_PER_DAY = True      # 하루에 한 번만 실행되도록 제한할지 여부


def log_message(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except OSError:
        pass


def flush_dns():
    """DNS 캐시 플러시 (코드 6 대응)"""
    try:
        subprocess.run(
            ["ipconfig", "/flushdns"],
            capture_output=True, timeout=10
        )
        log_message("DNS 캐시 플러시 실행")
        time.sleep(2)
    except Exception as e:
        log_message(f"DNS 플러시 실패: {e}")


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
                # DNS 실패(코드 6)면 플러시 후 재시도
                if result.returncode == 6:
                    log_message(f"API DNS 실패 (시도 {attempt+1}/{API_MAX_RETRIES}) → DNS 플러시")
                    flush_dns()
                raise RuntimeError(f"curl 반환 코드 {result.returncode}")

            if not result.stdout.strip():
                raise ValueError("API 응답이 비어 있습니다.")

            data = json.loads(result.stdout)
            urlbase = data["images"][0]["urlbase"]
            log_message(f"Bing API 요청 성공 (시도 {attempt + 1})")
            return urlbase

        except Exception as e:
            log_message(f"API 요청 실패 (시도 {attempt + 1}/{API_MAX_RETRIES}): {e}")
            if attempt < API_MAX_RETRIES - 1:
                time.sleep(API_RETRY_DELAY)

    return None


def download_image(urlbase, save_path):
    suffixes = ["_UHD.jpg", "_1920x1080.jpg"]

    for suffix in suffixes:
        image_url = "https://www.bing.com" + urlbase + suffix
        log_message(f"다운로드 시도: {suffix}")

        for attempt in range(3):  # 각 해상도별로 최대 3번
            try:
                result = subprocess.run(
                    ["curl.exe", "-sf", "--max-time", str(CURL_IMG_TIMEOUT),
                     "-o", save_path,
                     "-A", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                     image_url],
                    capture_output=True, text=True, timeout=CURL_IMG_TIMEOUT + 15
                )

                if result.returncode == 0 and os.path.exists(save_path) and os.path.getsize(save_path) > 10000:
                    log_message(f"다운로드 성공: {os.path.basename(save_path)}")
                    return True

                if result.returncode == 6:
                    log_message(f"다운로드 DNS 실패 ({suffix}) → DNS 플러시")
                    flush_dns()
                else:
                    log_message(f"다운로드 실패 ({suffix}): 반환 코드 {result.returncode}")

            except Exception as e:
                log_message(f"다운로드 예외 ({suffix}): {e}")

            if attempt < 2:
                time.sleep(10)

    return False


def replace_cache_images(source_image):
    if not os.path.exists(READONLY_DIR):
        log_message(f"ReadOnly 경로를 찾을 수 없음: {READONLY_DIR}")
        return False

    replaced = 0
    for folder_name in os.listdir(READONLY_DIR):
        if not folder_name.startswith("LockScreen_"):
            continue

        cache_dir = os.path.join(READONLY_DIR, folder_name)
        if not os.path.isdir(cache_dir):
            continue

        log_message(f"캐시 폴더 처리: {cache_dir}")
        for file in os.listdir(cache_dir):
            if not file.lower().endswith((".jpg", ".jpeg", ".png")):
                continue

            target_file = os.path.join(cache_dir, file)
            try:
                subprocess.run(["attrib", "-r", target_file], capture_output=True)
                shutil.copy2(source_image, target_file)
                replaced += 1
                log_message(f"  캐시 교체 성공: {folder_name}\\{file}")
            except Exception as e:
                log_message(f"  캐시 교체 실패 ({folder_name}\\{file}): {e}")

    return replaced > 0


def main():
    log_message("=== 잠금 화면 캐시 교체 + 이미지 보관 시작 ===")

    if RUN_ONCE_PER_DAY and already_ran_today():
        log_message("오늘 이미 실행됨. 작업을 건너뜁니다.")
        log_message("=== 작업 종료 (스킵) ===\n")
        return 0

    # 네트워크가 아직 준비 안 됐을 수 있으니 잠깐 대기
    time.sleep(5)

    urlbase = fetch_bing_image_url()
    if not urlbase:
        log_message("최종 API 요청 실패. 스케줄러 재시도를 위해 종료 코드 1 반환.")
        return 1

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_image_path = os.path.join(DOWNLOAD_DIR, f"bing_{timestamp}.jpg")

    if not download_image(urlbase, new_image_path):
        log_message("이미지 다운로드 실패. 스케줄러 재시도를 위해 종료 코드 1 반환.")
        return 1

    if not replace_cache_images(new_image_path):
        log_message("캐시 교체 실패.")
        return 1

    subprocess.run(["taskkill", "/f", "/im", "LockApp.exe"], capture_output=True)
    log_message("LockApp.exe 종료. Win+L에서 새 이미지가 표시됩니다.")
    log_message("=== 작업 완료 ===\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())