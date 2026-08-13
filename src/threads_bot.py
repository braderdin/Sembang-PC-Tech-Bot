import os
import time
import requests

THREADS_GRAPH_URL = "https://graph.threads.net/v1.0"
THREADS_REFRESH_URL = "https://graph.threads.net/refresh_access_token"

def smart_trim_for_threads(text, max_chars=480):
    """
    Memotong kapsyen secara pintar pada noktah, tanda soal, atau tanda seru terakhir
    supaya jumlah aksara PASTI di bawah had ketat Threads API (500 aksara).
    """
    if not text or len(text) <= max_chars:
        return text

    trimmed = text[:max_chars]
    last_punc = max(trimmed.rfind('.'), trimmed.rfind('?'), trimmed.rfind('!'))
    
    # Jika ada noktah dalam julat mesra, potong pada noktah
    if last_punc != -1 and last_punc > 80:
        return trimmed[:last_punc + 1].strip()
    
    # Jika tiada noktah, potong pada ruang kosong terakhir
    last_space = trimmed.rfind(' ')
    if last_space != -1:
        return trimmed[:last_space].strip() + "..."
    
    return trimmed[:max_chars - 3] + "..."

def auto_refresh_threads_token(access_token):
    """
    Memperbaharui Long-Lived Access Token Threads secara automatik.
    """
    if not access_token:
        return False, "THREADS_ACCESS_TOKEN tidak dijumpai."

    params = {
        "grant_type": "th_refresh_token",
        "access_token": access_token
    }

    try:
        res = requests.get(THREADS_REFRESH_URL, params=params, timeout=12)
        if res.status_code == 200:
            refresh_data = res.json()
            new_token = refresh_data.get("access_token")
            expires_in = refresh_data.get("expires_in")
            print(f"🔄 [THREADS TOKEN REFRESH] Token diperbaharui! Tempoh luput: {expires_in}s (~60 Hari).")
            return True, new_token
        else:
            return False, f"HTTP {res.status_code}: {res.text}"
    except Exception as e:
        return False, f"Ralat Rangkaian semasa Refresh Token: {str(e)}"

def send_to_threads(user_id, access_token, caption, image_url="", affiliate_link=""):
    """
    Menghantar hantaran ke Threads API dengan Perlindungan Had 500 Aksara Automatik.
    """
    if not user_id or not access_token:
        return False, "THREADS_USER_ID atau THREADS_ACCESS_TOKEN tidak wujud di persekitaran."

    # 1. BINA PAUTAN AFFILIATE (JIKA ADA)
    affiliate_text = ""
    if affiliate_link:
        affiliate_text = f"\n\n🛒 Dapatkan di sini: {affiliate_link}"

    # 2. HARI SAFETY GUARDRAIL (THREADS HARD LIMIT = 500 AKSARA)
    # Kira baki aksara yang tinggal untuk kapsyen
    max_caption_allowed = 500 - len(affiliate_text) - 5  # Buffer keselamatan 5 aksara
    if max_caption_allowed < 50:
        max_caption_allowed = 450

    # Potong kapsyen secara pintar
    trimmed_caption = smart_trim_for_threads(caption, max_chars=max_caption_allowed)
    full_text = f"{trimmed_caption}{affiliate_text}".strip()

    # Semakan terakhir jaminan 100% <= 500 aksara
    if len(full_text) > 500:
        full_text = full_text[:496] + "..."

    create_url = f"{THREADS_GRAPH_URL}/{user_id}/threads"

    # 3. TENTUKAN JENIS MEDIA
    if image_url and image_url.startswith("http"):
        create_payload = {
            "media_type": "IMAGE",
            "image_url": image_url,
            "text": full_text,
            "access_token": access_token
        }
    else:
        create_payload = {
            "media_type": "TEXT",
            "text": full_text,
            "access_token": access_token
        }

    try:
        # LANGKAH 1: Cipta Media Container di Threads
        print(f"🧵 [THREADS STEP A] Membina Media Container (Saiz Teks: {len(full_text)}/500 aksara)...")
        res_create = requests.post(create_url, data=create_payload, timeout=20)
        create_json = res_create.json()

        if res_create.status_code != 200 or "id" not in create_json:
            error_msg = f"HTTP {res_create.status_code} | {res_create.text}"
            print(f"❌ [THREADS ERROR STEP A] {error_msg}")
            return False, f"Langkah A Gagal: {error_msg}"

        creation_container_id = create_json["id"]
        print(f"✅ [THREADS STEP A SUCCESS] Container ID: {creation_container_id}")

        if create_payload.get("media_type") == "IMAGE":
            time.sleep(2)

        # LANGKAH 2: Terbitkan Container ke Threads Profile
        print("🧵 [THREADS STEP B] Menerbitkan hantaran ke akaun Threads...")
        publish_url = f"{THREADS_GRAPH_URL}/{user_id}/threads_publish"
        publish_payload = {
            "creation_id": creation_container_id,
            "access_token": access_token
        }

        res_publish = requests.post(publish_url, data=publish_payload, timeout=20)
        publish_json = res_publish.json()

        if res_publish.status_code != 200 or "id" not in publish_json:
            error_msg = f"HTTP {res_publish.status_code} | {res_publish.text}"
            print(f"❌ [THREADS ERROR STEP B] {error_msg}")
            return False, f"Langkah B Gagal: {error_msg}"

        thread_post_id = publish_json["id"]
        print(f"🎉 [THREADS SUCCESS] Hantaran berjaya dipos ke Threads! (Post ID: {thread_post_id})")
        return True, {"thread_post_id": thread_post_id}

    except Exception as e:
        print(f"❌ [THREADS EXCEPTION] Ralat tidak dijangka: {str(e)}")
        return False, f"Ralat Rangkaian Threads API: {str(e)}"