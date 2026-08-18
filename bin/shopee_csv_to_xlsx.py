#!/usr/bin/env python3
"""
Shopee CSV to Excel Converter & HD Image Extractor (Production Batch Engine)
Sembang PC & Tech Ecosystem
Features:
- Reads Shopee Affiliate CSV exports from shopee_links_csv/
- Automatic CSV Processed Memory Bank (data/processed_shopee_csv.json) to prevent reprocessing
- Sequential 4-digit Excel naming (link_affiliate_shopee_0001.xlsx) into shopee_affiliate_xlsx/
- Whitelisted Social Crawler Priority (Facebook & Telegram)
- Extracts 1 High-Resolution Main Product Image (Filters out shop logos & thumbnails)
- Standardized Schema aligned with Supabase & Lazada database
"""

import os
import re
import sys
import json
import time
import pandas as pd
import requests
from pathlib import Path
from typing import Optional, Set

# Setup Project Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Folder & File Paths
INPUT_CSV_DIR = PROJECT_ROOT / "shopee_links_csv"
OUTPUT_XLSX_DIR = PROJECT_ROOT / "shopee_affiliate_xlsx"
DATA_DIR = PROJECT_ROOT / "data"
MEMORY_FILE = DATA_DIR / "processed_shopee_csv.json"

# Header Utama Rasmi Media Sosial
PRIORITY_HEADERS = [
    {
        "User-Agent": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.html)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,ms;q=0.8",
    },
    {
        "User-Agent": "TelegramBot (like TwitterBot)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
]


def load_processed_memory() -> Set[str]:
    """Memuatkan senarai fail CSV yang telah selesai diproses sebelum ini."""
    if not MEMORY_FILE.exists():
        return set()
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return set(data)
    except Exception as e:
        print(f"⚠️ [MEMORY WARN] Gagal membaca fail memori: {e}")
    return set()


def save_processed_memory(processed_set: Set[str]):
    """Menyimpan senarai fail CSV yang telah diproses ke fail JSON."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(list(processed_set)), f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"⚠️ [MEMORY WARN] Gagal mengemas kini fail memori: {e}")


def get_next_xlsx_sequence_number() -> int:
    """Mengesan nombor siri tertinggi dalam folder output dan memulangkan siri seterusnya."""
    if not OUTPUT_XLSX_DIR.exists():
        return 1

    existing_files = OUTPUT_XLSX_DIR.glob("link_affiliate_shopee_*.xlsx")
    max_seq = 0

    for file_path in existing_files:
        match = re.search(r"link_affiliate_shopee_(\d+)\.xlsx$", file_path.name, re.I)
        if match:
            try:
                seq = int(match.group(1))
                if seq > max_seq:
                    max_seq = seq
            except ValueError:
                continue

    return max_seq + 1


def clean_shopee_image_url(url: str) -> Optional[str]:
    """Membersihkan URL gambar Shopee dan menolak logo kedai atau ikon."""
    if not url or not isinstance(url, str):
        return None

    url = url.strip()
    # Buang tag thumbnail (_tn) supaya dapat versi resolusi tinggi
    url = re.sub(r'_[a-zA-Z0-9]+$', '', url)

    # Tapis keluar avatar kedai (Shopee CDN logo biasa bermula dengan 11134216 / 11134233)
    if "11134216" in url or "11134233" in url or "avatar" in url.lower() or "logo" in url.lower():
        return None

    if "susercontent.com" in url or "shopee.com" in url:
        return url

    return None


def extract_single_hd_product_image(product_url: str, offer_url: str) -> str:
    """Mengekstrak 1 gambar produk rasmi HD resolusi tinggi."""
    target_urls = [u for u in [product_url, offer_url] if u and isinstance(u, str) and u.startswith("http")]

    for target_url in target_urls:
        for header in PRIORITY_HEADERS:
            try:
                res = requests.get(target_url, headers=header, timeout=10, allow_redirects=True)
                if res.status_code != 200:
                    continue

                html_text = res.text

                # 1. Cari meta property og:image & twitter:image
                og_matches = re.findall(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html_text, re.I)
                if not og_matches:
                    og_matches = re.findall(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', html_text, re.I)

                for img in og_matches:
                    cleaned = clean_shopee_image_url(img)
                    if cleaned:
                        return cleaned

                # 2. Imbas meta twitter:image jika og:image tiada
                twitter_matches = re.findall(r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']', html_text, re.I)
                for img in twitter_matches:
                    cleaned = clean_shopee_image_url(img)
                    if cleaned:
                        return cleaned

                # 3. Imbas Hash Imej Produk CDN
                cdn_hashes = re.findall(r'https://down-my\.img\.susercontent\.com/file/([a-zA-Z0-9_\-]+)', html_text)
                for h in cdn_hashes:
                    if len(h) >= 20 and not h.startswith("11134216"):
                        candidate = f"https://down-my.img.susercontent.com/file/{h}"
                        cleaned = clean_shopee_image_url(candidate)
                        if cleaned:
                            return cleaned

            except Exception:
                pass

    return ""


def convert_shopee_csv_to_enhanced_xlsx():
    print("\n" + "=" * 75)
    print("🛍️ [START] ENJIN PUKAL SHOPEE CSV ➔ EXCEL (.XLSX) BERSIRI & MEMORI")
    print("=" * 75)

    if not INPUT_CSV_DIR.exists():
        INPUT_CSV_DIR.mkdir(parents=True, exist_ok=True)

    OUTPUT_XLSX_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    processed_memory = load_processed_memory()
    print(f"🧠 [MEMORY BANK] {len(processed_memory)} fail CSV sedia ada direkodkan.")

    csv_files = sorted([f for f in INPUT_CSV_DIR.glob("*.csv") if f.is_file()])
    if not csv_files:
        print(f"❌ Tiada fail CSV dijumpai di: {INPUT_CSV_DIR}")
        return

    pending_csv_files = [f for f in csv_files if f.name not in processed_memory]
    skipped_count = len(csv_files) - len(pending_csv_files)

    if skipped_count > 0:
        print(f"⏭️ {skipped_count} fail CSV dilangkau kerana telah siap diproses sebelum ini.")

    if not pending_csv_files:
        print("✅ Semua fail CSV di dalam folder shopee_links_csv/ telah selesai diproses sepenuhnya!")
        return

    print(f"🎯 Dijumpai {len(pending_csv_files)} fail CSV baharu sedia untuk diproses.\n")

    current_seq = get_next_xlsx_sequence_number()

    for file_idx, csv_file in enumerate(pending_csv_files, start=1):
        print("=" * 75)
        print(f"📂 [FAIL {file_idx}/{len(pending_csv_files)}] Memproses: {csv_file.name}")
        print("=" * 75)

        df = None
        for enc in ["utf-8", "utf-8-sig", "latin1", "cp1252"]:
            try:
                df = pd.read_csv(csv_file, encoding=enc)
                break
            except Exception:
                continue

        if df is None or df.empty:
            print(f"⚠️ Gagal membaca fail {csv_file.name} atau kandungan kosong. Menandakan fail sebagai siap.")
            processed_memory.add(csv_file.name)
            save_processed_memory(processed_memory)
            continue

        total_rows = len(df)
        print(f"📊 Jumlah produk: {total_rows} item.")
        print("⏳ Memproses data & mengekstrak gambar HD rasmi (Delay 1.0 saat per item)...\n")

        enhanced_rows = []
        success_images_count = 0

        for idx, (_, row) in enumerate(df.iterrows(), start=1):
            item_id = str(row.get("Item Id", "")).strip()
            item_name = str(row.get("Item Name", "")).strip()
            price = row.get("Price", 0.0)
            sales = str(row.get("Sales", "")).strip()
            shop_name = str(row.get("Shop Name", "")).strip()
            commission_rate = str(row.get("Commission Rate", "")).strip()
            commission = str(row.get("Commission", "")).strip()
            product_link = str(row.get("Product Link", "")).strip()
            offer_link = str(row.get("Offer Link", "")).strip()

            try:
                price_val = float(str(price).replace("RM", "").replace(",", "").strip())
            except Exception:
                price_val = 0.0

            # Ekstrak 1 gambar HD rasmi produk
            product_image_url = extract_single_hd_product_image(product_link, offer_link)

            if product_image_url:
                success_images_count += 1
                status_symbol = "✅"
            else:
                status_symbol = "⚠️"

            print(f"[{idx}/{total_rows}] {status_symbol} ID: {item_id} | {item_name[:40]}...")

            enhanced_rows.append({
                "product_id": item_id,
                "product_name": item_name,
                "brand": shop_name or "Shopee Preferred",
                "price": price_val,
                "sales_count": sales,
                "commission_rate": commission_rate,
                "commission_amount": commission,
                "picture_url": product_image_url,
                "product_url": product_link,
                "affiliate_link": offer_link,
            })

            time.sleep(1.0)

        # Jana nama fail bersiri 4 digit tanpa tindihan (contoh: link_affiliate_shopee_0001.xlsx)
        output_filename = f"link_affiliate_shopee_{current_seq:04d}.xlsx"
        output_path = OUTPUT_XLSX_DIR / output_filename

        enhanced_df = pd.DataFrame(enhanced_rows)
        enhanced_df.to_excel(output_path, index=False, engine="openpyxl")

        # Kunci fail CSV ke dalam Bank Ingatan JSON
        processed_memory.add(csv_file.name)
        save_processed_memory(processed_memory)

        print("\n" + "-" * 75)
        print(f"🎉 [SELESAI] Disimpan ke: {output_path.name}")
        print(f"📁 Laluan Penuh          : {output_path}")
        print(f"📦 Jumlah Produk         : {total_rows}")
        print(f"🖼️ Gambar Berjaya Ditapis : {success_images_count} / {total_rows} ({round((success_images_count / total_rows) * 100, 1)}%)")
        print(f"🧠 Memori Dikemas Kini   : {csv_file.name} direkodkan.")
        print("-" * 75 + "\n")

        current_seq += 1

    print("=" * 75)
    print("🚀 [ALL DONE] Kesemua fail CSV Shopee telah berjaya ditukar kepada format Excel bersiri!")
    print(f"📁 Folder Output: {OUTPUT_XLSX_DIR}")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    convert_shopee_csv_to_enhanced_xlsx()