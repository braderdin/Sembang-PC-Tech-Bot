import os
import time
import requests

THREADS_GRAPH_URL = "https://graph.threads.net/v1.0"
THREADS_REFRESH_URL = "https://graph.threads.net/refresh_access_token"

def check_threads_profile_and_permissions(user_id, access_token):
    """
    1. Menyemak maklumat profil Threads dan mengesahkan keizinan (permissions) token.
    """
    if not user_id or not access_token:
        return False, "THREADS_USER_ID atau THREADS_ACCESS_TOKEN tidak lengkap."

    url = f"{THREADS_GRAPH_URL}/{user_id}"
    params = {
        "fields": "id,username,threads_profile_picture_url,threads_biography",
        "access_token": access_token
    }

    try:
        res = requests.get(url, params=params, timeout=12)
        if res.status_code == 200:
            profile_data = res.json()
            return True, profile_data
        else:
            return False, f"HTTP {res.status_code}: {res.text}"
    except Exception as e:
        return False, f"Ralat Rangkaian: {str(e)}"

def refresh_threads_access_token(access_token):
    """
    2. Trik Auto-Renew: Memperbaharui Long-Lived Access Token supaya kembali ke tempoh 60 Hari baharu.
    """
    if not access_token:
        return False, "Access Token tidak diberikan."

    params = {
        "grant_type": "th_refresh_token",
        "access_token": access_token
    }

    try:
        res = requests.get(THREADS_REFRESH_URL, params=params, timeout=12)
        if res.status_code == 200:
            refresh_data = res.json()
            return True, refresh_data
        else:
            return False, f"HTTP {res.status_code}: {res.text}"
    except Exception as e:
        return False, f"Ralat Rangkaian Refresh Token: {str(e)}"

def create_and_publish_threads_text_post(user_id, access_token, text_content):
    """
    3. Hantar hantaran TEKS SAHAJA ke Threads.
    """
    if not user_id or not access_token or not text_content:
        return False, "Maklumat muat naik Threads tidak lengkap."

    create_url = f"{THREADS_GRAPH_URL}/{user_id}/threads"
    create_payload = {
        "media_type": "TEXT",
        "text": text_content,
        "access_token": access_token
    }

    try:
        res_create = requests.post(create_url, data=create_payload, timeout=15)
        create_json = res_create.json()

        if res_create.status_code != 200 or "id" not in create_json:
            return False, f"Langkah A Gagal (HTTP {res_create.status_code}): {res_create.text}"

        creation_container_id = create_json["id"]

        publish_url = f"{THREADS_GRAPH_URL}/{user_id}/threads_publish"
        publish_payload = {
            "creation_id": creation_container_id,
            "access_token": access_token
        }

        res_publish = requests.post(publish_url, data=publish_payload, timeout=15)
        publish_json = res_publish.json()

        if res_publish.status_code != 200 or "id" not in publish_json:
            return False, f"Langkah B Gagal (HTTP {res_publish.status_code}): {res_publish.text}"

        return True, {"thread_post_id": publish_json["id"]}

    except Exception as e:
        return False, f"Ralat Rangkaian semasa memuat naik Threads: {str(e)}"

def create_and_publish_threads_image_post(user_id, access_token, text_content, image_url):
    """
    4. Hantar hantaran GAMBAR + TEKS + LINK ke Threads menggunakan 2-Langkah Meta Graph API.
    """
    if not user_id or not access_token or not image_url:
        return False, "Maklumat muat naik gambar Threads tidak lengkap."

    # LANGKAH A: Cipta Image Media Container
    create_url = f"{THREADS_GRAPH_URL}/{user_id}/threads"
    create_payload = {
        "media_type": "IMAGE",
        "image_url": image_url,
        "text": text_content or "",
        "access_token": access_token
    }

    try:
        print("  🔄 [STEP A] Mendaftarkan Media Container Gambar ke Threads...")
        res_create = requests.post(create_url, data=create_payload, timeout=15)
        create_json = res_create.json()

        if res_create.status_code != 200 or "id" not in create_json:
            return False, f"Langkah A (Gambar) Gagal (HTTP {res_create.status_code}): {res_create.text}"

        creation_container_id = create_json["id"]
        print(f"  ✅ [STEP A SUCCESS] Image Container ID: {creation_container_id}")

        # Beri masa 2 saat untuk pelayan Threads memproses & memuat turun gambar dari URL
        time.sleep(2)

        # LANGKAH B: Terbitkan Container ke Threads Profile
        publish_url = f"{THREADS_GRAPH_URL}/{user_id}/threads_publish"
        publish_payload = {
            "creation_id": creation_container_id,
            "access_token": access_token
        }

        print("  🔄 [STEP B] Menerbitkan hantaran gambar ke akaun Threads...")
        res_publish = requests.post(publish_url, data=publish_payload, timeout=15)
        publish_json = res_publish.json()

        if res_publish.status_code != 200 or "id" not in publish_json:
            return False, f"Langkah B (Gambar) Gagal (HTTP {res_publish.status_code}): {res_publish.text}"

        thread_post_id = publish_json["id"]
        print(f"  ✅ [STEP B SUCCESS] Thread Post ID (Gambar): {thread_post_id}")
        return True, {"thread_post_id": thread_post_id}

    except Exception as e:
        return False, f"Ralat Rangkaian semasa memuat naik gambar Threads: {str(e)}"