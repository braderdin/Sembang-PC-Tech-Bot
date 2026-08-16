#!/usr/bin/env python3
"""
Master Execution Runner for Pexels 9:16 Video Reels (Facebook, Instagram & Threads)
Sembang PC & Tech Ecosystem (2x Daily)
Optimized Execution Flow:
1. Detect Malaysian Time Slot & Load 5 Recent Memories from Redis.
2. AI Generates 10 Candidates -> Filters via Redis 5-Day & Vector DB 5-Day Guardrails -> 1 Keyword Selected.
3. 1 API Call to Pexels (per_page=20) -> Strict Faceless Filter -> Redis 30-Day Duplicate Filtering -> Pick 3 Clips.
4. [RENDER DAHULU] MoviePy stitches 3 clips (21-24s, 1080x1920) + local audio from assets/music/ (with Smart Metadata).
5. [AI JANA AYAT SELEPAS RENDER] AI Persona generates caption with full video & music metadata (Title, Artist, Genre, Vibe).
6. Vector DB checks caption semantic similarity (5-day window) with auto-retry loop.
7. Publish to Facebook Reels (Meta Graph API) with Fallback to Facebook Feed if Reels Limit.
8. Publish to Instagram Reels (@braderdin360) + Send Telegram Audit.
9. Publish to Threads (@braderdin360 via Backblaze B2 Signed Storage) + Send Telegram Audit.
10. Record Video IDs (Redis 30-Day TTL), Caption Memory & Vector Embeddings.
"""

import os
import sys
import requests
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

# Import Modules
from src.pexels_ai_persona import pexels_ai, detect_reel_time_slot
from src.pexels_keyword_engine import get_fresh_pexels_reel_keyword
from src.pexels_reel_bot import fetch_and_filter_pexels_videos, render_stitched_reel_video, upload_reel_to_facebook
from src.pexels_reel_bot_instagram import instagram_reel_bot
from src.pexels_reel_bot_threads import threads_reel_bot
from src.instagram_audit import send_instagram_audit_to_telegram
from src.pexels_redis_db import (
    get_reel_story_memories,
    save_reel_story_memory,
    mark_pexels_video_posted,
)
from src.pexels_vector_db import (
    is_similar_reel_story_posted,
    mark_reel_story_vector_posted,
)


def upload_video_to_facebook_feed(page_id: str, page_token: str, video_path: str, caption: str):
    """Fallback memuat naik video terus ke Facebook Page Feed jika FB Reels terhad/gagal."""
    if not page_id or not page_token or not os.path.exists(video_path):
        return False, {"error": "Parameter tidak lengkap atau fail video tidak dijumpai"}

    url = f"https://graph-video.facebook.com/v26.0/{page_id}/videos"
    payload = {
        "description": caption,
        "access_token": page_token,
    }

    try:
        with open(video_path, "rb") as video_file:
            files = {"source": (os.path.basename(video_path), video_file, "video/mp4")}
            res = requests.post(url, data=payload, files=files, timeout=60)

        data = res.json()
        if res.status_code in [200, 201] and "id" in data:
            return True, {"id": data["id"]}
        else:
            err_msg = data.get("error", {}).get("message", res.text)
            return False, {"error": err_msg}
    except Exception as e:
        return False, {"error": str(e)}


def run_pexels_reel_video_job():
    print("\n" + "=" * 70)
    print("🎬 [START] ENJIN PEMPOSAN VIDEO REELS (RENDER DAHULU ➔ AYAT AI ➔ POST)")
    print("=" * 70)

    # 1. Baca Konfigurasi Persekitaran
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

    fb_page_id = os.getenv("FACEBOOK_PAGE_ID", "").strip() or os.getenv("META_PAGE_ID", "").strip()
    fb_page_token = (
        os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN", "").strip()
        or os.getenv("FB_PAGE_ACCESS_TOKEN", "").strip()
        or os.getenv("META_PAGE_ACCESS_TOKEN", "").strip()
    )

    music_dir = PROJECT_ROOT / "assets" / "music"

    # 2. Kesan Slot Masa & Mood Hari
    slot_id, slot_desc, day_mood, _ = detect_reel_time_slot()
    print(f"\n⏰ [SLOT MASA]: {slot_desc}")
    print(f"🎭 [MOOD HARI]: {day_mood}")

    # 3. Baca Bank Ingatan Cerita Terkini dari Redis
    print("\n🧠 [STEP 1] Membaca Bank Ingatan Reels Terkini dari Upstash Redis...")
    previous_memories = get_reel_story_memories(redis_url, redis_token, limit=5)
    print(f"  ✅ {len(previous_memories)} ingatan Reels lepas berjaya dimuatkan.")

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

    # 5. Tarik 20 Video Pexels (1 API Call) & Tapis Muka + Penjara 30-Hari Redis
    print("\n🌐 [STEP 3] Menghantar 1 API Call ke Pexels untuk 20 video vertikal (9:16)...")
    selected_videos, _ = fetch_and_filter_pexels_videos(
        api_key=pexels_key,
        redis_url=redis_url,
        redis_token=redis_token,
        query=query_keyword,
        needed_count=3,
        batch_size=20,
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
    print(f"\n✍️ [STEP 5] [AI JANA AYAT] Menjana penceritaan Reels berjiwa (Visual: '{query_keyword}', Muzik: '{music_audit_label}', Durasi: {video_duration}s)...")
    caption_text = pexels_ai.generate_reel_caption(
        topic_keyword=query_keyword,
        music_info=music_info,
        video_duration=video_duration,
        previous_memories=previous_memories,
    )

    # 8. Semak Keserupaan Kapsyen di Vector DB (Window 5 Hari / Cosine >= 0.85)
    if is_similar_reel_story_posted(vector_url, vector_token, caption_text):
        print("⚠️ [PEXELS REEL VECTOR] Topik kapsyen serupa dikesan (< 5 hari lepas). Menjana alternatif...")
        caption_text = pexels_ai.generate_reel_caption(
            topic_keyword=query_keyword,
            music_info=music_info,
            video_duration=video_duration,
            previous_memories=previous_memories,
        )

    print(f"\n✅ [KAPSYEN AI REELS FINAL ({len(caption_text)} aksara)]:\n{caption_text}\n")

    fb_success = False
    ig_success = False
    threads_success = False

    try:
        # 9. Terbitkan ke Facebook Reels (Fallback ke Facebook Feed jika gagal/limit)
        print("🚀 [STEP 6] Memuat naik ke Facebook Reels...")
        fb_ok, res_fb = upload_reel_to_facebook(
            page_id=fb_page_id,
            page_token=fb_page_token,
            video_path=rendered_video_path,
            caption=caption_text,
        )
        if fb_ok:
            fb_success = True
            print("  ✅ Berjaya dipos ke Facebook Reels!")
        else:
            print(f"  ⚠️ [FB REEL SKIP/FAILED] {res_fb.get('error')}")
            print("  🔄 [FALLBACK] Mencuba muat naik video terus ke Facebook Page Feed...")
            fb_feed_ok, res_feed = upload_video_to_facebook_feed(
                page_id=fb_page_id,
                page_token=fb_page_token,
                video_path=rendered_video_path,
                caption=caption_text,
            )
            if fb_feed_ok:
                fb_success = True
                print(f"  ✅ Berjaya dipos ke Facebook Feed! (ID: {res_feed.get('id')})")
            else:
                print(f"  ❌ [FB FEED FAILED] {res_feed.get('error')}")

        # 10. Terbitkan ke Instagram Reels (@braderdin360) + Audit Telegram
        if instagram_reel_bot.is_configured():
            print("\n📸 [STEP 7] Memuat naik ke Instagram Reels (@braderdin360)...")
            ig_ok, res_ig = instagram_reel_bot.upload_reel_to_instagram(
                video_path=rendered_video_path,
                caption=caption_text,
            )

            if ig_ok:
                ig_success = True
                ig_permalink = res_ig.get("permalink", "")
                print(f"  ✅ Berjaya dipos ke Instagram Reels! Pautan: {ig_permalink}")

                if tg_token and tg_chat_id:
                    print("  🔍 Menghantar salinan audit Instagram Reel ke Telegram...")
                    send_instagram_audit_to_telegram(
                        token=tg_token,
                        chat_id=tg_chat_id,
                        caption=caption_text,
                        image_url="",
                        permalink=ig_permalink,
                        post_type=f"Pexels Reel ({query_keyword}) | Audio: {music_audit_label}",
                    )
            else:
                print(f"  ⚠️ [IG REEL FAILED] {res_ig.get('error')}")

        # 11. Terbitkan ke Threads Video Feed (@braderdin360 via Backblaze B2) + Audit Telegram
        if threads_reel_bot.is_configured():
            print("\n🧵 [STEP 8] Memuat naik Video ke Threads Feed (@braderdin360 via B2)...")
            th_ok, res_th = threads_reel_bot.upload_video_to_threads(
                video_path=rendered_video_path,
                caption=caption_text,
            )

            if th_ok:
                threads_success = True
                th_permalink = res_th.get("permalink", "")
                print(f"  ✅ Berjaya dipos ke Threads Video! Pautan: {th_permalink}")

                if tg_token and tg_chat_id:
                    print("  🔍 Menghantar salinan audit Threads Video ke Telegram...")
                    send_instagram_audit_to_telegram(
                        token=tg_token,
                        chat_id=tg_chat_id,
                        caption=caption_text,
                        image_url="",
                        permalink=th_permalink,
                        post_type=f"Threads Video ({query_keyword}) | Audio: {music_audit_label}",
                    )
            else:
                print(f"  ⚠️ [THREADS VIDEO FAILED] {res_th.get('error')}")

        # 12. Rekod Status jika Sekurang-kurangnya 1 Platform Berjaya
        if fb_success or ig_success or threads_success:
            print("\n💾 [STEP 9] Merekodkan status & ingatan ke pangkalan data...")

            # Kunci 3 Video ID ke Penjara 30 Hari Redis
            for vid_id in video_ids:
                mark_pexels_video_posted(redis_url, redis_token, vid_id)

            # Simpan Kapsyen ke Bank Ingatan Redis (10 Terkini)
            save_reel_story_memory(redis_url, redis_token, caption_text, max_memories=10)

            # Simpan Vector Embedding Kapsyen ke Vector DB (Window 5 Hari)
            primary_story_id = f"{video_ids[0]}_{query_keyword.replace(' ', '_')}"
            mark_reel_story_vector_posted(vector_url, vector_token, primary_story_id, caption_text)

            print("\n🎉 [SUCCESS] Seluruh aliran Video (Render Dahulu ➔ Ayat AI ➔ Multi-Post) selesai dengan jayanya!\n")
        else:
            print("\n❌ [FAILED] Video tidak berjaya dimuat naik ke mana-mana platform.\n")

    finally:
        # Bersihkan fail video sementara tempatan
        if os.path.exists(rendered_video_path):
            try:
                os.remove(rendered_video_path)
            except Exception:
                pass


if __name__ == "__main__":
    run_pexels_reel_video_job()