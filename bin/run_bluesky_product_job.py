#!/usr/bin/env python3
"""
Master Execution Runner for Bluesky Affiliate Product Posts (Link Card Embed)
Sembang PC & Tech Ecosystem (100% Dynamic Keys & Native AT-Protocol)
Execution Flow:
1. Load unused affiliate products from Supabase Cloud.
2. Filter candidates against Bluesky Redis (21-Day Cooldown) & Validate Image URLs.
3. AI Persona generates compact micro-blogging review (< 270 chars).
4. Semantic similarity check via Bluesky Vector DB (7-Day Window / Cosine >= 0.80) with auto-retry.
5. Publish External Link Card Embed to Bluesky Feed via AT Protocol.
6. Send rich audit notification with permalink & details to Telegram.
7. Record Product ID to Redis (21-Day TTL), Vector DB, and mark status in Supabase.
"""

import os
import re
import sys
import random
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

# Import Local Modules from src
from src.supabase_db import fetch_unused_links, mark_link_as_used, get_supabase_config
from src.bluesky_bot import bluesky_bot
from src.bluesky_ai_persona import bluesky_ai
from src.bluesky_audit import send_bluesky_audit_to_telegram
from src.bluesky_redis_db import bluesky_redis
from src.bluesky_vector_db import bluesky_vector


def clean_image_url(url: str) -> str:
    """Memperbetulkan extension bertindih seperti .jpg.jpg atau .png.png."""
    if not url:
        return ""
    cleaned = re.sub(r"(\.(jpg|jpeg|png|webp))\.\2$", r"\1", url, flags=re.I)
    cleaned = re.sub(r"(\.(jpg|jpeg|png|webp))\1$", r"\1", cleaned, flags=re.I)
    return cleaned


def is_image_url_valid(url: str) -> bool:
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
    """Cadangan kecemasan jika pautan unused kosong di Supabase."""
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


def run_bluesky_product_posting_job():
    print("\n" + "=" * 70)
    print("🦋 [START] ENJIN PEMPOSAN PRODUK AFFILIATE BLUESKY (CARD EMBED)")
    print("=" * 70)

    # 1. Semak Konfigurasi Bot
    if not bluesky_bot.is_configured():
        print("❌ [ABORT] Kunci BLUESKY_HANDLE atau BLUESKY_APP_PASSWORD tiada di .env.local.")
        return

    tg_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    tg_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    # 2. Ambil Calon Produk dari Supabase
    print("\n📦 [STEP 1] Membaca katalog produk dari Supabase Cloud...")
    ok, candidate_list, err_msg = fetch_unused_links(limit=100)

    if not ok or not candidate_list:
        print("  ⚠️ Tiada produk status_used=false. Mengambil senarai keseluruhan produk...")
        candidate_list = fetch_all_links_fallback()

    if not candidate_list:
        print("❌ [ABORT] Tiada produk dijumpai di dalam pangkalan data Supabase.")
        return

    print(f"  ✅ Diterima {len(candidate_list)} calon produk dari Supabase.")

    random.shuffle(candidate_list)
    selected_product = None

    # 3. Tapisan Anti-Duplikasi Redis (21 Hari) & Pra-Sahkan Imej
    print("\n🔍 [STEP 2] Menyemak tapisan penjarakan 21 hari Redis & kualiti gambar...")
    for item in candidate_list:
        p_id = str(item.get("product_id") or item.get("id") or "").strip()
        title = str(item.get("title") or item.get("product_name") or "").strip()
        aff_link = str(item.get("affiliate_link") or item.get("promo_short_link") or "").strip()
        raw_img_url = str(item.get("image_url") or item.get("picture_url") or "").strip()

        img_url = clean_image_url(raw_img_url)

        if not p_id or not title or not aff_link or not img_url:
            continue

        # A. Semak Penjara 21 Hari Redis Bluesky
        if bluesky_redis.is_product_posted(product_id=p_id, title=title):
            print(f"  ⏭️ [REDIS SKIP] ID {p_id} ('{title[:30]}...') pernah disiarkan ke Bluesky < 21 hari lepas.")
            continue

        # B. Semak Kesahan Gambar Thumbnail
        if not is_image_url_valid(img_url):
            print(f"  ⏭️ [IMAGE BROKEN SKIP] ID {p_id} Gambar tidak dapat diakses (404/Rosak). Langkau.")
            continue

        selected_product = {
            "product_id": p_id,
            "title": title,
            "affiliate_link": aff_link,
            "image_url": img_url,
            "category": item.get("category", "Gajet & Komputer"),
            "price": item.get("price", ""),
            "features": item.get("features", item.get("description", "")),
        }
        break

    if not selected_product:
        print("⚠️ Semua calon produk berada dalam tempoh bertenang Redis atau gambar tidak sah. Dibatalkan.")
        return

    p_id = selected_product["product_id"]
    title = selected_product["title"]
    aff_link = selected_product["affiliate_link"]
    img_url = selected_product["image_url"]
    price = selected_product.get("price", "")

    print(f"\n🎯 [CALON PRODUK TERPILIH]:")
    print(f"   ID    : {p_id}")
    print(f"   Tajuk : {title}")
    print(f"   Harga : RM {price if price else 'Promosi'}")
    print(f"   Link  : {aff_link}")
    print(f"   Imej  : {img_url}")

    # 4. Jana Kapsyen AI Persona Khusus Bluesky (< 270 Aksara)
    print("\n✍️ [STEP 3] Menjana kapsyen mikro-blog AI Persona Brader Din...")
    caption_text = bluesky_ai.generate_affiliate_post(selected_product)

    # 5. Semak Keserupaan Semantik di Vector DB (Window 7 Hari / Ambang >= 0.80)
    if bluesky_vector.is_similar(text=caption_text, category="affiliate"):
        print("⚠️ [BLUESKY VECTOR] Ayat ulasan mirip dikesan (< 7 hari lepas). Menjana alternatif...")
        caption_text = bluesky_ai.generate_affiliate_post(selected_product)

    print(f"\n✅ [KAPSYEN AI BLUESKY FINAL ({len(caption_text)} aksara)]:\n{caption_text}\n")

    # 6. Terbitkan ke Bluesky Menggunakan Kad Pautan Luar (External Link Card Embed)
    print("🚀 [STEP 4] Menerbitkan Kad Pautan Affiliate ke Bluesky...")
    card_title = f"{title[:75]} | Tawaran Rasmi"
    card_desc = f"Dapatkan aksesori komputer & gajet berkualiti pada harga promosi. Klik pautan untuk info lanjut!"

    bsky_ok, res_bsky = bluesky_bot.post_link_card(
        text=caption_text,
        link_url=aff_link,
        title=card_title,
        description=card_desc,
        thumb_image_url=img_url,
    )

    if not bsky_ok:
        print(f"❌ [BLUESKY POST FAILED] Ralat: {res_bsky.get('error')}")
        return

    permalink = res_bsky.get("permalink", "")
    print(f"  🎉 [BLUESKY SUCCESS] Hantaran berjaya diterbitkan! Pautan: {permalink}")

    # 7. Hantar Salinan Audit ke Telegram
    if tg_token and tg_chat_id:
        print("\n🔍 [STEP 5] Menghantar salinan audit ke Telegram...")
        send_bluesky_audit_to_telegram(
            token=tg_token,
            chat_id=tg_chat_id,
            caption=caption_text,
            permalink=permalink,
            post_type="Bluesky: Racun Gajet (Card Embed)",
            image_url=img_url,
            affiliate_link=aff_link,
        )

    # 8. Rekod Status & Ingatan ke Pangkalan Data
    print("\n💾 [STEP 6] Merekodkan status penjarakan & memori...")
    # A. Kunci Product ID ke Redis (21 Hari)
    bluesky_redis.mark_product_posted(product_id=p_id, title=title)
    print("  ✅ Product ID dikunci di Upstash Redis (TTL 21 Hari).")

    # B. Simpan Kapsyen ke Bank Ingatan Redis (10 Terkini)
    bluesky_redis.save_memory(caption=caption_text, category="affiliate", max_memories=10)

    # C. Simpan Embedding ke Vector DB (Window 7 Hari)
    bluesky_vector.mark_posted(doc_id=p_id, text=caption_text, category="affiliate")

    # D. Kemas kini status_used di Supabase
    sb_ok, sb_msg = mark_link_as_used(p_id)
    print(f"  ✅ Supabase: {sb_msg}")

    print("\n🎉 [SUCCESS] Seluruh aliran pemposan produk Bluesky selesai dengan jayanya!\n")


if __name__ == "__main__":
    run_bluesky_product_posting_job()