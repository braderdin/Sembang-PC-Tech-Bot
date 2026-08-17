#!/usr/bin/env python3
"""
Shopee CSV to Excel Converter & HD Image Extractor
Sembang PC & Tech Ecosystem
Features:
- Reads Shopee Affiliate CSV exports from shopee_links_csv/
- Whitelisted Social Crawler Priority (Facebook & Telegram)
- Extracts 1 High-Resolution Main Product Image (Filters out shop logos & thumbnails)
- Standardized Schema aligned with Supabase & Lazada database
- Generates clean .xlsx file directly in shopee_links_csv/shopee_output_xlsx/
"""

import os
import re
import sys
import time
import pandas as pd
import requests
from pathlib import Path
from typing import Optional

# Setup Project Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Folder Paths
INPUT_CSV_DIR = PROJECT_ROOT / "shopee_links_csv"
OUTPUT_XLSX_DIR = INPUT_CSV_DIR / "shopee_output_xlsx"

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
    print("🛍️ [START] SHOPEE CSV ➔ EXCEL (.XLSX) DENGAN GAMBAR PRODUK HD TUNGGAL")
    print("=" * 75)

    if not INPUT_CSV_DIR.exists():
        INPUT_CSV_DIR.mkdir(parents=True, exist_ok=True)

    OUTPUT_XLSX_DIR.mkdir(parents=True, exist_ok=True)

    csv_files = [f for f in INPUT_CSV_DIR.glob("*.csv") if f.is_file()]
    if not csv_files:
        print(f"❌ Tiada fail CSV dijumpai di: {INPUT_CSV_DIR}")
        return

    for csv_file in csv_files:
        print(f"\n📂 Memproses fail: {csv_file.name}...")

        df = None
        for enc in ["utf-8", "utf-8-sig", "latin1", "cp1252"]:
            try:
                df = pd.read_csv(csv_file, encoding=enc)
                break
            except Exception:
                continue

        if df is None or df.empty:
            print(f"⚠️ Gagal membaca kandungan fail {csv_file.name} atau fail kosong.")
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

        # Simpan fail Excel akhir
        output_filename = f"{csv_file.stem}_enhanced.xlsx"
        output_path = OUTPUT_XLSX_DIR / output_filename

        enhanced_df = pd.DataFrame(enhanced_rows)
        enhanced_df.to_excel(output_path, index=False, engine="openpyxl")

        print("\n" + "=" * 75)
        print("🎉 [PROSES SELESAI]")
        print("=" * 75)
        print(f"📁 Fail Excel Baharu Disimpan: {output_path}")
        print(f"📦 Jumlah Produk Diproses    : {total_rows}")
        print(f"🖼️ Produk Berjaya Ada Gambar : {success_images_count} / {total_rows} ({round((success_images_count / total_rows) * 100, 1)}%)")
        print("=" * 75 + "\n")


if __name__ == "__main__":
    convert_shopee_csv_to_enhanced_xlsx()