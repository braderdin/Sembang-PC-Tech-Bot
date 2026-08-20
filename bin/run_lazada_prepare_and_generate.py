#!/usr/bin/env python3
"""
Lazada Feed Auto-Poster: Step 1 & Step 2
Pipeline Runner:
1. Fetch candidates from Supabase Cloud (Table: 'affiliate_links').
2. Filter through Redis (30 Days TTL) & Vector DB (80% Similarity / 3 Days).
3. Validate Image URL CDN accessibility.
4. Fallback up to 5 batches if all candidates in current batch are filtered out.
5. Generate AI Captions for 4 platforms (FB, Threads, IG, Bluesky).
6. Save structured payload to 'temp/lazada_payload.json'.
"""

import os
import re
import sys
import json
import requests
from datetime import datetime, timezone
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
from src.lazada_redis_filter import is_lazada_product_posted
from src.lazada_vector_filter import is_similar_lazada_product_posted
from src.lazada_fb_Ai_persona import lazada_fb_ai
from src.lazada_thread_Ai_persona import lazada_threads_ai
from src.lazada_instagram_Ai_persona import lazada_instagram_ai
from src.lazada_bluesky_Ai_persona import lazada_bluesky_ai

TEMP_DIR = PROJECT_ROOT / "temp"
PAYLOAD_FILE = TEMP_DIR / "lazada_payload.json"


def ensure_temp_dir():
    """Memastikan direktori temp/ wujud."""
    TEMP_DIR.mkdir(parents=True, exist_ok=True)


def clean_image_url(url: str) -> str:
    """
    Memperbetulkan extension bertindih atau melengkapkan format imej
    secara automatik untuk keserasian Meta Graph API.
    """
    if not url:
        return ""
    cleaned = re.sub(r"(\.(jpg|jpeg|png|webp))\.\2$", r"\1", str(url).strip(), flags=re.I)
    cleaned = re.sub(r"(\.(jpg|jpeg|png|webp))\1$", r"\1", cleaned, flags=re.I)

    # Tambah format standard jika format URL CDN Lazada tiada extension di hujung
    if "slatic.net" in cleaned and not any(cleaned.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp"]):
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


def get_supabase_config():
    """Membaca konfigurasi sambungan Supabase."""
    supabase_url = os.getenv("SUPABASE_URL", "").strip() or os.getenv("NEXT_PUBLIC_SUPABASE_URL", "").strip()
    service_role_key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip() or 
        os.getenv("SUPABASE_SECRET_KEY", "").strip() or 
        os.getenv("SUPABASE_ANON_KEY", "").strip()
    )
    return supabase_url.rstrip("/"), service_role_key


def fetch_lazada_candidates(limit: int = 300, offset: int = 0):
    """
    Menarik senarai calon produk Lazada (status_used = false) daripada Supabase.
    Jika pautan belum guna habis, menarik senarai pautan secara keseluruhan.
    """
    supabase_url, api_key = get_supabase_config()
    if not supabase_url or not api_key:
        return False, [], "Konfigurasi Supabase tidak lengkap dalam persekitaran."

    headers = {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # Percubaan 1: Tarik produk yang belum digunakan (status_used = false)
    endpoint = f"{supabase_url}/rest/v1/affiliate_links?status_used=eq.false&order=created_at.desc&limit={limit}&offset={offset}"
    try:
        res = requests.get(endpoint, headers=headers, timeout=15)
        if res.status_code == 200:
            records = res.json()
            if isinstance(records, list) and len(records) > 0:
                return True, records, f"Berjaya menarik {len(records)} calon produk Lazada (Unused)."
    except Exception as e:
        print(f"⚠️ [SUPABASE FETCH WARN] {e}")

    # Percubaan 2: Fallback tarik keseluruhan rekod jika pautan unused kosong
    endpoint_all = f"{supabase_url}/rest/v1/affiliate_links?order=created_at.desc&limit={limit}&offset={offset}"
    try:
        res_all = requests.get(endpoint_all, headers=headers, timeout=15)
        if res_all.status_code == 200:
            records_all = res_all.json()
            if isinstance(records_all, list) and len(records_all) > 0:
                return True, records_all, f"Berjaya menarik {len(records_all)} calon produk Lazada (Pool Keseluruhan)."
    except Exception as e:
        return False, [], f"Ralat sambungan Supabase: {e}"

    return False, [], "Tiada rekod produk Lazada dijumpai di Supabase."


def select_candidate_product():
    """
    Menjalankan proses pemilihan calon produk Lazada:
    - Menarik kelompok data dari Supabase.
    - Menyemak Redis (30 Hari TTL), Vector DB (72 Jam / 80% kemiripan), dan kesahan gambar CDN.
    - Melakukan sehingga 5x percubaan kelompok (fallback pagination offset).
    """
    MAX_FALLBACK_ATTEMPTS = 5
    BATCH_SIZE = 300

    print("\n🔍 [STEP 1] Memulakan Pemilihan Calon Produk Lazada...")

    for attempt in range(MAX_FALLBACK_ATTEMPTS):
        offset = attempt * BATCH_SIZE
        print(f"\n📦 [KELOMPOK {attempt + 1}/{MAX_FALLBACK_ATTEMPTS}] Menarik 300 produk (Offset: {offset})...")

        ok, candidates, msg = fetch_lazada_candidates(limit=BATCH_SIZE, offset=offset)
        if not ok or not candidates:
            print(f"⚠️ {msg}")
            if attempt == 0:
                print("🔄 Mencuba semula dengan semakan kelompok seterusnya...")
            continue

        print(f"✅ {msg}")

        # Tapis calon satu persatu
        for item in candidates:
            p_id = str(item.get("product_id") or item.get("id") or "").strip()
            title = str(item.get("title") or item.get("product_name") or "").strip()
            brand = str(item.get("brand") or item.get("keyword") or "Lazada Preferred").strip()
            price = item.get("price", 0.0)
            category = str(item.get("category") or "Aksesori PC & Gajet").strip()
            raw_pic = str(item.get("image_url") or item.get("picture_url") or item.get("b2_image_url") or "").strip()
            aff_link = str(item.get("affiliate_link") or item.get("promo_short_link") or "").strip()

            pic_url = clean_image_url(raw_pic)

            if not p_id or not title or not aff_link or not pic_url:
                continue

            # A. Semak Upstash Redis (Kunci Sama: 30 Hari TTL)
            if is_lazada_product_posted(p_id):
                print(f"  ⏭️ [REDIS SKIP] ID {p_id} ('{title[:25]}...') pernah dipos dalam tempoh 30 hari.")
                continue

            # B. Semak Upstash Vector DB (Kemiripan Makna >= 80%: 72 Jam)
            if is_similar_lazada_product_posted(title):
                print(f"  ⏭️ [VECTOR SKIP] Tajuk '{title[:25]}...' serupa (>=80%) dengan hantaran < 72 jam lepas.")
                continue

            # C. Semak Akses Imej CDN
            if not is_image_url_valid(pic_url):
                print(f"  ⏭️ [IMAGE BROKEN SKIP] ID {p_id} Gambar tidak dapat diakses (404/Rosak).")
                continue

            # Calon Lulus Semua Tapisan!
            try:
                clean_price = float(price) if price else 0.0
            except Exception:
                clean_price = 0.0

            selected = {
                "product_id": p_id,
                "product_name": title,
                "title": title,
                "brand": brand,
                "price": clean_price,
                "category": category,
                "picture_url": pic_url,
                "image_url": pic_url,
                "affiliate_link": aff_link,
            }

            print(f"\n🎯 [CALON TERPILIH]:")
            print(f"   🆔 ID       : {p_id}")
            print(f"   📦 Tajuk    : {title}")
            print(f"   🏷️ Kategori : {category}")
            print(f"   💰 Harga    : RM {clean_price:.2f}" if clean_price > 0 else "   💰 Harga    : Tawaran Berbaloi")
            print(f"   🔗 Pautan   : {aff_link}")
            print(f"   🖼️ Gambar   : {pic_url}")
            return selected

    return None


def run_preparation_and_generation():
    ensure_temp_dir()

    # 1. Pilih Calon Produk
    selected_product = select_candidate_product()

    if not selected_product:
        print("\n❌ [ABORT] Tiada calon produk Lazada lulus tapisan selepas 5 kelompok. Aliran ditamatkan.")
        error_payload = {
            "status": "failed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reason": "Semua calon produk dalam tempoh bertenang (Redis/Vector) atau CDN gambar tidak sah."
        }
        with open(TEMP_DIR / "lazada_fallback_debug.json", "w", encoding="utf-8") as f:
            json.dump(error_payload, f, indent=2)
        sys.exit(1)

    # 2. STEP 2: JANA AYAT AI PERSONA BAGI KESEMUA 4 PLATFORM
    print("\n" + "=" * 70)
    print("🤖 [STEP 2] MENJANA KAPSYEN AI PERSONA MENGIKUT PLATFORM (LAZADA)")
    print("=" * 70)

    # A. Facebook Persona
    print("\n🔵 Menjana Kapsyen Facebook Feed (500 - 700 Aksara)...")
    _, fb_caption = lazada_fb_ai.generate_caption(selected_product)
    print("--- [PREVIEW FACEBOOK CAPTION] ---")
    print(fb_caption)

    # B. Threads Persona
    print("\n🧵 Menjana Kapsyen Threads Feed (Hard Limit <= 480 Aksara)...")
    _, threads_caption = lazada_threads_ai.generate_caption(selected_product)
    print("--- [PREVIEW THREADS CAPTION] ---")
    print(threads_caption)

    # C. Instagram & Pinterest Persona
    print("\n📸 Menjana Kapsyen Instagram & Pinterest Feed (350 - 450 Aksara)...")
    _, ig_caption = lazada_instagram_ai.generate_caption(selected_product)
    print("--- [PREVIEW INSTAGRAM CAPTION] ---")
    print(ig_caption)

    # D. Bluesky Persona
    print("\n🦋 Menjana Kapsyen Bluesky Feed (Hard Limit <= 295 Aksara)...")
    _, bluesky_caption = lazada_bluesky_ai.generate_caption(selected_product)
    print("--- [PREVIEW BLUESKY CAPTION] ---")
    print(bluesky_caption)

    # 3. BINA STRUKTUR PAYLOAD SEMENTARA (temp/lazada_payload.json)
    payload_data = {
        "product_id": selected_product["product_id"],
        "product_name": selected_product["product_name"],
        "title": selected_product["title"],
        "brand": selected_product["brand"],
        "price": selected_product["price"],
        "category": selected_product["category"],
        "picture_url": selected_product["picture_url"],
        "image_url": selected_product["image_url"],
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
    print("🎉 [STEP 1 & STEP 2 SELESAI] Bersedia untuk proses pemposan modular Lazada!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    run_preparation_and_generation()