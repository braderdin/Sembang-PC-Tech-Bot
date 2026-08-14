#!/usr/bin/env python3
"""
Live Test Post Script for Meta Instagram Graph API
Sembang PC & Tech Ecosystem
"""

import os
import sys
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

# 1. Muat naik pembolehubah persekitaran (.env.local diutamakan)
root_dir = Path(__file__).resolve().parent.parent.parent
env_local_path = root_dir / ".env.local"
env_path = root_dir / ".env"

if env_local_path.exists():
    load_dotenv(dotenv_path=env_local_path)
    print(f"📄 Memuatkan konfigurasi dari: {env_local_path.name}")
elif env_path.exists():
    load_dotenv(dotenv_path=env_path)
    print(f"📄 Memuatkan konfigurasi dari: {env_path.name}")
else:
    load_dotenv()
    print("⚠️ Fail .env/.env.local tidak dijumpai, membaca persekitaran sistem.")

# 2. Ambil Kunci Instagram
IG_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID", "").strip()
IG_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "").strip()

GRAPH_API_VERSION = "v26.0"
GRAPH_BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

# Gambar setup meja PC estetik dari Unsplash (Resolusi 1080x1080)
TEST_IMAGE_URL = (
    "https://images.unsplash.com/photo-1526738549149-8e07eca6c147?q=80&w=1080&auto=format&fit=crop"
)

TEST_CAPTION = """🧪 Test Post API Automasi dari Sembang PC & Tech Malaysia! ⚡💻

Jika anda nampak gambar setup meja kemas ni, maksudnya enjin Meta Graph API Instagram kita dah 100% berjaya berfungsi dan bersedia untuk auto-posting harian! 🔥

Port lepak gajet, racun perkakasan PC & lifestyle meja kemas. 🇲🇾

#SembangPCTech #TechMalaysia #PCSetup #DeskSetup #GamingSetup #AutomationTest #WorkspaceGoals"""


def create_instagram_post(image_url: str, caption: str):
    print("\n" + "=" * 60)
    print("🚀 MEMULAKAN UJIAN POSTING SEBENAR KE INSTAGRAM")
    print("=" * 60)

    if not IG_ACCOUNT_ID or not IG_ACCESS_TOKEN:
        print("❌ Ralat: INSTAGRAM_ACCOUNT_ID atau INSTAGRAM_ACCESS_TOKEN tiada di .env.local!")
        return False

    print(f"👤 Account ID  : {IG_ACCOUNT_ID}")
    print(f"🖼️ Image URL   : {image_url}")
    print(f"📝 Caption     : {caption[:60]}...")
    print("-" * 60)

    # ---------------------------------------------------------
    # LANGKAH 1: Cipta Media Container (Upload Container)
    # ---------------------------------------------------------
    print("\n📦 [Langkah 1/3] Menghantar media container ke Instagram...")
    container_url = f"{GRAPH_BASE_URL}/{IG_ACCOUNT_ID}/media"
    container_params = {
        "image_url": image_url,
        "caption": caption,
        "access_token": IG_ACCESS_TOKEN,
    }

    try:
        res_container = requests.post(container_url, data=container_params, timeout=30)
        res_json = res_container.json()

        if res_container.status_code != 200 or "id" not in res_json:
            print(f"❌ Gagal mencipta media container ({res_container.status_code}):")
            print(f"   {res_json.get('error', {}).get('message', res_json)}")
            return False

        creation_id = res_json["id"]
        print(f"✅ Container Berjaya Dicipta! ID: {creation_id}")

    except requests.exceptions.RequestException as e:
        print(f"❌ Ralat sambungan API (Langkah 1): {str(e)}")
        return False

    # ---------------------------------------------------------
    # LANGKAH 2: Semak Status Pemprosesan Media
    # ---------------------------------------------------------
    print("\n⏳ [Langkah 2/3] Menyemak status pemprosesan media Meta...")
    status_url = f"{GRAPH_BASE_URL}/{creation_id}"
    status_params = {
        "fields": "status_code",
        "access_token": IG_ACCESS_TOKEN,
    }

    # Berikan sela masa 3 saat untuk Meta memproses gambar
    time.sleep(3)
    try:
        res_status = requests.get(status_url, params=status_params, timeout=15)
        status_data = res_status.json()
        status_code = status_data.get("status_code", "FINISHED")
        print(f"ℹ️ Status Media: {status_code}")

        if status_code == "ERROR":
            print("❌ Meta gagal memproses fail gambar ini.")
            return False

    except Exception as e:
        print(f"⚠️ Amaran semakan status: {str(e)} (Meneruskan ke penyiaran)")

    # ---------------------------------------------------------
    # LANGKAH 3: Terbitkan Media (Publish Media Container)
    # ---------------------------------------------------------
    print("\n📢 [Langkah 3/3] Menerbitkan hantaran ke feed Instagram...")
    publish_url = f"{GRAPH_BASE_URL}/{IG_ACCOUNT_ID}/media_publish"
    publish_params = {
        "creation_id": creation_id,
        "access_token": IG_ACCESS_TOKEN,
    }

    try:
        res_publish = requests.post(publish_url, data=publish_params, timeout=30)
        publish_json = res_publish.json()

        if res_publish.status_code != 200 or "id" not in publish_json:
            print(f"❌ Gagal menerbitkan hantaran ({res_publish.status_code}):")
            print(f"   {publish_json.get('error', {}).get('message', publish_json)}")
            return False

        post_id = publish_json["id"]
        print(f"🎉 BERJAYA DIPOSKAN KE INSTAGRAM! Media ID: {post_id}")

        # ---------------------------------------------------------
        # LANGKAH 4: Dapatkan Pautan URL Post (Permalink)
        # ---------------------------------------------------------
        permalink_url = f"{GRAPH_BASE_URL}/{post_id}"
        permalink_params = {
            "fields": "permalink",
            "access_token": IG_ACCESS_TOKEN,
        }
        res_link = requests.get(permalink_url, params=permalink_params, timeout=15).json()
        post_link = res_link.get("permalink", f"https://www.instagram.com/p/{post_id}/")

        print("\n" + "=" * 60)
        print("🔗 PAUTAN HANTARAN ANDA:")
        print(f"👉 {post_link}")
        print("=" * 60 + "\n")
        return True

    except requests.exceptions.RequestException as e:
        print(f"❌ Ralat sambungan API (Langkah 3): {str(e)}")
        return False


if __name__ == "__main__":
    success = create_instagram_post(TEST_IMAGE_URL, TEST_CAPTION)
    if success:
        sys.exit(0)
    else:
        sys.exit(1)