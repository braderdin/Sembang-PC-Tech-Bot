import os
import requests
from typing import Any, Optional, Tuple

# Masa luput lalai 30 Hari dalam saat (30 * 24 * 60 * 60 = 2,592,000 saat)
DEFAULT_TTL_SECONDS = int(os.getenv("SHOPEE_REDIS_DEDUP_TTL_SECONDS", "2592000"))


def get_redis_config() -> Tuple[Optional[str], Optional[str], str]:
    """
    Membaca tetapan sambungan Upstash Redis REST daripada persekitaran (env).
    """
    redis_url = os.getenv("UPSTASH_REDIS_REST_URL", "").strip() or os.getenv("UPSTASH_REDIS_URL", "").strip()
    redis_token = os.getenv("UPSTASH_REDIS_REST_TOKEN", "").strip() or os.getenv("UPSTASH_API_KEY", "").strip()

    if not redis_url or not redis_token:
        return None, None, "Kunci UPSTASH_REDIS_REST_URL atau UPSTASH_REDIS_REST_TOKEN tidak lengkap dalam persekitaran."

    return redis_url.rstrip("/"), redis_token, ""


def get_shopee_redis_key(product_id: Any) -> str:
    """
    Menjana format kunci Redis khusus Shopee berdasarkan product_id.
    Format: shopee:product:<product_id>
    """
    clean_id = str(product_id or "").strip()
    return f"shopee:product:{clean_id}"


def is_shopee_product_posted(
    product_id: Any,
    redis_url: Optional[str] = None,
    redis_token: Optional[str] = None
) -> bool:
    """
    Menyemak sama ada product_id Shopee pernah dihantar dalam tempoh 30 hari lepas.
    Memulangkan True jika kunci wujud, False jika tiada / belum dipos.
    """
    if not redis_url or not redis_token:
        r_url, r_token, err = get_redis_config()
        if err:
            print(f"⚠️ [REDIS CONFIG WARN] {err}")
            return False
        redis_url, redis_token = r_url, r_token

    clean_id = str(product_id or "").strip()
    if not clean_id:
        return False

    redis_key = get_shopee_redis_key(clean_id)
    endpoint = f"{redis_url}/"
    headers = {
        "Authorization": f"Bearer {redis_token}",
        "Content-Type": "application/json"
    }
    payload = ["GET", redis_key]

    try:
        res = requests.post(endpoint, json=payload, headers=headers, timeout=10)
        if res.status_code == 200:
            res_json = res.json()
            result = res_json.get("result")
            # Jika nilai wujud dan bukan null/None, produk pernah dipos
            if result is not None and str(result) != "null":
                return True
        else:
            print(f"⚠️ [REDIS WARN] HTTP {res.status_code} semasa menyemak kunci '{redis_key}': {res.text}")
    except Exception as e:
        print(f"⚠️ [REDIS WARN] Gagal berhubung dengan Upstash Redis API: {e}")

    return False


def mark_shopee_product_posted(
    product_id: Any,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    redis_url: Optional[str] = None,
    redis_token: Optional[str] = None
) -> bool:
    """
    Menyimpan product_id Shopee ke Redis dengan nilai '1' dan TTL 30 Hari secara atomik.
    Perintah Upstash REST via POST: ["SET", key, "1", "EX", ttl_seconds]
    """
    if not redis_url or not redis_token:
        r_url, r_token, err = get_redis_config()
        if err:
            print(f"⚠️ [REDIS CONFIG ERROR] {err}")
            return False
        redis_url, redis_token = r_url, r_token

    clean_id = str(product_id or "").strip()
    if not clean_id:
        return False

    redis_key = get_shopee_redis_key(clean_id)
    endpoint = f"{redis_url}/"
    headers = {
        "Authorization": f"Bearer {redis_token}",
        "Content-Type": "application/json"
    }
    payload = ["SET", redis_key, "1", "EX", str(ttl_seconds)]

    try:
        res = requests.post(endpoint, json=payload, headers=headers, timeout=10)
        if res.status_code == 200:
            res_json = res.json()
            if res_json.get("result") == "OK":
                days = ttl_seconds // 86400
                print(f"💾 [REDIS SUCCESS] Kunci '{redis_key}' direkodkan dengan TTL {ttl_seconds}s (~{days} Hari).")
                return True
        else:
            print(f"⚠️ [REDIS ERROR] Gagal menyimpan kunci. HTTP {res.status_code}: {res.text}")
    except Exception as e:
        print(f"⚠️ [REDIS WARN] Gagal menyimpan kunci ke Redis: {e}")

    return False


def delete_shopee_product_posted(
    product_id: Any,
    redis_url: Optional[str] = None,
    redis_token: Optional[str] = None
) -> bool:
    """
    Memadam kunci product_id Shopee dari Redis (berguna jika perlu undur balik / rollback).
    """
    if not redis_url or not redis_token:
        r_url, r_token, err = get_redis_config()
        if err:
            return False
        redis_url, redis_token = r_url, r_token

    clean_id = str(product_id or "").strip()
    if not clean_id:
        return False

    redis_key = get_shopee_redis_key(clean_id)
    endpoint = f"{redis_url}/"
    headers = {
        "Authorization": f"Bearer {redis_token}",
        "Content-Type": "application/json"
    }
    payload = ["DEL", redis_key]

    try:
        res = requests.post(endpoint, json=payload, headers=headers, timeout=10)
        return res.status_code == 200 and res.json().get("result") == 1
    except Exception:
        return False