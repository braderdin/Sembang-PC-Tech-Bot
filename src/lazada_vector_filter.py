#!/usr/bin/env python3
"""
Lazada Vector Semantic Deduplication Engine
Sembang PC & Tech Ecosystem (Upstash Vector REST API)
Features:
- Semantic Cosine Similarity Threshold: >= 80% (0.80)
- Cooldown Window: 72 Hours (3 Days / 259,200 seconds)
- Automated embedding generation via Upstash Vector REST API
- Standalone helper with environment auto-loading
"""

import os
import time
import requests
from pathlib import Path
from typing import Optional, Tuple
from dotenv import load_dotenv

# 1. Konfigurasi Laluan Projek & Muat Turun Environment
PROJECT_ROOT = Path(__file__).resolve().parent.parent
env_local = PROJECT_ROOT / ".env.local"
if env_local.exists():
    load_dotenv(dotenv_path=env_local)
else:
    load_dotenv()

# Tetapan Keserupaan & Tempoh Bertenang
SIMILARITY_THRESHOLD = 0.80  # 80% kemiripan makna
TIME_WINDOW_3_DAYS = 259200  # 72 Jam dalam saat (3 * 24 * 60 * 60)


def get_vector_config() -> Tuple[str, str]:
    """Membaca kelayakan Upstash Vector secara dinamik daripada persekitaran."""
    url = os.getenv("UPSTASH_VECTOR_REST_URL", "").strip().rstrip("/")
    token = os.getenv("UPSTASH_VECTOR_REST_TOKEN", "").strip()
    return url, token


def is_similar_lazada_product_posted(
    product_title: str,
    vector_url: Optional[str] = None,
    vector_token: Optional[str] = None
) -> bool:
    """
    Semak sama ada terdapat produk dengan makna/fungsi serupa (Cosine Similarity >= 80%)
    yang pernah dipos dalam tempoh 72 jam (3 hari) menggunakan Upstash Vector REST API.
    """
    url = (vector_url or os.getenv("UPSTASH_VECTOR_REST_URL", "")).strip().rstrip("/")
    token = (vector_token or os.getenv("UPSTASH_VECTOR_REST_TOKEN", "")).strip()

    if not url or not token or not product_title:
        return False

    query_url = f"{url}/query-data"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload = {
        "data": str(product_title).strip(),
        "topK": 5,
        "includeMetadata": True
    }

    try:
        res = requests.post(query_url, json=payload, headers=headers, timeout=15)
        if res.status_code == 200:
            results = res.json().get("result", [])
            current_time = int(time.time())

            for match in results:
                score = match.get("score", 0.0)
                metadata = match.get("metadata", {}) or {}
                posted_at = metadata.get("posted_at", 0)
                platform = metadata.get("platform", "lazada")

                # Kira perbezaan masa dalam jam
                hours_ago = (current_time - posted_at) / 3600

                # Semak jika kemiripan >= 80% dan dalam tempoh 72 jam (3 hari)
                if score >= SIMILARITY_THRESHOLD and (current_time - posted_at) < TIME_WINDOW_3_DAYS:
                    matched_title = metadata.get("title", "Produk Serupa")
                    print(
                        f"⏭️ [VECTOR DB MATCH] Produk serupa dikesan! '{product_title[:45]}...' "
                        f"mirip ({score * 100:.1f}%) dengan '{matched_title[:45]}...' "
                        f"({hours_ago:.1f} jam lepas pada platform '{platform}'). Langkau."
                    )
                    return True
        else:
            print(f"⚠️ [LAZADA VECTOR WARN] HTTP {res.status_code} semasa semakan carian: {res.text}")
    except Exception as e:
        print(f"⚠️ [LAZADA VECTOR WARN] Gagal membuat semakan di Upstash Vector DB: {e}")

    return False


def mark_lazada_vector_posted(
    product_id: str,
    product_title: str,
    vector_url: Optional[str] = None,
    vector_token: Optional[str] = None
) -> bool:
    """
    Simpan vector embedding tajuk produk ke dalam Upstash Vector DB dengan metadata lengkap.
    """
    url = (vector_url or os.getenv("UPSTASH_VECTOR_REST_URL", "")).strip().rstrip("/")
    token = (vector_token or os.getenv("UPSTASH_VECTOR_REST_TOKEN", "")).strip()

    if not url or not token or not product_id or not product_title:
        return False

    upsert_url = f"{url}/upsert-data"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    current_time = int(time.time())
    clean_id = str(product_id).strip()
    vector_id = f"lz_{clean_id}"

    payload = {
        "id": vector_id,
        "data": str(product_title).strip(),
        "metadata": {
            "product_id": clean_id,
            "title": str(product_title).strip(),
            "platform": "lazada",
            "posted_at": current_time
        }
    }

    try:
        res = requests.post(upsert_url, json=payload, headers=headers, timeout=15)
        if res.status_code == 200:
            print(f"🟢 [VECTOR SUCCESS] Embedding '{product_title[:45]}...' (ID: {vector_id}) berjaya direkodkan ke Vector DB.")
            return True
        else:
            print(f"⚠️ [LAZADA VECTOR ERROR] Ralat HTTP {res.status_code}: {res.text}")
    except Exception as e:
        print(f"⚠️ [LAZADA VECTOR WARN] Gagal menyimpan rekod embedding ke Upstash Vector DB: {e}")

    return False


# Alias keserasian ke belakang (backward compatibility)
is_similar_product_posted = is_similar_lazada_product_posted
mark_vector_posted = mark_lazada_vector_posted