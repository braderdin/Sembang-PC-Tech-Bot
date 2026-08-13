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
    generate_lifestyle_theme_keyword,
    generate_lifestyle_story
)
from src.lifestyle_image_fetcher import (
    fetch_similar_theme_images,
    mark_image_id_posted
)
from src.lifestyle_reel_bot import send_lifestyle_to_facebook_reel
from src.telegram_bot import send_photo_to_telegram
from src.facebook_bot import send_to_facebook_page
from src.redis_db import mark_product_posted
from src.vector_db import is_similar_product_posted, mark_vector_posted

def run_lifestyle_posting_job():
    print("\n" + "=" * 70)
    print("📖 [START] ENJIN PEMPOSAN CERITA HARIAN & LIFESTYLE REEL (AI TECH SPECIALIST)")
    print("=" * 70)

    # Pembacaan daripada Pembolehubah Persekitaran (.env.local / GitHub Secrets)
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
        os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN", "").strip() or
        os.getenv("FB_PAGE_ACCESS_TOKEN", "").strip() or
        os.getenv("META_PAGE_ACCESS_TOKEN", "").strip()
    )

    # 1. KESAN SLOT MASA & JANA KATA KUNCI INDUK
    slot_id, slot_desc = detect_current_time_slot()
    print(f"\n⏰ [SLOT MASA] Waktu Semasa: {slot_desc}")

    print("\n💡 [STEP 1] AI Persona menjana 1 Kata Kunci Tema Induk Unsplash...")
    query_keyword = generate_lifestyle_theme_keyword(base_url, model, api_key)
    print(f"🎯 [KATA KUNCI INDUK]: '{query_keyword}'")

    # 2. TARIK 3 GAMBAR BERTEMA SERUPA DARI UNSPLASH (1 API CALL)
    print("\n🌐 [STEP 2] Menarik 3 gambar bertema serupa dari Unsplash API (1 Request)...")
    image_candidates = fetch_similar_theme_images(
        access_key=unsplash_key,
        query_keyword=query_keyword,
        redis_url=redis_url,
        redis_token=redis_token,
        count=3
    )

    if not image_candidates:
        print("❌ [ABORT] Tiada gambar yang sah dijumpai dari Unsplash.")
        return

    print(f"✅ Berjaya mengumpul {len(image_candidates)} gambar Unsplash bertema serupa.")

    image_urls = [img["image_url"] for img in image_candidates]
    image_descs = [img["description"] for img in image_candidates]
    photo_ids = [img["photo_id"] for img in image_candidates]

    for idx, img in enumerate(image_candidates, 1):
        print(f"   {idx}. Photo ID: {img['photo_id']} | Desc: {img['description'][:60]}...")

    # 3. AI TECH SPECIALIST JANA PENCERITAAN
    print("\n✍️ [STEP 3] AI Tech Specialist menjana cerita Facebook berdasarkan 3 gambar...")
    ai_ok, story_text = generate_lifestyle_story(
        base_url=base_url,
        model=model,
        api_key=api_key,
        image_descriptions_list=image_descs
    )

    if not ai_ok or not story_text:
        story_text = "Salam kawan-kawan! Kopi pagi dah siap, setup meja dah kemas. Semoga hari ini penuh dengan ilham dan produktiviti untuk kita semua!"

    print(f"\n✅ [KAPSYEN AI TECH SPECIALIST]:\n{story_text}\n")

    tg_success = False
    fb_feed_success = False
    fb_reel_success = False

    # 4. POS KE TELEGRAM CHANNEL (Guna Gambar Pertama)
    if tg_token and tg_chat_id:
        print("✈️ [STEP 4] Pos ke Telegram Channel...")
        sent_tg, res_tg = send_photo_to_telegram(
            token=tg_token,
            chat_id=tg_chat_id,
            caption=story_text,
            image_url=image_urls[0],
            affiliate_link=""
        )
        if sent_tg:
            print("  ✅ Berjaya dipos ke Telegram Channel!")
            tg_success = True
        else:
            print(f"  ❌ Gagal pos ke Telegram: {res_tg}")

    # 5. POS KE FACEBOOK PAGE FEED (Guna Gambar Pertama)
    if fb_page_id and fb_page_token:
        print("\n📘 [STEP 5] Pos ke Facebook Page Feed...")
        sent_fb, res_fb = send_to_facebook_page(
            page_id=fb_page_id,
            page_token=fb_page_token,
            caption=story_text,
            image_url=image_urls[0],
            affiliate_link=""
        )
        if sent_fb:
            print(f"  ✅ Berjaya dipos ke Facebook Page Feed! (Post ID: {res_fb.get('post_id')})")
            fb_feed_success = True
        else:
            print(f"  ❌ Gagal pos ke Facebook Page Feed: {res_fb}")

    # 6. POS KE FACEBOOK REELS (Slideshow 3 Gambar + Lagu Meta)
    if fb_page_id and fb_page_token:
        print("\n🎬 [STEP 6] Pos ke Facebook Reels (Slideshow 3 Gambar + Lagu Meta)...")
        sent_reel, res_reel = send_lifestyle_to_facebook_reel(
            page_id=fb_page_id,
            page_token=fb_page_token,
            caption=story_text,
            image_urls=image_urls
        )
        if sent_reel:
            print(f"  ✅ Berjaya dipos ke Facebook Lifestyle Reels! (Video ID: {res_reel.get('video_id')})")
            fb_reel_success = True
        else:
            print(f"  ❌ Gagal pos ke Facebook Reels: {res_reel}")

    # 7. REKOD STATUS KE REDIS & VECTOR DB
    if tg_success or fb_feed_success or fb_reel_success:
        print("\n💾 [STEP 7] Merekodkan status pemposan ke pangkalan data...")
        for pid in photo_ids:
            mark_image_id_posted(redis_url, redis_token, pid)
        print(f"  ✅ {len(photo_ids)} Unsplash Photo ID direkodkan di Upstash Redis (TTL 30 Hari).")

        unique_id = f"lifestyle_{photo_ids[0]}"
        if redis_url and redis_token:
            mark_product_posted(redis_url, redis_token, unique_id, story_text)
            print("  ✅ Rekod cerita direkodkan di Upstash Redis.")

        if vector_url and vector_token:
            mark_vector_posted(vector_url, vector_token, unique_id, story_text)
            print("  ✅ Rekod embedding disimpan di Upstash Vector DB.")

        print("\n🎉 [SUCCESS] Seluruh aliran pemposan cerita lifestyle selesai dengan jayanya!\n")

if __name__ == "__main__":
    run_lifestyle_posting_job()