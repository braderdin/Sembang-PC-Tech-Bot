#!/usr/bin/env python3
"""
Diagnostic Tool: Supabase Image URL Validator (100% READ-ONLY)
Sembang PC & Tech Ecosystem
Fungsi:
1. Membaca SEMUA produk dari Supabase (Pagination Fetch) secara READ-ONLY.
2. Menguji kesahan setiap 'image_url' (HTTP status, 404, 403, timeout, format).
3. Mengesan sambungan bertindih (.jpg.jpg) atau isu sekatan hotlink CDN.
4. Menjana ringkasan ralat & perincian produk yang bermasalah.
5. JAMINAN: Tiada sebarang kemas kini (PATCH/POST/DELETE) dilakukan ke atas pangkalan data.
"""

import os
import re
import sys
import time
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

# Tetapkan laluan akar projek
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Muat turun pembolehubah persekitaran
env_local = PROJECT_ROOT / ".env.local"
if env_local.exists():
    load_dotenv(dotenv_path=env_local)
else:
    load_dotenv()

SUPABASE_URL = (os.getenv("SUPABASE_URL", "").strip() or os.getenv("NEXT_PUBLIC_SUPABASE_URL", "").strip()).rstrip("/")
SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    or os.getenv("SUPABASE_KEY", "").strip()
    or os.getenv("SUPABASE_ANON_KEY", "").strip()
)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"


def fetch_all_supabase_products_readonly():
    """Membaca semua rekod dari Supabase menggunakan paginasi (100% READ-ONLY)."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ [ERROR] SUPABASE_URL atau SUPABASE_SERVICE_ROLE_KEY tidak dijumpai!")
        return []

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }

    all_products = []
    page_size = 500
    offset = 0

    print(f"📦 [READ-ONLY] Menyambung ke Supabase ({SUPABASE_URL})...")

    while True:
        endpoint = f"{SUPABASE_URL}/rest/v1/affiliate_links?select=product_id,title,category,image_url,status_used&order=id.asc&limit={page_size}&offset={offset}"
        try:
            res = requests.get(endpoint, headers=headers, timeout=20)
            if res.status_code != 200:
                print(f"❌ Ralat penarikan data: HTTP {res.status_code} - {res.text}")
                break

            data = res.json()
            if not data or not isinstance(data, list) or len(data) == 0:
                break

            all_products.extend(data)
            print(f"  📥 Memuat turun rekod {offset + 1} hingga {offset + len(data)}...")
            
            if len(data) < page_size:
                break
            offset += page_size
        except Exception as e:
            print(f"❌ Ralat sambungan Supabase: {e}")
            break

    return all_products


def verify_single_image_url(product):
    """Menguji kesahan URL gambar secara individu."""
    p_id = str(product.get("product_id") or "").strip()
    title = str(product.get("title") or "Tiada Tajuk").strip()
    raw_url = str(product.get("image_url") or "").strip()

    # 1. Semakan URL Kosong / Null
    if not raw_url or raw_url.lower() == "nan" or raw_url.lower() == "none":
        return {
            "product_id": p_id,
            "title": title[:50],
            "url": raw_url,
            "is_valid": False,
            "status_code": None,
            "error_type": "EMPTY_OR_NULL",
            "error_message": "Medan image_url kosong atau tiada nilai di Supabase."
        }

    # 2. Semakan Sambungan Bertindih (.jpg.jpg / .png.png)
    has_duplicate_ext = bool(re.search(r"(\.(jpg|jpeg|png|webp))\.\2$", raw_url, re.I) or re.search(r"(\.(jpg|jpeg|png|webp))\1$", raw_url, re.I))

    # 3. Ujian Sambungan HTTP ke CDN Gambar
    headers = {"User-Agent": USER_AGENT, "Accept": "image/*,*/*;q=0.8"}
    try:
        # Gunakan stream=True untuk jimat bandwidth (hanya baca header & sebahagian data)
        res = requests.get(raw_url, headers=headers, timeout=8, stream=True)
        status_code = res.status_code

        if status_code == 200:
            content_type = res.headers.get("Content-Type", "").lower()
            # Baca 1024 bait pertama untuk pastikan imej tidak kosong
            first_chunk = next(res.iter_content(1024), b"")
            
            if len(first_chunk) < 100:
                return {
                    "product_id": p_id,
                    "title": title[:50],
                    "url": raw_url,
                    "is_valid": False,
                    "status_code": status_code,
                    "error_type": "EMPTY_IMAGE_CONTENT",
                    "error_message": "Fail gambar wujud tetapi saiz kandungan kosong (<100 bytes)."
                }

            if has_duplicate_ext:
                return {
                    "product_id": p_id,
                    "title": title[:50],
                    "url": raw_url,
                    "is_valid": True,
                    "status_code": status_code,
                    "error_type": "DUPLICATE_EXTENSION_WARN",
                    "error_message": "Gambar sah tetapi mempunyai format sambungan bertindih (.jpg.jpg)."
                }

            return {
                "product_id": p_id,
                "title": title[:50],
                "url": raw_url,
                "is_valid": True,
                "status_code": 200,
                "error_type": None,
                "error_message": "OK"
            }
        else:
            return {
                "product_id": p_id,
                "title": title[:50],
                "url": raw_url,
                "is_valid": False,
                "status_code": status_code,
                "error_type": f"HTTP_{status_code}",
                "error_message": f"Pelayan CDN membalas status HTTP {status_code} ({res.reason})."
            }

    except requests.exceptions.Timeout:
        return {
            "product_id": p_id,
            "title": title[:50],
            "url": raw_url,
            "is_valid": False,
            "status_code": None,
            "error_type": "TIMEOUT",
            "error_message": "Sambungan ke pelayan gambar tamat masa (>8 saat)."
        }
    except requests.exceptions.SSLError as ssl_err:
        return {
            "product_id": p_id,
            "title": title[:50],
            "url": raw_url,
            "is_valid": False,
            "status_code": None,
            "error_type": "SSL_ERROR",
            "error_message": f"Ralat Sijil Keselamatan SSL CDN: {ssl_err}"
        }
    except Exception as e:
        return {
            "product_id": p_id,
            "title": title[:50],
            "url": raw_url,
            "is_valid": False,
            "status_code": None,
            "error_type": "REQUEST_ERROR",
            "error_message": str(e)
        }


def run_diagnostics():
    print("\n" + "=" * 75)
    print("🔍 [START] DIAGNOSTIK KESAHAN URL GAMBAR SUPABASE (100% READ-ONLY)")
    print("=" * 75)

    products = fetch_all_supabase_products_readonly()
    total_products = len(products)

    if total_products == 0:
        print("⚠️ Tiada produk ditemui untuk diuji.")
        return

    print(f"\n📊 Jumlah keseluruhan produk dijumpai: {total_products} produk.")
    print(f"🚀 Memulakan semakan serentak (20 Threads)...\n")

    valid_count = 0
    invalid_count = 0
    duplicate_ext_count = 0
    error_summary = {}
    broken_products_list = []

    start_time = time.time()

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(verify_single_image_url, p): p for p in products}
        
        for idx, future in enumerate(as_completed(futures), 1):
            res = future.result()

            if res["is_valid"]:
                valid_count += 1
                if res.get("error_type") == "DUPLICATE_EXTENSION_WARN":
                    duplicate_ext_count += 1
            else:
                invalid_count += 1
                err_type = res["error_type"]
                error_summary[err_type] = error_summary.get(err_type, 0) + 1
                broken_products_list.append(res)

            # Bar kemajuan terminal
            if idx % 100 == 0 or idx == total_products:
                sys.stdout.write(f"\r  ⚡ Mengimbas: {idx}/{total_products} | Sah: {valid_count} | Ralat: {invalid_count}")
                sys.stdout.flush()

    duration = round(time.time() - start_time, 2)
    print(f"\n\n🏁 Imbisan selesai dalam masa {duration} saat.")

    # =========================================================================
    # PAPARAN LAPORAN DIAGNOSTIK LENGKAP
    # =========================================================================
    print("\n" + "=" * 75)
    print("📋 RINGKASAN KESELURUHAN STATUS GAMBAR")
    print("=" * 75)
    print(f"📦 Jumlah Produk Diimbas   : {total_products}")
    print(f"✅ Gambar Sah & Aktif (200): {valid_count} ({(valid_count/total_products)*100:.1f}%)")
    print(f"❌ Gambar Rosak / Bermasalah: {invalid_count} ({(invalid_count/total_products)*100:.1f}%)")
    if duplicate_ext_count > 0:
        print(f"⚠️ Sambungan Bertindih (.jpg.jpg): {duplicate_ext_count} produk")

    if error_summary:
        print("\n🔍 PECAHAN JENIS RALAT:")
        for err_type, count in sorted(error_summary.items(), key=lambda x: x[1], reverse=True):
            print(f"  • {err_type:<25} : {count} produk")

    if broken_products_list:
        print("\n" + "=" * 75)
        print("🚨 CONTOH 10 PRODUK DENGAN GAMBAR BERMASALAH:")
        print("=" * 75)
        for idx, item in enumerate(broken_products_list[:10], 1):
            print(f"{idx}. ID: {item['product_id']} | Tajuk: {item['title']}")
            print(f"   URL   : {item['url'] if item['url'] else '[KOSONG]'}")
            print(f"   Ralat : {item['error_type']} ➔ {item['error_message']}\n")

    print("🛡️ [STATUS DB] Tiada sebarang data, kolum, atau status_used diubah suai (100% Selamat).\n")


if __name__ == "__main__":
    run_diagnostics()