#!/usr/bin/env python3
"""
🧪 EKSPERIMEN: Threads Video Publishing via Backblaze B2 Storage (Signed Public URL)
Lokasi: experiments/test_threads_b2_video.py
Ciri-ciri:
1. Mengambil fail video MP4 dari experiments/output/.
2. Muat naik fail ke Backblaze B2 via Native REST API.
3. Menjana B2 Download Authorization Token (Menyokong Private & Public Bucket 100%).
4. Ujian Pengesahan Kendiri (Self-Check HTTP 200) sebelum diserahkan ke Meta Threads.
5. Hantar ke Meta Threads API & tunggu sehingga status bertukar ke FINISHED/PUBLISHED.
6. Padam fail video dari B2 selepas selesai.
"""

import os
import sys
import time
import hashlib
import urllib.parse
import requests
from pathlib import Path
from dotenv import load_dotenv

# Laluan Projek & .env.local
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

env_local = PROJECT_ROOT / ".env.local"
if env_local.exists():
    load_dotenv(dotenv_path=env_local)
else:
    load_dotenv()

# Konfigurasi Backblaze B2 (100% Environment Driven)
B2_KEY_ID = os.getenv("B2_ACC1_KEY_ID", "").strip()
B2_APP_KEY = os.getenv("B2_ACC1_APPLICATION_KEY", "").strip()
B2_BUCKET_ID = os.getenv("B2_ACC1_BUCKET_ID", "").strip()
B2_BUCKET_NAME = os.getenv("B2_ACC1_BUCKET_NAME", "").strip()

# Konfigurasi Threads API
THREADS_USER_ID = os.getenv("THREADS_USER_ID", "").strip()
THREADS_ACCESS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN", "").strip()
THREADS_BASE_URL = "https://graph.threads.net/v1.0"

OUTPUT_DIR = PROJECT_ROOT / "experiments" / "output"


# =============================================================================
# 1. ENJIN BACKBLAZE B2 NATIVE REST API (DENGAN SIGNED DOWNLOAD AUTH)
# =============================================================================

def b2_authorize_account():
    """Mendapatkan Authorization Token dan API URL dari Backblaze B2."""
    if not B2_KEY_ID or not B2_APP_KEY:
        print("❌ [B2 ERROR] Kunci 'B2_ACC1_KEY_ID' atau 'B2_ACC1_APPLICATION_KEY' tiada dalam .env.local.")
        return None, None, None

    auth_url = "https://api.backblazeb2.com/b2api/v2/b2_authorize_account"
    try:
        res = requests.get(auth_url, auth=(B2_KEY_ID, B2_APP_KEY), timeout=15)
        if res.status_code == 200:
            data = res.json()
            return data.get("authorizationToken"), data.get("apiUrl"), data.get("downloadUrl")
        else:
            print(f"❌ [B2 AUTH ERROR] HTTP {res.status_code}: {res.text}")
    except Exception as e:
        print(f"❌ [B2 AUTH EXCEPTION] {e}")
    return None, None, None


def b2_get_upload_url(api_url: str, auth_token: str):
    """Mendapatkan Upload URL khusus untuk Bucket B2."""
    url = f"{api_url}/b2api/v2/b2_get_upload_url"
    headers = {"Authorization": auth_token}
    payload = {"bucketId": B2_BUCKET_ID}

    try:
        res = requests.post(url, json=payload, headers=headers, timeout=15)
        if res.status_code == 200:
            data = res.json()
            return data.get("uploadUrl"), data.get("authorizationToken")
        else:
            print(f"❌ [B2 GET UPLOAD URL ERROR] HTTP {res.status_code}: {res.text}")
    except Exception as e:
        print(f"❌ [B2 GET UPLOAD URL EXCEPTION] {e}")
    return None, None


def b2_get_download_authorization(api_url: str, auth_token: str, file_name: str, valid_duration: int = 3600):
    """
    Menjana Authorization Token untuk membolehkan fail dimuat turun secara awam
    walaupun status Bucket B2 anda adalah Private.
    """
    url = f"{api_url}/b2api/v2/b2_get_download_authorization"
    headers = {"Authorization": auth_token}
    payload = {
        "bucketId": B2_BUCKET_ID,
        "fileNamePrefix": file_name,
        "validDurationInSeconds": valid_duration
    }

    try:
        res = requests.post(url, json=payload, headers=headers, timeout=15)
        if res.status_code == 200:
            return res.json().get("authorizationToken")
        else:
            print(f"⚠️ [B2 DOWNLOAD AUTH WARN] HTTP {res.status_code}: {res.text}")
    except Exception as e:
        print(f"⚠️ [B2 DOWNLOAD AUTH EXCEPTION] {e}")
    return None


def upload_video_to_b2(video_path: str):
    """
    Memuat naik fail MP4 ke B2 dan memulangkan Signed Public Download URL.
    """
    if not os.path.exists(video_path):
        print(f"❌ [B2 ERROR] Fail video tidak dijumpai di laluan: {video_path}")
        return None, None, None, None, None

    print("\n☁️ [B2 STEP 1] Mengesahkan akaun Backblaze B2...")
    auth_token, api_url, download_url = b2_authorize_account()
    if not auth_token:
        return None, None, None, None, None

    print("☁️ [B2 STEP 2] Mendapatkan URL muat naik B2...")
    upload_url, upload_auth_token = b2_get_upload_url(api_url, auth_token)
    if not upload_url:
        return None, None, None, None, None

    file_name = f"threads_video_{int(time.time())}.mp4"
    encoded_file_name = urllib.parse.quote(file_name)

    print(f"☁️ [B2 STEP 3] Memuat naik fail MP4 ({os.path.getsize(video_path):,} bytes)...")
    with open(video_path, "rb") as f:
        file_bytes = f.read()

    sha1_hash = hashlib.sha1(file_bytes).hexdigest()

    headers = {
        "Authorization": upload_auth_token,
        "X-Bz-File-Name": encoded_file_name,
        "Content-Type": "video/mp4",
        "Content-Length": str(len(file_bytes)),
        "X-Bz-Content-Sha1": sha1_hash,
    }

    try:
        res = requests.post(upload_url, headers=headers, data=file_bytes, timeout=60)
        if res.status_code == 200:
            data = res.json()
            file_id = data.get("fileId")

            # Jana Download Auth Token supaya Meta boleh akses tanpa sekatan
            print("☁️ [B2 STEP 4] Menjana Signed Download Token untuk pelayan Meta Threads...")
            download_token = b2_get_download_authorization(api_url, auth_token, file_name, valid_duration=3600)

            base_download_url = f"{download_url}/file/{B2_BUCKET_NAME}/{encoded_file_name}"
            if download_token:
                public_url = f"{base_download_url}?Authorization={download_token}"
            else:
                public_url = base_download_url

            print(f"  ✅ [B2 SUCCESS] Video berjaya dihoskan!")
            print(f"  🔗 Pautan Akses: {base_download_url}")
            return public_url, file_id, file_name, api_url, auth_token
        else:
            print(f"❌ [B2 UPLOAD ERROR] HTTP {res.status_code}: {res.text}")
    except Exception as e:
        print(f"❌ [B2 UPLOAD EXCEPTION] {e}")

    return None, None, None, None, None


def verify_url_accessibility(url: str) -> bool:
    """Menguji sama ada pautan video boleh diakses terus melalui HTTP GET (Status 200 OK)."""
    print("\n🔍 [SELF-CHECK] Menguji capaian fail video sebelum dihantar ke Threads...")
    try:
        res = requests.get(url, stream=True, timeout=15)
        content_type = res.headers.get("Content-Type", "")
        print(f"  ℹ️ Status HTTP: {res.status_code} | Content-Type: {content_type}")
        if res.status_code == 200 and "video" in content_type.lower():
            print("  ✅ Pautan disahkan 100% sah dan sedia dimuat turun oleh Meta!")
            return True
        else:
            print(f"  ❌ Pautan gagal diakses atau bukan video MP4 yang sah.")
            return False
    except Exception as e:
        print(f"  ❌ Ralat menguji capaian URL: {e}")
        return False


def delete_video_from_b2(api_url: str, auth_token: str, file_id: str, file_name: str):
    """Memadam fail video dari B2 selepas diterbitkan ke Threads."""
    if not file_id or not file_name or not api_url:
        return

    url = f"{api_url}/b2api/v2/b2_delete_file_version"
    headers = {"Authorization": auth_token}
    payload = {"fileId": file_id, "fileName": file_name}

    try:
        requests.post(url, json=payload, headers=headers, timeout=10)
        print(f"  🧹 [B2 CLEANUP] Fail sementara '{file_name}' dipadam dari B2.")
    except Exception:
        pass


# =============================================================================
# 2. ENJIN META THREADS VIDEO PUBLISHING
# =============================================================================

def post_video_to_threads(video_url: str, caption: str):
    """
    Menghantar pautan video ke Meta Threads API dan memantau status pemprosesan.
    """
    print("\n" + "=" * 65)
    print("🧵 [THREADS API] Memulakan Proses Penerbitan Video ke Threads...")
    print("=" * 65)

    if not THREADS_USER_ID or not THREADS_ACCESS_TOKEN:
        print("❌ [THREADS ERROR] THREADS_USER_ID atau THREADS_ACCESS_TOKEN tiada dalam .env.local!")
        return False, None

    # -------------------------------------------------------------------------
    # LANGKAH 1: Cipta Media Container (media_type=VIDEO)
    # -------------------------------------------------------------------------
    print("🔹 [LANGKAH 1] Mencipta Media Container di Threads...")
    create_url = f"{THREADS_BASE_URL}/{THREADS_USER_ID}/threads"
    payload = {
        "media_type": "VIDEO",
        "video_url": video_url,
        "text": caption,
        "access_token": THREADS_ACCESS_TOKEN,
    }

    res_create = requests.post(create_url, data=payload, timeout=30)
    create_json = res_create.json()

    if res_create.status_code != 200 or "id" not in create_json:
        err_msg = create_json.get("error", {}).get("message", res_create.text)
        print(f"❌ [LANGKAH 1 GAGAL] {err_msg}")
        return False, None

    container_id = create_json["id"]
    print(f"  ✅ Sesi Berjaya Dimulakan! Container ID: {container_id}")

    # -------------------------------------------------------------------------
    # LANGKAH 2: Tunggu Status Video Bertukar ke FINISHED (Transcoding)
    # -------------------------------------------------------------------------
    print("\n🔹 [LANGKAH 2] Menunggu pemprosesan video di pelayan Meta Threads...")
    status_url = f"{THREADS_BASE_URL}/{container_id}"
    params = {"fields": "status,error_message", "access_token": THREADS_ACCESS_TOKEN}
    
    max_wait = 120
    start_time = time.time()
    is_ready = False

    while time.time() - start_time < max_wait:
        time.sleep(6)
        try:
            res_status = requests.get(status_url, params=params, timeout=15).json()
            status_code = res_status.get("status", "")
            print(f"  ⏳ Status Semasa: {status_code} ({int(time.time() - start_time)}s)")

            if status_code in ["FINISHED", "PUBLISHED"]:
                is_ready = True
                break
            elif status_code in ["ERROR", "EXPIRED"]:
                err_msg = res_status.get("error_message", "Unknown error")
                print(f"❌ [LANGKAH 2 GAGAL] Status pemprosesan Meta: {status_code} ({err_msg})")
                return False, None
        except Exception as e:
            print(f"  ⚠️ Menunggu sambungan status: {e}")

    if not is_ready:
        print("⚠️ [TIMEOUT] Meneruskan percubaan penerbitan...")

    # -------------------------------------------------------------------------
    # LANGKAH 3: Terbitkan Hantaran Video (threads_publish)
    # -------------------------------------------------------------------------
    print("\n🔹 [LANGKAH 3] Menerbitkan Hantaran ke Profil Threads...")
    publish_url = f"{THREADS_BASE_URL}/{THREADS_USER_ID}/threads_publish"
    pub_payload = {
        "creation_id": container_id,
        "access_token": THREADS_ACCESS_TOKEN,
    }

    res_pub = requests.post(publish_url, data=pub_payload, timeout=30)
    pub_json = res_pub.json()

    if res_pub.status_code == 200 and "id" in pub_json:
        thread_id = pub_json["id"]
        permalink = f"https://www.threads.net/post/{thread_id}"
        print("\n" + "=" * 65)
        print(f"🎉 [BERJAYA] Video berjaya diterbitkan di Threads!")
        print(f"🔗 Pautan Threads: {permalink}")
        print("=" * 65 + "\n")
        return True, permalink
    else:
        err_msg = pub_json.get("error", {}).get("message", res_pub.text)
        print(f"❌ [LANGKAH 3 GAGAL] {err_msg}")
        return False, None


# =============================================================================
# MAIN RUNNER
# =============================================================================

def find_latest_local_video() -> str:
    """Mencari video MP4 terkini di folder experiments/output/."""
    if not OUTPUT_DIR.exists():
        return ""
    mp4_files = sorted(OUTPUT_DIR.glob("*.mp4"), key=os.path.getmtime, reverse=True)
    return str(mp4_files[0]) if mp4_files else ""


def main():
    print("=" * 70)
    print("🧪 [START] UJIAN THREADS VIDEO VIA BACKBLAZE B2 (SIGNED PUBLIC URL)")
    print("=" * 70)

    # 1. Cari video MP4 tempatan sedia ada
    video_file = find_latest_local_video()
    if not video_file or not os.path.exists(video_file):
        print("⚠️ Tiada video MP4 ditemui di folder experiments/output/.")
        print("💡 Sila jalankan 'python experiments/test_pexels_local_generator.py' terlebih dahulu.")
        return

    print(f"📁 Menggunakan video ujian: {video_file} ({os.path.getsize(video_file):,} bytes)")

    # 2. Kapsyen Santai Brader Din
    sample_caption = (
        "Bila setup meja kemas dan layout keyboard sedap di mata, fokus buat kerja rasa makin tenang. ☕️🖤\n\n"
        "Korang jenis suka layout minimalis atau penuh dengan lampu ambient? Cer sembang sikit. 👇\n\n"
        "#SembangPCTech #TechMalaysia #PCSetup #MechanicalKeyboard #Workspace"
    )

    # 3. Muat naik ke Backblaze B2 dengan Signed Download Token
    public_url, file_id, file_name, api_url, auth_token = upload_video_to_b2(video_file)
    if not public_url:
        print("❌ Gagal memuat naik video ke Backblaze B2.")
        return

    # 4. Ujian pengesahan akses URL
    if not verify_url_accessibility(public_url):
        print("⚠️ Menghentikan penerbitan kerana fail tidak dapat diakses oleh Meta.")
        if api_url and auth_token:
            delete_video_from_b2(api_url, auth_token, file_id, file_name)
        return

    # 5. Hantar ke Threads API
    try:
        success, permalink = post_video_to_threads(public_url, sample_caption)
    finally:
        # 6. Pembersihan fail sementara di B2
        print("🧹 Memulakan proses pembersihan fail storan B2...")
        if api_url and auth_token:
            delete_video_from_b2(api_url, auth_token, file_id, file_name)


if __name__ == "__main__":
    main()