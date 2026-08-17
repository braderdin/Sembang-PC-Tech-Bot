#!/usr/bin/env python3
"""
Shopee CSV to Excel Converter & HD Image Extractor
Sembang PC & Tech Ecosystem
Features:
- Reads Shopee Affiliate CSV exports from shopee_links_csv/
- Whitelisted Social Crawler & Browser Headers (Facebook / Telegram / WhatsApp)
- Multi-layer HD Image Extraction (OpenGraph, Twitter Cards & CDN Hashes)
- Captures up to 3 high-resolution product image URLs per item
- Human-like 1.0-second delay per request to avoid rate limits
- Generates a cleanly structured .xlsx file in shopee_links_csv/shopee_output_xlsx/
"""

import os
import re
import sys
import time
import random
import pandas as pd
import requests
from pathlib import Path
from typing import List, Dict, Any, Tuple
from urllib.parse import urlparse

# Setup Project Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Folder Paths
INPUT_CSV_DIR = PROJECT_ROOT / "shopee_links_csv"
OUTPUT_XLSX_DIR = INPUT_CSV_DIR / "shopee_output_xlsx"

# Senarai Header Mesra Media Sosial (Whitelisted Crawlers)
SOCIAL_CRAWLER_HEADERS = [
    {
        "User-Agent": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.html)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,ms;q=0.8",
    },
    {
        "User-Agent": "TelegramBot (like TwitterBot)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    },
    {
        "User-Agent": "WhatsApp/2.21.12.21 A",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    },
    {
        "User-Agent": "Twitterbot/1.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    },
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,ms;q=0.8",
        "Referer": "https://shopee.com.my/",
    }
]


def extract_shopee_images(product_url: str, offer_url: str) -> List[str]:
    """Mengekstrak sehingga 3 URL gambar produk HD menggunakan kaedah header OpenGraph & CDN scanner."""
    target_urls = [u for u in [product_url, offer_url] if u and isinstance(u, str) and u.startswith("http")]
    extracted_images = []

    for target_url in target_urls:
        header = random.choice(SOCIAL_CRAWLER_HEADERS)
        try:
            res = requests.get(target_url, headers=header, timeout=12, allow_redirects=True)
            if res.status_code != 200:
                continue

            html_text = res.text

            # 1. Kaedah Utama: Cari meta property og:image & twitter:image
            og_matches = re.findall(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html_text, re.I)
            if not og_matches:
                og_matches = re.findall(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', html_text, re.I)

            twitter_matches = re.findall(r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']', html_text, re.I)
            if not twitter_matches:
                twitter_matches = re.findall(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']', html_text, re.I)

            for img in og_matches + twitter_matches:
                img_clean = img.strip()
                if "susercontent.com" in img_clean or "shopee.com" in img_clean:
                    # Buang thumbnail resize tag (_tn) supaya dapat resolusi asal HD
                    img_clean = re.sub(r'_[a-zA-Z0-9]+$', '', img_clean)
                    if img_clean not in extracted_images:
                        extracted_images.append(img_clean)

            # 2. Kaedah Tambahan: Imbas Hash Imej CDN Shopee dari kod sumber (down-my.img.susercontent.com)
            cdn_hashes = re.findall(r'https://down-my\.img\.susercontent\.com/file/([a-zA-Z0-9_\-]+)', html_text)
            for h in cdn_hashes:
                # Elakkan ikon kecil atau placeholder
                if len(h) >= 15 and "icon" not in h.lower() and "logo" not in h.lower():
                    full_cdn_url = f"https://down-my.img.susercontent.com/file/{h}"
                    if full_cdn_url not in extracted_images:
                        extracted_images.append(full_cdn_url)

            # 3. Imbas array imej mentah Shopee JSON: "images":["hash1", "hash2"]
            json_image_matches = re.findall(r'"images"\s*:\s*\[([^\]]+)\]', html_text)
            for jm in json_image_matches:
                hashes = re.findall(r'"([a-zA-Z0-9_\-]+)"', jm)
                for h in hashes:
                    if len(h) >= 20:
                        full_cdn_url = f"https://down-my.img.susercontent.com/file/{h}"
                        if full_cdn_url not in extracted_images:
                            extracted_images.append(full_cdn_url)

            if len(extracted_images) >= 3:
                break

        except Exception:
            pass

    return extracted_images[:3]


def convert_shopee_csv_to_enhanced_xlsx():
    print("\n" + "=" * 75)
    print("🛍️ [START] SHOPEE CSV ➔ EXCEL (.XLSX) DENGAN PENGECASAN GAMBAR HD")
    print("=" * 75)

    if not INPUT_CSV_DIR.exists():
        INPUT_CSV_DIR.mkdir(parents=True, exist_ok=True)
        print(f"📁 Folder dicipta: {INPUT_CSV_DIR}")

    OUTPUT_XLSX_DIR.mkdir(parents=True, exist_ok=True)

    csv_files = [f for f in INPUT_CSV_DIR.glob("*.csv") if f.is_file()]
    if not csv_files:
        print(f"❌ Tiada fail CSV dijumpai di: {INPUT_CSV_DIR}")
        print("💡 Sila letakkan fail 'shopee-affiliate.csv' ke dalam folder tersebut dahulu.")
        return

    for csv_file in csv_files:
        print(f"\n📂 Memproses fail: {csv_file.name}...")

        # Baca CSV dengan pelbagai cubaan encoding
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
        print(f"📊 Jumlah produk dijumpai: {total_rows} item.")
        print("⏳ Memulakan ekstraksi metadata & gambar (Delay 1.0 saat per item)...\n")

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

            # Bersihkan tanda RM daripada kolum harga & komisen jika wujud
            try:
                price_val = float(str(price).replace("RM", "").replace(",", "").strip())
            except Exception:
                price_val = 0.0

            # Dapatkan URL Gambar HD
            images = extract_shopee_images(product_link, offer_link)
            img_1 = images[0] if len(images) > 0 else ""
            img_2 = images[1] if len(images) > 1 else ""
            img_3 = images[2] if len(images) > 2 else ""

            if img_1:
                success_images_count += 1
                status_symbol = "✅"
            else:
                status_symbol = "⚠️"

            print(f"[{idx}/{total_rows}] {status_symbol} ID: {item_id} | {item_name[:40]}... ({len(images)} Gambar Dikesan)")

            enhanced_rows.append({
                "product_id": item_id,
                "product_name": item_name,
                "brand": shop_name or "Shopee Preferred",
                "price": price_val,
                "sales_count": sales,
                "commission_rate": commission_rate,
                "commission_amount": commission,
                "product_url": product_link,
                "affiliate_link": offer_link,
                "image_url_1": img_1,
                "image_url_2": img_2,
                "image_url_3": img_3,
                "total_images_found": len(images)
            })

            # Delay 1 saat seperti diminta
            time.sleep(1.0)

        # Simpan ke fail Excel .xlsx di folder khusus shopee_links_csv/shopee_output_xlsx/
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