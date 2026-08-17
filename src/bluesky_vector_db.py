#!/usr/bin/env python3
"""
Dedicated Bluesky Upstash Vector Database Engine
Sembang PC & Tech Ecosystem (100% Dynamic REST & Semantic Guardrails)
Features:
- Semantic Similarity Duplicate Check (Cosine Similarity Threshold >= 0.80)
- 7-Day Anti-Duplication Jail for AI-Generated Captions
- Dedicated Bluesky Namespace to Prevent Memory Leakage with FB/IG Long Posts
- Native Upstash Vector REST API Integration (Automatic Embedding via BGE/Dense Models)
"""

import os
import requests
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple
from pathlib import Path
from dotenv import load_dotenv

# Set Project Root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
env_local = PROJECT_ROOT / ".env.local"
if env_local.exists():
    load_dotenv(dotenv_path=env_local)
else:
    load_dotenv()

DEFAULT_THRESHOLD = 0.80  # 80% ambang keserupaan semantik
DEFAULT_WINDOW_DAYS = 7   # Penjara 7 hari


def _get_vector_creds(vector_url: Optional[str] = None, vector_token: Optional[str] = None) -> Tuple[str, str]:
    """Membaca URL dan Token Upstash Vector secara dinamik."""
    url = (vector_url or os.getenv("UPSTASH_VECTOR_REST_URL") or "").strip().rstrip("/")
    token = (vector_token or os.getenv("UPSTASH_VECTOR_REST_TOKEN") or "").strip()
    return url, token


# -----------------------------------------------------------------------------
# 1. SEMAKAN KESERUPAAN SEMANTIK (SEMANTIC SIMILARITY CHECK)
# -----------------------------------------------------------------------------
def is_similar_bluesky_post_posted(
    vector_url: Optional[str] = None,
    vector_token: Optional[str] = None,
    text: str = "",
    threshold: float = DEFAULT_THRESHOLD,
    days_window: int = DEFAULT_WINDOW_DAYS,
    category: str = "general"
) -> bool:
    """
    Menyemak sama ada ayat kapsyen ini mempunyai persamaan semantik >= 80%
    dengan kapsyen Bluesky yang pernah diterbitkan dalam tempoh 7 hari lepas.
    """
    url, token = _get_vector_creds(vector_url, vector_token)
    clean_text = text.strip()
    if not url or not token or not clean_text:
        return False

    endpoint = f"{url}/query-data"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "data": clean_text,
        "topK": 3,
        "includeMetadata": True
    }

    try:
        res = requests.post(endpoint, headers=headers, json=payload, timeout=12)
        if res.status_code != 200:
            return False

        results = res.json().get("result", [])
        if not results:
            return False

        now_utc = datetime.now(timezone.utc)
        cutoff_time = now_utc - timedelta(days=days_window)

        for match in results:
            score = match.get("score", 0.0)
            meta = match.get("metadata", {}) or {}

            # Tapis hanya untuk rekod platform Bluesky
            if meta.get("platform") != "bluesky":
                continue

            # Semak kategori jika ditentukan
            if category and meta.get("category") and meta.get("category") != category:
                continue

            if score >= threshold:
                timestamp_str = meta.get("posted_at")
                if timestamp_str:
                    try:
                        posted_dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                        if posted_dt >= cutoff_time:
                            pct = round(score * 100, 1)
                            print(f"  ⏭️ [BLUESKY VECTOR MATCH] Kapsyen mirip ({pct}%) dikesan: '{meta.get('text_snippet', '')}' (< {days_window} hari).")
                            return True
                    except Exception:
                        return True
                else:
                    return True

    except Exception as e:
        print(f"⚠️ [BLUESKY VECTOR EXCEPTION] {e}")

    return False


# -----------------------------------------------------------------------------
# 2. REKOD EMBEDDING BARU KE VECTOR DB
# -----------------------------------------------------------------------------
def mark_bluesky_vector_posted(
    vector_url: Optional[str] = None,
    vector_token: Optional[str] = None,
    doc_id: str = "",
    text: str = "",
    category: str = "general",
    extra_metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Menyimpan embedding teks pos Bluesky baharu ke Upstash Vector DB
    berserta metadata masa dan platform.
    """
    url, token = _get_vector_creds(vector_url, vector_token)
    clean_text = text.strip()
    if not url or not token or not clean_text:
        return False

    unique_id = f"bsky_{category}_{doc_id or int(datetime.now(timezone.utc).timestamp())}"
    endpoint = f"{url}/upsert-data"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    metadata = {
        "platform": "bluesky",
        "category": category,
        "text_snippet": clean_text[:120],
        "posted_at": datetime.now(timezone.utc).isoformat()
    }
    if extra_metadata and isinstance(extra_metadata, dict):
        metadata.update(extra_metadata)

    payload = {
        "id": unique_id,
        "data": clean_text,
        "metadata": metadata
    }

    try:
        res = requests.post(endpoint, headers=headers, json=payload, timeout=12)
        if res.status_code == 200:
            print(f"  🟢 [BLUESKY VECTOR SAVED] Embedding pos '{unique_id}' direkodkan ke Vector DB.")
            return True
        else:
            print(f"⚠️ [BLUESKY VECTOR ERROR] HTTP {res.status_code}: {res.text}")
            return False
    except Exception as e:
        print(f"⚠️ [BLUESKY VECTOR UPSERT EXCEPTION] {e}")
        return False


class BlueskyVectorManager:
    """Kelas pembungkus untuk akses modular."""

    def __init__(self):
        self.url = os.getenv("UPSTASH_VECTOR_REST_URL", "").strip()
        self.token = os.getenv("UPSTASH_VECTOR_REST_TOKEN", "").strip()

    def is_similar(
        self,
        text: str,
        threshold: float = DEFAULT_THRESHOLD,
        days_window: int = DEFAULT_WINDOW_DAYS,
        category: str = "general"
    ) -> bool:
        return is_similar_bluesky_post_posted(
            vector_url=self.url,
            vector_token=self.token,
            text=text,
            threshold=threshold,
            days_window=days_window,
            category=category
        )

    def mark_posted(
        self,
        doc_id: str,
        text: str,
        category: str = "general",
        extra_metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        return mark_bluesky_vector_posted(
            vector_url=self.url,
            vector_token=self.token,
            doc_id=doc_id,
            text=text,
            category=category,
            extra_metadata=extra_metadata
        )


# Singleton instance
bluesky_vector = BlueskyVectorManager()