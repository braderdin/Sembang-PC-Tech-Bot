#!/usr/bin/env python3
"""
Shopee Feed Auto-Poster: Step 1 & Step 2
Pipeline Runner:
1. Fetch 300 candidates from Supabase (Sorted by Sales & Status Used).
2. Filter through Redis (30 Days TTL) & Vector DB (80% Similarity / 3 Days).
3. Validate Image URL CDN accessibility.
4. Fallback up to 5 batches if all candidates in current batch are filtered out.
5. Generate AI Captions for 4 platforms (FB, Threads, IG, Bluesky).
6. Save structured payload to 'temp/shopee_payload.json'.
"""

import os
import re
import sys
import json
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path
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
from src.shopee_supabase import fetch_shopee_candidates
from src.shopee_redis_filter import is_shopee_product_posted
from src.shopee_vector_filter import is_similar_shopee_product_posted
from src.shopee_fb_Ai_persona import shopee_fb_ai
from src.shopee_thread_Ai_persona import shopee_threads_ai
from src.shopee_instagram_Ai_persona import shopee_instagram_ai
from src.shopee_bluesky_Ai_persona import shopee_bluesky_ai

TEMP_DIR = PROJECT_ROOT / "temp"
PAYLOAD_FILE = TEMP_DIR / "shopee_payload.json"


def ensure_temp_dir():
    """Memastikan direktori temp/ wujud."""
    TEMP_DIR.mkdir(parents=True, exist_ok=True)


def clean_image_url(url: str) -> str:
    """
    Memperbetulkan extension bertindih atau menambah sambungan .jpg
    secara automatik bagi format CDN Shopee untuk keserasian Meta Graph API.
    """
    if not url:
        return ""
    cleaned = re.sub(r"(\.(jpg|jpeg|png|webp))\.\2$", r"\1", str(url).strip(), flags=re.I)
    cleaned = re.sub(r"(\.(jpg|jpeg|png|webp))\1$", r"\1", cleaned, flags=re.I)

    # Jika URL Shopee sah tetapi tiada extension di hujung, Meta Graph API memerlukan .jpg
    if "susercontent.com" in cleaned and not any(cleaned.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp"]):
        cleaned = f"{cleaned}.jpg"

    return cleaned


def is_image_url_valid(url: str) -> bool:
    """Memastikan URL gambar sah dan boleh dimuat turun daripada CDN (HTTP 200)."""
    if not url or not url.startswith("http"):
        return False
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        res = requests.get(url, headers=headers, timeout=10)
        return res.status_code == 200 and len(res.content) > 500
    except Exception:
        return False


def select_candidate_product():
    """
    Menjalankan proses pemilihan calon produk Shopee:
    - Menarik kelompok 300 data dari Supabase.
    - Menyemak Redis & Vector DB serta kesahan gambar.
    - Melakukan sehingga 5x percubaan kelompok (fallback pagination offset).
    """
    MAX_FALLBACK_ATTEMPTS = 5
    BATCH_SIZE = 300

    print("\n🔍 [STEP 1] Memulakan Pemilihan Calon Produk Shopee...")

    for attempt in range(MAX_FALLBACK_ATTEMPTS):
        offset = attempt * BATCH_SIZE
        print(f"\n📦 [KELOMPOK {attempt + 1}/{MAX_FALLBACK_ATTEMPTS}] Menarik 300 produk (Offset: {offset})...")
        
        ok, candidates, msg = fetch_shopee_candidates(limit=BATCH_SIZE, offset=offset)
        if not ok or not candidates:
            print(f"⚠️ {msg}")
            if attempt == 0:
                print("🔄 Mencuba semula dengan semakan status...")
            continue

        print(f"✅ {msg}")

        # Tapis calon satu persatu
        for item in candidates:
            p_id = str(item.get("shopee_product_id") or "").strip()
            name = str(item.get("shopee_product_name") or "").strip()
            brand = str(item.get("shopee_brand") or "Shopee Preferred").strip()
            price = item.get("shopee_price", 0.0)
            category = str(item.get("shopee_category") or "Aksesori PC & Gajet").strip()
            raw_pic = str(item.get("shopee_picture_url") or "").strip()
            aff_link = str(item.get("shopee_affiliate_link") or "").strip()

            pic_url = clean_image_url(raw_pic)

            if not p_id or not name or not aff_link or not pic_url:
                continue

            # A. Semak Upstash Redis (Kunci Sama: 30 Hari TTL)
            if is_shopee_product_posted(p_id):
                print(f"  ⏭️ [REDIS SKIP] ID {p_id} ('{name[:25]}...') pernah dipos dalam tempoh 30 hari.")
                continue

            # B. Semak Upstash Vector DB (Kemiripan Makna >= 80%: 3 Hari)
            if is_similar_shopee_product_posted(name):
                print(f"  ⏭️ [VECTOR SKIP] Tajuk '{name[:25]}...' serupa (>=80%) dengan hantaran < 72 jam lepas.")
                continue

            # C. Semak Akses Imej CDN
            if not is_image_url_valid(pic_url):
                print(f"  ⏭️ [IMAGE BROKEN SKIP] ID {p_id} Gambar tidak dapat diakses (404/Rosak).")
                continue

            # Calon Lulus Semua Tapisan!
            try:
                clean_price = float(price)
            except Exception:
                clean_price = 0.0

            selected = {
                "product_id": p_id,
                "product_name": name,
                "brand": brand,
                "price": clean_price,
                "category": category,
                "picture_url": pic_url,
                "affiliate_link": aff_link,
            }

            print(f"\n🎯 [CALON TERPILIH]:")
            print(f"   🆔 ID       : {p_id}")
            print(f"   📦 Tajuk    : {name}")
            print(f"   🏷️ Kategori : {category}")
            print(f"   💰 Harga    : RM {clean_price:.2f}")
            print(f"   🔗 Pautan   : {aff_link}")
            print(f"   🖼️ Gambar   : {pic_url}")
            return selected

    return None


def run_preparation_and_generation():
    ensure_temp_dir()

    # 1. Pilih Produk Calon
    selected_product = select_candidate_product()

    if not selected_product:
        print("\n❌ [ABORT] Tiada calon produk lulus tapisan selepas 5 kelompok. Aliran ditamatkan.")
        # Simpan rekod ralat sementara untuk tujuan audit
        error_payload = {
            "status": "failed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reason": "Semua calon produk dalam tempoh bertenang (Redis/Vector) atau CDN gambar tidak sah."
        }
        with open(TEMP_DIR / "shopee_fallback_debug.json", "w", encoding="utf-8") as f:
            json.dump(error_payload, f, indent=2)
        sys.exit(1)

    # 2. STEP 2: JANA AYAT AI PERSONA BAGI KESEMUA 4 PLATFORM
    print("\n" + "=" * 70)
    print("🤖 [STEP 2] MENJANA KAPSYEN AI PERSONA MENGIKUT PLATFORM")
    print("=" * 70)

    # A. Facebook Persona
    print("\n🔵 Menjana Kapsyen Facebook Feed (500 - 700 Aksara)...")
    _, fb_caption = shopee_fb_ai.generate_caption(selected_product)
    print("--- [PREVIEW FACEBOOK CAPTION] ---")
    print(fb_caption)

    # B. Threads Persona
    print("\n🧵 Menjana Kapsyen Threads Feed (Hard Limit <= 480 Aksara)...")
    _, threads_caption = shopee_threads_ai.generate_caption(selected_product)
    print("--- [PREVIEW THREADS CAPTION] ---")
    print(threads_caption)

    # C. Instagram & Pinterest Persona
    print("\n📸 Menjana Kapsyen Instagram & Pinterest Feed (350 - 450 Aksara)...")
    _, ig_caption = shopee_instagram_ai.generate_caption(selected_product)
    print("--- [PREVIEW INSTAGRAM CAPTION] ---")
    print(ig_caption)

    # D. Bluesky Persona
    print("\n🦋 Menjana Kapsyen Bluesky Feed (Hard Limit <= 295 Aksara)...")
    _, bluesky_caption = shopee_bluesky_ai.generate_caption(selected_product)
    print("--- [PREVIEW BLUESKY CAPTION] ---")
    print(bluesky_caption)

    # 3. BINA STRUKTUR PAYLOAD SEMENTARA (temp/shopee_payload.json)
    payload_data = {
        "product_id": selected_product["product_id"],
        "product_name": selected_product["product_name"],
        "brand": selected_product["brand"],
        "price": selected_product["price"],
        "category": selected_product["category"],
        "picture_url": selected_product["picture_url"],
        "affiliate_link": selected_product["affiliate_link"],
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

    # 4. SIMPAN KE FAIL JSON SEMENTARA
    with open(PAYLOAD_FILE, "w", encoding="utf-8") as f:
        json.dump(payload_data, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    print(f"💾 [SAVED] Payload sementara berjaya dicipta di: {PAYLOAD_FILE}")
    print("🎉 [STEP 1 & STEP 2 SELESAI] Bersedia untuk proses pemposan modular!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    run_preparation_and_generation()