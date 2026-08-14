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
    Menghantar hantaran ke Threads API dengan Perlindungan Had 500 Aksara
    serta Logik Auto-Retry 3 Saat untuk kestabilan media.
    """
    if not user_id or not access_token:
        return False, "THREADS_USER_ID atau THREADS_ACCESS_TOKEN tidak wujud di persekitaran."

    # 1. BINA PAUTAN AFFILIATE (JIKA ADA)
    affiliate_text = ""
    if affiliate_link:
        affiliate_text = f"\n\n🛒 Dapatkan di sini: {affiliate_link}"

    # 2. SAFETY GUARDRAIL (THREADS HARD LIMIT = 500 AKSARA)
    max_caption_allowed = 500 - len(affiliate_text) - 5  # Buffer keselamatan 5 aksara
    if max_caption_allowed < 50:
        max_caption_allowed = 450

    trimmed_caption = smart_trim_for_threads(caption, max_chars=max_caption_allowed)
    full_text = f"{trimmed_caption}{affiliate_text}".strip()

    if len(full_text) > 500:
        full_text = full_text[:496] + "..."

    create_url = f"{THREADS_GRAPH_URL}/{user_id}/threads"

    # 3. TENTUKAN JENIS MEDIA (KEKAL WAJIB BERGAMBAR JIKA ADA URL)
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
        # LANGKAH 1: Cipta Media Container di Threads (Auto-Retry jika CDN lambat)
        print(f"🧵 [THREADS STEP A] Membina Media Container (Saiz Teks: {len(full_text)}/500 aksara)...")
        
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
                    print(f"⚠️ [THREADS STEP A RETRY] Percubaan 1 gagal. Menunggu 3 saat untuk percubaan semula...")
                    time.sleep(3)
                else:
                    print(f"❌ [THREADS ERROR STEP A] {last_error_a}")
                    return False, f"Langkah A Gagal: {last_error_a}"

        # Beri masa pelayan Meta memproses binary imej sebelum diterbitkan
        if create_payload.get("media_type") == "IMAGE":
            time.sleep(3)

        # LANGKAH 2: Terbitkan Container ke Threads Profile (Auto-Retry)
        print("🧵 [THREADS STEP B] Menerbitkan hantaran ke akaun Threads...")
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
                print(f"🎉 [THREADS SUCCESS] Hantaran berjaya dipos ke Threads! (Post ID: {thread_post_id})")
                return True, {"thread_post_id": thread_post_id}
            else:
                last_error_b = f"HTTP {res_publish.status_code} | {res_publish.text}"
                if attempt == 0:
                    print(f"⚠️ [THREADS STEP B RETRY] Percubaan 1 gagal. Menunggu 3 saat...")
                    time.sleep(3)
                else:
                    print(f"❌ [THREADS ERROR STEP B] {last_error_b}")
                    return False, f"Langkah B Gagal: {last_error_b}"

    except Exception as e:
        print(f"❌ [THREADS EXCEPTION] Ralat tidak dijangka: {str(e)}")
        return False, f"Ralat Rangkaian Threads API: {str(e)}"