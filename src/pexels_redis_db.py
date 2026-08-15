#!/usr/bin/env python3
"""
Dedicated Upstash Redis REST Manager for Facebook Pexels Video Reels
Sembang PC & Tech Ecosystem
Features:
- Video ID Deduplication (TTL 30 Hari / 2,592,000s)
- Keyword Exact Match Deduplication (TTL 5 Hari / 432,000s)
- Reel Story/Caption Bank Memory (LPUSH + LTRIM 10 Terkini)
"""

import os
import re
import json
import requests
from typing import List, Optional

# Kunci & Parameter Masa Luput (TTL)
VIDEO_ID_TTL_SECONDS = 30 * 86400   # 30 Hari (2,592,000 saat)
KEYWORD_TTL_SECONDS = 5 * 86400      # 5 Hari (432,000 saat)
REDIS_MEMORY_KEY = "pexels_reel:memory:recent_stories"


# -----------------------------------------------------------------------------
# 1. PENGURUS DEDUPLIKASI VIDEO ID PEXELS (30 HARI)
# -----------------------------------------------------------------------------

def is_pexels_video_posted(redis_url: str, redis_token: str, video_id: str) -> bool:
    """
    Semak sama ada video_id Pexels pernah digunakan dalam tempoh 30 hari lepas.
    Format Kunci: pexels_reel:video_id:<video_id>
    """
    if not redis_url or not redis_token or not video_id:
        return False

    clean_url = redis_url.rstrip("/")
    redis_key = f"pexels_reel:video_id:{str(video_id).strip()}"
    headers = {"Authorization": f"Bearer {redis_token}", "Content-Type": "application/json"}
    payload = ["GET", redis_key]

    try:
        res = requests.post(f"{clean_url}/", json=payload, headers=headers, timeout=10)
        if res.status_code == 200:
            result = res.json().get("result")
            return result is not None and str(result) != "null"
    except Exception as e:
        print(f"⚠️ [Pexels Redis Video Check Warn]: {e}")

    return False


def mark_pexels_video_posted(redis_url: str, redis_token: str, video_id: str, ttl_seconds: int = VIDEO_ID_TTL_SECONDS) -> bool:
    """
    Simpan video_id Pexels ke Redis dengan nilai 'USED' dan TTL 30 Hari secara atomik.
    """
    if not redis_url or not redis_token or not video_id:
        return False

    clean_url = redis_url.rstrip("/")
    redis_key = f"pexels_reel:video_id:{str(video_id).strip()}"
    headers = {"Authorization": f"Bearer {redis_token}", "Content-Type": "application/json"}
    payload = ["SET", redis_key, "USED", "EX", str(ttl_seconds)]

    try:
        res = requests.post(f"{clean_url}/", json=payload, headers=headers, timeout=10)
        if res.status_code == 200 and res.json().get("result") == "OK":
            print(f"💾 [PEXELS REDIS] Video ID '{video_id}' dikunci dalam penjara Redis (TTL 30 Hari).")
            return True
    except Exception as e:
        print(f"⚠️ [Pexels Redis Video Save Warn]: {e}")

    return False


# -----------------------------------------------------------------------------
# 2. PENGURUS DEDUPLIKASI KATA KUNCI TEMA (5 HARI)
# -----------------------------------------------------------------------------

def is_reel_keyword_in_redis(redis_url: str, redis_token: str, keyword: str) -> bool:
    """
    Semak sama ada kata kunci tema 100% sama pernah digunakan dalam tempoh 5 hari.
    """
    if not redis_url or not redis_token or not keyword:
        return False

    clean_url = redis_url.rstrip("/")
    clean_kw = re.sub(r"[^a-zA-Z0-9]", "_", keyword.lower().strip())
    redis_key = f"pexels_reel:kw_exact:{clean_kw}"
    headers = {"Authorization": f"Bearer {redis_token}", "Content-Type": "application/json"}
    payload = ["GET", redis_key]

    try:
        res = requests.post(f"{clean_url}/", json=payload, headers=headers, timeout=10)
        if res.status_code == 200:
            val = res.json().get("result")
            return val is not None and str(val) != "null"
    except Exception as e:
        print(f"⚠️ [Pexels Keyword Redis Check Warn]: {e}")

    return False


def save_reel_keyword_to_redis(redis_url: str, redis_token: str, keyword: str, ttl_seconds: int = KEYWORD_TTL_SECONDS) -> bool:
    """
    Simpan kata kunci tema ke Redis dengan TTL 5 Hari (432,000 saat).
    """
    if not redis_url or not redis_token or not keyword:
        return False

    clean_url = redis_url.rstrip("/")
    clean_kw = re.sub(r"[^a-zA-Z0-9]", "_", keyword.lower().strip())
    redis_key = f"pexels_reel:kw_exact:{clean_kw}"
    headers = {"Authorization": f"Bearer {redis_token}", "Content-Type": "application/json"}
    payload = ["SET", redis_key, "USED", "EX", str(ttl_seconds)]

    try:
        res = requests.post(f"{clean_url}/", json=payload, headers=headers, timeout=10)
        return res.status_code == 200 and res.json().get("result") == "OK"
    except Exception as e:
        print(f"⚠️ [Pexels Keyword Redis Save Warn]: {e}")

    return False


# -----------------------------------------------------------------------------
# 3. BANK INGATAN KAPSYEN REELS (10 INGATAN TERKINI)
# -----------------------------------------------------------------------------

def get_reel_story_memories(redis_url: str, redis_token: str, limit: int = 5) -> List[str]:
    """
    Mengambil 'limit' (default 5) kapsyen Reel terakhir daripada Redis
    untuk dijadikan rujukan konteks prompt AI Persona.
    """
    if not redis_url or not redis_token:
        return []

    clean_url = redis_url.rstrip("/")
    headers = {"Authorization": f"Bearer {redis_token}", "Content-Type": "application/json"}
    payload = ["LRANGE", REDIS_MEMORY_KEY, "0", str(limit - 1)]

    try:
        res = requests.post(f"{clean_url}/", json=payload, headers=headers, timeout=10)
        if res.status_code == 200:
            result = res.json().get("result", [])
            if isinstance(result, list):
                return [str(item) for item in result if item]
    except Exception as e:
        print(f"⚠️ [Pexels Reel Memory Read Warn]: {e}")

    return []


def save_reel_story_memory(redis_url: str, redis_token: str, story_text: str, max_memories: int = 10) -> bool:
    """
    Simpan kapsyen Reel baharu ke dalam senarai ingatan Redis (LPUSH)
    dan kekalkan maksimum 10 ingatan terkini sahaja (LTRIM).
    """
    if not redis_url or not redis_token or not story_text:
        return False

    clean_url = redis_url.rstrip("/")
    headers = {"Authorization": f"Bearer {redis_token}", "Content-Type": "application/json"}
    pipeline_payload = [
        ["LPUSH", REDIS_MEMORY_KEY, str(story_text)],
        ["LTRIM", REDIS_MEMORY_KEY, "0", str(max_memories - 1)],
    ]

    try:
        res = requests.post(f"{clean_url}/pipeline", json=pipeline_payload, headers=headers, timeout=10)
        if res.status_code == 200:
            print(f"🧠 [PEXELS REEL REDIS] Kapsyen baharu disimpan ke Bank Ingatan Persona (Kekal {max_memories} terkini).")
            return True
    except Exception as e:
        print(f"⚠️ [Pexels Reel Memory Save Warn]: {e}")

    return False