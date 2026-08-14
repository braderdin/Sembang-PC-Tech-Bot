#!/usr/bin/env python3
"""
Dedicated Unsplash Keyword Generation & Deduplication Engine
Sembang PC & Tech Ecosystem (Redis 5-Day & Vector 2-Day Guardrails + 2-Round Feedback Loop)
"""

import os
import re
import json
import time
import random
import requests
from typing import List, Optional, Tuple
from dotenv import load_dotenv

from src.lifestyle_ai_persona import detect_current_time_slot, TECH_VISUAL_SEEDS

load_dotenv()


# -----------------------------------------------------------------------------
# 1. BANTUAN REST API UPSTASH REDIS (EXACT MATCH 5 HARI)
# -----------------------------------------------------------------------------

def is_keyword_in_redis(redis_url: str, redis_token: str, keyword: str) -> bool:
    """Semak sama ada kata kunci 100% sama pernah digunakan dalam 5 hari."""
    if not redis_url or not redis_token:
        return False

    clean_kw = re.sub(r'[^a-zA-Z0-9]', '_', keyword.lower().strip())
    key = f"lifestyle:kw_exact:{clean_kw}"
    headers = {"Authorization": f"Bearer {redis_token}"}

    try:
        res = requests.post(
            redis_url.rstrip("/"),
            headers=headers,
            json=["GET", key],
            timeout=10
        )
        if res.status_code == 200:
            val = res.json().get("result")
            return val is not None
    except Exception as e:
        print(f"⚠️ [Keyword Redis Check Warn]: {e}")
    return False


def save_keyword_to_redis(redis_url: str, redis_token: str, keyword: str, ttl_days: int = 5) -> bool:
    """Simpan kata kunci terpilih ke Redis dengan TTL 5 Hari (432,000 saat)."""
    if not redis_url or not redis_token:
        return False

    clean_kw = re.sub(r'[^a-zA-Z0-9]', '_', keyword.lower().strip())
    key = f"lifestyle:kw_exact:{clean_kw}"
    ttl_seconds = ttl_days * 86400
    headers = {"Authorization": f"Bearer {redis_token}"}

    try:
        res = requests.post(
            redis_url.rstrip("/"),
            headers=headers,
            json=["SETEX", key, ttl_seconds, "USED"],
            timeout=10
        )
        return res.status_code == 200
    except Exception as e:
        print(f"⚠️ [Keyword Redis Save Warn]: {e}")
    return False


# -----------------------------------------------------------------------------
# 2. BANTUAN REST API UPSTASH VECTOR (SIMILARITY >= 90% 2 HARI)
# -----------------------------------------------------------------------------

def is_keyword_too_similar_in_vector(
    vector_url: str,
    vector_token: str,
    keyword: str,
    threshold: float = 0.90
) -> Tuple[bool, float, str]:
    """
    Semak sama ada makna kata kunci mirip >= 90% dengan kata kunci dalam 48 jam lepas.
    """
    if not vector_url or not vector_token:
        return False, 0.0, ""

    headers = {
        "Authorization": f"Bearer {vector_token}",
        "Content-Type": "application/json",
    }
    endpoint = f"{vector_url.rstrip('/')}/query"
    payload = {
        "data": keyword.strip(),
        "topK": 3,
        "includeMetadata": True,
    }

    try:
        res = requests.post(endpoint, headers=headers, json=payload, timeout=10)
        if res.status_code == 200:
            matches = res.json().get("result", [])
            current_ts = int(time.time())
            window_48h = 48 * 3600  # 2 Hari

            for match in matches:
                score = match.get("score", 0.0)
                metadata = match.get("metadata", {})
                item_type = metadata.get("type", "")

                # Hanya semak vektor jenis 'unsplash_keyword'
                if item_type != "unsplash_keyword":
                    continue

                posted_ts = metadata.get("timestamp", 0)
                if current_ts - posted_ts <= window_48h:
                    if score >= threshold:
                        matched_kw = metadata.get("keyword", match.get("id", ""))
                        return True, score, matched_kw
    except Exception as e:
        print(f"⚠️ [Keyword Vector Check Warn]: {e}")

    return False, 0.0, ""


def save_keyword_to_vector(vector_url: str, vector_token: str, keyword: str) -> bool:
    """Simpan vektor kata kunci ke Upstash Vector DB."""
    if not vector_url or not vector_token:
        return False

    clean_kw_id = re.sub(r'[^a-zA-Z0-9]', '_', keyword.lower().strip())
    headers = {
        "Authorization": f"Bearer {vector_token}",
        "Content-Type": "application/json",
    }
    endpoint = f"{vector_url.rstrip('/')}/upsert"
    payload = {
        "id": f"kw_{clean_kw_id}_{int(time.time())}",
        "data": keyword.strip(),
        "metadata": {
            "keyword": keyword.strip(),
            "type": "unsplash_keyword",
            "timestamp": int(time.time()),
        },
    }

    try:
        res = requests.post(endpoint, headers=headers, json=payload, timeout=10)
        return res.status_code == 200
    except Exception as e:
        print(f"⚠️ [Keyword Vector Save Warn]: {e}")
    return False


# -----------------------------------------------------------------------------
# 3. AI JANA 10 CALON KATA KUNCI & PENAPISAN DINAMIK (DENGAN MAKLUM BALAS)
# -----------------------------------------------------------------------------

def generate_10_keyword_candidates(
    base_url: str,
    model: str,
    api_key: str,
    rejected_keywords: Optional[List[str]] = None
) -> List[str]:
    """
    Panggil OpenRouter untuk menjana 10 cadangan kata kunci visual Unsplash.
    Jika rejected_keywords dibekalkan, AI diberi arahan mengelak tema tersebut.
    """
    slot_id, slot_desc, day_mood, _ = detect_current_time_slot()
    sampled_seeds = random.sample(TECH_VISUAL_SEEDS, min(5, len(TECH_VISUAL_SEEDS)))

    if not base_url or not model or not api_key:
        return random.sample(TECH_VISUAL_SEEDS, 10)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json; charset=utf-8",
        "HTTP-Referer": "https://sembangpctech.local",
        "X-Title": "Sembang PC & Tech Bot",
    }

    feedback_context = ""
    if rejected_keywords and len(rejected_keywords) > 0:
        rejected_str = ", ".join([f"'{k}'" for k in rejected_keywords])
        feedback_context = f"""
PERHATIAN - KATA KUNCI BERIKUT BARU SAHAJA DIGUNAKAN & DITOLAK (DILARANG ULANG ATAU BERI YANG SERUPA):
[{rejected_str}]
Sila terokai sub-niche teknologi / gaya hidup komputer yang berbeza sama sekali!
"""

    system_prompt = f"""
Anda adalah pakar visual carian foto Unsplash untuk tema teknologi, perkakasan PC, dan lifestyle ruang kerja di Malaysia.

WAKTU HANTARAN: {slot_desc}
MOOD SUASANA: {day_mood}
CONTOH INSPIRASI: {', '.join(sampled_seeds)}
{feedback_context}
TUGAS ANDA:
Hasilkan TEPAT 10 kata kunci carian foto Unsplash yang unik, pelbagai, dan berbeza sudut visual dalam Bahasa Inggeris.
Setiap kata kunci WAJIB ringkas (2 hingga 3 patah perkataan sahaja).

FORMAT JAWAPAN (JSON ARRAY SAHAJA):
["mechanical keyboard", "minimalist desk setup", "server rack room", "ultrawide monitor", "dark coding room", "coffee tech workspace", "pc water cooling", "cyberpunk desk", "macro keycaps", "studio audio desk"]
"""

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": "Beri senarai 10 kata kunci carian Unsplash unik (2-3 perkataan setiap satu) dalam format JSON array."},
        ],
        "temperature": 0.80 if rejected_keywords else 0.75,
        "max_tokens": 300,
    }

    try:
        res = requests.post(f"{base_url.rstrip('/')}/chat/completions", headers=headers, json=payload, timeout=20)
        if res.status_code == 200:
            content = res.json()["choices"][0]["message"]["content"].strip()
            match = re.search(r'\[[\s\S]*?\]', content)
            if match:
                candidates = json.loads(match.group(0))
                cleaned = []
                for kw in candidates:
                    kw_clean = " ".join(str(kw).strip().split()[:3])  # Hadkan max 3 perkataan
                    if len(kw_clean) >= 4:
                        cleaned.append(kw_clean.lower())
                if len(cleaned) >= 5:
                    return cleaned
    except Exception as e:
        print(f"⚠️ [Keyword Batch Generation Warn]: {e}")

    # Fallback jika model gagal pulangkan JSON
    return random.sample(TECH_VISUAL_SEEDS, 10)


def get_fresh_lifestyle_keyword(
    base_url: str,
    model: str,
    api_key: str,
    redis_url: str,
    redis_token: str,
    vector_url: str,
    vector_token: str
) -> str:
    """
    Menjana kata kunci dengan sistem 2 Pusingan (Feedback & Retry Loop),
    menapis melalui Redis (5 hari) & Vector (90% 2 hari),
    dan mengembalikan 1 kata kunci terbaik yang sah dan segar.
    """
    selected_keyword = None
    all_rejected_keywords = []

    # =========================================================================
    # PUSINGAN 1: JANA 10 CALON PERTAMA
    # =========================================================================
    print("\n💡 [KEYWORD ENGINE] [Pusingan 1] Menjana 10 calon kata kunci carian Unsplash dari AI...")
    candidates_r1 = generate_10_keyword_candidates(base_url, model, api_key)
    print(f"📋 [CALON PUSINGAN 1]: {candidates_r1}")

    for idx, kw in enumerate(candidates_r1, 1):
        print(f"\n  🔍 [R1] Calon #{idx}: '{kw}'")

        # 1. Semakan Redis (Exact Match 100% - 5 Hari)
        if is_keyword_in_redis(redis_url, redis_token, kw):
            print(f"     ⏭️ [REDIS SKIP] Kata kunci 100% sama pernah digunakan < 5 hari lepas.")
            all_rejected_keywords.append(kw)
            continue

        # 2. Semakan Upstash Vector (Mirip >= 90% - 2 Hari)
        is_similar, score, matched_kw = is_keyword_too_similar_in_vector(
            vector_url=vector_url,
            vector_token=vector_token,
            keyword=kw,
            threshold=0.90
        )
        if is_similar:
            print(f"     ⏭️ [VECTOR SKIP] Mirip ({score:.1%}) dengan '{matched_kw}' (< 48 jam lepas).")
            all_rejected_keywords.append(kw)
            continue

        # Lulus Pusingan 1!
        selected_keyword = kw
        print(f"     ✅ [LULUS TAPISAN R1] Kata kunci disahkan segar & unik!")
        break

    # =========================================================================
    # PUSINGAN 2: JIKA SEMUA 10 CALON R1 GAGAL (RETRY DENGAN MAKLUM BALAS)
    # =========================================================================
    if not selected_keyword:
        print("\n" + "=" * 65)
        print("⚠️ [PUSINGAN 1 GAGAL] Kesemua 10 calon tersangkut pada tapisan Redis/Vector.")
        print("🔄 [PUSINGAN 2 - RETRY LOOP] Menghantar maklum balas senarai ditolak ke AI...")
        print("=" * 65)

        candidates_r2 = generate_10_keyword_candidates(
            base_url=base_url,
            model=model,
            api_key=api_key,
            rejected_keywords=all_rejected_keywords
        )
        print(f"📋 [CALON PUSINGAN 2]: {candidates_r2}")

        for idx, kw in enumerate(candidates_r2, 1):
            print(f"\n  🔍 [R2] Calon #{idx}: '{kw}'")

            # 1. Semakan Redis (Exact Match 100% - 5 Hari)
            if is_keyword_in_redis(redis_url, redis_token, kw):
                print(f"     ⏭️ [REDIS SKIP] Kata kunci 100% sama pernah digunakan < 5 hari lepas.")
                continue

            # 2. Semakan Upstash Vector (Mirip >= 90% - 2 Hari)
            is_similar, score, matched_kw = is_keyword_too_similar_in_vector(
                vector_url=vector_url,
                vector_token=vector_token,
                keyword=kw,
                threshold=0.90
            )
            if is_similar:
                print(f"     ⏭️ [VECTOR SKIP] Mirip ({score:.1%}) dengan '{matched_kw}' (< 48 jam lepas).")
                continue

            # Lulus Pusingan 2!
            selected_keyword = kw
            print(f"     ✅ [LULUS TAPISAN R2] Kata kunci pusingan kedua disahkan segar & unik!")
            break

    # =========================================================================
    # FALLBACK KECEMASAN (JIKA KEDUA-DUA PUSINGAN MASIH GAGAL)
    # =========================================================================
    if not selected_keyword:
        print("\n⚠️ [KEYWORD FALLBACK] Semua calon Pusingan 1 & 2 dalam tempoh bertenang. Memilih tema sandaran selamat...")
        selected_keyword = random.choice(TECH_VISUAL_SEEDS)

    # Simpan rekod kata kunci terpilih ke Redis (5 Hari) & Vector DB (2 Hari)
    save_keyword_to_redis(redis_url, redis_token, selected_keyword, ttl_days=5)
    save_keyword_to_vector(vector_url, vector_token, selected_keyword)
    print(f"\n🎯 [KATA KUNCI RASMI DIPILIH]: '{selected_keyword}' (Direkod ke Redis 5-Hari & Vector 2-Hari)\n")

    return selected_keyword