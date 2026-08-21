#!/usr/bin/env python3
"""
Reddit Tech Storyteller Engine: Hybrid Image Engine & Anti-Face Filter
Lokasi Fail: src/reddit_image_engine.py

Ciri-ciri Penambahbaikan (Tuned):
1. Dinamik 100% (Sifar Hardcode Model): Membaca REDDIT_OPENROUTER_MODEL, REDDIT_OPENROUTER_MODEL_FALLBACK, dan fallback am OPENROUTER_MODEL.
2. Penyingkiran Penalti Inferens: Membuang parameter presence_penalty dan frequency_penalty untuk keserasian optimum model Gemma 4 & pelayan percuma OpenRouter.
3. Penghurai JSON Kebal Glitch: Menggunakan pembersih regex teguh yang membuang blok pemikiran (<think>...</think>) dan mengekstrak elemen JSON Array secara selamat tanpa ralat JSON decode.
4. Tapisan Anti-Wajah (Unsplash 40-Pool): Menapis imej berwajah manusia serta menyemak penapis duplikasi Upstash Redis.
"""

import os
import re
import json
import time
import random
import requests
from typing import Dict, Any, Optional, Tuple, List

# =============================================================================
# 1. SENARAI TAG KESELAMATAN & KATA KUNCI SANDARAN
# =============================================================================
FORBIDDEN_FACE_TAGS = {
    "face", "portrait", "smiling", "smile", "woman looking", "man looking",
    "close up face", "selfie", "girl looking at camera", "guy looking at camera",
    "facial expression", "headshot", "lip", "eyes looking", "model looking",
    "human face", "female portrait", "male portrait", "front face", "person looking"
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
    "cable management desk",
    "electronics circuit board",
    "retro vintage computer"
]


# =============================================================================
# 2. PENGESAHAN CAPAIAN IMEJ REDDIT
# =============================================================================
def verify_image_accessibility(image_url: str) -> Tuple[bool, int, str]:
    """
    Memastikan URL imej boleh diakses oleh perayap media sosial (HTTP 200),
    mempunyai jenis MIME imej yang sah, dan saiz fail mencukupi (> 1KB).
    """
    if not image_url or not image_url.startswith("http"):
        return False, 0, "URL imej kosong atau tidak sah."

    headers = {
        "User-Agent": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)"
    }

    try:
        res = requests.get(image_url, headers=headers, timeout=12, stream=True)
        if res.status_code != 200:
            return False, res.status_code, f"HTTP {res.status_code}"

        content_type = res.headers.get("Content-Type", "").lower()
        if not any(t in content_type for t in ["image/jpeg", "image/png", "image/webp", "image/jpg"]):
            return False, res.status_code, f"MIME bukan imej ({content_type})"

        content_length = int(res.headers.get("Content-Length", 0))
        if content_length == 0:
            sample_bytes = res.raw.read(2048)
            content_length = len(sample_bytes)

        if content_length < 1000:
            return False, res.status_code, "Saiz imej terlalu kecil (< 1KB)."

        return True, res.status_code, f"Imej sah ({content_type}, ~{content_length} bytes)"
    except Exception as e:
        return False, 0, f"Ralat sambungan imej: {str(e)}"


# =============================================================================
# 3. PENAPIS DEDUP UPSTASH REDIS UNTUK FOTO UNSPLASH
# =============================================================================
def is_unsplash_id_posted(photo_id: str, redis_url: str, redis_token: str) -> bool:
    """Semak sama ada photo_id Unsplash pernah digunakan dalam tempoh 30 hari."""
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
# 4. PENGHURAI JSON TEGUH & PENJANAAN 10 KATA KUNCI VISUAL
# =============================================================================
def extract_json_array_robust(text: str) -> List[str]:
    """
    Mengekstrak senarai JSON array secara selamat daripada output AI,
    termasuk membuang blok pemikiran (<think>...</think>) dan tag Markdown.
    """
    if not text:
        return []

    # 1. Buang sebarang blok pemikiran model reasoning
    clean_text = re.sub(r'<think>[\s\S]*?</think>', '', text, flags=re.IGNORECASE)
    clean_text = re.sub(r'(?i)here\'?s\s+a\s+thinking\s+process[\s\S]*?\n\n', '', clean_text)
    clean_text = re.sub(r'```json\s*', '', clean_text, flags=re.IGNORECASE)
    clean_text = re.sub(r'```\s*', '', clean_text)

    # 2. Cari kurungan JSON array [...]
    match = re.search(r'\[[\s\S]*?\]', clean_text)
    if match:
        raw_json_str = match.group(0).strip()
        try:
            parsed = json.loads(raw_json_str)
            if isinstance(parsed, list):
                result = []
                for item in parsed:
                    clean_kw = " ".join(str(item).strip().split()[:3])
                    clean_kw = re.sub(r'[^a-zA-Z0-9\s]', '', clean_kw).strip().lower()
                    if len(clean_kw) >= 3:
                        result.append(clean_kw)
                if len(result) >= 3:
                    return result
        except Exception:
            pass

    # 3. Fallback Regex jika JSON decode gagal akibat koma/tanda petik rosak
    fallback_matches = re.findall(r'["\']([a-zA-Z0-9\s]{3,35})["\']', clean_text)
    cleaned_fallback = []
    for item in fallback_matches:
        kw = " ".join(item.strip().split()[:3]).lower()
        if len(kw) >= 3 and kw not in cleaned_fallback:
            cleaned_fallback.append(kw)

    return cleaned_fallback if len(cleaned_fallback) >= 3 else []


def generate_10_visual_keywords(
    title: str,
    cleaned_text: str,
    base_url: str,
    model: str,
    model_fallback: str,
    api_key: str
) -> List[str]:
    """
    Model AI membaca intipati artikel Reddit dan menjana senarai 10 calon kata kunci
    visual Unsplash dalam Bahasa Inggeris (2 hingga 3 perkataan setiap satu).
    """
    if not base_url or not api_key:
        return SAFE_TECH_KEYWORDS

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json; charset=utf-8",
        "HTTP-Referer": "https://sembangpctech.local",
        "X-Title": "Sembang PC & Tech Hybrid Image Engine",
    }

    system_prompt = """
You are a Visual Director for Tech Media.
Your task: Read the Reddit topic and generate EXACTLY 10 visual search keywords for Unsplash in English (2 to 3 words each).

RULES:
1. Short, aesthetic, hardware/desk/gadget/tech oriented (e.g. "mechanical keyboard", "server cable room", "minimalist desk setup", "smartwatch design", "dark coding room").
2. DO NOT include personal names or rare obscure brands.
3. OUTPUT FORMAT: JSON Array of 10 strings ONLY. No conversational intro.
["keyword 1", "keyword 2", ..., "keyword 10"]
"""

    user_prompt = f"""
Reddit Topic:
- Title: {title[:120]}
- Summary: {cleaned_text[:350] if cleaned_text else 'Technology community discussion'}

Generate JSON Array with 10 Unsplash keywords:
"""

    # Model dinamik mengikut keutamaan konfigurasi env
    primary_m = (
        model
        or os.getenv("REDDIT_OPENROUTER_MODEL", "").strip()
        or os.getenv("OPENROUTER_MODEL", "").strip()
    )
    fallback_m = (
        model_fallback
        or os.getenv("REDDIT_OPENROUTER_MODEL_FALLBACK", "").strip()
        or os.getenv("OPENROUTER_MODEL_FALLBACK", "").strip()
    )

    models_to_try = [m for m in [primary_m, fallback_m] if m]
    if not models_to_try:
        return SAFE_TECH_KEYWORDS

    for selected_model in models_to_try:
        payload = {
            "model": selected_model,
            "messages": [
                {"role": "system", "content": system_prompt.strip()},
                {"role": "user", "content": user_prompt.strip()},
            ],
            "temperature": 0.65,
            "max_tokens": 300
        }

        try:
            res = requests.post(f"{base_url.rstrip('/')}/chat/completions", json=payload, headers=headers, timeout=20)
            if res.status_code == 200:
                raw_response = res.json()["choices"][0]["message"]["content"].strip()
                extracted_keywords = extract_json_array_robust(raw_response)
                if extracted_keywords:
                    return extracted_keywords
            elif res.status_code == 429:
                print(f"⚠️ [IMAGE AI 429] Model '{selected_model}' sesak. Mencuba model seterusnya...")
                time.sleep(2)
        except Exception as e:
            print(f"⚠️ [IMAGE AI EXCEPTION]: {e}")

    return SAFE_TECH_KEYWORDS


# =============================================================================
# 5. ANTI-FACE FILTER & UNSPLASH 40-POOL INGESTION
# =============================================================================
def is_photo_face_free(photo_data: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Menyemak metadata foto Unsplash (tags, description, alt_description).
    Menolak imej jika mengandungi wajah/potret manusia di hadapan kamera.
    """
    alt_desc = (photo_data.get("alt_description") or "").lower()
    desc = (photo_data.get("description") or "").lower()

    tags = photo_data.get("tags", [])
    tag_titles = [t.get("title", "").lower() for t in tags if isinstance(t, dict)]

    combined_metadata_text = f"{alt_desc} {desc} {' '.join(tag_titles)}"

    for forbidden in FORBIDDEN_FACE_TAGS:
        pattern = r'\b' + re.escape(forbidden) + r'\b'
        if re.search(pattern, combined_metadata_text):
            if any(allowed in combined_metadata_text for allowed in ALLOWED_HUMAN_ANGLE_TAGS):
                return True, "Dibenarkan (Sudut Tangan / Pandangan Belakang)"
            return False, f"Ditolak (Dikesan Tag Wajah: '{forbidden}')"

    return True, "Lulus (Sifar Wajah Manusia)"


def fetch_unsplash_images(keyword: str, access_key: str, count: int = 40) -> List[Dict[str, Any]]:
    """
    Membuat 1 panggilan ke Unsplash API untuk menarik sehingga 40 gambar bertema.
    """
    if not access_key:
        return []

    url = "https://api.unsplash.com/search/photos"
    params = {
        "query": keyword,
        "per_page": count,
        "page": 1,
        "client_id": access_key,
    }

    try:
        res = requests.get(url, params=params, timeout=15)
        if res.status_code == 200:
            return res.json().get("results", [])
    except Exception as e:
        print(f"❌ [UNSPLASH FETCH ERROR]: {e}")

    return []


def select_best_matching_image(
    photos: List[Dict[str, Any]],
    article_title: str,
    article_text: str,
    keyword_used: str,
    redis_url: str = "",
    redis_token: str = ""
) -> Optional[Dict[str, Any]]:
    """
    Menapis senarai 40 imej daripada Unsplash:
    1. Menyingkirkan imej berwajah manusia.
    2. Menolak foto yang pernah digunakan di Upstash Redis (< 30 hari).
    3. Mengira skor keserasian (Relevance Score) berasaskan tajuk & artikel.
    """
    scored_candidates = []
    context_words = set(re.findall(r'\b[a-zA-Z]{4,}\b', f"{article_title} {article_text}".lower()))

    for photo in photos:
        photo_id = photo.get("id")
        img_url = photo.get("urls", {}).get("regular") or photo.get("urls", {}).get("full")
        if not photo_id or not img_url:
            continue

        # 1. Tapisan Anti-Wajah Manusia
        is_face_free, _ = is_photo_face_free(photo)
        if not is_face_free:
            continue

        # 2. Semakan Dedup Redis (30 Hari)
        if is_unsplash_id_posted(photo_id, redis_url, redis_token):
            continue

        # 3. Semak kesahan capaian imej
        ok_img, _, _ = verify_image_accessibility(img_url)
        if not ok_img:
            continue

        # 4. Kira Skor Keserasian Visual
        alt_desc = (photo.get("alt_description") or photo.get("description") or "").lower()
        photo_words = set(re.findall(r'\b[a-zA-Z]{4,}\b', alt_desc))

        relevance_score = len(photo_words.intersection(context_words))
        likes_count = photo.get("likes", 0)
        total_score = (relevance_score * 10) + min(likes_count, 50)

        scored_candidates.append({
            "total_score": total_score,
            "data": {
                "source": "UNSPLASH_FALLBACK",
                "image_url": img_url,
                "photo_id": photo_id,
                "keyword_used": keyword_used,
                "author": photo.get("user", {}).get("name", "Unsplash Creator"),
                "description": alt_desc if alt_desc else keyword_used
            }
        })

    if scored_candidates:
        scored_candidates.sort(key=lambda x: x["total_score"], reverse=True)
        return scored_candidates[0]["data"]

    return None


# =============================================================================
# 6. ENJIN RESOLUSI IMEJ HIBRID (PINTU UTAMA)
# =============================================================================
def resolve_reddit_story_image(
    reddit_post: Dict[str, Any],
    base_url: str,
    model: str = "",
    model_fallback: str = "",
    api_key: str = "",
    unsplash_key: str = "",
    redis_url: str = "",
    redis_token: str = ""
) -> Tuple[bool, Dict[str, Any], str]:
    """
    Pintu Utama Resolusi Imej:
    - Langkah 1: Semak imej asal Reddit. Jika sah, terus gunakan.
    - Langkah 2: Jika tiada imej Reddit, jana 10 kata kunci AI, pilih 1 terbaik,
      tarik 40 gambar dari Unsplash, dan pilih 1 imej paling serasi.
    """
    raw_reddit_img = reddit_post.get("image_url")
    title = reddit_post.get("title", "Sembang PC Tech")
    cleaned_text = reddit_post.get("cleaned_text", "")

    # -------------------------------------------------------------------------
    # ALIRAN 1: PENGESAHAN IMEJ ASAL REDDIT
    # -------------------------------------------------------------------------
    if raw_reddit_img:
        is_ok, _, msg = verify_image_accessibility(raw_reddit_img)
        if is_ok:
            return True, {
                "source": "REDDIT_DIRECT",
                "image_url": raw_reddit_img,
                "photo_id": str(reddit_post.get("post_id", "reddit_direct")),
                "description": title,
                "keyword_used": "reddit_original"
            }, "Menggunakan imej asal Reddit yang disahkan."

    # -------------------------------------------------------------------------
    # ALIRAN 2: FALLBACK ENJIN UNSPLASH (ANTI-FACE + AI 10-KEYWORD ENGINE)
    # -------------------------------------------------------------------------
    # 1. AI jana 10 calon kata kunci visual
    keywords_10 = generate_10_visual_keywords(
        title=title,
        cleaned_text=cleaned_text,
        base_url=base_url,
        model=model,
        model_fallback=model_fallback,
        api_key=api_key
    )

    # 2. Gunakan kata kunci teratas (paling relevan)
    chosen_keyword = keywords_10[0] if keywords_10 else random.choice(SAFE_TECH_KEYWORDS)

    # 3. Tarik kelompok 40 gambar dari Unsplash API
    photos_40 = fetch_unsplash_images(chosen_keyword, unsplash_key, count=40)

    # Jika kata kunci pertama tiada hasil, cuba kata kunci kedua
    if not photos_40 and len(keywords_10) > 1:
        chosen_keyword = keywords_10[1]
        photos_40 = fetch_unsplash_images(chosen_keyword, unsplash_key, count=40)

    # Jika masih tiada, cuba tema sandaran selamat
    if not photos_40:
        chosen_keyword = random.choice(SAFE_TECH_KEYWORDS)
        photos_40 = fetch_unsplash_images(chosen_keyword, unsplash_key, count=40)

    # 4. Tapis anti-wajah, semak Redis, dan pilih 1 gambar terbaik
    selected_img = select_best_matching_image(
        photos=photos_40,
        article_title=title,
        article_text=cleaned_text,
        keyword_used=chosen_keyword,
        redis_url=redis_url,
        redis_token=redis_token
    )

    if selected_img:
        return True, selected_img, f"Imej Unsplash dipilih bagi kata kunci '{chosen_keyword}'."

    return False, {}, "Gagal mendapatkan imej daripada Reddit mahupun Unsplash."