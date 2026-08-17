#!/usr/bin/env python3
"""
Dedicated Bluesky Upstash Redis Database Engine
Sembang PC & Tech Ecosystem (100% Dynamic REST & Anti-Duplication Guardrails)
Features:
- Product Anti-Duplication Jail (14-30 Days TTL / 2-4 Weeks)
- Unsplash Photo & Keyword Anti-Duplication (14-21 Days TTL)
- Pexels Video ID Anti-Duplication Jail (30 Days TTL)
- 5-Day Recent Caption Memory Bank (Keeps 10 latest entries per category)
- Resilient REST API Calls with Native Fallback
"""

import os
import json
import requests
from typing import List, Optional, Union
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

# Set Project Root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
env_local = PROJECT_ROOT / ".env.local"
if env_local.exists():
    load_dotenv(dotenv_path=env_local)
else:
    load_dotenv()

# TTL Constants (in seconds)
TTL_14_DAYS = 14 * 86400   # 1,209,600 saat (2 minggu)
TTL_21_DAYS = 21 * 86400   # 1,814,400 saat (3 minggu)
TTL_30_DAYS = 30 * 86400   # 2,592,000 saat (1 bulan)
TTL_7_DAYS  = 7 * 86400    # 604,800 saat (1 minggu)


def _get_redis_creds(redis_url: Optional[str] = None, redis_token: Optional[str] = None) -> tuple:
    """Membaca URL dan Token Upstash Redis secara dinamik."""
    url = (redis_url or os.getenv("UPSTASH_REDIS_REST_URL") or "").strip().rstrip("/")
    token = (redis_token or os.getenv("UPSTASH_REDIS_REST_TOKEN") or "").strip()
    return url, token


def _send_redis_command(url: str, token: str, command: List[Union[str, int]]) -> Optional[dict]:
    """Menghantar arahan REST Array terus ke Upstash Redis."""
    if not url or not token:
        return None

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    try:
        res = requests.post(url, headers=headers, json=command, timeout=12)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        print(f"⚠️ [BLUESKY REDIS EXCEPTION] Ralat arahan {command[0] if command else ''}: {e}")
    return None


# -----------------------------------------------------------------------------
# 1. ANTI-DUPLIKASI PRODUK AFFILIATE (PENJARA 21 HARI / 3 MINGGU)
# -----------------------------------------------------------------------------
def is_bluesky_product_posted(
    redis_url: Optional[str] = None,
    redis_token: Optional[str] = None,
    product_id: str = "",
    title: str = ""
) -> bool:
    """
    Menyemak sama ada produk ini pernah disiarkan ke Bluesky dalam tempoh bertenang.
    """
    url, token = _get_redis_creds(redis_url, redis_token)
    clean_id = str(product_id).strip()
    if not url or not token or not clean_id:
        return False

    key = f"bsky:prod:{clean_id}"
    res = _send_redis_command(url, token, ["GET", key])
    if res and res.get("result"):
        return True

    return False


def mark_bluesky_product_posted(
    redis_url: Optional[str] = None,
    redis_token: Optional[str] = None,
    product_id: str = "",
    title: str = "",
    ttl_seconds: int = TTL_21_DAYS
) -> bool:
    """
    Mengunci Product ID ke dalam penjara Redis Bluesky (Lalai: 21 Hari).
    """
    url, token = _get_redis_creds(redis_url, redis_token)
    clean_id = str(product_id).strip()
    if not url or not token or not clean_id:
        return False

    key = f"bsky:prod:{clean_id}"
    payload = json.dumps({
        "product_id": clean_id,
        "title": title[:80],
        "posted_at": datetime.now(timezone.utc).isoformat()
    })

    res = _send_redis_command(url, token, ["SET", key, payload, "EX", ttl_seconds])
    if res and res.get("result") == "OK":
        return True

    return False


# -----------------------------------------------------------------------------
# 2. ANTI-DUPLIKASI GAMBAR LIFESTYLE UNSPLASH (PENJARA 21 HARI)
# -----------------------------------------------------------------------------
def is_bluesky_image_posted(
    redis_url: Optional[str] = None,
    redis_token: Optional[str] = None,
    photo_id: str = ""
) -> bool:
    """Menyemak sama ada Photo ID Unsplash pernah digunakan di Bluesky."""
    url, token = _get_redis_creds(redis_url, redis_token)
    clean_pid = str(photo_id).strip()
    if not url or not token or not clean_pid:
        return False

    key = f"bsky:img:{clean_pid}"
    res = _send_redis_command(url, token, ["GET", key])
    return bool(res and res.get("result"))


def mark_bluesky_image_posted(
    redis_url: Optional[str] = None,
    redis_token: Optional[str] = None,
    photo_id: str = "",
    ttl_seconds: int = TTL_21_DAYS
) -> bool:
    """Mengunci Photo ID Unsplash ke dalam penjara Redis Bluesky."""
    url, token = _get_redis_creds(redis_url, redis_token)
    clean_pid = str(photo_id).strip()
    if not url or not token or not clean_pid:
        return False

    key = f"bsky:img:{clean_pid}"
    val = datetime.now(timezone.utc).isoformat()
    res = _send_redis_command(url, token, ["SET", key, val, "EX", ttl_seconds])
    return bool(res and res.get("result") == "OK")


# -----------------------------------------------------------------------------
# 3. ANTI-DUPLIKASI VIDEO PEXELS (PENJARA 30 HARI / 1 BULAN)
# -----------------------------------------------------------------------------
def is_bluesky_video_posted(
    redis_url: Optional[str] = None,
    redis_token: Optional[str] = None,
    video_id: str = ""
) -> bool:
    """Menyemak sama ada Video ID Pexels pernah disiarkan di Bluesky dalam 30 hari."""
    url, token = _get_redis_creds(redis_url, redis_token)
    clean_vid = str(video_id).strip()
    if not url or not token or not clean_vid:
        return False

    key = f"bsky:vid:{clean_vid}"
    res = _send_redis_command(url, token, ["GET", key])
    return bool(res and res.get("result"))


def mark_bluesky_video_posted(
    redis_url: Optional[str] = None,
    redis_token: Optional[str] = None,
    video_id: str = "",
    ttl_seconds: int = TTL_30_DAYS
) -> bool:
    """Mengunci Video ID Pexels ke dalam penjara Redis Bluesky (30 Hari)."""
    url, token = _get_redis_creds(redis_url, redis_token)
    clean_vid = str(video_id).strip()
    if not url or not token or not clean_vid:
        return False

    key = f"bsky:vid:{clean_vid}"
    val = datetime.now(timezone.utc).isoformat()
    res = _send_redis_command(url, token, ["SET", key, val, "EX", ttl_seconds])
    return bool(res and res.get("result") == "OK")


# -----------------------------------------------------------------------------
# 4. ANTI-DUPLIKASI KATA KUNCI TEMA (PENJARA 7 HARI)
# -----------------------------------------------------------------------------
def is_bluesky_keyword_posted(
    redis_url: Optional[str] = None,
    redis_token: Optional[str] = None,
    keyword: str = ""
) -> bool:
    """Menyemak sama ada kata kunci tema carian pernah digunakan < 7 hari lepas."""
    url, token = _get_redis_creds(redis_url, redis_token)
    clean_kw = keyword.lower().strip().replace(" ", "_")
    if not url or not token or not clean_kw:
        return False

    key = f"bsky:kw:{clean_kw}"
    res = _send_redis_command(url, token, ["GET", key])
    return bool(res and res.get("result"))


def mark_bluesky_keyword_posted(
    redis_url: Optional[str] = None,
    redis_token: Optional[str] = None,
    keyword: str = "",
    ttl_seconds: int = TTL_7_DAYS
) -> bool:
    """Mengunci kata kunci carian tema ke dalam penjara Redis Bluesky (7 Hari)."""
    url, token = _get_redis_creds(redis_url, redis_token)
    clean_kw = keyword.lower().strip().replace(" ", "_")
    if not url or not token or not clean_kw:
        return False

    key = f"bsky:kw:{clean_kw}"
    val = datetime.now(timezone.utc).isoformat()
    res = _send_redis_command(url, token, ["SET", key, val, "EX", ttl_seconds])
    return bool(res and res.get("result") == "OK")


# -----------------------------------------------------------------------------
# 5. BANK INGATAN KAPSYEN AI (5 HARI / 10 TERKINI)
# -----------------------------------------------------------------------------
def get_bluesky_story_memories(
    redis_url: Optional[str] = None,
    redis_token: Optional[str] = None,
    category: str = "general",
    limit: int = 5
) -> List[str]:
    """
    Membaca senarai kapsyen pos Bluesky terkini untuk disuapkan ke AI Persona
    bagi mengelakkan pengulangan ayat dan plot yang sama.
    """
    url, token = _get_redis_creds(redis_url, redis_token)
    if not url or not token:
        return []

    key = f"bsky:memories:{category.lower()}"
    res = _send_redis_command(url, token, ["GET", key])
    if res and res.get("result"):
        try:
            data = json.loads(res["result"])
            if isinstance(data, list):
                return data[:limit]
        except Exception:
            pass

    return []


def save_bluesky_story_memory(
    redis_url: Optional[str] = None,
    redis_token: Optional[str] = None,
    caption: str = "",
    category: str = "general",
    max_memories: int = 10,
    ttl_seconds: int = TTL_7_DAYS
) -> bool:
    """
    Menyimpan kapsyen pos Bluesky baharu ke dalam bank ingatan memori.
    Mengekalkan maksimum 10 rekod terkini secara gelung (*FIFO ring-buffer*).
    """
    url, token = _get_redis_creds(redis_url, redis_token)
    clean_caption = caption.strip()
    if not url or not token or not clean_caption:
        return False

    key = f"bsky:memories:{category.lower()}"
    current_memories = get_bluesky_story_memories(url, token, category=category, limit=max_memories)

    # Tambah ingatan baharu di hadapan dan kekalkan had
    updated = [clean_caption] + [m for m in current_memories if m != clean_caption]
    updated = updated[:max_memories]

    res = _send_redis_command(url, token, ["SET", key, json.dumps(updated), "EX", ttl_seconds])
    return bool(res and res.get("result") == "OK")


class BlueskyRedisManager:
    """Kelas pembungkus untuk akses modular."""

    def __init__(self):
        self.url = os.getenv("UPSTASH_REDIS_REST_URL", "").strip()
        self.token = os.getenv("UPSTASH_REDIS_REST_TOKEN", "").strip()

    def is_product_posted(self, product_id: str, title: str = "") -> bool:
        return is_bluesky_product_posted(self.url, self.token, product_id, title)

    def mark_product_posted(self, product_id: str, title: str = "", ttl_seconds: int = TTL_21_DAYS) -> bool:
        return mark_bluesky_product_posted(self.url, self.token, product_id, title, ttl_seconds)

    def is_image_posted(self, photo_id: str) -> bool:
        return is_bluesky_image_posted(self.url, self.token, photo_id)

    def mark_image_posted(self, photo_id: str, ttl_seconds: int = TTL_21_DAYS) -> bool:
        return mark_bluesky_image_posted(self.url, self.token, photo_id, ttl_seconds)

    def is_video_posted(self, video_id: str) -> bool:
        return is_bluesky_video_posted(self.url, self.token, video_id)

    def mark_video_posted(self, video_id: str, ttl_seconds: int = TTL_30_DAYS) -> bool:
        return mark_bluesky_video_posted(self.url, self.token, video_id, ttl_seconds)

    def is_keyword_posted(self, keyword: str) -> bool:
        return is_bluesky_keyword_posted(self.url, self.token, keyword)

    def mark_keyword_posted(self, keyword: str, ttl_seconds: int = TTL_7_DAYS) -> bool:
        return mark_bluesky_keyword_posted(self.url, self.token, keyword, ttl_seconds)

    def get_memories(self, category: str = "general", limit: int = 5) -> List[str]:
        return get_bluesky_story_memories(self.url, self.token, category, limit)

    def save_memory(self, caption: str, category: str = "general", max_memories: int = 10) -> bool:
        return save_bluesky_story_memory(self.url, self.token, caption, category, max_memories)


# Singleton instance
bluesky_redis = BlueskyRedisManager()