import os
import re
import random
import requests

# Senarai kata kunci sandaran teras (dijamin ribuan gambar di Unsplash)
SAFE_FALLBACK_KEYWORDS = [
    "minimalist workspace",
    "computer desk setup",
    "dark coding setup",
    "gaming room neon",
    "mechanical keyboard",
    "dual monitor workspace"
]

def _clean_image_description(raw_desc, fallback_keyword):
    """
    Membersihkan teks deskripsi Unsplash daripada metadata kamera,
    nama jurugambar, dan tag teknikal sebelum disalurkan ke AI.
    """
    if not raw_desc:
        return f"Suasana bertema {fallback_keyword}"

    # Buang tag jurugambar, kamera, resolusi, dan pautan
    cleaned = re.sub(
        r'(photo by|shot on|taken by|image by|picture by|photographer|camera|lens|iso\s*\d+|f/\d+(\.\d+)?|unsplash|wallpaper|http\S+|www\S+)[\w\s\.\,\-\_]*',
        '',
        str(raw_desc),
        flags=re.IGNORECASE
    )
    # Buang simbol pelik dan ruang kosong berlebihan
    cleaned = re.sub(r'[\r\n\t]+', ' ', cleaned)
    cleaned = re.sub(r'[^\w\s\.\,\-\']', '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    if len(cleaned) < 6:
        return f"Suasana bertema {fallback_keyword}"

    return cleaned[:120]

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

def _fetch_from_unsplash_api(access_key, keyword, per_page=15):
    """
    Fungsi bantuan dalaman untuk membuat panggilan carian ke Unsplash API.
    """
    url = "https://api.unsplash.com/search/photos"
    params = {
        "query": keyword,
        "per_page": per_page,
        "page": 1,
        "orientation": "portrait", # Format tegak ideal untuk Reels & Feed
        "client_id": access_key,
    }
    try:
        res = requests.get(url, params=params, timeout=12)
        if res.status_code == 200:
            return res.json().get("results", [])
        else:
            print(f"⚠️ [UNSPLASH HTTP {res.status_code}] Ralat respon: {res.text}")
            return []
    except Exception as e:
        print(f"❌ [UNSPLASH EXCEPTION]: {e}")
        return []

def fetch_similar_theme_images(access_key, query_keyword, redis_url="", redis_token="", count=3):
    """
    Menarik sehingga 'count' (3) gambar bertema serupa daripada Unsplash API.
    Menyokong kolam 15 gambar, pembersihan deskripsi automatik, dan mekanisma Smart Fallback.
    """
    if not access_key:
        print("❌ [UNSPLASH ERROR] Kunci UNSPLASH_ACCESS_KEY tidak ditemui di persekitaran.")
        return []

    print(f"📡 [UNSPLASH 1-API CALL] Carian Tema Induk: '{query_keyword}'...")
    results = _fetch_from_unsplash_api(access_key, query_keyword, per_page=15)

    # SMART FALLBACK: Jika kata kunci utama tiada gambar, buat 1 carian sandaran selamat
    active_keyword = query_keyword
    if not results:
        active_keyword = random.choice(SAFE_FALLBACK_KEYWORDS)
        print(f"⚠️ [UNSPLASH AUTO-FALLBACK] Kata kunci utama tiada gambar. Mengaktifkan carian sandaran: '{active_keyword}'...")
        results = _fetch_from_unsplash_api(access_key, active_keyword, per_page=15)

    if not results:
        print("❌ [ABORT] Tiada gambar yang sah dijumpai dari Unsplash selepas carian sandaran.")
        return []

    collected_images = []
    for photo in results:
        photo_id = photo.get("id")
        img_url = photo.get("urls", {}).get("regular") or photo.get("urls", {}).get("full")
        raw_desc = photo.get("alt_description") or photo.get("description") or ""

        if not img_url or not photo_id:
            continue

        # Semak penapis Redis (elak gambar berulang < 30 hari)
        if is_image_id_posted(redis_url, redis_token, photo_id):
            print(f"  ⏭️ [REDIS SKIP] Photo ID '{photo_id}' pernah digunakan < 30 hari lepas.")
            continue

        # Bersihkan deskripsi visual sebelum disimpan
        clean_desc = _clean_image_description(raw_desc, active_keyword)

        collected_images.append({
            "photo_id": photo_id,
            "image_url": img_url,
            "description": clean_desc,
            "keyword": active_keyword
        })

        if len(collected_images) >= count:
            break

    # Jika kolam pertama masih tidak mencukupi 3 gambar selepas Redis filter, tambah dari fallback
    if len(collected_images) < count:
        print("⚠️ [UNSPLASH TOP-UP] Memerlukan baki gambar. Menarik kolam tambahan...")
        fallback_kw = random.choice([k for k in SAFE_FALLBACK_KEYWORDS if k != active_keyword])
        extra_results = _fetch_from_unsplash_api(access_key, fallback_kw, per_page=15)
        for photo in extra_results:
            photo_id = photo.get("id")
            img_url = photo.get("urls", {}).get("regular") or photo.get("urls", {}).get("full")
            raw_desc = photo.get("alt_description") or photo.get("description") or ""
            
            if not img_url or not photo_id:
                continue
            if any(img["photo_id"] == photo_id for img in collected_images):
                continue
            if is_image_id_posted(redis_url, redis_token, photo_id):
                continue

            clean_desc = _clean_image_description(raw_desc, fallback_kw)

            collected_images.append({
                "photo_id": photo_id,
                "image_url": img_url,
                "description": clean_desc,
                "keyword": fallback_kw
            })

            if len(collected_images) >= count:
                break

    print(f"✅ [UNSPLASH SUCCESS] Berjaya mengumpul {len(collected_images)} gambar bertema serupa.")
    return collected_images