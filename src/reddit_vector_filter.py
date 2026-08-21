#!/usr/bin/env python3
"""
Reddit Tech Storyteller Engine: Upstash Vector DB Semantic Dedup Guardrail
Lokasi Fail: src/reddit_vector_filter.py

Fungsi Utama:
1. Membaca konfigurasi Upstash Vector REST API daripada persekitaran (env).
2. Menyemak kemiripan semantik cerita Reddit (Cosine Similarity >= 80%) dalam tempoh 72 jam (3 Hari).
3. Menyimpan embedding tajuk/cerita ke Upstash Vector DB dengan ID berformat `rd_<post_id>`.
4. Menyediakan fungsi pemadaman vektor jika berlaku undur balik transaksi.
"""

import os
import time
import requests
from typing import Any, Optional, Tuple

# Tetapan Keserupaan & Tempoh Masa Semakan (Penjarakan 72 Jam / 80% Cosine Similarity)
SIMILARITY_THRESHOLD = float(os.getenv("REDDIT_VECTOR_SIMILARITY_THRESHOLD", "0.80"))
TIME_WINDOW_3_DAYS = int(os.getenv("REDDIT_VECTOR_WINDOW_SECONDS", "259200"))  # 72 Jam / 3 Hari dalam saat


def get_vector_config() -> Tuple[Optional[str], Optional[str], str]:
    """
    Membaca tetapan sambungan Upstash Vector REST API daripada persekitaran (env).
    """
    vector_url = (
        os.getenv("UPSTASH_VECTOR_REST_URL", "").strip()
        or os.getenv("UPSTASH_VECTOR_ENDPOINT_URL", "").strip()
    )
    vector_token = os.getenv("UPSTASH_VECTOR_REST_TOKEN", "").strip()

    if not vector_url or not vector_token:
        return None, None, "Kunci UPSTASH_VECTOR_REST_URL atau UPSTASH_VECTOR_REST_TOKEN tidak lengkap dalam persekitaran."

    return vector_url.rstrip("/"), vector_token, ""


def get_reddit_vector_id(post_id: Any) -> str:
    """
    Menjana format ID Dokumen Vector khusus Reddit.
    Format: rd_<post_id> (cth: rd_1vtalc7)
    """
    clean_id = str(post_id or "").strip()
    return f"rd_{clean_id}"


def is_similar_reddit_story_posted(
    story_text: str,
    vector_url: Optional[str] = None,
    vector_token: Optional[str] = None,
    threshold: float = SIMILARITY_THRESHOLD,
    window_seconds: int = TIME_WINDOW_3_DAYS
) -> bool:
    """
    Menyemak sama ada terdapat cerita/topik Reddit dengan makna serupa (Cosine Similarity >= 80%)
    yang pernah dipos dalam tempoh 72 jam (259,200 saat) melalui Upstash Vector REST API.
    """
    if not vector_url or not vector_token:
        v_url, v_token, err = get_vector_config()
        if err:
            print(f"⚠️ [REDDIT VECTOR CONFIG WARN] {err}")
            return False
        vector_url, vector_token = v_url, v_token

    clean_story = str(story_text or "").strip()
    if not clean_story:
        return False

    endpoint = f"{vector_url}/query-data"
    headers = {
        "Authorization": f"Bearer {vector_token}",
        "Content-Type": "application/json"
    }

    # topK: 5 untuk menyemak 5 hantaran terdahulu yang paling hampir maksudnya
    payload = {
        "data": clean_story[:1000],
        "topK": 5,
        "includeMetadata": True
    }

    try:
        res = requests.post(endpoint, json=payload, headers=headers, timeout=12)
        if res.status_code == 200:
            results = res.json().get("result", [])
            current_time = int(time.time())

            for match in results:
                score = match.get("score", 0.0)
                metadata = match.get("metadata", {}) or {}
                posted_at = metadata.get("posted_at", 0)
                platform = metadata.get("platform", "reddit")

                # Semak kesamaan tajuk >= threshold DAN jarak masa pos kurang daripada 72 jam
                time_diff = current_time - posted_at
                if score >= threshold and time_diff < window_seconds:
                    matched_title = metadata.get("title", "Topik Reddit Serupa")
                    hours_ago = time_diff / 3600
                    print(
                        f"⏭️ [VECTOR DB MATCH] Cerita Reddit serupa dikesan! '{clean_story[:40]}...' mirip "
                        f"({score * 100:.1f}%) dengan '{matched_title}' ({hours_ago:.1f} jam lepas pada platform '{platform}'). Langkau."
                    )
                    return True
        else:
            print(f"⚠️ [REDDIT VECTOR WARN] HTTP {res.status_code} semasa semakan carian vektor: {res.text}")
    except Exception as e:
        print(f"⚠️ [REDDIT VECTOR WARN] Gagal membuat semakan di Upstash Vector DB: {e}")

    return False


def mark_reddit_vector_posted(
    post_id: Any,
    story_title: str,
    vector_url: Optional[str] = None,
    vector_token: Optional[str] = None
) -> bool:
    """
    Menyimpan embedding tajuk cerita Reddit ke dalam Upstash Vector DB.
    Format ID: rd_<post_id>
    Metadata: platform: reddit, post_id, title, posted_at
    """
    if not vector_url or not vector_token:
        v_url, v_token, err = get_vector_config()
        if err:
            print(f"⚠️ [REDDIT VECTOR CONFIG ERROR] {err}")
            return False
        vector_url, vector_token = v_url, v_token

    clean_id = str(post_id or "").strip()
    clean_title = str(story_title or "").strip()
    if not clean_id or not clean_title:
        return False

    endpoint = f"{vector_url}/upsert-data"
    headers = {
        "Authorization": f"Bearer {vector_token}",
        "Content-Type": "application/json"
    }

    doc_id = get_reddit_vector_id(clean_id)
    current_time = int(time.time())

    payload = {
        "id": doc_id,
        "data": clean_title[:1000],
        "metadata": {
            "platform": "reddit",
            "post_id": clean_id,
            "title": clean_title,
            "posted_at": current_time
        }
    }

    try:
        res = requests.post(endpoint, json=payload, headers=headers, timeout=12)
        if res.status_code == 200:
            print(f"🟢 [VECTOR SUCCESS] Embedding '{clean_title[:35]}...' (ID: {doc_id}) berjaya direkodkan ke Vector DB.")
            return True
        else:
            print(f"⚠️ [VECTOR ERROR] Ralat HTTP {res.status_code}: {res.text}")
    except Exception as e:
        print(f"⚠️ [VECTOR WARN] Gagal menyimpan rekod embedding pos Reddit ke Upstash Vector DB: {e}")

    return False


def delete_reddit_vector_posted(
    post_id: Any,
    vector_url: Optional[str] = None,
    vector_token: Optional[str] = None
) -> bool:
    """
    Memadam rekod embedding pos Reddit dari Vector DB (jika berlaku undur balik / rollback).
    """
    if not vector_url or not vector_token:
        v_url, v_token, err = get_vector_config()
        if err:
            return False
        vector_url, vector_token = v_url, v_token

    clean_id = str(post_id or "").strip()
    if not clean_id:
        return False

    endpoint = f"{vector_url}/delete"
    headers = {
        "Authorization": f"Bearer {vector_token}",
        "Content-Type": "application/json"
    }
    doc_id = get_reddit_vector_id(clean_id)
    payload = {"ids": [doc_id]}

    try:
        res = requests.post(endpoint, json=payload, headers=headers, timeout=10)
        return res.status_code == 200
    except Exception:
        return False