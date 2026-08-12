import time
import requests

# Tetapan Keserupaan & Masa Luput
SIMILARITY_THRESHOLD = 0.85 # Skor 0.85 ke atas dianggap barang/tema yang sama (cth: "Mouse Logitech M170" vs "Logitech Mouse Wireless")
TIME_WINDOW_2_DAYS = 172800  # 2 Hari dalam saat (2 * 24 * 60 * 60)

def is_similar_product_posted(vector_url, vector_token, product_title):
    """
    Semak sama ada terdapat produk dengan makna/fungsi serupa (Cosine Similarity >= 0.85)
    yang pernah dipos dalam tempoh 2 hari (172,800 saat) menggunakan Upstash Vector REST API.
    """
    if not vector_url or not vector_token or not product_title:
        return False

    clean_url = vector_url.rstrip('/')
    query_url = f"{clean_url}/query-data"
    headers = {
        "Authorization": f"Bearer {vector_token}",
        "Content-Type": "application/json"
    }

    # topK: 3 bermaksud kita semak 3 hasil yang paling hampir maknanya
    payload = {
        "data": str(product_title),
        "topK": 3,
        "includeMetadata": True
    }

    try:
        res = requests.post(query_url, json=payload, headers=headers, timeout=12)
        if res.status_code == 200:
            results = res.json().get("result", [])
            current_time = int(time.time())

            for match in results:
                score = match.get("score", 0.0)
                metadata = match.get("metadata", {}) or {}
                posted_at = metadata.get("posted_at", 0)

                # Semak jika skor >= 0.85 DAN jarak masa pos kurang daripada 2 hari (172,800 saat)
                if score >= SIMILARITY_THRESHOLD and (current_time - posted_at) < TIME_WINDOW_2_DAYS:
                    matched_title = metadata.get('title', 'Produk Tech Serupa')
                    print(f"⏭️ [VECTOR DB MATCH] Gajet/Tema serupa dikesan! '{product_title}' mirip ({score*100:.1f}%) dengan '{matched_title}' (< 48 jam lepas). Langkau.")
                    return True
    except Exception as e:
        print(f"⚠️ [VECTOR WARN] Gagal membuat semakan di Upstash Vector DB: {e}")

    return False

def mark_vector_posted(vector_url, vector_token, product_id, product_title):
    """
    Simpan vector embedding tajuk produk ke dalam Upstash Vector DB.
    Ini membolehkan AI mengesan jika kita cuba pos barang yang sama/bertema serupa pada masa hadapan.
    """
    if not vector_url or not vector_token or not product_id or not product_title:
        return False

    clean_url = vector_url.rstrip('/')
    upsert_url = f"{clean_url}/upsert-data"
    headers = {
        "Authorization": f"Bearer {vector_token}",
        "Content-Type": "application/json"
    }

    current_time = int(time.time())
    
    payload = {
        "id": str(product_id),
        "data": str(product_title),
        "metadata": {
            "title": str(product_title),
            "posted_at": current_time
        }
    }

    try:
        res = requests.post(upsert_url, json=payload, headers=headers, timeout=12)
        if res.status_code == 200:
            print(f"🟢 [VECTOR SUCCESS] Embedding '{product_title}' (ID: {product_id}) berjaya direkodkan ke Vector DB.")
            return True
        else:
            print(f"⚠️ [VECTOR ERROR] Ralat HTTP {res.status_code}: {res.text}")
    except Exception as e:
        print(f"⚠️ [VECTOR WARN] Gagal menyimpan rekod embedding ke Upstash Vector DB: {e}")

    return False