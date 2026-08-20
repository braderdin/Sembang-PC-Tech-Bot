#!/usr/bin/env python3
"""
Lazada Redis Deduplication & Cooldown Filter Engine
Sembang PC & Tech Ecosystem (Upstash REST API)
Features:
- 30-Day TTL Exact Match Lock (Key: 'lazada:product:<product_id>')
- Atomic SET with EX 2,592,000s
- Standalone helper with environment auto-loading
"""

import os
import requests
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# 1. Konfigurasi Laluan Projek & Muat Turun Environment
PROJECT_ROOT = Path(__file__).resolve().parent.parent
env_local = PROJECT_ROOT / ".env.local"
if env_local.exists():
    load_dotenv(dotenv_path=env_local)
else:
    load_dotenv()

# Masa luput lalai 30 Hari dalam saat (30 * 24 * 60 * 60 = 2,592,000 saat)
DEFAULT_TTL_SECONDS = int(os.getenv("REDIS_DEDUP_TTL_SECONDS", "2592000"))


def get_redis_config() -> tuple[str, str]:
    """Membaca kelayakan Upstash Redis secara dinamik daripada persekitaran."""
    url = os.getenv("UPSTASH_REDIS_REST_URL", "").strip().rstrip("/")
    token = os.getenv("UPSTASH_REDIS_REST_TOKEN", "").strip()
    return url, token


def get_lazada_redis_key(product_id: str) -> str:
    """Menjana format kunci Redis berstruktur untuk produk affiliate Lazada."""
    clean_id = str(product_id or "").strip()
    return f"lazada:product:{clean_id}"


def is_lazada_product_posted(
    product_id: str,
    redis_url: Optional[str] = None,
    redis_token: Optional[str] = None
) -> bool:
    """
    Menyemak sama ada product_id pernah dihantar dalam tempoh 30 hari lepas.
    Format Kunci: lazada:product:<product_id>
    """
    url = (redis_url or os.getenv("UPSTASH_REDIS_REST_URL", "")).strip().rstrip("/")
    token = (redis_token or os.getenv("UPSTASH_REDIS_REST_TOKEN", "")).strip()

    if not url or not token or not product_id:
        return False

    redis_key = get_lazada_redis_key(product_id)
    endpoint = f"{url}/"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = ["GET", redis_key]

    try:
        res = requests.post(endpoint, json=payload, headers=headers, timeout=10)
        if res.status_code == 200:
            res_json = res.json()
            result = res_json.get("result")
            # Jika nilai wujud dan bukan null, produk masih dalam tempoh sekatan 30 hari
            if result is not None and str(result) != "null":
                return True
        else:
            print(f"⚠️ [LAZADA REDIS WARN] HTTP {res.status_code} semasa semakan kunci: {res.text}")
    except Exception as e:
        print(f"⚠️ [LAZADA REDIS WARN] Ralat sambungan Upstash Redis: {e}")

    return False


def mark_lazada_product_posted(
    product_id: str,
    redis_url: Optional[str] = None,
    redis_token: Optional[str] = None
) -> bool:
    """
    Merekodkan product_id ke Redis dengan nilai '1' dan masa luput (TTL) 30 Hari secara atomik.
    Perintah Upstash REST via POST: ["SET", key, "1", "EX", 2592000]
    """
    url = (redis_url or os.getenv("UPSTASH_REDIS_REST_URL", "")).strip().rstrip("/")
    token = (redis_token or os.getenv("UPSTASH_REDIS_REST_TOKEN", "")).strip()

    if not url or not token or not product_id:
        return False

    redis_key = get_lazada_redis_key(product_id)
    endpoint = f"{url}/"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = ["SET", redis_key, "1", "EX", str(DEFAULT_TTL_SECONDS)]

    try:
        res = requests.post(endpoint, json=payload, headers=headers, timeout=10)
        if res.status_code == 200:
            res_json = res.json()
            if res_json.get("result") == "OK":
                print(f"💾 [REDIS SUCCESS] Kunci '{redis_key}' direkodkan dengan TTL {DEFAULT_TTL_SECONDS}s (~30 Hari).")
                return True
        else:
            print(f"⚠️ [LAZADA REDIS ERROR] Gagal simpan kunci. HTTP {res.status_code}: {res.text}")
    except Exception as e:
        print(f"⚠️ [LAZADA REDIS WARN] Ralat menyimpan kunci ke Redis: {e}")

    return False


def delete_lazada_product_posted(
    product_id: str,
    redis_url: Optional[str] = None,
    redis_token: Optional[str] = None
) -> bool:
    """
    Memadam kunci product_id daripada Redis sekiranya aliran pemposan dibatalkan.
    """
    url = (redis_url or os.getenv("UPSTASH_REDIS_REST_URL", "")).strip().rstrip("/")
    token = (redis_token or os.getenv("UPSTASH_REDIS_REST_TOKEN", "")).strip()

    if not url or not token or not product_id:
        return False

    redis_key = get_lazada_redis_key(product_id)
    endpoint = f"{url}/"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = ["DEL", redis_key]

    try:
        res = requests.post(endpoint, json=payload, headers=headers, timeout=10)
        return res.status_code == 200 and res.json().get("result") == 1
    except Exception:
        return False


# Alias keserasian ke belakang (backward compatibility)
is_product_posted = is_lazada_product_posted
mark_product_posted = mark_lazada_product_posted
delete_product_posted = delete_lazada_product_posted