import os
import json
import requests

# Kunci Redis khas untuk bank ingatan lifestyle
REDIS_MEMORY_KEY = "lifestyle:memory:recent_stories"

def get_lifestyle_story_memories(redis_url, redis_token, limit=5):
    """
    Mengambil 'limit' (default 5) cerita terakhir yang pernah dijana oleh AI Persona.
    Digunakan untuk dimasukkan ke dalam prompt AI sebagai konteks ingatan.
    """
    if not redis_url or not redis_token:
        return []

    clean_url = redis_url.rstrip("/")
    endpoint = f"{clean_url}/"
    headers = {
        "Authorization": f"Bearer {redis_token}",
        "Content-Type": "application/json",
    }
    
    # Ambil elemen 0 hingga (limit - 1) dari senarai Redis
    payload = ["LRANGE", REDIS_MEMORY_KEY, "0", str(limit - 1)]

    try:
        res = requests.post(endpoint, json=payload, headers=headers, timeout=10)
        if res.status_code == 200:
            result = res.json().get("result", [])
            if isinstance(result, list):
                return [str(item) for item in result if item]
    except Exception as e:
        print(f"⚠️ [LIFESTYLE REDIS WARN] Gagal membaca ingatan cerita dari Redis: {e}")

    return []

def save_lifestyle_story_memory(redis_url, redis_token, story_text, max_memories=10):
    """
    Simpan cerita baharu ke dalam senarai ingatan Redis (LPUSH) 
    dan simpan maksimum 'max_memories' (default 10) cerita sahaja (LTRIM).
    """
    if not redis_url or not redis_token or not story_text:
        return False

    clean_url = redis_url.rstrip("/")
    endpoint = f"{clean_url}/pipeline"  # Gunakan Pipeline untuk jalankan 2 perintah serentak
    headers = {
        "Authorization": f"Bearer {redis_token}",
        "Content-Type": "application/json",
    }

    # Pipeline payload: LPUSH (tambah di depan) + LTRIM (kekalkan 10 terkini)
    pipeline_payload = [
        ["LPUSH", REDIS_MEMORY_KEY, str(story_text)],
        ["LTRIM", REDIS_MEMORY_KEY, "0", str(max_memories - 1)]
    ]

    try:
        res = requests.post(endpoint, json=pipeline_payload, headers=headers, timeout=10)
        if res.status_code == 200:
            print(f"🧠 [LIFESTYLE REDIS SUCCESS] Cerita baharu dimasukkan ke Bank Ingatan Persona (Kekal {max_memories} terkini).")
            return True
        else:
            print(f"⚠️ [LIFESTYLE REDIS ERROR] Ralat menyimpan ingatan. HTTP {res.status_code}: {res.text}")
    except Exception as e:
        print(f"⚠️ [LIFESTYLE REDIS WARN] Gagal menyimpan ingatan ke Redis: {e}")

    return False