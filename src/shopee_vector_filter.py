import os
import time
import requests
from typing import Any, Optional, Tuple

# Tetapan Keserupaan & Masa Luput (Penjarakan 3 Hari / 80% Cosine Similarity)
SIMILARITY_THRESHOLD = float(os.getenv("SHOPEE_VECTOR_SIMILARITY_THRESHOLD", "0.80"))
TIME_WINDOW_3_DAYS = int(os.getenv("SHOPEE_VECTOR_WINDOW_SECONDS", "259200"))  # 3 Hari dalam saat (3 * 24 * 60 * 60)


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


def get_shopee_vector_id(product_id: Any) -> str:
    """
    Menjana format ID Dokumen Vector khusus Shopee.
    Format: sp_<product_id> (cth: sp_29990142221)
    """
    clean_id = str(product_id or "").strip()
    return f"sp_{clean_id}"


def is_similar_shopee_product_posted(
    product_title: str,
    vector_url: Optional[str] = None,
    vector_token: Optional[str] = None,
    threshold: float = SIMILARITY_THRESHOLD,
    window_seconds: int = TIME_WINDOW_3_DAYS
) -> bool:
    """
    Menyemak sama ada terdapat produk Shopee dengan makna/tema serupa (Cosine Similarity >= 80%)
    yang pernah dipos dalam tempoh 3 hari (259,200 saat) melalui Upstash Vector REST API.
    """
    if not vector_url or not vector_token:
        v_url, v_token, err = get_vector_config()
        if err:
            print(f"⚠️ [VECTOR CONFIG WARN] {err}")
            return False
        vector_url, vector_token = v_url, v_token

    clean_title = str(product_title or "").strip()
    if not clean_title:
        return False

    endpoint = f"{vector_url}/query-data"
    headers = {
        "Authorization": f"Bearer {vector_token}",
        "Content-Type": "application/json"
    }

    # topK: 5 untuk menyemak 5 hantaran terdahulu yang paling hampir maksudnya
    payload = {
        "data": clean_title,
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
                platform = metadata.get("platform", "shopee")

                # Semak kesamaan tajuk >= threshold DAN jarak masa pos kurang daripada 3 hari
                time_diff = current_time - posted_at
                if score >= threshold and time_diff < window_seconds:
                    matched_title = metadata.get("title", "Produk Tech Serupa")
                    hours_ago = time_diff / 3600
                    print(
                        f"⏭️ [VECTOR DB MATCH] Produk serupa dikesan! '{clean_title}' mirip "
                        f"({score * 100:.1f}%) dengan '{matched_title}' ({hours_ago:.1f} jam lepas pada platform '{platform}'). Langkau."
                    )
                    return True
        else:
            print(f"⚠️ [VECTOR WARN] HTTP {res.status_code} semasa semakan carian vektor: {res.text}")
    except Exception as e:
        print(f"⚠️ [VECTOR WARN] Gagal membuat semakan di Upstash Vector DB: {e}")

    return False


def mark_shopee_vector_posted(
    product_id: Any,
    product_title: str,
    vector_url: Optional[str] = None,
    vector_token: Optional[str] = None
) -> bool:
    """
    Menyimpan embedding tajuk produk ke dalam Upstash Vector DB.
    Format ID: sp_<product_id>
    Metadata: platform: shopee, product_id, title, posted_at
    """
    if not vector_url or not vector_token:
        v_url, v_token, err = get_vector_config()
        if err:
            print(f"⚠️ [VECTOR CONFIG ERROR] {err}")
            return False
        vector_url, vector_token = v_url, v_token

    clean_id = str(product_id or "").strip()
    clean_title = str(product_title or "").strip()
    if not clean_id or not clean_title:
        return False

    endpoint = f"{vector_url}/upsert-data"
    headers = {
        "Authorization": f"Bearer {vector_token}",
        "Content-Type": "application/json"
    }

    doc_id = get_shopee_vector_id(clean_id)
    current_time = int(time.time())

    payload = {
        "id": doc_id,
        "data": clean_title,
        "metadata": {
            "platform": "shopee",
            "product_id": clean_id,
            "title": clean_title,
            "posted_at": current_time
        }
    }

    try:
        res = requests.post(endpoint, json=payload, headers=headers, timeout=12)
        if res.status_code == 200:
            print(f"🟢 [VECTOR SUCCESS] Embedding '{clean_title}' (ID: {doc_id}) berjaya direkodkan ke Vector DB.")
            return True
        else:
            print(f"⚠️ [VECTOR ERROR] Ralat HTTP {res.status_code}: {res.text}")
    except Exception as e:
        print(f"⚠️ [VECTOR WARN] Gagal menyimpan rekod embedding ke Upstash Vector DB: {e}")

    return False


def delete_shopee_vector_posted(
    product_id: Any,
    vector_url: Optional[str] = None,
    vector_token: Optional[str] = None
) -> bool:
    """
    Memadam rekod embedding produk Shopee dari Vector DB (jika berlaku rollback).
    """
    if not vector_url or not vector_token:
        v_url, v_token, err = get_vector_config()
        if err:
            return False
        vector_url, vector_token = v_url, v_token

    clean_id = str(product_id or "").strip()
    if not clean_id:
        return False

    endpoint = f"{vector_url}/delete"
    headers = {
        "Authorization": f"Bearer {vector_token}",
        "Content-Type": "application/json"
    }
    doc_id = get_shopee_vector_id(clean_id)
    payload = {"ids": [doc_id]}

    try:
        res = requests.post(endpoint, json=payload, headers=headers, timeout=10)
        return res.status_code == 200
    except Exception:
        return False