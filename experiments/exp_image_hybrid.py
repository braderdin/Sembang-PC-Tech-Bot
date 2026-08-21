#!/usr/bin/env python3
"""
Reddit Tech Storyteller Engine - Experiment 2: Hybrid Image Engine & Anti-Face Filter
Lokasi Fail: experiments/exp_image_hybrid.py

Fungsi:
1. Mengesahkan capaian dan integriti imej asal dari Reddit (JPEG/PNG/WebP).
2. Jika pos Reddit berasaskan teks tanpa gambar:
   - AI menjana kata kunci visual Bahasa Inggeris (2-3 perkataan).
   - Menarik kelompok 40 gambar daripada Unsplash API.
   - Menapis keluar gambar berwajah manusia (Anti-Face Filter).
   - Menyemak rekod penduaan Upstash Redis (30 Hari TTL).
3. Mengembalikan URL imej berkualiti tinggi yang siap untuk media sosial.
"""

import os
import sys
import re
import json
import random
import requests
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from dotenv import load_dotenv

# 1. Konfigurasi Laluan Projek & Muat Turun .env.local
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

env_local = PROJECT_ROOT / ".env.local"
if env_local.exists():
    load_dotenv(dotenv_path=env_local)
else:
    load_dotenv()

# Import enjin fetcher daripada Experiment 1
try:
    from experiments.exp_reddit_fetch import select_best_reddit_story
except ImportError:
    select_best_reddit_story = None

# =============================================================================
# 2. SENARAI TAG LARANGAN WAJAH & KATA KUNCI KESELAMATAN UNSPLASH
# =============================================================================
FORBIDDEN_FACE_TAGS = {
    "face", "portrait", "smiling", "smile", "woman looking", "man looking",
    "close up face", "selfie", "girl looking at camera", "guy looking at camera",
    "facial expression", "headshot", "lip", "eyes looking", "model looking",
    "human face", "female portrait", "male portrait", "front face"
}

ALLOWED_HUMAN_ANGLE_TAGS = {
    "hands typing", "back view", "rear view", "silhouette", "over the shoulder",
    "person typing", "sitting desk back", "unrecognizable person", "from behind"
}

SAFE_TECH_KEYWORDS = [
    "mechanical keyboard desk",
    "minimalist workspace pc",
    "dark coding setup",
    "datacenter server hardware",
    "ultrawide monitor setup",
    "custom pc water cooling",
    "gaming room ambient neon",
    "cable management desk"
]


# =============================================================================
# 3. PENGESAHAN CAPAIAN & INTEGRITI IMEJ REDDIT
# =============================================================================
def verify_image_accessibility(image_url: str) -> Tuple[bool, int, str]:
    """
    Memastikan URL imej boleh diakses oleh bot sosial (HTTP 200),
    mempunyai Content-Type imej, dan saiz fail mencukupi (> 1KB).
    """
    if not image_url or not image_url.startswith("http"):
        return False, 0, "URL imej kosong atau format tidak sah."

    headers = {
        "User-Agent": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)"
    }

    try:
        res = requests.get(image_url, headers=headers, timeout=12, stream=True)
        if res.status_code != 200:
            return False, res.status_code, f"HTTP {res.status_code}"

        content_type = res.headers.get("Content-Type", "").lower()
        if not any(t in content_type for t in ["image/jpeg", "image/png", "image/webp", "image/jpg"]):
            return False, res.status_code, f"Content-Type bukan imej sah ({content_type})"

        # Baca saiz awal data
        content_length = int(res.headers.get("Content-Length", 0))
        if content_length == 0:
            sample_bytes = res.raw.read(2048)
            content_length = len(sample_bytes)

        if content_length < 1000:
            return False, res.status_code, "Saiz imej terlalu kecil (< 1KB)."

        return True, res.status_code, f"Imej sah ({content_type}, ~{content_length} bytes)"
    except Exception as e:
        return False, 0, f"Ralat rangkaian semasa semakan imej: {str(e)}"


# =============================================================================
# 4. PENAPIS DEDUP REDIS UNTUK FOTO UNSPLASH
# =============================================================================
def is_unsplash_id_posted(photo_id: str, redis_url: str, redis_token: str) -> bool:
    """Semak sama ada photo_id Unsplash pernah digunakan dalam 30 hari."""
    if not redis_url or not redis_token or not photo_id:
        return False

    endpoint = f"{redis_url.rstrip('/')}/"
    headers = {"Authorization": f"Bearer {redis_token}"}
    payload = ["GET", f"posted:unsplash:{photo_id}"]

    try:
        res = requests.post(endpoint, json=payload, headers=headers, timeout=6)
        if res.status_code == 200:
            return res.json().get("result") is not None
    except Exception:
        pass
    return False


# =============================================================================
# 5. AI KEYWORD EXTRACTOR (OPENROUTER AI)
# =============================================================================
def generate_visual_keyword_via_ai(
    title: str,
    cleaned_text: str,
    base_url: str,
    model: str,
    api_key: str
) -> str:
    """
    Model AI membaca intipati cerita Reddit dan mengekstrak 2-3 perkataan
    kata kunci visual Bahasa Inggeris untuk carian foto Unsplash.
    """
    if not base_url or not model or not api_key:
        return random.choice(SAFE_TECH_KEYWORDS)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json; charset=utf-8",
        "HTTP-Referer": "https://sembangpctech.local",
        "X-Title": "Sembang PC & Tech Hybrid Image Engine",
    }

    system_prompt = """
Anda ialah Pakar Visual dan Pengarah Seni Media Sosial untuk Sembang PC & Tech.
Tugas anda: Baca tajuk dan intipati topik Reddit yang diberikan, kemudian hasilkan TEPAT 1 kata kunci carian foto Unsplash dalam Bahasa Inggeris (2 hingga 3 perkataan sahaja).

SYARAT KATA KUNCI:
1. Pendek, estetik, dan menepati konsep cerita (contoh: "mechanical keyboard", "server cable room", "minimalist desk workspace", "broken computer hardware", "dark coding room").
2. DILARANG sebut nama orang atau jenama spesifik yang jarang dijumpai di Unsplash.
3. DILARANG menghasilkan ayat panjang atau tanda petik. TULIS KATA KUNCI SAHAJA.
"""

    user_prompt = f"""
Topik Reddit:
- Tajuk: {title[:120]}
- Ringkasan Kandungan: {cleaned_text[:300] if cleaned_text else 'Topik perbincangan tech & PC'}

Hasilkan 1 kata kunci carian Unsplash (2-3 perkataan Inggeris):
"""

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": user_prompt.strip()},
        ],
        "temperature": 0.65,
        "max_tokens": 25,
    }

    url = f"{base_url.rstrip('/')}/chat/completions"

    try:
        res = requests.post(url, json=payload, headers=headers, timeout=15)
        if res.status_code == 200:
            res_json = res.json()
            raw_keyword = res_json["choices"][0]["message"]["content"].strip()
            # Bersihkan tanda baca
            clean_kw = re.sub(r'["\'\.\,\-]', '', raw_keyword).strip()
            words = clean_kw.split()
            if words:
                final_kw = " ".join(words[:3])
                if len(final_kw) >= 3:
                    return final_kw.lower()
    except Exception as e:
        print(f"⚠️ [AI KEYWORD WARN] Gagal jana kata kunci via AI: {e}")

    return random.choice(SAFE_TECH_KEYWORDS)


# =============================================================================
# 6. ANTI-FACE FILTER & UNSPLASH 40-POOL INGESTION
# =============================================================================
def is_photo_face_free(photo_data: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Menyemak metadata foto Unsplash (tags, description, alt_description).
    Menolak imej jika mengandungi wajah/potret manusia di hadapan kamera.
    """
    alt_desc = (photo_data.get("alt_description") or "").lower()
    desc = (photo_data.get("description") or "").lower()
    
    # Kumpulkan semua tag teks Unsplash
    tags = photo_data.get("tags", [])
    tag_titles = [t.get("title", "").lower() for t in tags if isinstance(t, dict)]

    combined_metadata_text = f"{alt_desc} {desc} {' '.join(tag_titles)}"

    # 1. Semak tag larangan wajah
    for forbidden in FORBIDDEN_FACE_TAGS:
        pattern = r'\b' + re.escape(forbidden) + r'\b'
        if re.search(pattern, combined_metadata_text):
            # Semak pengecualian jika ada sudut belakang/tangan
            if any(allowed in combined_metadata_text for allowed in ALLOWED_HUMAN_ANGLE_TAGS):
                return True, f"Dibenarkan (Sudut Diterima: Hands/Back Angle)"
            return False, f"Ditolak (Dikesan Tag Wajah: '{forbidden}')"

    return True, "Lulus (Sifar Wajah Manusia)"


def fetch_unsplash_fallback_image(
    keyword: str,
    unsplash_key: str,
    redis_url: str = "",
    redis_token: str = ""
) -> Optional[Dict[str, Any]]:
    """
    Menarik 40 calon imej daripada Unsplash API mengikut kata kunci,
    menapis wajah manusia dan menyemak penduaan Redis.
    """
    if not unsplash_key:
        print("❌ [UNSPLASH ERROR] UNSPLASH_ACCESS_KEY tidak dijumpai dalam env.")
        return None

    url = "https://api.unsplash.com/search/photos"
    params = {
        "query": keyword,
        "per_page": 40,  # Tarik kolam maksimum 40 gambar
        "page": 1,
        "client_id": unsplash_key,
    }

    print(f"📡 [UNSPLASH API CALL] Mencari 40 gambar untuk kata kunci: '{keyword}'...")

    try:
        res = requests.get(url, params=params, timeout=15)
        if res.status_code != 200:
            print(f"⚠️ [UNSPLASH HTTP {res.status_code}] {res.text[:120]}")
            return None

        data = res.json()
        results = data.get("results", [])
        if not results:
            print(f"⚠️ [UNSPLASH NO MATCH] Tiada gambar dijumpai untuk '{keyword}'. Mencuba carian sandaran...")
            fallback_kw = random.choice(SAFE_TECH_KEYWORDS)
            params["query"] = fallback_kw
            res_fb = requests.get(url, params=params, timeout=15)
            if res_fb.status_code == 200:
                results = res_fb.json().get("results", [])

        print(f"📥 Diterima {len(results)} calon imej mentah dari Unsplash. Memulakan tapisan anti-wajah...")

        rejected_faces = 0
        rejected_redis = 0

        for photo in results:
            photo_id = photo.get("id")
            img_url = photo.get("urls", {}).get("regular") or photo.get("urls", {}).get("full")
            if not photo_id or not img_url:
                continue

            # 1. Semakan Penapis Anti-Wajah Manusia
            is_face_free, reason = is_photo_face_free(photo)
            if not is_face_free:
                rejected_faces += 1
                continue

            # 2. Semakan Dedup Redis (30 Hari)
            if is_unsplash_id_posted(photo_id, redis_url, redis_token):
                rejected_redis += 1
                continue

            # 3. Sahkan capaian imej
            ok_img, _, _ = verify_image_accessibility(img_url)
            if not ok_img:
                continue

            print(f"  ✅ [FOTO TERPILIH] Unsplash ID: {photo_id} | {reason}")
            return {
                "source": "UNSPLASH_FALLBACK",
                "image_url": img_url,
                "photo_id": photo_id,
                "keyword_used": keyword,
                "author": photo.get("user", {}).get("name", "Unsplash Creator"),
                "description": photo.get("alt_description") or photo.get("description") or keyword
            }

        print(f"⚠️ [UNSPLASH FILTER STATS] Ditolak {rejected_faces} foto (Wajah) & {rejected_redis} foto (Redis).")

    except Exception as e:
        print(f"❌ [UNSPLASH EXCEPTION] {e}")

    return None


# =============================================================================
# 7. ENJIN RESOLUSI IMEJ HIBRID (FUNGSI UTAMA)
# =============================================================================
def resolve_hybrid_story_image(
    reddit_post: Dict[str, Any],
    base_url: str,
    model: str,
    api_key: str,
    unsplash_key: str,
    redis_url: str = "",
    redis_token: str = ""
) -> Tuple[bool, Dict[str, Any], str]:
    """
    Fungsi Utama Resolusi Imej:
    - Langkah 1: Semak jika pos Reddit mempunyai imej langsung yang sah.
    - Langkah 2: Jika tiada atau gagal, jana kata kunci AI & tarik dari Unsplash.
    """
    raw_reddit_img = reddit_post.get("image_url")
    title = reddit_post.get("title", "Sembang PC Tech")
    cleaned_text = reddit_post.get("cleaned_text", "")

    # -------------------------------------------------------------------------
    # ALIRAN 1: PENGESAHAN IMEJ ASAL REDDIT
    # -------------------------------------------------------------------------
    if raw_reddit_img:
        print(f"🔍 [LALUAN 1] Menguji imej asal Reddit: {raw_reddit_img} ...")
        is_ok, status_code, msg = verify_image_accessibility(raw_reddit_img)
        if is_ok:
            print(f"  ✅ Imej Reddit sah ({msg}). Menggunakan imej asal!")
            return True, {
                "source": "REDDIT_DIRECT",
                "image_url": raw_reddit_img,
                "photo_id": reddit_post.get("post_id", "reddit_img"),
                "description": title,
                "keyword_used": "reddit_original"
            }, "Berjaya menggunakan imej asal Reddit."
        else:
            print(f"  ⚠️ Imej Reddit gagal disahkan ({msg}). Beralih ke Fallback Unsplash...")

    # -------------------------------------------------------------------------
    # ALIRAN 2: FALLBACK ENJIN UNSPLASH (ANTI-FACE + AI KEYWORD)
    # -------------------------------------------------------------------------
    print(f"🌐 [LALUAN 2] Mengaktifkan Enjin Imej Sandaran Unsplash...")
    
    # 1. Jana kata kunci pintar berasaskan cerita
    visual_kw = generate_visual_keyword_via_ai(title, cleaned_text, base_url, model, api_key)
    print(f"🤖 [AI VISUAL KEYWORD] Kata kunci carian dijana: '{visual_kw}'")

    # 2. Tarik & tapis daripada Unsplash
    unsplash_res = fetch_unsplash_fallback_image(visual_kw, unsplash_key, redis_url, redis_token)
    if unsplash_res:
        return True, unsplash_res, f"Berjaya mendapatkan imej Unsplash tanpa wajah bagi kata kunci '{visual_kw}'."

    return False, {}, "Gagal mendapatkan imej daripada Reddit mahupun Unsplash."


# =============================================================================
# 8. RUNNER UJIAN EKSPERIMEN 2
# =============================================================================
if __name__ == "__main__":
    print("\n" + "=" * 75)
    print("🚀 [EXPERIMENT 2] MEMULAKAN UJIAN HYBRID IMAGE ENGINE & ANTI-FACE FILTER")
    print("=" * 75)

    base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip()
    model = os.getenv("OPENROUTER_MODEL", "").strip()
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    unsplash_key = os.getenv("UNSPLASH_ACCESS_KEY", "").strip()
    redis_url = os.getenv("UPSTASH_REDIS_REST_URL", "").strip()
    redis_token = os.getenv("UPSTASH_REDIS_REST_TOKEN", "").strip()

    # Dapatkan calon pos daripada Ujian 1 jika modul tersedia
    selected_story = None
    if select_best_reddit_story:
        print("\n📡 Mengambil data pos Reddit langsung daripada Experiment 1...")
        ok_fetch, story, _, _ = select_best_reddit_story()
        if ok_fetch:
            selected_story = story

    # Jika tiada, sediakan mock post ujian (1 Pos Gambar + 1 Pos Teks Tanpa Gambar)
    if not selected_story:
        print("\nℹ️ Menggunakan data ujian mock...")
        selected_story = {
            "post_id": "mock_story_101",
            "subreddit": "talesfromtechsupport",
            "title": "User plugged the power strip into itself and wondered why the PC died",
            "cleaned_text": "Working as IT support for 10 years, today a user called panicked saying the workstation smelled like smoke...",
            "image_url": None  # Sengaja kosongkan untuk menguji Unsplash Fallback
        }

    print("\n" + "-" * 75)
    print(f"📦 [DATA INPUT POS]:")
    print(f"   📌 Subreddit : r/{selected_story.get('subreddit')}")
    print(f"   📖 Tajuk     : {selected_story.get('title')}")
    print(f"   🖼️ Imej Asal : {selected_story.get('image_url') or '[TIADA - Menguji Unsplash Fallback]'}")
    print("-" * 75 + "\n")

    success, final_image, status_msg = resolve_hybrid_story_image(
        reddit_post=selected_story,
        base_url=base_url,
        model=model,
        api_key=api_key,
        unsplash_key=unsplash_key,
        redis_url=redis_url,
        redis_token=redis_token
    )

    if success and final_image:
        print("\n" + "🎉" * 38)
        print("🏆 HASIL RESOLUSI ENJIN IMEJ HIBRID BERJAYA:")
        print("🎉" * 38)
        print(f"⚙️ Sumber Terpilih : {final_image['source']}")
        print(f"🖼️ URL Imej Akhir  : {final_image['image_url']}")
        print(f"🆔 ID Foto/Imej    : {final_image['photo_id']}")
        print(f"🔑 Kata Kunci Diguna: {final_image['keyword_used']}")
        print(f"📝 Keterangan Visual: {final_image['description']}")
        print("=" * 75)
        print("✨ Ujian 2 Selesai! Enjin Imej bersedia untuk digabungkan dengan Enjin AI Persona (Ujian 3).\n")
    else:
        print(f"\n❌ [RALAT UJIAN 2] {status_msg}\n")