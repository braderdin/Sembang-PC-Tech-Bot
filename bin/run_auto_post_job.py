import os
import re
import sys
import random
import requests
from dotenv import load_dotenv

# Memastikan laluan akar projek dimasukkan ke dalam sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Memuatkan persekitaran tempatan secara dinamik daripada .env.local (jika wujud)
env_local_path = os.path.join(PROJECT_ROOT, ".env.local")
if os.path.exists(env_local_path):
    load_dotenv(dotenv_path=env_local_path)
else:
    load_dotenv()

# Import modul tempatan dari src
from src.supabase_db import fetch_unused_links, mark_link_as_used, get_supabase_config
from src.redis_db import is_product_posted, mark_product_posted
from src.vector_db import is_similar_product_posted, mark_vector_posted
from src.ai_persona import generate_caption
from src.telegram_bot import send_photo_to_telegram
from src.facebook_bot import send_to_facebook_page
from src.facebook_reel_bot import send_to_facebook_reel
from src.threads_bot import send_to_threads
from src.threads_ai_persona import generate_threads_affiliate_caption
from src.threads_token_manager import get_active_threads_token

# Import Modul Khas Instagram & Audit Telegram
from src.instagram_bot import instagram_bot
from src.instagram_ai_persona import instagram_ai
from src.instagram_redis import instagram_redis
from src.instagram_audit import send_instagram_audit_to_telegram


def clean_image_url(url):
    """Memperbetulkan extension bertindih seperti .jpg.jpg atau .png.png."""
    if not url:
        return ""
    cleaned = re.sub(r"(\.(jpg|jpeg|png|webp))\.\2$", r"\1", url, flags=re.I)
    cleaned = re.sub(r"(\.(jpg|jpeg|png|webp))\1$", r"\1", cleaned, flags=re.I)
    return cleaned


def is_image_url_valid(url):
    """Memastikan URL gambar sah, wujud, dan boleh dimuat turun (Status HTTP 200)."""
    if not url:
        return False
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        res = requests.get(url, headers=headers, timeout=10)
        return res.status_code == 200 and len(res.content) > 500
    except Exception:
        return False


def fetch_all_links_fallback():
    """Cadangan kecemasan jika pautan unused kosong."""
    supabase_url, api_key, err = get_supabase_config()
    if err or not supabase_url:
        return []

    endpoint = f"{supabase_url}/rest/v1/affiliate_links?select=*&order=created_at.desc&limit=100"
    headers = {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    try:
        res = requests.get(endpoint, headers=headers, timeout=15)
        if res.status_code == 200:
            records = res.json()
            return records if isinstance(records, list) else []
    except Exception as e:
        print(f"⚠️ [SUPABASE FALLBACK WARN] {e}")
    return []


def run_auto_posting_job():
    print("\n" + "=" * 70)
    print("🤖 [START] ENJIN PEMPOSAN AUTOMATIK SOCIAL MEDIA (TG, FB, REELS, THREADS & IG)")
    print("=" * 70)

    # Membaca semua tetapan secara dinamik dari persekitaran
    base_url = os.getenv("OPENROUTER_BASE_URL", "").strip()
    model = os.getenv("OPENROUTER_MODEL", "").strip()
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()

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

    print("\n📦 [STEP 1] Membaca pautan dari Supabase Cloud...")
    ok, candidate_list, err_msg = fetch_unused_links(limit=100)

    if not ok or not candidate_list:
        print("⚠️ Tiada pautan status_used=false. Membaca senarai pautan keseluruhan dari Supabase...")
        candidate_list = fetch_all_links_fallback()

    if not candidate_list:
        print("❌ [ABORT] Tiada produk dijumpai di dalam Supabase DB.")
        return

    print(f"✅ Berjaya menarik {len(candidate_list)} produk calon dari Supabase.")

    random.shuffle(candidate_list)
    selected_product = None

    print("\n🔍 [STEP 2] Menyemak syarat penjarakan & pra-sahkan gambar...")
    for item in candidate_list:
        p_id = str(item.get("product_id") or item.get("id") or "").strip()
        title = str(item.get("title") or item.get("product_name") or "").strip()
        aff_link = str(item.get("affiliate_link") or item.get("promo_short_link") or "").strip()
        raw_img_url = str(item.get("image_url") or item.get("picture_url") or "").strip()

        img_url = clean_image_url(raw_img_url)

        if not p_id or not title or not aff_link or not img_url:
            continue

        # A. Semak Upstash Redis (Exact Match 15 Hari)
        if is_product_posted(redis_url, redis_token, p_id, title):
            print(f"  ⏭️ [REDIS SKIP] ID {p_id} ('{title[:30]}...') pernah dipos dalam tempoh 15 hari.")
            continue

        # B. Semak Instagram Redis Khusus
        if instagram_redis.is_product_posted(p_id):
            print(f"  ⏭️ [IG REDIS SKIP] ID {p_id} pernah dipos ke Instagram.")
            continue

        # C. Semak Upstash Vector DB (Semantic Similarity 2 Hari)
        if is_similar_product_posted(vector_url, vector_token, title):
            print(f"  ⏭️ [VECTOR SKIP] Tajuk '{title[:30]}...' serupa dengan produk dipos < 48 jam lepas.")
            continue

        # D. Semak Kesahan Gambar
        if not is_image_url_valid(img_url):
            print(f"  ⏭️ [IMAGE BROKEN SKIP] ID {p_id} Gambar tidak dapat diakses (404/Rosak). Langkau.")
            continue

        selected_product = {
            "product_id": p_id,
            "title": title,
            "affiliate_link": aff_link,
            "image_url": img_url,
            "category": item.get("category", ""),
            "price": item.get("price", ""),
            "features": item.get("features", item.get("description", "")),
        }
        break

    if not selected_product:
        print("⚠️ Semua calon produk masih dalam tempoh bertenang atau gambar tidak sah. Pemposan dibatalkan.")
        return

    p_id = selected_product["product_id"]
    title = selected_product["title"]
    aff_link = selected_product["affiliate_link"]
    img_url = selected_product["image_url"]

    print(f"\n🎯 [CALON TERPILIH] ID: {p_id}")
    print(f"   Tajuk : {title}")
    print(f"   Gambar: {img_url}")
    print(f"   Link  : {aff_link}")

    # 3. JANA KAPSYEN PENCERITAAN AI PERSONA TECH SPECIALIST
    print("\n✍️ [STEP 3] Menjana kapsyen penceritaan AI Tech Specialist...")
    ai_ok, shared_caption = generate_caption(
        base_url=base_url,
        model=model,
        api_key=api_key,
        product_title=title,
        product_desc=title,
    )

    if not ai_ok or not shared_caption:
        shared_caption = f"Korang yang tengah nak upgrade setup, tengok {title} ni. Memang ngam dan berbaloi sangat!"

    print(f"✅ [KAPSYEN AI BERJAYA DIJANA]:\n{shared_caption}\n")

    tg_success = False
    fb_success = False
    reel_success = False
    threads_success = False
    ig_success = False

    # 4. PROSES TELEGRAM CHANNEL
    if tg_token and tg_chat_id:
        print("✈️ [STEP 4] Pos ke Telegram Channel...")
        sent_tg_ok, res_tg = send_photo_to_telegram(
            token=tg_token,
            chat_id=tg_chat_id,
            caption=shared_caption,
            image_url=img_url,
            affiliate_link=aff_link,
        )
        if sent_tg_ok:
            print("  ✅ Berjaya dipos ke Telegram Channel!")
            tg_success = True
        else:
            print(f"  ❌ Gagal pos ke Telegram: {res_tg}")

    # 5. PROSES FACEBOOK PAGE FEED
    if fb_page_id and fb_page_token:
        print("\n📘 [STEP 5] Pos ke Facebook Page Feed...")
        sent_fb_ok, res_fb = send_to_facebook_page(
            page_id=fb_page_id,
            page_token=fb_page_token,
            caption=shared_caption,
            image_url=img_url,
            affiliate_link=aff_link,
        )
        if sent_fb_ok:
            print(f"  ✅ Berjaya dipos ke Facebook Page Feed! (Post ID: {res_fb.get('post_id')})")
            fb_success = True
        else:
            print(f"  ❌ Gagal pos ke Facebook Page Feed: {res_fb}")

    # 6. PROSES FACEBOOK REELS
    if fb_page_id and fb_page_token:
        print("\n🎬 [STEP 6] Pos ke Facebook Reels...")
        sent_reel_ok, res_reel = send_to_facebook_reel(
            page_id=fb_page_id,
            page_token=fb_page_token,
            caption=shared_caption,
            image_url=img_url,
            affiliate_link=aff_link,
        )
        if sent_reel_ok:
            print(f"  ✅ Berjaya dipos ke Facebook Reels! (Video ID: {res_reel.get('video_id')})")
            reel_success = True
        else:
            print(f"  ❌ Gagal pos ke Facebook Reels: {res_reel}")

    # 7. PROSES THREADS
    if threads_user_id and threads_token:
        print("\n🧵 [STEP 7] Pos ke Threads...")
        threads_custom_caption = generate_threads_affiliate_caption(
            base_url=base_url,
            model=model,
            api_key=api_key,
            product_title=title,
            product_desc=title,
        )
        sent_threads_ok, res_threads = send_to_threads(
            user_id=threads_user_id,
            access_token=threads_token,
            caption=threads_custom_caption,
            image_url=img_url,
            affiliate_link=aff_link,
        )
        if sent_threads_ok:
            print(f"  ✅ Berjaya dipos ke Threads! (Post ID: {res_threads.get('thread_post_id')})")
            threads_success = True
        else:
            print(f"  ❌ Gagal pos ke Threads: {res_threads}")

    # 8. PROSES INSTAGRAM FEED + AUDIT NOTIFICATION KE TELEGRAM
    if instagram_bot.is_configured():
        print("\n📸 [STEP 8] Pos ke Instagram Feed (@braderdin360)...")
        ig_caption = instagram_ai.generate_affiliate_caption(selected_product)
        res_ig = instagram_bot.post_photo(
            image_url=img_url,
            caption=ig_caption,
            product_id=p_id,
            post_type="affiliate",
        )

        if res_ig.get("success"):
            ig_permalink = res_ig.get("permalink", "")
            print(f"  ✅ Berjaya dipos ke Instagram! Pautan: {ig_permalink}")
            ig_success = True

            # Hantar kad audit ke Telegram peribadi/channel
            if tg_token and tg_chat_id:
                print("  🔍 Menghantar salinan audit Instagram ke Telegram...")
                send_instagram_audit_to_telegram(
                    token=tg_token,
                    chat_id=tg_chat_id,
                    caption=ig_caption,
                    image_url=img_url,
                    permalink=ig_permalink,
                    post_type="Affiliate Racun Gajet",
                )
        else:
            print(f"  ❌ Gagal pos ke Instagram: {res_ig.get('error')}")

    # 9. REKOD STATUS KE PANGKALAN DATA JIKA SEKURANG-KURANGNYA 1 PLATFORM BERJAYA
    if tg_success or fb_success or reel_success or threads_success or ig_success:
        print("\n💾 [STEP 9] Merekodkan status pemposan ke pangkalan data...")

        if mark_product_posted(redis_url, redis_token, p_id, title):
            print("  ✅ Rekod direkodkan di Upstash Redis (TTL 15 Hari).")

        if mark_vector_posted(vector_url, vector_token, p_id, title):
            print("  ✅ Rekod embedding disimpan di Upstash Vector DB (Window 2 Hari).")

        sb_ok, sb_msg = mark_link_as_used(p_id)
        print(f"  ✅ Supabase: {sb_msg}")

        print("\n🎉 [SUCCESS] Seluruh aliran pemposan automatik selesai dengan jayanya!\n")
    else:
        print("\n❌ Pemposan tidak berjaya dilaksanakan di mana-mana platform.")


if __name__ == "__main__":
    run_auto_posting_job()