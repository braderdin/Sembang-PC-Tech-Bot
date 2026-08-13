import os
import requests

def is_image_id_posted(redis_url, redis_token, photo_id):
    """
    Semak sama ada ID Gambar Unsplash ini pernah digunakan di Upstash Redis.
    """
    if not redis_url or not redis_token or not photo_id:
        return False
        
    clean_url = redis_url.rstrip("/")
    redis_key = f"posted:unsplash:{photo_id}"
    headers = {
        "Authorization": f"Bearer {redis_token}",
        "Content-Type": "application/json",
    }
    try:
        res = requests.post(
            f"{clean_url}/", 
            json=["GET", redis_key], 
            headers=headers, 
            timeout=5
        )
        return res.status_code == 200 and res.json().get("result") is not None
    except Exception:
        return False

def mark_image_id_posted(redis_url, redis_token, photo_id, ttl=2592000):
    """
    Simpan ID Gambar Unsplash ke Upstash Redis dengan tempoh luput 30 Hari (2,592,000s).
    """
    if not redis_url or not redis_token or not photo_id:
        return False
        
    clean_url = redis_url.rstrip("/")
    redis_key = f"posted:unsplash:{photo_id}"
    headers = {
        "Authorization": f"Bearer {redis_token}",
        "Content-Type": "application/json",
    }
    try:
        requests.post(
            f"{clean_url}/",
            json=["SET", redis_key, "1", "EX", str(ttl)],
            headers=headers,
            timeout=5,
        )
        return True
    except Exception:
        return False

def fetch_similar_theme_images(access_key, query_keyword, redis_url="", redis_token="", count=3):
    """
    Masa Hantar 1 Permintaan API ke Unsplash untuk mendapatkan sehingga 'count' (3) gambar 
    bertema serupa yang belum pernah dipos.
    
    Memulangkan: Senarai dictionary [{'photo_id': ..., 'image_url': ..., 'description': ...}]
    """
    if not access_key:
        print("❌ [UNSPLASH ERROR] Kunci UNSPLASH_ACCESS_KEY tidak ditemui di persekitaran.")
        return []

    url = "https://api.unsplash.com/search/photos"
    
    # 1 API CALL SAHAJA: Minta 10 gambar daripada kata kunci induk yang sama
    params = {
        "query": query_keyword,
        "per_page": 10,
        "page": 1,
        "orientation": "portrait", # Format tegak (9:16) paling ideal untuk FB Reel & Feed
        "client_id": access_key,
    }

    print(f"📡 [UNSPLASH 1-API CALL] Carian Tema Induk: '{query_keyword}'...")
    try:
        res = requests.get(url, params=params, timeout=12)
        if res.status_code != 200:
            print(f"⚠️ [UNSPLASH HTTP {res.status_code}] Gagal menarik gambar: {res.text}")
            return []

        results = res.json().get("results", [])
        if not results:
            print(f"⚠️ [UNSPLASH WARN] Tiada gambar dijumpai untuk kata kunci: '{query_keyword}'")
            return []

        collected_images = []
        for photo in results:
            photo_id = photo.get("id")
            # Utamakan URL gambar bersaiz regular yang jernih dan pantas dimuat turun
            img_url = photo.get("urls", {}).get("regular") or photo.get("urls", {}).get("full")
            raw_desc = (
                photo.get("alt_description") or 
                photo.get("description") or 
                f"Suasana bertema {query_keyword}"
            )

            if not img_url or not photo_id:
                continue

            # Semak elak imej bertindih via Redis
            if is_image_id_posted(redis_url, redis_token, photo_id):
                print(f"  ⏭️ [REDIS SKIP] Photo ID '{photo_id}' pernah digunakan < 30 hari lepas.")
                continue

            collected_images.append({
                "photo_id": photo_id,
                "image_url": img_url,
                "description": raw_desc,
                "keyword": query_keyword
            })

            # Berhenti sebaik sahaja kuota gambar bertema serupa dicapai (contoh: 3 gambar)
            if len(collected_images) >= count:
                break

        print(f"✅ [UNSPLASH SUCCESS] Berjaya mengumpul {len(collected_images)} gambar bertema serupa.")
        return collected_images

    except Exception as e:
        print(f"❌ [UNSPLASH EXCEPTION] Ralat carian Unsplash API: {e}")
        return []