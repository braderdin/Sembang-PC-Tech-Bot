#!/usr/bin/env python3
"""
Bulk Import Engine for Affiliate Excel (.xlsx) to Supabase Database
100% Compatible with Existing Supabase Schema (affiliate_links)
Features:
- Smart Auto-Categorization (Tech, Furniture, Kitchen, Outdoor, Lifestyle)
- Strict Affiliate Link Verification
- Status Preservation (Maintains status_used=TRUE for previously posted products)
- Batch Upsert via REST API
"""

import os
import re
import sys
import glob
import warnings
import pandas as pd
import requests
from dotenv import load_dotenv

# Suppress openpyxl stylesheet warnings
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

# Set Project Root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Load environment variables (.env.local priority)
env_local = os.path.join(PROJECT_ROOT, ".env.local")
if os.path.exists(env_local):
    load_dotenv(dotenv_path=env_local)
else:
    load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip() 
    or os.getenv("SUPABASE_KEY", "").strip() 
    or os.getenv("SUPABASE_ANON_KEY", "").strip()
)


def auto_detect_category(title: str, brand: str = "") -> str:
    """
    Enjin Pengecaman Kategori Pintar Berdasarkan Kata Kunci Tajuk & Jenama.
    Menyokong pelbagai kategori semasa & fasa masa depan (Tech, Dapur, Pancing, Hobi).
    """
    text = f"{title} {brand}".lower()

    # 1. Kerusi Gaming & Ergonomik
    if any(k in text for k in ['chair', 'kerusi', 'office chair', 'gaming chair', 'ergonomic chair', 'reclining', 'mesh chair']):
        return "🪑 Kerusi Gaming & Ergonomik"

    # 2. Penyejuk & Kipas PC (AIO, Liquid Cooler, Fan, Radiator)
    if any(k in text for k in ['cooler', 'cooling', 'fan', 'aio', 'liquid cooler', 'water cooling', 'heatsink', 'radiator', 'thermalright', 'fantech polar', 'arctic liquid', 'cooler master']):
        return "🖥️ Penyejuk & Kipas PC"

    # 3. Komponen Utama PC (Motherboard, CPU, GPU, RAM, SSD, PSU, Case)
    if any(k in text for k in ['motherboard', 'mainboard', 'b760', 'b850', 'b650', 'b550', 'b450', 'am5', 'am4', 'lga 1700', 'lga 1851', 'ram ddr', 'ddr5', 'ddr4', 'ryzen', 'intel core', 'graphics card', 'rtx', 'gtx', 'gpu', 'power supply', 'psu', 'ssd', 'nvme', 'm.2', 'pc case', 'casing pc']):
        return "⚙️ Komponen & Perkakasan PC"

    # 4. Aksesori Gaming, Audio & Gajet Setup
    if any(k in text for k in ['keyboard', 'mouse', 'mousepad', 'desk mat', 'monitor', 'screen', 'stand', 'speaker', 'headset', 'earphone', 'headphone', 'microphone', 'mic', 'webcam', 'cable', 'charger', 'hub', 'docking', 'card reader', 'adapter', 'bluetooth', 'otg', 'power bank']):
        return "🎧 Aksesori Gaming & Audio"

    # 5. Peralatan Dapur & Rumah (Untuk Projek Masa Depan)
    if any(k in text for k in ['kitchen', 'dapur', 'pan', 'pot', 'cookware', 'blender', 'air fryer', 'knife', 'pisau', 'kuali', 'periuk', 'kettle', 'rak dapur', 'bekas makanan', 'vacuum']):
        return "🍳 Peralatan Dapur & Rumah"

    # 6. Hobi, Outdoor & Memancing (Untuk Projek Masa Depan)
    if any(k in text for k in ['fishing', 'pancing', 'joran', 'reel pancing', 'tackle', 'outdoor', 'camping', 'tent', 'backpack', 'beg travel', 'khemah', 'lampu suluh', 'hiking']):
        return "🎣 Hobi & Outdoor / Memancing"

    return "📦 Tawaran Gajet & Gaya Hidup"


def clean_image_url(url: str) -> str:
    """Membersihkan sambungan format gambar bertindih (.jpg.jpg / .png.png)."""
    if not url or pd.isna(url):
        return ""
    u = str(url).strip()
    u = re.sub(r"(\.(jpg|jpeg|png|webp))\.\2$", r"\1", u, flags=re.I)
    u = re.sub(r"(\.(jpg|jpeg|png|webp))\1$", r"\1", cleaned := u, flags=re.I)
    return cleaned


def extract_verified_affiliate_link(row) -> str:
    """
    [WAJIB] Memastikan hanya pautan affiliate rasmi berbayar yang diambil:
    1. promo_short_link (cth: https://s.lazada.com.my/s.ZdejVM?...)
    2. promo_link (cth: https://pages.lazada.com.my/...exlaz=...)
    """
    short_link = str(row.get("promo_short_link", "")).strip()
    if short_link and short_link.lower() != "nan" and "s.lazada.com.my" in short_link:
        return short_link

    promo_link = str(row.get("promo_link", "")).strip()
    if promo_link and promo_link.lower() != "nan" and ("exlaz=" in promo_link or "from_affiliate=1" in promo_link):
        return promo_link

    return ""


def bulk_import_to_supabase():
    print("\n" + "=" * 70)
    print("🚀 [START] ENJIN IMPORT PUKAL XLSX KE SUPABASE (STATUS-PRESERVED)")
    print("=" * 70)

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ [ERROR] SUPABASE_URL atau SUPABASE_SERVICE_ROLE_KEY tidak dijumpai dalam .env.local!")
        return

    folder_path = os.path.join(PROJECT_ROOT, "link_affiliate_xlsx")
    xlsx_files = sorted(glob.glob(os.path.join(folder_path, "*.xlsx")))

    if not xlsx_files:
        print(f"⚠️ Tiada fail .xlsx dijumpai di dalam folder: {folder_path}")
        return

    print(f"📂 Dijumpai {len(xlsx_files)} fail Excel dalam direktori...")

    all_records = []
    seen_ids = set()

    for file_path in xlsx_files:
        file_name = os.path.basename(file_path)
        try:
            df = pd.read_excel(file_path)
            valid_file_count = 0

            for _, row in df.iterrows():
                raw_id = row.get("item_id")
                if pd.isna(raw_id):
                    continue

                p_id = str(int(raw_id) if isinstance(raw_id, (int, float)) else raw_id).strip()
                if not p_id or p_id in seen_ids:
                    continue

                title = str(row.get("product_name", "")).strip()
                aff_link = extract_verified_affiliate_link(row)
                img_url = clean_image_url(row.get("picture_url", ""))

                if not title or not aff_link or not img_url:
                    continue

                # Nilai harga (Utamakan discounted_price jika wujud)
                raw_disc_price = row.get("discounted_price")
                raw_sale_price = row.get("sale_price")
                price = 0.0
                if not pd.isna(raw_disc_price):
                    price = float(raw_disc_price)
                elif not pd.isna(raw_sale_price):
                    price = float(raw_sale_price)

                # Kadar komisen
                comm_rate = str(row.get("maximum commission_rate", ">=2.5%")).strip()
                if comm_rate.lower() == "nan" or not comm_rate:
                    comm_rate = ">=2.5%"

                brand = str(row.get("brand", "No Brand")).strip()
                if brand.lower() == "nan":
                    brand = ""

                category = auto_detect_category(title, brand)

                # Format data sepadan 100% dengan skema Supabase
                record = {
                    "product_id": p_id,
                    "title": title,
                    "category": category,
                    "keyword": category,
                    "original_url": str(row.get("product_url", "")).strip(),
                    "affiliate_link": aff_link,
                    "image_url": img_url,
                    "price": price,
                    "commission_rate": comm_rate,
                    "status_used": False,
                }

                all_records.append(record)
                seen_ids.add(p_id)
                valid_file_count += 1

            print(f"  📄 {file_name} ➔ {valid_file_count} produk sah diekstrak.")
        except Exception as e:
            print(f"  ⚠️ Ralat membaca {file_name}: {e}")

    total_valid = len(all_records)
    print(f"\n📊 [JUMLAH KESELURUHAN]: {total_valid} produk unik diekstrak daripada fail Excel.")

    if total_valid == 0:
        print("⚠️ Tiada produk yang sah untuk disimpan.")
        return

    # Header REST API Supabase
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }

    # 🔍 Langkah Pengekalan Status: Dapatkan produk yang sedia ada berstatus TRUE di Supabase
    print("\n🔍 Memeriksa rekod sedia ada di Supabase untuk memelihara status 'TRUE'...")
    existing_used_ids = set()
    try:
        check_url = f"{SUPABASE_URL}/rest/v1/affiliate_links?select=product_id&status_used=eq.true"
        r_check = requests.get(check_url, headers=headers, timeout=20)
        if r_check.status_code == 200:
            existing_used_ids = {item["product_id"] for item in r_check.json() if "product_id" in item}
            print(f"  🛡️ {len(existing_used_ids)} produk berstatus TRUE ditemui. Status ini akan dikekalkan!")
        else:
            print(f"  ℹ️ Status semakan sedia ada: HTTP {r_check.status_code}")
    except Exception as e:
        print(f"  ⚠️ Amaran sambungan semakan status: {e}")

    # Kemas kini status_used dalam memori sebelum muat naik
    preserved_count = 0
    for rec in all_records:
        if rec["product_id"] in existing_used_ids:
            rec["status_used"] = True
            preserved_count += 1

    if preserved_count > 0:
        print(f"  ✅ Sebanyak {preserved_count} produk dipelihara status TRUE.")

    # Muat naik secara pukal berkelompok (Batch 50)
    endpoint = f"{SUPABASE_URL}/rest/v1/affiliate_links?on_conflict=product_id"
    batch_size = 50
    success_count = 0

    print("\n💾 Memulakan penyimpanan pukal ke Supabase Cloud...")
    for i in range(0, total_valid, batch_size):
        batch = all_records[i : i + batch_size]
        try:
            res = requests.post(endpoint, headers=headers, json=batch, timeout=20)
            if res.status_code in [200, 201]:
                success_count += len(batch)
                print(f"  ✅ Disimpan: {success_count}/{total_valid} produk...")
            else:
                print(f"  ❌ Gagal pada kelompok {i+1}-{i+len(batch)}: HTTP {res.status_code} | {res.text}")
        except Exception as e:
            print(f"  ❌ Ralat sambungan kelompok: {e}")

    print("\n" + "=" * 70)
    print(f"🎉 [SELESAI] {success_count}/{total_valid} Produk Berjaya Disimpan/Dikemas Kini!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    bulk_import_to_supabase()