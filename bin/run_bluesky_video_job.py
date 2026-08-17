#!/usr/bin/env python3
"""
Master Execution Runner for Bluesky 9:16 Video Posts (Pexels Video + Music Metadata + Affiliate Auto-Reply)
Sembang PC & Tech Ecosystem (100% Dynamic Keys & Native AT-Protocol)
Execution Flow:
1. Detect Malaysian Time Slot & Load 5 Recent Video Memories from Redis.
2. AI Generates Fresh Keyword -> Filters against Redis & Vector DB.
3. 1 API Call to Pexels (per_page=40) -> Strict Faceless Filter -> Bluesky Redis 30-Day Duplicate Filtering -> Pick 3 Clips.
4. [RENDER DAHULU] MoviePy stitches clips (1080x1920, 21-24s) + local audio from assets/music/.
5. [AI JANA AYAT SELEPAS RENDER] AI Persona generates concise video micro-caption (< 270 chars) with audio metadata.
6. Semantic similarity check via Bluesky Vector DB (7-Day Window / Cosine >= 0.80) with auto-retry loop.
7. Pull 1 relevant affiliate product link from Supabase for the first comment.
8. Publish Video + Auto-Reply Affiliate Comment to Bluesky Feed & Video Tab.
9. Send rich audit notification with permalinks to Telegram.
10. Record Video IDs (30-Day TTL), Memories, and Vector Embeddings.
"""

import os
import sys
import random
import tempfile
import requests
from pathlib import Path
from typing import List, Dict, Any, Tuple
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
from src.pexels_keyword_engine import get_fresh_pexels_reel_keyword
from src.pexels_reel_bot import is_video_safe_and_faceless, download_video_clip, render_stitched_reel_video
from src.supabase_db import fetch_unused_links
from src.bluesky_bot import bluesky_bot
from src.bluesky_ai_persona import bluesky_ai, detect_bluesky_time_slot
from src.bluesky_audit import send_bluesky_audit_to_telegram
from src.bluesky_redis_db import bluesky_redis
from src.bluesky_vector_db import bluesky_vector


def fetch_and_filter_pexels_for_bluesky(
    api_key: str,
    query: str,
    needed_count: int = 3,
    batch_size: int = 40,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Menghantar 1 permintaan API ke Pexels (per_page=40) dan menapis kandungan selamat serta segar untuk Bluesky."""
    print(f"\n📡 [PEXELS API] Menghantar 1 request (per_page={batch_size}) carian video: '{query}'...")

    if not api_key:
        print("❌ [PEXELS ERROR] Kunci API Pexels tidak disediakan.")
        return [], []

    url = "https://api.pexels.com/videos/search"
    headers = {"Authorization": api_key}
    params = {
        "query": query,
        "orientation": "portrait",
        "per_page": batch_size,
        "size": "medium",
    }

    try:
        res = requests.get(url, headers=headers, params=params, timeout=25)
        if res.status_code != 200:
            print(f"❌ [PEXELS ERROR] HTTP {res.status_code}: {res.text}")
            return [], []

        data = res.json()
        videos = data.get("videos", [])
        print(f"  ✅ Diterima {len(videos)} calon video dari Pexels API.")

        selected_videos = []
        skipped_ids = []

        for vid in videos:
            vid_id = str(vid.get("id"))
            duration = vid.get("duration", 0)
            files = vid.get("video_files", [])

            # 1. Tapisan Muka Orang & Haiwan Sensitif
            if not is_video_safe_and_faceless(vid):
                vid_slug = vid.get("url", "").split("/")[-2] if "/" in vid.get("url", "") else vid_id
                print(f"  🚫 [FACE SKIP] ID {vid_id} ditolak (Dikesan manusia/muka: '{vid_slug}').")
                continue

            # 2. Semak Penjara 30 Hari Redis Bluesky
            if bluesky_redis.is_video_posted(video_id=vid_id):
                print(f"  ⏭️ [REDIS VIDEO SKIP] ID {vid_id} pernah digunakan di Bluesky < 30 hari lepas.")
                skipped_ids.append(vid_id)
                continue

            # 3. Cari fail MP4 vertikal (height >= width)
            best_file = None
            for f in files:
                if f.get("file_type") == "video/mp4":
                    w = f.get("width") or 0
                    h = f.get("height") or 0
                    if h >= w and h >= 720:
                        best_file = f
                        break

            if not best_file and files:
                for f in files:
                    if f.get("file_type") == "video/mp4":
                        best_file = f
                        break

            if best_file and "link" in best_file:
                selected_videos.append({
                    "id": vid_id,
                    "duration": duration,
                    "url": best_file["link"],
                    "width": best_file.get("width"),
                    "height": best_file.get("height"),
                })

            if len(selected_videos) >= needed_count:
                break

        print(f"  🎯 Berjaya memilih {len(selected_videos)} video 9:16 bebas muka yang disahkan 100% segar.")
        return selected_videos, skipped_ids

    except Exception as e:
        print(f"❌ [PEXELS EXCEPTION] Ralat membuat panggilan API: {e}")
        return [], []


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

    return "Katalog Racun Gajet & Setup", "https://t.me/lubuk_barang_murah_padu_bot"


def run_bluesky_video_posting_job():
    print("\n" + "=" * 70)
    print("🦋 [START] ENJIN PEMPOSAN VIDEO BLUESKY (RENDER DAHULU ➔ AYAT AI ➔ POST)")
    print("=" * 70)

    # 1. Semak Konfigurasi Bot
    if not bluesky_bot.is_configured():
        print("❌ [ABORT] Kunci BLUESKY_HANDLE atau BLUESKY_APP_PASSWORD tiada di .env.local.")
        return

    base_url = os.getenv("OPENROUTER_BASE_URL", "").strip()
    model = os.getenv("OPENROUTER_MODEL", "").strip()
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()

    pexels_key = os.getenv("PEXELS_API_KEY", "").strip()

    redis_url = os.getenv("UPSTASH_REDIS_REST_URL", "").strip()
    redis_token = os.getenv("UPSTASH_REDIS_REST_TOKEN", "").strip()
    vector_url = os.getenv("UPSTASH_VECTOR_REST_URL", "").strip()
    vector_token = os.getenv("UPSTASH_VECTOR_REST_TOKEN", "").strip()

    tg_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    tg_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    music_dir = PROJECT_ROOT / "assets" / "music"

    # 2. Kesan Slot Masa & Mood Hari
    slot_id, slot_desc, day_mood, _ = detect_bluesky_time_slot()
    print(f"\n⏰ [SLOT MASA]: {slot_desc}")
    print(f"🎭 [MOOD HARI]: {day_mood}")

    # 3. Baca Bank Ingatan Cerita Terkini dari Redis
    print("\n🧠 [STEP 1] Membaca Bank Ingatan Video dari Upstash Redis...")
    previous_memories = bluesky_redis.get_memories(category="video", limit=5)
    print(f"  ✅ {len(previous_memories)} ingatan pos lepas berjaya dimuatkan.")

    # 4. Jana & Tapis Kata Kunci Segar Bebas Muka (Redis 5-Hari & Vector 5-Hari)
    print("\n💡 [STEP 2] Enjin Kata Kunci meneliti & menapis kata kunci video segar (Faceless B-Roll)...")
    query_keyword = get_fresh_pexels_reel_keyword(
        base_url=base_url,
        model=model,
        api_key=api_key,
        redis_url=redis_url,
        redis_token=redis_token,
        vector_url=vector_url,
        vector_token=vector_token,
    )

    # 5. Tarik 40 Video Pexels (1 API Call) & Tapis Muka + Penjara 30-Hari Redis
    print("\n🌐 [STEP 3] Menghantar 1 API Call ke Pexels untuk 40 video vertikal (9:16)...")
    selected_videos, _ = fetch_and_filter_pexels_for_bluesky(
        api_key=pexels_key,
        query=query_keyword,
        needed_count=3,
        batch_size=40,
    )

    if len(selected_videos) < 3:
        print("❌ [ABORT] Calon video 9:16 bersih tidak mencukupi (Minimum 3 video diperlukan).")
        return

    video_ids = [v["id"] for v in selected_videos]

    # 6. [RENDER DAHULU] MoviePy Membina Video MP4 + Pilih Audio Latar & Metadata
    print("\n🎬 [STEP 4] [RENDER DAHULU] Membina video Reel MP4 berserta audio latar & metadata...")
    rendered_video_path, music_info, video_duration = render_stitched_reel_video(
        video_items=selected_videos,
        music_dir=music_dir,
        single_clip_duration=8,
    )

    if not rendered_video_path or not os.path.exists(rendered_video_path):
        print("❌ [ABORT] Gagal menjana fail video akhir.")
        return

    music_title_display = music_info.get("title", "Original Audio")
    music_artist_display = music_info.get("artist", "")
    music_audit_label = f"{music_title_display} ({music_artist_display})" if music_artist_display else music_title_display

    # 7. [AI JANA AYAT SELEPAS RENDER] AI Menjana Kapsyen Berdasarkan Video Siap + Metadata Muzik Penuh
    print(f"\n✍️ [STEP 5] [AI JANA AYAT] Menjana penceritaan video mikro Bluesky (Visual: '{query_keyword}', Muzik: '{music_audit_label}', Durasi: {video_duration}s)...")
    caption_text = bluesky_ai.generate_video_post(
        topic_keyword=query_keyword,
        music_info=music_info,
        video_duration=video_duration,
        previous_memories=previous_memories,
    )

    # 8. Semak Keserupaan Semantik di Vector DB (Window 7 Hari / Ambang >= 0.80)
    if bluesky_vector.is_similar(text=caption_text, category="video"):
        print("⚠️ [BLUESKY VECTOR] Ayat ulasan mirip dikesan (< 7 hari lepas). Menjana alternatif...")
        caption_text = bluesky_ai.generate_video_post(
            topic_keyword=query_keyword,
            music_info=music_info,
            video_duration=video_duration,
            previous_memories=previous_memories,
        )

    print(f"\n✅ [KAPSYEN AI BLUESKY FINAL ({len(caption_text)} aksara)]:\n{caption_text}\n")

    # 9. Sediakan Pautan & Teks Komen Pertama Affiliate (Auto-Reply)
    prod_title, prod_link = get_affiliate_recommendation()
    reply_comment_text = bluesky_ai.generate_affiliate_comment(
        product_title=prod_title,
        affiliate_link=prod_link,
    )
    print(f"💬 [AUTO-REPLY TEKS]:\n{reply_comment_text}\n")

    try:
        # 10. Terbitkan Video MP4 + Auto-Reply Komen ke Bluesky
        print("🚀 [STEP 6] Menerbitkan Video ke Bluesky (Feed & Video Tab)...")
        bsky_ok, res_bsky = bluesky_bot.post_with_affiliate_reply(
            main_text=caption_text,
            affiliate_reply_text=reply_comment_text,
            video_path=rendered_video_path,
            alt_text=f"Sembang PC & Tech: {query_keyword} video",
        )

        if not bsky_ok:
            print(f"❌ [BLUESKY POST FAILED] Ralat: {res_bsky.get('error')}")
            return

        permalink = res_bsky.get("permalink", "")
        reply_permalink = res_bsky.get("reply_permalink", "")
        print(f"  🎉 [BLUESKY SUCCESS] Video berjaya diterbitkan! Pautan: {permalink}")

        # 11. Hantar Salinan Audit ke Telegram
        if tg_token and tg_chat_id:
            print("\n🔍 [STEP 7] Menghantar salinan audit ke Telegram...")
            send_bluesky_audit_to_telegram(
                token=tg_token,
                chat_id=tg_chat_id,
                caption=caption_text,
                permalink=permalink,
                post_type=f"Bluesky: Video Reel ({query_keyword}) | Audio: {music_audit_label}",
                reply_permalink=reply_permalink,
                affiliate_link=prod_link,
            )

        # 12. Rekod Status & Ingatan ke Pangkalan Data
        print("\n💾 [STEP 8] Merekodkan status penjarakan & memori...")
        # A. Kunci 3 Video ID ke Redis (30 Hari)
        for vid_id in video_ids:
            bluesky_redis.mark_video_posted(video_id=vid_id)
        print("  ✅ 3 Video ID Pexels dikunci di Upstash Redis (TTL 30 Hari).")

        # B. Kunci Kata Kunci Tema (7 Hari)
        bluesky_redis.mark_keyword_posted(keyword=query_keyword)

        # C. Simpan Kapsyen ke Bank Ingatan Redis (10 Terkini)
        bluesky_redis.save_memory(caption=caption_text, category="video", max_memories=10)

        # D. Simpan Embedding ke Vector DB (Window 7 Hari)
        primary_doc_id = f"{video_ids[0]}_{query_keyword.replace(' ', '_')}"
        bluesky_vector.mark_posted(doc_id=primary_doc_id, text=caption_text, category="video")

        print("\n🎉 [SUCCESS] Seluruh aliran pemposan Video Bluesky (Render Dahulu ➔ Ayat AI ➔ Post) selesai dengan jayanya!\n")

    finally:
        # Bersihkan fail video sementara tempatan
        if os.path.exists(rendered_video_path):
            try:
                os.remove(rendered_video_path)
            except Exception:
                pass


if __name__ == "__main__":
    run_bluesky_video_posting_job()