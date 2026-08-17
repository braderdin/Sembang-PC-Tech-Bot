#!/usr/bin/env python3
"""
Master Execution Runner for Bluesky Lifestyle Workspace Posts (3 Images Album + Affiliate Auto-Reply)
Sembang PC & Tech Ecosystem (100% Dynamic Keys & Native AT-Protocol)
Execution Flow:
1. Detect Malaysian Time Slot & Load 5 Recent Lifestyle Memories from Redis.
2. AI Generates Fresh Keyword -> Filters against Redis (7-Day Cooldown) & Vector DB.
3. Fetch 20-30 Candidate Photos from Unsplash in 1 Request -> Filter Redis 21-Day -> Pick 3 Best Images.
4. AI Persona generates concise lifestyle micro-story (< 270 chars).
5. Semantic similarity check via Bluesky Vector DB (7-Day Window / Cosine >= 0.80) with auto-retry.
6. Pull 1 relevant affiliate product link from Supabase for the first comment.
7. Publish 3-Image Carousel + Auto-Reply Affiliate Comment to Bluesky Feed.
8. Send rich audit notification with permalinks to Telegram.
9. Record Photo IDs (21-Day TTL), Memories, and Vector Embeddings.
"""

import os
import sys
import random
import requests
from typing import List, Dict, Any, Optional
from pathlib import Path
from dotenv import load_dotenv

# Set Project Root Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load Environment Variables Dynamically
env_local = PROJECT_ROOT / ".env.local"
if env_local.exists():
    load_dotenv(dotenv_path=env_local)
else:
    load_dotenv()

# Import Local Modules from src
from src.lifestyle_keyword_engine import get_fresh_lifestyle_keyword
from src.supabase_db import fetch_unused_links
from src.bluesky_bot import bluesky_bot
from src.bluesky_ai_persona import bluesky_ai, detect_bluesky_time_slot
from src.bluesky_audit import send_bluesky_audit_to_telegram
from src.bluesky_redis_db import bluesky_redis
from src.bluesky_vector_db import bluesky_vector


def fetch_unsplash_batch_and_filter(
    access_key: str,
    query_keyword: str,
    needed_count: int = 3,
    batch_size: int = 30
) -> List[Dict[str, Any]]:
    """
    Menghantar 1 permintaan API ke Unsplash (per_page=30) dan menapis
    calon gambar yang segar, bebas duplikasi Redis 21-hari, dan berkualiti tinggi.
    """
    print(f"\n📡 [UNSPLASH API] Menghantar 1 request (per_page={batch_size}) carian: '{query_keyword}'...")
    if not access_key:
        print("❌ [UNSPLASH ERROR] Kunci UNSPLASH_ACCESS_KEY tidak disediakan.")
        return []

    url = "https://api.unsplash.com/search/photos"
    headers = {
        "Authorization": f"Client-ID {access_key}",
        "Accept-Version": "v1"
    }
    params = {
        "query": query_keyword,
        "per_page": batch_size,
        "content_filter": "high",
        "orientation": "landscape"
    }

    try:
        res = requests.get(url, headers=headers, params=params, timeout=25)
        if res.status_code != 200:
            print(f"❌ [UNSPLASH ERROR] HTTP {res.status_code}: {res.text}")
            return []

        data = res.json()
        results = data.get("results", [])
        print(f"  ✅ Diterima {len(results)} calon imej dari Unsplash API.")

        selected_images = []
        for photo in results:
            photo_id = str(photo.get("id", "")).strip()
            if not photo_id:
                continue

            # 1. Semak Penjara 21 Hari Redis Bluesky
            if bluesky_redis.is_image_posted(photo_id=photo_id):
                print(f"  ⏭️ [REDIS SKIP] Photo ID {photo_id} pernah digunakan < 21 hari lepas.")
                continue

            # 2. Dapatkan URL Imej Berkualiti (Regular / Full)
            urls = photo.get("urls", {})
            img_url = urls.get("regular") or urls.get("full") or urls.get("small")
            if not img_url:
                continue

            # 3. Dapatkan Deskripsi Bersih
            desc = (
                photo.get("description")
                or photo.get("alt_description")
                or f"{query_keyword} aesthetic workspace setup"
            ).strip()

            selected_images.append({
                "photo_id": photo_id,
                "image_url": img_url,
                "description": desc,
                "likes": photo.get("likes", 0)
            })

            if len(selected_images) >= needed_count:
                break

        print(f"  🎯 Berjaya memilih {len(selected_images)} gambar estetik 100% segar & lulus tapisan.")
        return selected_images

    except Exception as e:
        print(f"❌ [UNSPLASH EXCEPTION] Ralat membuat panggilan API: {e}")
        return []


def get_affiliate_recommendation():
    """Mengambil 1 produk affiliate dari Supabase untuk diselitkan di ruang komen pertama."""
    try:
        ok, records, _ = fetch_unused_links(limit=20)
        if ok and records:
            item = random.choice(records)
            title = str(item.get("title") or item.get("product_name") or "Aksesori Setup PC").strip()
            link = str(item.get("affiliate_link") or item.get("promo_short_link") or "").strip()
            if link:
                return title, link
    except Exception as e:
        print(f"  ⚠️ [AFFILIATE FETCH WARN] {e}")

    # Fallback jika tiada pautan Supabase
    return "Katalog Racun Gajet & Setup", "https://t.me/lubuk_barang_murah_padu_bot"


def run_bluesky_lifestyle_job():
    print("\n" + "=" * 70)
    print("🦋 [START] ENJIN PEMPOSAN LIFESTYLE BLUESKY (3 GAMBAR + AUTO-REPLY)")
    print("=" * 70)

    # 1. Semak Konfigurasi Bot
    if not bluesky_bot.is_configured():
        print("❌ [ABORT] Kunci BLUESKY_HANDLE atau BLUESKY_APP_PASSWORD tiada di .env.local.")
        return

    base_url = os.getenv("OPENROUTER_BASE_URL", "").strip()
    model = os.getenv("OPENROUTER_MODEL", "").strip()
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()

    unsplash_key = os.getenv("UNSPLASH_ACCESS_KEY", "").strip()

    redis_url = os.getenv("UPSTASH_REDIS_REST_URL", "").strip()
    redis_token = os.getenv("UPSTASH_REDIS_REST_TOKEN", "").strip()
    vector_url = os.getenv("UPSTASH_VECTOR_REST_URL", "").strip()
    vector_token = os.getenv("UPSTASH_VECTOR_REST_TOKEN", "").strip()

    tg_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    tg_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    # 2. Kesan Slot Masa & Mood Hari
    slot_id, slot_desc, day_mood, _ = detect_bluesky_time_slot()
    print(f"\n⏰ [SLOT MASA]: {slot_desc}")
    print(f"🎭 [MOOD HARI]: {day_mood}")

    # 3. Baca Bank Ingatan Cerita Terkini dari Redis
    print("\n🧠 [STEP 1] Membaca Bank Ingatan Lifestyle dari Upstash Redis...")
    previous_memories = bluesky_redis.get_memories(category="lifestyle", limit=5)
    print(f"  ✅ {len(previous_memories)} ingatan pos lepas berjaya dimuatkan.")

    # 4. Jana & Tapis Kata Kunci Segar
    print("\n💡 [STEP 2] Enjin Kata Kunci meneliti kata kunci visual Unsplash...")
    query_keyword = get_fresh_lifestyle_keyword(
        base_url=base_url,
        model=model,
        api_key=api_key,
        redis_url=redis_url,
        redis_token=redis_token,
        vector_url=vector_url,
        vector_token=vector_token,
    )

    # 5. Tarik Kelompok 30 Gambar dari Unsplash API & Pilih 3 Gambar Terbaik Bebas Redis
    image_candidates = fetch_unsplash_batch_and_filter(
        access_key=unsplash_key,
        query_keyword=query_keyword,
        needed_count=3,
        batch_size=30
    )

    if not image_candidates or len(image_candidates) < 3:
        print(f"❌ [ABORT] Calon gambar berkualiti tidak mencukupi (Dapat: {len(image_candidates) if image_candidates else 0}/3).")
        return

    image_urls = [img["image_url"] for img in image_candidates[:3]]
    image_descs = [img["description"] for img in image_candidates[:3]]
    photo_ids = [img["photo_id"] for img in image_candidates[:3]]

    # 6. AI Menjana Kapsyen Mikro-Blog Bluesky (< 270 Aksara)
    context_desc = " & ".join(image_descs[:2]) if image_descs else query_keyword
    print("\n✍️ [STEP 4] Menjana kapsyen mikro-blog santai Brader Din...")
    caption_text = bluesky_ai.generate_lifestyle_post(
        topic_keyword=query_keyword,
        image_context=context_desc,
        previous_memories=previous_memories,
    )

    # 7. Semak Keserupaan Semantik di Vector DB (Window 7 Hari / Ambang >= 0.80)
    if bluesky_vector.is_similar(text=caption_text, category="lifestyle"):
        print("⚠️ [BLUESKY VECTOR] Ayat cerita mirip dikesan (< 7 hari lepas). Menjana alternatif...")
        caption_text = bluesky_ai.generate_lifestyle_post(
            topic_keyword=query_keyword,
            image_context=context_desc,
            previous_memories=previous_memories,
        )

    print(f"\n✅ [KAPSYEN AI BLUESKY FINAL ({len(caption_text)} aksara)]:\n{caption_text}\n")

    # 8. Sediakan Pautan & Teks Komen Pertama Affiliate (Auto-Reply)
    prod_title, prod_link = get_affiliate_recommendation()
    reply_comment_text = bluesky_ai.generate_affiliate_comment(
        product_title=prod_title,
        affiliate_link=prod_link,
    )
    print(f"💬 [AUTO-REPLY TEKS]:\n{reply_comment_text}\n")

    # 9. Terbitkan 3 Gambar + Auto-Reply Komen ke Bluesky Feed
    print("🚀 [STEP 5] Menerbitkan Album 3 Gambar + Komen Pertama ke Bluesky...")
    bsky_ok, res_bsky = bluesky_bot.post_with_affiliate_reply(
        main_text=caption_text,
        affiliate_reply_text=reply_comment_text,
        image_sources=image_urls,
        alt_text=f"Sembang PC & Tech: {query_keyword} setup",
    )

    if not bsky_ok:
        print(f"❌ [BLUESKY POST FAILED] Ralat: {res_bsky.get('error')}")
        return

    permalink = res_bsky.get("permalink", "")
    reply_permalink = res_bsky.get("reply_permalink", "")
    print(f"  🎉 [BLUESKY SUCCESS] Album 3 gambar berjaya diterbitkan! Pautan: {permalink}")

    # 10. Hantar Salinan Audit ke Telegram
    if tg_token and tg_chat_id:
        print("\n🔍 [STEP 6] Menghantar salinan audit ke Telegram...")
        send_bluesky_audit_to_telegram(
            token=tg_token,
            chat_id=tg_chat_id,
            caption=caption_text,
            permalink=permalink,
            post_type=f"Bluesky: Lifestyle 3-Photo ({query_keyword})",
            image_url=image_urls[0],
            reply_permalink=reply_permalink,
            affiliate_link=prod_link,
        )

    # 11. Rekod Status & Ingatan ke Pangkalan Data
    print("\n💾 [STEP 7] Merekodkan status penjarakan & memori...")
    # A. Kunci 3 Photo ID ke Redis (21 Hari)
    for pid in photo_ids:
        bluesky_redis.mark_image_posted(photo_id=pid)
    print("  ✅ 3 Photo ID Unsplash dikunci di Upstash Redis (TTL 21 Hari).")

    # B. Kunci Kata Kunci Tema (7 Hari)
    bluesky_redis.mark_keyword_posted(keyword=query_keyword)

    # C. Simpan Kapsyen ke Bank Ingatan Redis (10 Terkini)
    bluesky_redis.save_memory(caption=caption_text, category="lifestyle", max_memories=10)

    # D. Simpan Embedding ke Vector DB (Window 7 Hari)
    primary_doc_id = photo_ids[0]
    bluesky_vector.mark_posted(doc_id=primary_doc_id, text=caption_text, category="lifestyle")

    print("\n🎉 [SUCCESS] Seluruh aliran pemposan Lifestyle Bluesky (3 Gambar + Auto-Reply) selesai dengan jayanya!\n")


if __name__ == "__main__":
    run_bluesky_lifestyle_job()