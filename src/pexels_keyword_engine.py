#!/usr/bin/env python3
"""
Dedicated Pexels 9:16 Video Keyword Generation & Deduplication Engine
Sembang PC & Tech Ecosystem
Features:
- 40 Faceless B-Roll Tech Seeds (Strictly no human faces, no sensitive animals)
- Automatic ASCII Sanitization (Removes mojibake glitch tokens)
- 20-Keyword Redis Memory Bank Ingestion (Supplies past themes to AI to prevent repetition)
- Multi-Candidate Vetted Pool Generation (Redis 5-Day & Upstash Vector 5-Day Semantic Guardrails)
- Post-Validation Commit Mechanism (Only locks keyword after video download succeeds)
"""

import os
import re
import json
import random
import requests
from typing import List, Optional
from dotenv import load_dotenv

from src.pexels_ai_persona import detect_reel_time_slot
from src.pexels_redis_db import (
    is_reel_keyword_in_redis,
    save_reel_keyword_to_redis,
    get_recent_reel_keywords,
    save_reel_keyword_memory,
)
from src.pexels_vector_db import is_similar_reel_keyword_in_vector, save_reel_keyword_to_vector

load_dotenv()

# =============================================================================
# 40 HARDCORE FACELESS TECH VISUAL SEEDS (B-ROLL & OBJECT FOCUS ONLY)
# =============================================================================
PEXELS_TECH_VISUAL_SEEDS = [
    "mechanical keyboard typing close up",
    "rgb gaming pc cooling fans",
    "cable management desk closeup",
    "coding dark screen terminal",
    "minimalist workspace aesthetic desk",
    "custom liquid cooled pc tubes",
    "laptop coffee desk closeup",
    "ultrawide curved monitor setup",
    "server rack flashing led lights",
    "keyboard switches macro shot",
    "clean desk setup lightbar",
    "electronics soldering circuit board",
    "retro green terminal coding",
    "dual monitor workspace night",
    "ambient neon desk strip lights",
    "standing desk adjustable frame",
    "typing code macbook closeup",
    "cinematic gpu cooling fans",
    "cozy night workspace lofi lamp",
    "mechanical keyboard sound asmr",
    "custom artisan keycaps macro",
    "cyberpunk desk neon aesthetic",
    "coffee cup next to keyboard",
    "mini itx small form factor pc",
    "audio studio monitor speakers desk",
    "wire management cable sleeve",
    "screenbar led monitor light",
    "ergonomic mesh office chair",
    "ipad pro note taking desk",
    "linux terminal bash matrix",
    "acoustic soundproof foam wall",
    "triple monitor trading workspace",
    "wooden desk plant zen aesthetic",
    "cpu processor gold pins closeup",
    "custom coiled keyboard cable",
    "macro electronics motherboard components",
    "dark aesthetic workspace warm light",
    "gaming mouse rgb lighting",
    "usb c hub aluminum dock",
    "cat sleeping near desk computer"
]


def sanitize_keyword(kw: str) -> str:
    """Membersihkan aksara rosak mojibake / bukan ASCII daripada kata kunci AI."""
    if not kw:
        return ""
    clean = re.sub(r'[^a-zA-Z0-9\s]', ' ', str(kw))
    words = [w.strip() for w in clean.split() if len(w.strip()) > 1]
    return " ".join(words[:4]).lower().strip()


def generate_10_pexels_keyword_candidates(
    base_url: str,
    model: str,
    api_key: str,
    recent_keywords: Optional[List[str]] = None,
    rejected_keywords: Optional[List[str]] = None,
) -> List[str]:
    """Menjana 10 calon kata kunci carian video Pexels bebas muka dan bersih dari sebarang glitch."""
    slot_id, slot_desc, day_mood, _ = detect_reel_time_slot()
    sampled_seeds = random.sample(PEXELS_TECH_VISUAL_SEEDS, min(5, len(PEXELS_TECH_VISUAL_SEEDS)))

    if not base_url or not model or not api_key:
        return [sanitize_keyword(k) for k in random.sample(PEXELS_TECH_VISUAL_SEEDS, 10)]

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json; charset=utf-8",
        "HTTP-Referer": "https://sembangpctech.local",
        "X-Title": "Sembang PC & Tech Pexels Keyword Engine",
    }

    recent_context = ""
    if recent_keywords and len(recent_keywords) > 0:
        recent_str = ", ".join([f"'{k}'" for k in recent_keywords[:20]])
        recent_context = f"""
BANK INGATAN SEJARAH (20 KATA KUNCI LEPAS - DILARANG ULANG ATAU JANA YANG TERLALU SERUPA):
[{recent_str}]
"""

    feedback_context = ""
    if rejected_keywords and len(rejected_keywords) > 0:
        rejected_str = ", ".join([f"'{k}'" for k in rejected_keywords])
        feedback_context = f"""
PERHATIAN - KATA KUNCI BERIKUT BARU DITOLAK DALAM TAPISAN PUSINGAN INI:
[{rejected_str}]
"""

    system_prompt = f"""
Anda adalah pakar visual carian stok video vertikal Pexels (9:16 Portrait) untuk tema komputer, teknologi, dan lifestyle ruang kerja di Malaysia.

WAKTU HANTARAN: {slot_desc}
MOOD HARI INI: {day_mood}
CONTOH INSPIRASI: {', '.join(sampled_seeds)}
{recent_context}{feedback_context}
PANTANGAN MUTLAK (STRICT NEGATIVE CONSTRAINTS):
1. DILARANG SAMA SEKALI menjana kata kunci yang melibatkan muka manusia, gamer, model, streamer, atau wanita/lelaki (DILARANG: man, woman, person, girl, face, portrait, model, gamer, streamer).
2. DILARANG menjana perkataan haiwan sensitif (DILARANG: dog, puppy, pig, pork).
3. HANYA fokus kepada B-Roll objek & sudut POV (keyboard, pc build, monitors, cables, desk, coffee, ambient light, circuit board, terminal screen, cat sleeping).
4. Pastikan teks adalah abjad Bahasa Inggeris tulen (Sifar simbol pelik).

TUGAS ANDA:
Hasilkan TEPAT 10 kata kunci carian video Pexels dalam Bahasa Inggeris (Short search query, 2-3 perkataan sahaja) yang SEGAR dan BERBEZA daripada senarai sejarah ingatan.

FORMAT JAWAPAN (JSON ARRAY SAHAJA):
["mechanical keyboard typing", "rgb gaming pc fans", "cable management desk", "coding dark screen", "minimalist workspace desk", "server room led lights", "coffee laptop desk", "ultrawide monitor setup", "custom keycaps macro", "studio audio speakers"]
"""

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": "Beri senarai 10 kata kunci carian video Pexels faceless b-roll unik (2-3 perkataan setiap satu) dalam format JSON array."},
        ],
        "temperature": 0.80 if (rejected_keywords or recent_keywords) else 0.70,
        "max_tokens": 300,
    }

    try:
        res = requests.post(f"{base_url.rstrip('/')}/chat/completions", headers=headers, json=payload, timeout=20)
        if res.status_code == 200:
            res_data = res.json()
            if "choices" in res_data and len(res_data["choices"]) > 0:
                content = res_data["choices"][0]["message"]["content"].strip()
                match = re.search(r'\[[\s\S]*?\]', content)
                if match:
                    candidates = json.loads(match.group(0))
                    cleaned = []
                    for kw in candidates:
                        sanitized_kw = sanitize_keyword(kw)
                        if len(sanitized_kw) >= 5:
                            cleaned.append(sanitized_kw)
                    if len(cleaned) >= 5:
                        return cleaned
    except Exception as e:
        print(f"⚠️ [Pexels Keyword Batch Generation Warn]: {e}")

    return [sanitize_keyword(k) for k in random.sample(PEXELS_TECH_VISUAL_SEEDS, 10)]


def get_fresh_pexels_reel_keyword_candidates(
    base_url: str,
    model: str,
    api_key: str,
    redis_url: str,
    redis_token: str,
    vector_url: str,
    vector_token: str,
) -> List[str]:
    """
    Menjana dan menapis senarai calon kata kunci Pexels segar (memulangkan senarai calon lulus tapisan).
    Membaca 20 sejarah kata kunci lepas dari Redis agar AI tidak mengulang tema yang sama.
    """
    # 1. Baca 20 kata kunci lepas dari Bank Ingatan Redis
    recent_keywords = get_recent_reel_keywords(redis_url, redis_token, limit=20)
    if recent_keywords:
        print(f"  🧠 [KEYWORD MEMORY] Memuatkan {len(recent_keywords)} sejarah kata kunci lepas dari Redis.")

    passed_candidates = []
    all_rejected_keywords = []

    print("\n💡 [PEXELS KEYWORD ENGINE] [Pusingan 1] Menjana 10 calon kata kunci carian video Pexels (Faceless B-Roll)...")
    candidates_r1 = generate_10_pexels_keyword_candidates(
        base_url=base_url,
        model=model,
        api_key=api_key,
        recent_keywords=recent_keywords,
    )
    print(f"📋 [CALON PUSINGAN 1]: {candidates_r1}")

    for idx, kw in enumerate(candidates_r1, 1):
        print(f"  🔍 [R1] Calon #{idx}: '{kw}'")

        if is_reel_keyword_in_redis(redis_url, redis_token, kw):
            print(f"     ⏭️ [REDIS SKIP] Kata kunci 100% sama pernah digunakan < 5 hari lepas.")
            all_rejected_keywords.append(kw)
            continue

        is_similar, score, matched_kw = is_similar_reel_keyword_in_vector(
            vector_url=vector_url,
            vector_token=vector_token,
            keyword=kw,
            threshold=0.85,
            window_seconds=5 * 86400,
        )
        if is_similar:
            print(f"     ⏭️ [VECTOR SKIP] Mirip ({score * 100:.1f}%) dengan '{matched_kw}' (< 5 hari lepas).")
            all_rejected_keywords.append(kw)
            continue

        print(f"     ✅ [LULUS TAPISAN R1] Calon layak & unik.")
        passed_candidates.append(kw)

    # Jika tiada calon lulus, jalankan Pusingan 2
    if not passed_candidates:
        print("\n" + "=" * 65)
        print("⚠️ [PUSINGAN 1 GAGAL] Kesemua 10 calon tersangkut pada tapisan Redis/Vector 5-Hari.")
        print("🔄 [PUSINGAN 2 - RETRY LOOP] Menghantar maklum balas senarai ditolak ke AI...")
        print("=" * 65)

        candidates_r2 = generate_10_pexels_keyword_candidates(
            base_url=base_url,
            model=model,
            api_key=api_key,
            recent_keywords=recent_keywords,
            rejected_keywords=all_rejected_keywords,
        )
        print(f"📋 [CALON PUSINGAN 2]: {candidates_r2}")

        for idx, kw in enumerate(candidates_r2, 1):
            print(f"  🔍 [R2] Calon #{idx}: '{kw}'")

            if is_reel_keyword_in_redis(redis_url, redis_token, kw):
                print(f"     ⏭️ [REDIS SKIP] Kata kunci 100% sama pernah digunakan < 5 hari lepas.")
                continue

            is_similar, score, matched_kw = is_similar_reel_keyword_in_vector(
                vector_url=vector_url,
                vector_token=vector_token,
                keyword=kw,
                threshold=0.85,
                window_seconds=5 * 86400,
            )
            if is_similar:
                print(f"     ⏭️ [VECTOR SKIP] Mirip ({score * 100:.1f}%) dengan '{matched_kw}' (< 5 hari lepas).")
                continue

            print(f"     ✅ [LULUS TAPISAN R2] Calon layak & unik.")
            passed_candidates.append(kw)

    # Fallback jika masih tiada calon
    if not passed_candidates:
        print("\n⚠️ [KEYWORD FALLBACK] Semua calon Pusingan 1 & 2 dalam tempoh bertenang. Memilih tema sandaran selamat...")
        shuffled_seeds = random.sample(PEXELS_TECH_VISUAL_SEEDS, len(PEXELS_TECH_VISUAL_SEEDS))
        for seed in shuffled_seeds:
            clean_seed = sanitize_keyword(seed)
            if not is_reel_keyword_in_redis(redis_url, redis_token, clean_seed):
                passed_candidates.append(clean_seed)
            if len(passed_candidates) >= 3:
                break

    print(f"\n🎯 [SENARAI CALON DISAHKAN SEGAR]: {passed_candidates}")
    return passed_candidates


def commit_reel_keyword(
    redis_url: str,
    redis_token: str,
    vector_url: str,
    vector_token: str,
    keyword: str,
) -> bool:
    """
    Mengunci kata kunci yang BERJAYA menjana video ke dalam:
    1. Redis 5-Hari (Exact match TTL 5 hari)
    2. Upstash Vector DB (Cosine similarity window 5 hari)
    3. Bank Ingatan 20 Sejarah Kata Kunci Terkini Redis (LPUSH + LTRIM 20)
    """
    if not keyword:
        return False

    print(f"\n💾 [PEXELS KEYWORD COMMIT] Mengunci kata kunci rasmi '{keyword}' ke semua pangkalan data...")
    save_reel_keyword_to_redis(redis_url, redis_token, keyword)
    save_reel_keyword_to_vector(vector_url, vector_token, keyword)
    save_reel_keyword_memory(redis_url, redis_token, keyword, max_keywords=20)
    return True


def get_fresh_pexels_reel_keyword(
    base_url: str,
    model: str,
    api_key: str,
    redis_url: str,
    redis_token: str,
    vector_url: str,
    vector_token: str,
) -> str:
    """Fungsi pembantu yang memulangkan calon pertama dan menguncinya secara automatik."""
    candidates = get_fresh_pexels_reel_keyword_candidates(
        base_url, model, api_key, redis_url, redis_token, vector_url, vector_token
    )
    selected = candidates[0] if candidates else sanitize_keyword(random.choice(PEXELS_TECH_VISUAL_SEEDS))
    commit_reel_keyword(redis_url, redis_token, vector_url, vector_token, selected)
    return selected