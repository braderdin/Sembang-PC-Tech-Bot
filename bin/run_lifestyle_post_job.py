import os
import sys
import random
from dotenv import load_dotenv

# Memastikan laluan akar projek dimasukkan ke dalam sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Memuatkan persekitaran tempatan daripada .env.local (jika wujud)
env_local_path = os.path.join(PROJECT_ROOT, ".env.local")
if os.path.exists(env_local_path):
    load_dotenv(dotenv_path=env_local_path)
else:
    load_dotenv()

# Import modul tempatan dari folder src
from src.lifestyle_ai_persona import (
    detect_current_time_slot,
    generate_lifestyle_story,
)
from src.lifestyle_keyword_engine import get_fresh_lifestyle_keyword  # 🌟 ENJIN BARU
from src.lifestyle_image_fetcher import (
    fetch_similar_theme_images,
    mark_image_id_posted,
)
from src.lifestyle_reel_bot import send_lifestyle_to_facebook_reel
from src.telegram_bot import send_photo_to_telegram
from src.facebook_bot import send_to_facebook_page
from src.threads_bot import send_to_threads
from lazada_thread_Ai_persona import generate_threads_lifestyle_caption
from src.threads_token_manager import get_active_threads_token

# Import Modul Pangkalan Data KHAS Lifestyle
from src.lifestyle_redis_db import (
    get_lifestyle_story_memories,
    save_lifestyle_story_memory,
)
from src.lifestyle_vector_db import (
    is_similar_lifestyle_story_posted,
    mark_lifestyle_vector_posted,
)

# Import Modul Khas Instagram & Audit Telegram
from src.instagram_bot import instagram_bot
from lazada_instagram_Ai_persona import instagram_ai
from src.instagram_audit import send_instagram_audit_to_telegram


def run_lifestyle_posting_job():
    print("\n" + "=" * 70)
    print("📖 [START] ENJIN PEMPOSAN CERITA HARIAN & LIFESTYLE (ALL PLATFORMS + IG)")
    print("=" * 70)

    # Pembacaan daripada Pembolehubah Persekitaran (100% Dinamik)
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

    fb_page_id = os.getenv("FACEBOOK_PAGE_ID", "").strip() or os.getenv("META_PAGE_ID", "").strip()
    fb_page_token = (
        os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN", "").strip()
        or os.getenv("FB_PAGE_ACCESS_TOKEN", "").strip()
        or os.getenv("META_PAGE_ACCESS_TOKEN", "").strip()
    )

    threads_user_id = os.getenv("THREADS_USER_ID", "").strip()
    raw_threads_token = os.getenv("THREADS_ACCESS_TOKEN", "").strip()
    threads_token = get_active_threads_token(redis_url, redis_token, raw_threads_token)

    # 1. KESAN SLOT MASA & MOOD HARI
    slot_id, slot_desc, day_mood, temp_val = detect_current_time_slot()
    print(f"\n⏰ [SLOT MASA]: {slot_desc}")
    print(f"🎭 [MOOD HARI]: {day_mood}")

    # 2. BACA BANK INGATAN REDIS (MEMORIES)
    print("\n🧠 [STEP 1] Membaca Bank Ingatan Cerita Terkini dari Upstash Redis...")
    previous_memories = get_lifestyle_story_memories(redis_url, redis_token, limit=5)
    print(f"  ✅ {len(previous_memories)} ingatan cerita lepas berjaya dimuatkan.")

    # 3. JANA & TAPIS 10 KATA KUNCI DENGAN ENJIN DEDIKASI
    print("\n💡 [STEP 2] Enjin Kata Kunci meneliti dan menapis kata kunci segar...")
    query_keyword = get_fresh_lifestyle_keyword(
        base_url=base_url,
        model=model,
        api_key=api_key,
        redis_url=redis_url,
        redis_token=redis_token,
        vector_url=vector_url,
        vector_token=vector_token
    )

    # 4. TARIK 3 GAMBAR BERTEMA SERUPA DARI UNSPLASH
    print("🌐 [STEP 3] Menarik 3 gambar bertema serupa dari Unsplash API...")
    image_candidates = fetch_similar_theme_images(
        access_key=unsplash_key,
        query_keyword=query_keyword,
        redis_url=redis_url,
        redis_token=redis_token,
        count=3,
    )

    if not image_candidates:
        print("❌ [ABORT] Tiada gambar yang sah dijumpai dari Unsplash.")
        return

    image_urls = [img["image_url"] for img in image_candidates]
    image_descs = [img["description"] for img in image_candidates]
    photo_ids = [img["photo_id"] for img in image_candidates]

    # 5. AI TECH SPECIALIST JANA PENCERITAAN (DENGAN INGATAN & DESKRIPSI GAMBAR)
    print("\n✍️ [STEP 4] AI Tech Specialist menjana cerita bersumberkan deskripsi gambar...")
    ai_ok, story_text = generate_lifestyle_story(
        base_url=base_url,
        model=model,
        api_key=api_key,
        image_descriptions_list=image_descs,
        previous_memories=previous_memories,
    )

    if not ai_ok or not story_text:
        story_text = (
            "Salam kawan-kawan! Selesai urusan seharian di hadapan skrin. "
            "Bila meja kerja kemas dan susun atur teratur, rasa tenang sikit nak santai rehatkan fikiran. "
            "Korang punya setup meja dah sedia untuk aktiviti santai malam ni?"
        )

    # 6. SEMAK KESERUPAAN CERITA DI VECTOR DB (ANTI-DUPLIKASI CERITA 48 JAM)
    if is_similar_lifestyle_story_posted(vector_url, vector_token, story_text):
        print("⚠️ [LIFESTYLE VECTOR] Topik cerita ini dikesan serupa dengan cerita < 48 jam lepas. Menjana alternatif...")
        ai_ok, story_text = generate_lifestyle_story(
            base_url=base_url,
            model=model,
            api_key=api_key,
            image_descriptions_list=image_descs,
            previous_memories=previous_memories,
        )

    print(f"\n✅ [KAPSYEN AI TECH SPECIALIST]:\n{story_text}\n")

    tg_success = False
    fb_feed_success = False
    fb_reel_success = False
    threads_success = False
    ig_success = False

    # 7. POS KE TELEGRAM CHANNEL
    if tg_token and tg_chat_id:
        print("✈️ [STEP 5] Pos ke Telegram Channel...")
        tg_caption = story_text[:980] + "..." if len(story_text) > 1000 else story_text
        sent_tg, res_tg = send_photo_to_telegram(
            token=tg_token,
            chat_id=tg_chat_id,
            caption=tg_caption,
            image_url=image_urls[0],
            affiliate_link="",
        )
        if sent_tg:
            print("  ✅ Berjaya dipos ke Telegram Channel!")
            tg_success = True

    # 8. POS KE FACEBOOK PAGE FEED (ALBUM 3 GAMBAR)
    if fb_page_id and fb_page_token:
        print("\n📘 [STEP 6] Pos ke Facebook Page Feed (3 Gambar Album)...")
        sent_fb, res_fb = send_to_facebook_page(
            page_id=fb_page_id,
            page_token=fb_page_token,
            caption=story_text,
            image_urls=image_urls,
            affiliate_link="",
        )
        if sent_fb:
            print(f"  ✅ Berjaya dipos ke Facebook Page Feed! (Post ID: {res_fb.get('post_id')})")
            fb_feed_success = True

    # 9. POS KE FACEBOOK REELS
    if fb_page_id and fb_page_token:
        print("\n🎬 [STEP 7] Pos ke Facebook Reels...")
        sent_reel, res_reel = send_lifestyle_to_facebook_reel(
            page_id=fb_page_id,
            page_token=fb_page_token,
            caption=story_text,
            image_urls=image_urls,
        )
        if sent_reel:
            print(f"  ✅ Berjaya dipos ke Facebook Lifestyle Reels! (Video ID: {res_reel.get('video_id')})")
            fb_reel_success = True

    # 10. POS KE THREADS
    if threads_user_id and threads_token:
        print("\n🧵 [STEP 8] Pos ke Threads...")
        threads_custom_caption = generate_threads_lifestyle_caption(
            base_url=base_url,
            model=model,
            api_key=api_key,
            image_description=image_descs[0],
            slot_desc=slot_desc,
            day_mood=day_mood,
        )
        sent_threads, res_threads = send_to_threads(
            user_id=threads_user_id,
            access_token=threads_token,
            caption=threads_custom_caption,
            image_url=image_urls[0],
            affiliate_link="",
        )
        if sent_threads:
            print(f"  ✅ Berjaya dipos ke Threads! (Post ID: {res_threads.get('thread_post_id')})")
            threads_success = True

    # 11. POS KE INSTAGRAM (CAROUSEL / SINGLE PHOTO) + AUDIT TELEGRAM
    if instagram_bot.is_configured():
        print("\n📸 [STEP 9] Pos ke Instagram Feed (@braderdin360)...")
        ig_lifestyle_caption = instagram_ai.generate_lifestyle_caption(
            topic=query_keyword,
            key_points=f"Mood: {day_mood} | Waktu: {slot_desc}",
        )

        if len(image_urls) >= 2:
            res_ig = instagram_bot.post_carousel(
                image_urls=image_urls,
                caption=ig_lifestyle_caption,
            )
        else:
            res_ig = instagram_bot.post_photo(
                image_url=image_urls[0],
                caption=ig_lifestyle_caption,
                post_type="lifestyle",
            )

        if res_ig.get("success"):
            ig_permalink = res_ig.get("permalink", "")
            print(f"  ✅ Berjaya dipos ke Instagram Lifestyle! Pautan: {ig_permalink}")
            ig_success = True

            if tg_token and tg_chat_id:
                print("  🔍 Menghantar salinan audit Instagram ke Telegram...")
                send_instagram_audit_to_telegram(
                    token=tg_token,
                    chat_id=tg_chat_id,
                    caption=ig_lifestyle_caption,
                    image_url=image_urls[0],
                    permalink=ig_permalink,
                    post_type=f"Lifestyle ({query_keyword})",
                )
        else:
            print(f"  ❌ Gagal pos ke Instagram: {res_ig.get('error')}")

    # 12. REKOD STATUS KE REDIS MEMORY & VECTOR DB
    if tg_success or fb_feed_success or fb_reel_success or threads_success or ig_success:
        print("\n💾 [STEP 10] Merekodkan status & ingatan ke pangkalan data...")

        for pid in photo_ids:
            mark_image_id_posted(redis_url, redis_token, pid)

        save_lifestyle_story_memory(redis_url, redis_token, story_text, max_memories=10)

        story_id = photo_ids[0]
        mark_lifestyle_vector_posted(vector_url, vector_token, story_id, story_text)

        print("\n🎉 [SUCCESS] Seluruh aliran pemposan cerita lifestyle selesai dengan jayanya!\n")


if __name__ == "__main__":
    run_lifestyle_posting_job()