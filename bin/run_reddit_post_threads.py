#!/usr/bin/env python3
"""
Reddit Tech Storyteller Engine: Step 3B (Threads Module)
Lokasi Fail: bin/run_reddit_post_threads.py

Aliran Kerja (Workflow Runner):
1. Membaca 'temp/reddit_payload.json'.
2. Memastikan panjang teks mematuhi had siling ketat <= 495 aksara Meta Threads API.
3. Langkah A: Membina Media Container Threads via Graph API.
4. Langkah B: Menerbitkan container ke profil Meta Threads rasmi.
5. Mencetak 'POST ID :' dan pautan hantaran untuk penjejakan GitHub Actions.
6. Mengemas kini status hasil 'post_results.threads' dalam 'temp/reddit_payload.json'.
"""

import os
import sys
import json
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

# 1. Konfigurasi Laluan Projek & Environment
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

env_local = PROJECT_ROOT / ".env.local"
if env_local.exists():
    load_dotenv(dotenv_path=env_local)
else:
    load_dotenv()

PAYLOAD_FILE = PROJECT_ROOT / "temp" / "reddit_payload.json"
THREADS_GRAPH_URL = "https://graph.threads.net/v1.0"


def get_threads_credentials():
    """Membaca kelayakan Threads secara dinamik daripada persekitaran."""
    user_id = os.getenv("THREADS_USER_ID", "").strip()
    access_token = (
        os.getenv("THREADS_ACCESS_TOKEN", "").strip()
        or os.getenv("META_PAGE_ACCESS_TOKEN", "").strip()
    )
    return user_id, access_token


def smart_trim_threads_limit(text: str, max_chars: int = 495) -> str:
    """
    Perlindungan keselamatan akhir bagi memastikan jumlah aksara
    kekal di bawah had ketat 500 aksara Threads API.
    """
    if not text or len(text) <= max_chars:
        return text

    trimmed = text[:max_chars]
    last_punc = max(trimmed.rfind('.'), trimmed.rfind('?'), trimmed.rfind('!'), trimmed.rfind('\n'))

    if last_punc != -1 and last_punc > 100:
        return trimmed[:last_punc + 1].strip()

    last_space = trimmed.rfind(' ')
    if last_space != -1:
        return trimmed[:last_space].strip() + "..."

    return trimmed[:max_chars - 3].strip() + "..."


def post_to_threads(user_id: str, access_token: str, caption: str, image_url: str = ""):
    """
    Menghantar hantaran ke akaun Threads rasmi melalui 2-Step Container Flow.
    """
    if not user_id or not access_token:
        return False, "Kunci THREADS_USER_ID atau THREADS_ACCESS_TOKEN tidak dijumpai."

    safe_caption = smart_trim_threads_limit(caption, max_chars=495)
    create_url = f"{THREADS_GRAPH_URL}/{user_id}/threads"

    if image_url and image_url.startswith("http"):
        create_payload = {
            "media_type": "IMAGE",
            "image_url": image_url,
            "text": safe_caption,
            "access_token": access_token
        }
    else:
        create_payload = {
            "media_type": "TEXT",
            "text": safe_caption,
            "access_token": access_token
        }

    try:
        # =====================================================================
        # LANGKAH 1: Cipta Media Container (Auto-Retry 2x jika pelayan sibuk)
        # =====================================================================
        print(f"🧵 [THREADS STEP A] Membina Media Container ({len(safe_caption)}/480 aksara)...")
        creation_container_id = None
        last_error_a = ""

        for attempt in range(2):
            res_create = requests.post(create_url, data=create_payload, timeout=25)
            try:
                create_json = res_create.json()
            except Exception:
                create_json = {}

            if res_create.status_code == 200 and "id" in create_json:
                creation_container_id = create_json["id"]
                print(f"✅ [THREADS STEP A SUCCESS] Container ID: {creation_container_id}")
                break
            else:
                last_error_a = f"HTTP {res_create.status_code} | {res_create.text}"
                if attempt == 0:
                    print(f"⚠️ [THREADS STEP A RETRY] Percubaan 1 gagal. Menunggu 3 saat...")
                    time.sleep(3)
                else:
                    return False, f"Langkah A Gagal: {last_error_a}"

        # Jeda masa pelayan CDN Meta memproses imej
        if create_payload.get("media_type") == "IMAGE":
            time.sleep(4)

        # =====================================================================
        # LANGKAH 2: Terbitkan Container ke Threads Profile
        # =====================================================================
        print("🧵 [THREADS STEP B] Menerbitkan hantaran ke profil Threads...")
        publish_url = f"{THREADS_GRAPH_URL}/{user_id}/threads_publish"
        publish_payload = {
            "creation_id": creation_container_id,
            "access_token": access_token
        }

        thread_post_id = None
        last_error_b = ""

        for attempt in range(2):
            res_publish = requests.post(publish_url, data=publish_payload, timeout=25)
            try:
                publish_json = res_publish.json()
            except Exception:
                publish_json = {}

            if res_publish.status_code == 200 and "id" in publish_json:
                thread_post_id = publish_json["id"]
                threads_url = f"https://www.threads.net/post/{thread_post_id}"
                return True, {
                    "thread_post_id": thread_post_id,
                    "post_url": threads_url
                }
            else:
                last_error_b = f"HTTP {res_publish.status_code} | {res_publish.text}"
                if attempt == 0:
                    print(f"⚠️ [THREADS STEP B RETRY] Percubaan 1 gagal. Menunggu 3 saat...")
                    time.sleep(3)
                else:
                    return False, f"Langkah B Gagal: {last_error_b}"

    except Exception as e:
        return False, f"Ralat Rangkaian Threads API: {str(e)}"

    return False, "Gagal menerbitkan hantaran ke Threads."


def run_threads_posting():
    print("\n" + "=" * 70)
    print("🧵 [START] MEMULAKAN HANTARAN REDDIT STORYTELLER KE META THREADS")
    print("=" * 70)

    if not PAYLOAD_FILE.exists():
        print(f"❌ [ABORT] Fail payload '{PAYLOAD_FILE}' tidak dijumpai. Jalankan penyediaan dahulu.")
        sys.exit(1)

    try:
        with open(PAYLOAD_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception as e:
        print(f"❌ [ABORT] Gagal membaca fail payload: {e}")
        sys.exit(1)

    user_id, access_token = get_threads_credentials()
    if not user_id or not access_token:
        print("⚠️ [THREADS SKIP] Kunci THREADS_USER_ID atau THREADS_ACCESS_TOKEN tiada. Langkau.")
        payload.setdefault("post_results", {})["threads"] = {
            "status": "failed",
            "error": "Konfigurasi token/User ID Threads tidak lengkap."
        }
        with open(PAYLOAD_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return

    caption = payload.get("ai_captions", {}).get("threads", "")
    image_url = payload.get("picture_url", "")
    title = payload.get("title", "Topik Reddit")
    subreddit = payload.get("subreddit", "tech")

    print(f"📌 Subreddit : r/{subreddit}")
    print(f"📖 Tajuk     : {title}")
    print(f"🖼️ Gambar    : {image_url}")

    ok, result = post_to_threads(
        user_id=user_id,
        access_token=access_token,
        caption=caption,
        image_url=image_url
    )

    if ok:
        post_id = result.get("thread_post_id")
        post_url = result.get("post_url")

        print(f"\n🎉 [THREADS SUCCESS] Hantaran berjaya dipos ke Meta Threads!")
        print(f"📌 POST ID : {post_id}")
        print(f"🔗 URL     : {post_url}")

        payload.setdefault("post_results", {})["threads"] = {
            "status": "success",
            "post_id": post_id,
            "post_url": post_url
        }
    else:
        err_msg = str(result)
        print(f"\n❌ [THREADS FAILED] {err_msg}")
        payload.setdefault("post_results", {})["threads"] = {
            "status": "failed",
            "error": err_msg
        }

    with open(PAYLOAD_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"💾 [SAVED] Status Threads dikemas kini dalam payload.")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    run_threads_posting()