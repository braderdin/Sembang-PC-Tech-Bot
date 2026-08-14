#!/usr/bin/env python3
"""
Instagram Dedicated Upstash Redis REST Manager
Sembang PC & Tech Ecosystem (100% Environment Driven)
"""

import os
import json
import requests
from datetime import datetime
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

IG_KEY_PREFIX = "ig:"


class InstagramRedisManager:
    """Pengurus cache Upstash Redis REST API khusus Instagram."""

    def __init__(self):
        self.rest_url = os.getenv("UPSTASH_REDIS_REST_URL", "").strip().rstrip("/")
        self.rest_token = os.getenv("UPSTASH_REDIS_REST_TOKEN", "").strip()

    def _execute(self, command: list) -> Any:
        """Menghantar arahan REST API ke Upstash Redis."""
        if not self.rest_url or not self.rest_token:
            return None
        headers = {"Authorization": f"Bearer {self.rest_token}"}
        try:
            res = requests.post(f"{self.rest_url}", headers=headers, json=command, timeout=10)
            if res.status_code == 200:
                return res.json().get("result")
        except Exception as e:
            print(f"⚠️ [Instagram Redis Warning] {e}")
        return None

    def is_product_posted(self, product_id: str) -> bool:
        """Semak sama ada produk wujud dalam set posted Instagram."""
        key = f"{IG_KEY_PREFIX}posted_products"
        result = self._execute(["SISMEMBER", key, str(product_id)])
        return bool(result == 1)

    def mark_product_as_posted(self, product_id: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Tandakan produk telah dipos ke Instagram."""
        set_key = f"{IG_KEY_PREFIX}posted_products"
        detail_key = f"{IG_KEY_PREFIX}product_log:{product_id}"

        # 1. Tambah ke Set
        self._execute(["SADD", set_key, str(product_id)])

        # 2. Simpan perincian (TTL 45 Hari)
        record = {
            "product_id": str(product_id),
            "posted_at": datetime.now().isoformat(),
            "metadata": metadata or {},
        }
        self._execute(["SETEX", detail_key, 3888000, json.dumps(record)])
        return True

    def increment_daily_post_count(self) -> int:
        """Menambah kiraan kuota harian Instagram."""
        today_str = datetime.now().strftime("%Y-%m-%d")
        key = f"{IG_KEY_PREFIX}daily_count:{today_str}"
        new_count = self._execute(["INCR", key])
        if new_count == 1:
            self._execute(["EXPIRE", key, 172800])
        return new_count or 1


# Singleton instance
instagram_redis = InstagramRedisManager()