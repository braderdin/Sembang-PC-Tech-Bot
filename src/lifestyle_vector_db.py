import time
import requests

# Tetapan keserupaan & masa luput khas lifestyle
SIMILARITY_THRESHOLD = 0.85  # Skor >= 0.85 dianggap topik/isu yang serupa
TIME_WINDOW_2_DAYS = 172800  # 48 Jam dalam saat (2 * 24 * 60 * 60)

def is_similar_lifestyle_story_posted(vector_url, vector_token, story_text):
    """
    Semak sama ada AI Persona pernah menulis cerita dengan jalan cerita/topik serupa (Cosine Similarity >= 0.85)
    dalam tempoh 48 jam lepas di Upstash Vector DB.
    """
    if not vector_url or not vector_token or not story_text:
        return False

    clean_url = vector_url.rstrip('/')
    query_url = f"{clean_url}/query-data"
    headers = {
        "Authorization": f"Bearer {vector_token}",
        "Content-Type": "application/json"
    }

    payload = {
        "data": str(story_text),
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

                # Semak jika skor >= 0.85 DAN ditulis kurang dari 48 jam lepas
                if score >= SIMILARITY_THRESHOLD and (current_time - posted_at) < TIME_WINDOW_2_DAYS:
                    matched_summary = metadata.get('story_snippet', 'Cerita Lifestyle Serupa')
                    print(f"⏭️ [LIFESTYLE VECTOR MATCH] Topik cerita serupa dikesan ({score*100:.1f}%) dengan: '{matched_summary}' (< 48 jam).")
                    return True
    except Exception as e:
        print(f"⚠️ [LIFESTYLE VECTOR WARN] Ralat menyemak keserupaan cerita di Vector DB: {e}")

    return False

def mark_lifestyle_vector_posted(vector_url, vector_token, story_id, story_text):
    """
    Simpan vector embedding teks cerita lifestyle ke dalam Upstash Vector DB.
    """
    if not vector_url or not vector_token or not story_id or not story_text:
        return False

    clean_url = vector_url.rstrip('/')
    upsert_url = f"{clean_url}/upsert-data"
    headers = {
        "Authorization": f"Bearer {vector_token}",
        "Content-Type": "application/json"
    }

    current_time = int(time.time())
    snippet = story_text[:100] + "..." if len(story_text) > 100 else story_text

    payload = {
        "id": f"lifestyle_{story_id}",
        "data": str(story_text),
        "metadata": {
            "story_snippet": str(snippet),
            "posted_at": current_time,
            "type": "lifestyle"
        }
    }

    try:
        res = requests.post(upsert_url, json=payload, headers=headers, timeout=12)
        if res.status_code == 200:
            print(f"🟢 [LIFESTYLE VECTOR SUCCESS] Embedding cerita (ID: lifestyle_{story_id}) berjaya disimpan ke Vector DB.")
            return True
        else:
            print(f"⚠️ [LIFESTYLE VECTOR ERROR] Ralat HTTP {res.status_code}: {res.text}")
    except Exception as e:
        print(f"⚠️ [LIFESTYLE VECTOR WARN] Gagal menyimpan rekod embedding cerita: {e}")

    return False