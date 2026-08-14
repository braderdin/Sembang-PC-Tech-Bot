#!/usr/bin/env python3
"""
Instagram Dedicated Redis Storage & Cache Manager
Sembang PC & Tech Ecosystem
"""

import os
import json
import time
from datetime import datetime
from typing import Optional, Dict, Any, List
import redis
from dotenv import load_dotenv

load_dotenv()

# Konfigurasi Sambungan Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
IG_KEY_PREFIX = "ig:"
DEFAULT_LOCK_TIMEOUT = 300  # 5 minit


class InstagramRedisManager:
    """Pengurus Redis khas untuk operasi automasi Instagram."""

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or REDIS_URL
        self.client = None
        self._connect()

    def _connect(self):
        """Membuat sambungan ke Redis server."""
        try:
            self.client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            self.client.ping()
        except Exception as e:
            print(f"⚠️ [Instagram Redis] Amaran Sambungan: {e}")
            self.client = None

    def is_connected(self) -> bool:
        """Semak status sambungan Redis."""
        if not self.client:
            return False
        try:
            return bool(self.client.ping())
        except Exception:
            return False

    # -------------------------------------------------------------------------
    # 1. SEMAKAN & PENDAFTARAN PRODUK POSTED (ANTI-DUPLICATE)
    # -------------------------------------------------------------------------

    def is_product_posted(self, product_id: str) -> bool:
        """
        Menyemak sama ada produk ini telah pun dipos ke Instagram sebelum ini.
        """
        if not self.is_connected():
            return False
        key = f"{IG_KEY_PREFIX}posted_products"
        try:
            return bool(self.client.sismember(key, str(product_id)))
        except Exception as e:
            print(f"⚠️ [Instagram Redis] Ralat semak produk: {e}")
            return False

    def mark_product_as_posted(
        self, product_id: str, metadata: Optional[Dict[str, Any]] = None, ttl_days: int = 45
    ) -> bool:
        """
        Menandakan produk sebagai telah dipos ke Instagram dan menyimpan log masa.
        """
        if not self.is_connected():
            return False
        set_key = f"{IG_KEY_PREFIX}posted_products"
        detail_key = f"{IG_KEY_PREFIX}product_log:{product_id}"
        
        try:
            # Masukkan ke Set utama
            self.client.sadd(set_key, str(product_id))

            # Simpan rekod terperinci bersama masa
            record = {
                "product_id": str(product_id),
                "posted_at": datetime.now().isoformat(),
                "metadata": metadata or {},
            }
            self.client.setex(detail_key, ttl_days * 86400, json.dumps(record))
            return True
        except Exception as e:
            print(f"⚠️ [Instagram Redis] Ralat simpan status produk: {e}")
            return False

    # -------------------------------------------------------------------------
    # 2. SISTEM KUNCI KESELAMATAN (DISTRIBUTED LOCK)
    # -------------------------------------------------------------------------

    def acquire_lock(self, lock_name: str = "auto_post_lock", timeout: int = DEFAULT_LOCK_TIMEOUT) -> bool:
        """
        Mengunci proses hantaran IG agar tidak bertembung semasa cron job berjalan serentak.
        """
        if not self.is_connected():
            return True  # Lulus jika tiada Redis (fallback)
        lock_key = f"{IG_KEY_PREFIX}lock:{lock_name}"
        try:
            # Set key jika belum wujud (NX) dengan masa luput (EX)
            acquired = self.client.set(lock_key, "LOCKED", nx=True, ex=timeout)
            return bool(acquired)
        except Exception as e:
            print(f"⚠️ [Instagram Redis] Ralat acquire lock: {e}")
            return True

    def release_lock(self, lock_name: str = "auto_post_lock") -> bool:
        """Melepaskan kunci hantaran Instagram."""
        if not self.is_connected():
            return True
        lock_key = f"{IG_KEY_PREFIX}lock:{lock_name}"
        try:
            self.client.delete(lock_key)
            return True
        except Exception as e:
            print(f"⚠️ [Instagram Redis] Ralat release lock: {e}")
            return False

    # -------------------------------------------------------------------------
    # 3. PENGESAN HAD KUOTA HARIAN (DAILY POST COUNTER)
    # -------------------------------------------------------------------------

    def get_daily_post_count(self) -> int:
        """Mendapatkan jumlah pos yang telah dibuat hari ini di Instagram."""
        if not self.is_connected():
            return 0
        today_str = datetime.now().strftime("%Y-%m-%d")
        key = f"{IG_KEY_PREFIX}daily_count:{today_str}"
        try:
            count = self.client.get(key)
            return int(count) if count else 0
        except Exception:
            return 0

    def increment_daily_post_count(self) -> int:
        """Menambah kiraan kuota harian Instagram."""
        if not self.is_connected():
            return 1
        today_str = datetime.now().strftime("%Y-%m-%d")
        key = f"{IG_KEY_PREFIX}daily_count:{today_str}"
        try:
            new_count = self.client.incr(key)
            # Set luput 48 jam untuk jimat memori
            if new_count == 1:
                self.client.expire(key, 172800)
            return new_count
        except Exception:
            return 1

    # -------------------------------------------------------------------------
    # 4. LOG REKOD HANTARAN TERKINI (RECENT POST HISTORY)
    # -------------------------------------------------------------------------

    def log_published_post(self, post_type: str, item_id: str, media_id: str, permalink: str):
        """Menyimpan sejarah 50 hantaran terkini Instagram."""
        if not self.is_connected():
            return
        history_key = f"{IG_KEY_PREFIX}recent_posts"
        data = {
            "type": post_type,
            "item_id": item_id,
            "media_id": media_id,
            "permalink": permalink,
            "timestamp": datetime.now().isoformat(),
        }
        try:
            self.client.lpush(history_key, json.dumps(data))
            self.client.ltrim(history_key, 0, 49)  # Simpan 50 sahaja
        except Exception as e:
            print(f"⚠️ [Instagram Redis] Ralat log sejarah pos: {e}")


# Singleton instance untuk kegunaan pantas seluruh modul
instagram_redis = InstagramRedisManager()