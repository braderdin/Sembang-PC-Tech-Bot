#!/usr/bin/env python3
"""
Reddit Tech Storyteller Engine: Step 1 & Step 2 (Pipeline Runner)
Lokasi Fail: bin/run_reddit_prepare_and_generate.py

Ciri-ciri Penambahbaikan (Tuned):
1. Dinamik 100% (Sifar Hardcode Model): Mengutamakan pembacaan REDDIT_OPENROUTER_MODEL dan REDDIT_OPENROUTER_MODEL_FALLBACK sebelum fallback am OPENROUTER_MODEL.
2. Resolusi Imej Kalis Glitch: Menyalurkan model dinamik ke enjin resolusi imej hibrid tanpa sebarang teks hardcoded.
3. Penjanaan Kapsyen 4 Platform Berperingkat: Melaksanakan pacing sela masa (rate-limit pacing) bagi memastikan kuota percuma OpenRouter tidak terbeban.
4. Struktur Pertukaran Data JSON Bersih: Menyimpan seluruh hasil penapisan, imej, dan teks AI ke 'temp/reddit_payload.json'.
"""

import os
import sys
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# 1. Konfigurasi Laluan Projek & Environment
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Baca .env.local (tempatan) atau persekitaran GitHub Actions
env_local = PROJECT_ROOT / ".env.local"
if env_local.exists():
    load_dotenv(dotenv_path=env_local)
else:
    load_dotenv()

# 2. Import Modul Teras dari src/
from src.reddit_fetcher import fetch_all_reddit_candidates, get_current_myt_context
from src.reddit_redis_filter import is_reddit_post_processed
from src.reddit_vector_filter import is_similar_reddit_story_posted
from src.reddit_image_engine import resolve_reddit_story_image
from src.reddit_fb_Ai_persona import reddit_fb_ai
from src.reddit_thread_Ai_persona import reddit_threads_ai
from src.reddit_instagram_Ai_persona import reddit_instagram_ai
from src.reddit_bluesky_Ai_persona import reddit_bluesky_ai

TEMP_DIR = PROJECT_ROOT / "temp"
PAYLOAD_FILE = TEMP_DIR / "reddit_payload.json"


def ensure_temp_dir():
    """Memastikan direktori temp/ wujud."""
    TEMP_DIR.mkdir(parents=True, exist_ok=True)


def select_best_reddit_candidate() -> Optional[Dict[str, Any]]:
    """
    Menjalankan proses pemilihan dan penapisan calon pos Reddit:
    - Menarik calon pos daripada subreddit sasaran harian.
    - Menapis melalui Upstash Redis (ID Post) & Upstash Vector DB (Keserupaan Teks).
    - Mengesahkan atau mendapatkan imej yang sah (Reddit / Unsplash Anti-Face).
    """
    print("\n🔍 [STEP 1] Memulakan Pemilihan & Penapisan Calon Pos Reddit...")

    # Baca kunci konfigurasi secara dinamik tanpa nilai hardcoded
    base_url = (os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1").strip().rstrip("/")
    model = (
        os.getenv("REDDIT_OPENROUTER_MODEL", "").strip()
        or os.getenv("OPENROUTER_MODEL", "").strip()
    )
    model_fallback = (
        os.getenv("REDDIT_OPENROUTER_MODEL_FALLBACK", "").strip()
        or os.getenv("OPENROUTER_MODEL_FALLBACK", "").strip()
    )
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    unsplash_key = os.getenv("UNSPLASH_ACCESS_KEY", "").strip()

    redis_url = (os.getenv("UPSTASH_REDIS_REST_URL") or os.getenv("UPSTASH_REDIS_URL", "")).strip().rstrip("/")
    redis_token = (os.getenv("UPSTASH_REDIS_REST_TOKEN") or os.getenv("UPSTASH_API_KEY", "")).strip()

    ok_fetch, candidates, temporal_ctx, fetch_msg = fetch_all_reddit_candidates()
    if not ok_fetch or not candidates:
        print(f"❌ [FETCH ERROR] {fetch_msg}")
        return None

    print(f"✅ {fetch_msg}")
    print(f"🕒 Sesi Semasa: {temporal_ctx['slot_label']} -> {temporal_ctx['theme_name']}")
    print(f"📋 Mengimbas {len(candidates)} calon pos merentasi penapis keselamatan...\n")

    for idx, post in enumerate(candidates, 1):
        p_id = str(post.get("post_id", "")).strip()
        title = str(post.get("title", "")).strip()
        sub = str(post.get("subreddit", "")).strip()
        clean_text = str(post.get("cleaned_text", "")).strip()
        score = post.get("score", 0)

        if not p_id or not title:
            continue

        print(f"  🔍 [{idx}/{len(candidates)}] Menilai: r/{sub} - \"{title[:45]}...\" (ID: {p_id})")

        # A. Semak Penapis Upstash Redis (Exact Match ID - 30 Hari TTL)
        if is_reddit_post_processed(p_id):
            print(f"     ⏭️ [REDIS SKIP] Post ID '{p_id}' pernah dipos dalam tempoh 30 hari.")
            continue

        # B. Semak Penapis Upstash Vector DB (Kemiripan Semantik >= 80% / 72 Jam)
        semantic_text_sample = f"{title} {clean_text}"[:800]
        if is_similar_reddit_story_posted(semantic_text_sample):
            print(f"     ⏭️ [VECTOR SKIP] Topik pos ini mirip (>= 80%) dengan hantaran < 72 jam lepas.")
            continue

        # C. Resolusi Imej Hibrid (Reddit Direct atau Unsplash Fallback Anti-Face)
        print(f"     🖼️ Menyelesaikan imej visual untuk pos ini...")
        ok_img, img_data, img_msg = resolve_reddit_story_image(
            reddit_post=post,
            base_url=base_url,
            model=model,
            model_fallback=model_fallback,
            api_key=api_key,
            unsplash_key=unsplash_key,
            redis_url=redis_url,
            redis_token=redis_token
        )

        if not ok_img or not img_data.get("image_url"):
            print(f"     ⏭️ [IMAGE FAILED SKIP] {img_msg}")
            continue

        print(f"     ✅ [IMEJ DISAHKAN] Sumber: {img_data.get('source')} | URL: {img_data.get('image_url')}")

        # Calon Lulus Kesemua Tapisan!
        selected_story = {
            "post_id": p_id,
            "subreddit": sub,
            "title": title,
            "cleaned_text": clean_text,
            "author": post.get("author", "Anonymous"),
            "score": score,
            "permalink": post.get("permalink", ""),
            "picture_url": img_data.get("image_url"),
            "image_source": img_data.get("source"),
            "image_description": img_data.get("description", title),
            "temporal_context": temporal_ctx
        }

        print("\n" + "=" * 70)
        print(f"🎯 [CALON REDDIT TERPILIH]:")
        print(f"   🆔 Post ID   : {selected_story['post_id']}")
        print(f"   📌 Subreddit : r/{selected_story['subreddit']}")
        print(f"   📖 Tajuk     : {selected_story['title']}")
        print(f"   👍 Undian    : ~{selected_story['score']} Upvotes")
        print(f"   🖼️ Imej      : {selected_story['picture_url']} ({selected_story['image_source']})")
        print(f"   🔗 Pautan    : {selected_story['permalink']}")
        print("=" * 70 + "\n")

        return selected_story

    return None


def run_preparation_and_generation():
    ensure_temp_dir()

    # =========================================================================
    # STEP 1: PEMILIHAN & PENAPISAN CALON POS
    # =========================================================================
    selected_story = select_best_reddit_candidate()

    if not selected_story:
        print("\n❌ [ABORT] Tiada calon pos Reddit lulus tapisan keselamatan hari ini. Aliran ditamatkan.")
        error_payload = {
            "status": "failed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reason": "Semua calon Reddit berada dalam tempoh bertenang (Redis/Vector) atau tiada imej sah."
        }
        with open(TEMP_DIR / "reddit_fallback_debug.json", "w", encoding="utf-8") as f:
            json.dump(error_payload, f, indent=2)
        sys.exit(1)

    temporal_ctx = selected_story.get("temporal_context", get_current_myt_context())

    # =========================================================================
    # STEP 2: PENJANAAN KAPSYEN AI PERSONA MERENTAS 4 PLATFORM
    # =========================================================================
    print("\n" + "=" * 70)
    print("🤖 [STEP 2] MENJANA KAPSYEN AI PERSONA 'ABANG DIN' MENGIKUT PLATFORM")
    print("=" * 70)

    # A. Facebook Page Feed (500 - 750 Aksara)
    print("\n🔵 [1/4] Menjana Kapsyen Facebook Page Feed...")
    _, fb_caption = reddit_fb_ai.generate_caption(selected_story, temporal_ctx)
    print("--- [PREVIEW FACEBOOK STORY] ---")
    print(fb_caption)

    # Jeda masa keselamatan bagi mengelakkan had kadar (rate-limit pacing)
    time.sleep(3)

    # B. Meta Threads Feed (Had Siling <= 480 Aksara)
    print("\n🧵 [2/4] Menjana Kapsyen Meta Threads Feed...")
    _, threads_caption = reddit_threads_ai.generate_caption(selected_story, temporal_ctx)
    print("--- [PREVIEW THREADS STORY] ---")
    print(threads_caption)

    time.sleep(3)

    # C. Instagram Feed (500 - 750 Aksara)
    print("\n📸 [3/4] Menjana Kapsyen Instagram Feed...")
    _, ig_caption = reddit_instagram_ai.generate_caption(selected_story, temporal_ctx)
    print("--- [PREVIEW INSTAGRAM STORY] ---")
    print(ig_caption)

    time.sleep(3)

    # D. Bluesky Social Feed (Had Siling <= 295 Aksara)
    print("\n🦋 [4/4] Menjana Kapsyen Bluesky Social Feed...")
    _, bluesky_caption = reddit_bluesky_ai.generate_caption(selected_story, temporal_ctx)
    print("--- [PREVIEW BLUESKY STORY] ---")
    print(bluesky_caption)

    # =========================================================================
    # STEP 3: BINA DAN SIMPAN PAYLOAD SEMENTARA
    # =========================================================================
    payload_data = {
        "post_id": selected_story["post_id"],
        "subreddit": selected_story["subreddit"],
        "title": selected_story["title"],
        "cleaned_text": selected_story["cleaned_text"],
        "author": selected_story["author"],
        "score": selected_story["score"],
        "permalink": selected_story["permalink"],
        "picture_url": selected_story["picture_url"],
        "image_source": selected_story["image_source"],
        "image_description": selected_story["image_description"],
        "temporal_context": selected_story["temporal_context"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "ai_captions": {
            "facebook": fb_caption,
            "threads": threads_caption,
            "instagram": ig_caption,
            "bluesky": bluesky_caption
        },
        "post_results": {
            "facebook": {"status": "pending"},
            "threads": {"status": "pending"},
            "instagram": {"status": "pending"},
            "bluesky": {"status": "pending"}
        }
    }

    with open(PAYLOAD_FILE, "w", encoding="utf-8") as f:
        json.dump(payload_data, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    print(f"💾 [SAVED] Fail payload sementara berjaya dicipta di: {PAYLOAD_FILE}")
    print("🎉 [STEP 1 & STEP 2 SELESAI] Bersedia untuk proses pemposan modular media sosial!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    run_preparation_and_generation()