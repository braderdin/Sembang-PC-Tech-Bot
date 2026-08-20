#!/usr/bin/env python3
"""
Shopee Feed Auto-Poster: Step 1 & Step 2
Pipeline Runner:
1. Fetch candidates from Supabase (Sorted by Sales & Status Used).
2. Filter through Redis (30 Days TTL) & Vector DB (80% Similarity / 3 Days).
3. Validate Image URL CDN accessibility & Content-Type for Meta Graph API.
4. Fallback up to 5 batches if all candidates in current batch are filtered out.
5. Generate AI Captions for 4 platforms (FB, Threads, IG, Bluesky).
6. Save structured payload to 'temp/shopee_payload.json'.
"""

import os
import re
import sys
import json
import requests
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
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
    Membersihkan dan memformat URL imej CDN Shopee untuk keserasian optimum Meta Graph API.
    """
    if not url:
        return ""
    clean = str(url).strip()
    
    # Buang query parameters yang merosakkan URL imej
    clean = re.sub(r"\?.*$", "", clean)
    
    # Buang sambungan bertindih atau tidak standard
    clean = re.sub(r"(\.(jpg|jpeg|png|webp))\.\2$", r"\1", clean, flags=re.I)
    clean = re.sub(r"(\.(jpg|jpeg|png|webp))\1$", r"\1", clean, flags=re.I)
    clean = re.sub(r"(\.jpg|\.png)_webp$", r"\1", clean, flags=re.I)
    clean = re.sub(r"_tn$", "", clean)

    # Untuk Shopee CDN (susercontent.com), tambah .jpg jika tiada extension
    if "susercontent.com" in clean and not any(clean.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp"]):
        clean = f"{clean}.jpg"

    return clean


def is_image_url_valid(url: str) -> bool:
    """
    Memastikan URL gambar sah, boleh diakses (HTTP 200),
    dan mengembalikan Content-Type imej tulen tanpa sekatan bot Meta.
    """
    if not url or not url.startswith("http"):
        return False
    try:
        headers = {
            "User-Agent": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)"
        }
        res = requests.get(url, headers=headers, timeout=12)
        content_type = res.headers.get("Content-Type", "").lower()

        # Semak kod status HTTP 200, saiz fail minimum (> 500 bytes), dan jenis MIME imej sah
        is_status_ok = (res.status_code == 200)
        is_size_ok = (len(res.content) > 500)
        is_content_image = any(img_type in content_type for img_type in ["image/jpeg", "image/png", "image/webp", "image/jpg"]) or not content_type.startswith("text/")

        return is_status_ok and is_size_ok and is_content_image
    except Exception:
        return False


def resolve_best_shopee_image_url(raw_url: str) -> Optional[str]:
    """
    Mencari variasi URL CDN Shopee yang sah dan boleh dimuat turun oleh crawler Meta.
    """
    if not raw_url or not raw_url.startswith("http"):
        return None

    cleaned = clean_image_url(raw_url)
    variations = [cleaned]

    # Variasi tanpa .jpg dan dengan .jpg
    if cleaned.endswith(".jpg"):
        variations.append(cleaned[:-4])
    else:
        variations.append(f"{cleaned}.jpg")

    # Variasi domain gantian cf.shopee.com.my jika susercontent.com disekat
    if "susercontent.com/file/" in cleaned:
        hash_part = cleaned.split("susercontent.com/file/")[-1]
        variations.append(f"https://cf.shopee.com.my/file/{hash_part}")
        if not hash_part.endswith(".jpg"):
            variations.append(f"https://cf.shopee.com.my/file/{hash_part}.jpg")

    for v in variations:
        if is_image_url_valid(v):
            return v

    return None


def select_candidate_product():
    """
    Menjalankan proses pemilihan calon produk Shopee:
    - Menarik kelompok data dari Supabase.
    - Menyemak Redis & Vector DB serta kesahan gambar CDN.
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
            p_id = str(item.get("shopee_product_id") or item.get("product_id") or "").strip()
            name = str(item.get("shopee_product_name") or item.get("product_name") or "").strip()
            brand = str(item.get("shopee_brand") or item.get("brand") or "Shopee Preferred").strip()
            price = item.get("shopee_price", item.get("price", 0.0))
            category = str(item.get("shopee_category") or item.get("category") or "Aksesori PC & Gajet").strip()
            raw_pic = str(item.get("shopee_picture_url") or item.get("picture_url") or "").strip()
            aff_link = str(item.get("shopee_affiliate_link") or item.get("affiliate_link") or "").strip()

            if not p_id or not name or not aff_link or not raw_pic:
                continue

            # A. Semak Upstash Redis (Kunci Sama: 30 Hari TTL)
            if is_shopee_product_posted(p_id):
                print(f"  ⏭️ [REDIS SKIP] ID {p_id} ('{name[:25]}...') pernah dipos dalam tempoh 30 hari.")
                continue

            # B. Semak Upstash Vector DB (Kemiripan Makna >= 80%: 72 Jam)
            if is_similar_shopee_product_posted(name):
                print(f"  ⏭️ [VECTOR SKIP] Tajuk '{name[:25]}...' serupa (>=80%) dengan hantaran < 72 jam lepas.")
                continue

            # C. Semak dan Dapatkan Format Imej CDN Sah
            valid_pic_url = resolve_best_shopee_image_url(raw_pic)
            if not valid_pic_url:
                print(f"  ⏭️ [IMAGE BROKEN SKIP] ID {p_id} Gambar tidak dapat diakses (404/MIME bukan imej).")
                continue

            # Calon Lulus Semua Tapisan!
            try:
                clean_price = float(price) if price else 0.0
            except Exception:
                clean_price = 0.0

            selected = {
                "product_id": p_id,
                "shopee_product_id": p_id,
                "product_name": name,
                "shopee_product_name": name,
                "title": name,
                "brand": brand,
                "shopee_brand": brand,
                "price": clean_price,
                "shopee_price": clean_price,
                "category": category,
                "shopee_category": category,
                "picture_url": valid_pic_url,
                "image_url": valid_pic_url,
                "shopee_picture_url": valid_pic_url,
                "affiliate_link": aff_link,
                "shopee_affiliate_link": aff_link,
            }

            print(f"\n🎯 [CALON TERPILIH]:")
            print(f"   🆔 ID       : {p_id}")
            print(f"   📦 Tajuk    : {name}")
            print(f"   🏷️ Kategori : {category}")
            print(f"   💰 Harga    : RM {clean_price:.2f}" if clean_price > 0 else "   💰 Harga    : Tawaran Berbaloi")
            print(f"   🔗 Pautan   : {aff_link}")
            print(f"   🖼️ Gambar   : {valid_pic_url}")
            return selected

    return None


def run_preparation_and_generation():
    ensure_temp_dir()

    # 1. Pilih Produk Calon
    selected_product = select_candidate_product()

    if not selected_product:
        print("\n❌ [ABORT] Tiada calon produk Shopee lulus tapisan selepas 5 kelompok. Aliran ditamatkan.")
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
    print("🤖 [STEP 2] MENJANA KAPSYEN AI PERSONA MENGIKUT PLATFORM (SHOPEE)")
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
        "shopee_product_id": selected_product["shopee_product_id"],
        "product_name": selected_product["product_name"],
        "shopee_product_name": selected_product["shopee_product_name"],
        "title": selected_product["title"],
        "brand": selected_product["brand"],
        "shopee_brand": selected_product["shopee_brand"],
        "price": selected_product["price"],
        "shopee_price": selected_product["shopee_price"],
        "category": selected_product["category"],
        "shopee_category": selected_product["shopee_category"],
        "picture_url": selected_product["picture_url"],
        "image_url": selected_product["image_url"],
        "shopee_picture_url": selected_product["shopee_picture_url"],
        "affiliate_link": selected_product["affiliate_link"],
        "shopee_affiliate_link": selected_product["shopee_affiliate_link"],
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
    print("🎉 [STEP 1 & STEP 2 SELESAI] Bersedia untuk proses pemposan modular Shopee!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    run_preparation_and_generation()