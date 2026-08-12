import os
import requests

# Masa luput lalai 15 Hari dalam saat (15 * 24 * 60 * 60 = 1,296,000 saat)
DEFAULT_TTL_SECONDS = int(os.getenv("REDIS_DEDUP_TTL_SECONDS", "1296000"))

def get_redis_key(product_id):
    """
    Menjana format kunci Redis berdasarkan product_id (item_id) secara terus tanpa hash SHA-256.
    """
    clean_id = str(product_id or "").strip()
    return f"posted:product_id:{clean_id}"

def is_product_posted(redis_url, redis_token, product_id, title=""):
    """
    Semak sama ada product_id pernah dihantar dalam tempoh 15 hari lepas.
    Format Kunci: posted:product_id:<product_id>
    """
    if not redis_url or not redis_token or not product_id:
        return False
    
    clean_url = redis_url.rstrip('/')
    redis_key = get_redis_key(product_id)
    
    endpoint = f"{clean_url}/"
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
            print(f"⚠️ [REDIS WARN] HTTP {res.status_code} semasa menyemak kunci: {res.text}")
    except Exception as e:
        print(f"⚠️ [REDIS WARN] Gagal berhubung dengan Upstash Redis API: {e}")
        
    return False

def mark_product_posted(redis_url, redis_token, product_id, title=""):
    """
    Simpan product_id ke Redis dengan nilai '1' dan masa luput (TTL) 15 Hari secara atomik.
    Perintah Upstash REST via POST: ["SET", key, "1", "EX", 1296000]
    """
    if not redis_url or not redis_token or not product_id:
        return False
    
    clean_url = redis_url.rstrip('/')
    redis_key = get_redis_key(product_id)
    
    endpoint = f"{clean_url}/"
    headers = {
        "Authorization": f"Bearer {redis_token}",
        "Content-Type": "application/json"
    }
    payload = ["SET", redis_key, "1", "EX", str(DEFAULT_TTL_SECONDS)]
    
    try:
        res = requests.post(endpoint, json=payload, headers=headers, timeout=10)
        if res.status_code == 200:
            res_json = res.json()
            if res_json.get("result") == "OK":
                print(f"💾 [REDIS SUCCESS] Kunci '{redis_key}' direkodkan dengan TTL {DEFAULT_TTL_SECONDS}s (15 Hari).")
                return True
        else:
            print(f"⚠️ [REDIS ERROR] Gagal menyimpan kunci. HTTP {res.status_code}: {res.text}")
    except Exception as e:
        print(f"⚠️ [REDIS WARN] Gagal menyimpan kunci ke Redis: {e}")
        
    return False

def delete_product_posted(redis_url, redis_token, product_id, title=""):
    """
    Memadam kunci product_id dari Redis sekiranya pemprosesan hantaran seterusnya gagal.
    """
    if not redis_url or not redis_token or not product_id:
        return False
        
    clean_url = redis_url.rstrip('/')
    redis_key = get_redis_key(product_id)
    
    endpoint = f"{clean_url}/"
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