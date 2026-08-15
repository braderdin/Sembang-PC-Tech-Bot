#!/usr/bin/env python3
"""
Dedicated Upstash Vector REST Manager for Facebook Pexels Video Reels
Sembang PC & Tech Ecosystem
Features:
- Reel Caption Semantic Similarity Guardrail (Cosine Similarity >= 0.85, Window 5 Hari)
- Pexels Keyword Semantic Similarity Guardrail (Cosine Similarity >= 0.85, Window 5 Hari)
"""

import re
import time
import requests
from typing import Tuple, Optional

# Tetapan Keserupaan & Masa Luput
SIMILARITY_THRESHOLD = 0.85          # Skor >= 0.85 (85%) dianggap tema/ayat serupa
TIME_WINDOW_5_DAYS = 5 * 86400       # 5 Hari dalam saat (432,000 saat)


# -----------------------------------------------------------------------------
# 1. TAPISAN SEMANTIK KAPSYEN AI REELS (5 HARI / 85% COSINE SIMILARITY)
# -----------------------------------------------------------------------------

def is_similar_reel_story_posted(
    vector_url: str,
    vector_token: str,
    story_text: str,
    threshold: float = SIMILARITY_THRESHOLD,
    window_seconds: int = TIME_WINDOW_5_DAYS,
) -> bool:
    """
    Semak sama ada AI Persona pernah menulis kapsyen Reels dengan mesej/struktur serupa
    (Cosine Similarity >= 0.85) dalam tempoh 5 hari lepas di Upstash Vector DB.
    """
    if not vector_url or not vector_token or not story_text:
        return False

    clean_url = vector_url.rstrip("/")
    query_url = f"{clean_url}/query-data"
    headers = {"Authorization": f"Bearer {vector_token}", "Content-Type": "application/json"}
    payload = {
        "data": str(story_text),
        "topK": 3,
        "includeMetadata": True,
    }

    try:
        res = requests.post(query_url, json=payload, headers=headers, timeout=12)
        if res.status_code == 200:
            results = res.json().get("result", [])
            current_time = int(time.time())

            for match in results:
                score = match.get("score", 0.0)
                metadata = match.get("metadata", {}) or {}
                item_type = metadata.get("type", "")

                if item_type != "pexels_reel_story":
                    continue

                posted_at = metadata.get("posted_at", 0)
                if score >= threshold and (current_time - posted_at) < window_seconds:
                    matched_snippet = metadata.get("story_snippet", "Kapsyen Reel Serupa")
                    print(f"⏭️ [PEXELS REEL VECTOR MATCH] Kapsyen serupa dikesan ({score * 100:.1f}%) dengan: '{matched_snippet}' (< 5 hari lepas).")
                    return True
    except Exception as e:
        print(f"⚠️ [Pexels Reel Vector Check Warn]: {e}")

    return False


def mark_reel_story_vector_posted(vector_url: str, vector_token: str, story_id: str, story_text: str) -> bool:
    """
    Simpan vector embedding teks kapsyen Reels ke dalam Upstash Vector DB.
    """
    if not vector_url or not vector_token or not story_id or not story_text:
        return False

    clean_url = vector_url.rstrip("/")
    upsert_url = f"{clean_url}/upsert-data"
    headers = {"Authorization": f"Bearer {vector_token}", "Content-Type": "application/json"}

    current_time = int(time.time())
    snippet = story_text[:120] + "..." if len(story_text) > 120 else story_text

    payload = {
        "id": f"pexels_reel_{story_id}",
        "data": str(story_text),
        "metadata": {
            "story_snippet": str(snippet),
            "posted_at": current_time,
            "type": "pexels_reel_story",
        },
    }

    try:
        res = requests.post(upsert_url, json=payload, headers=headers, timeout=12)
        if res.status_code == 200:
            print(f"🟢 [PEXELS REEL VECTOR] Embedding kapsyen (ID: pexels_reel_{story_id}) disimpan ke Vector DB (Window 5 Hari).")
            return True
    except Exception as e:
        print(f"⚠️ [Pexels Reel Vector Save Warn]: {e}")

    return False


# -----------------------------------------------------------------------------
# 2. TAPISAN SEMANTIK KATA KUNCI PEXELS (5 HARI / 85% COSINE SIMILARITY)
# -----------------------------------------------------------------------------

def is_similar_reel_keyword_in_vector(
    vector_url: str,
    vector_token: str,
    keyword: str,
    threshold: float = SIMILARITY_THRESHOLD,
    window_seconds: int = TIME_WINDOW_5_DAYS,
) -> Tuple[bool, float, str]:
    """
    Semak sama ada makna kata kunci tema mirip >= 85% dengan kata kunci dalam tempoh 5 hari lepas.
    """
    if not vector_url or not vector_token or not keyword:
        return False, 0.0, ""

    clean_url = vector_url.rstrip("/")
    query_url = f"{clean_url}/query-data"
    headers = {"Authorization": f"Bearer {vector_token}", "Content-Type": "application/json"}
    payload = {
        "data": str(keyword).strip(),
        "topK": 3,
        "includeMetadata": True,
    }

    try:
        res = requests.post(query_url, json=payload, headers=headers, timeout=10)
        if res.status_code == 200:
            results = res.json().get("result", [])
            current_time = int(time.time())

            for match in results:
                score = match.get("score", 0.0)
                metadata = match.get("metadata", {}) or {}
                item_type = metadata.get("type", "")

                if item_type != "pexels_keyword":
                    continue

                posted_at = metadata.get("posted_at", 0)
                if score >= threshold and (current_time - posted_at) < window_seconds:
                    matched_kw = metadata.get("keyword", match.get("id", ""))
                    return True, score, matched_kw
    except Exception as e:
        print(f"⚠️ [Pexels Keyword Vector Check Warn]: {e}")

    return False, 0.0, ""


def save_reel_keyword_to_vector(vector_url: str, vector_token: str, keyword: str) -> bool:
    """
    Simpan vector embedding kata kunci Pexels ke dalam Upstash Vector DB.
    """
    if not vector_url or not vector_token or not keyword:
        return False

    clean_url = vector_url.rstrip("/")
    upsert_url = f"{clean_url}/upsert-data"
    headers = {"Authorization": f"Bearer {vector_token}", "Content-Type": "application/json"}

    current_time = int(time.time())
    clean_kw_id = re.sub(r"[^a-zA-Z0-9]", "_", keyword.lower().strip())

    payload = {
        "id": f"pkw_{clean_kw_id}_{current_time}",
        "data": str(keyword).strip(),
        "metadata": {
            "keyword": str(keyword).strip(),
            "posted_at": current_time,
            "type": "pexels_keyword",
        },
    }

    try:
        res = requests.post(upsert_url, json=payload, headers=headers, timeout=10)
        return res.status_code == 200
    except Exception as e:
        print(f"⚠️ [Pexels Keyword Vector Save Warn]: {e}")

    return False