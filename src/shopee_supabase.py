import os
import re
import requests
from typing import List, Dict, Any, Tuple, Optional


def get_supabase_config() -> Tuple[Optional[str], Optional[str], str]:
    """
    Membaca tetapan sambungan Supabase secara dinamik daripada persekitaran (env).
    """
    supabase_url = os.getenv("SUPABASE_URL", "").strip() or os.getenv("NEXT_PUBLIC_SUPABASE_URL", "").strip()
    service_role_key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        or os.getenv("SUPABASE_SECRET_KEY", "").strip()
        or os.getenv("SUPABASE_KEY", "").strip()
        or os.getenv("SUPABASE_ANON_KEY", "").strip()
    )

    if not supabase_url or not service_role_key:
        return None, None, "Kunci SUPABASE_URL atau SUPABASE_SERVICE_ROLE_KEY/ANON_KEY tidak lengkap dalam persekitaran."

    return supabase_url.rstrip("/"), service_role_key, ""


def parse_sales_count(val: Any) -> int:
    """
    Menukar format teks jualan Shopee (cth: '9k+', '30k+', '999', '1.5k', '0')
    kepada nombor bulat (integer) untuk susunan ketepatan jualan.
    """
    if val is None:
        return 0
    
    text = str(val).strip().lower()
    if not text or text == "nan":
        return 0

    try:
        if "k" in text:
            # Ekstrak nombor sebelum huruf 'k' (cth: '9.5k+' -> 9.5 * 1000 = 9500)
            match = re.search(r"([\d\.]+)\s*k", text)
            if match:
                return int(float(match.group(1)) * 1000)
        
        # Ekstrak semua digit nombor biasa (cth: '999+' -> 999)
        clean_num = re.sub(r"[^\d]", "", text)
        return int(clean_num) if clean_num else 0
    except Exception:
        return 0


def check_and_reset_shopee_status() -> Tuple[bool, str]:
    """
    Menyemak baki produk berstatus shopee_status_used=false.
    Jika semua produk telah digunakan (baki 0), set semula semua rekod kepada false.
    """
    supabase_url, api_key, err = get_supabase_config()
    if err:
        return False, err

    headers = {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Prefer": "count=exact"
    }

    # 1. Kira jumlah produk yang masih FALSE
    check_url = f"{supabase_url}/rest/v1/shopee_affiliate_links?select=shopee_product_id&shopee_status_used=eq.false&limit=1"
    try:
        res = requests.get(check_url, headers=headers, timeout=15)
        content_range = res.headers.get("content-range", "")
        unused_count = 0
        if "/" in content_range:
            total_part = content_range.split("/")[1]
            if total_part.isdigit():
                unused_count = int(total_part)

        if unused_count > 0:
            return True, f"Masih terdapat {unused_count} produk sedia ada (shopee_status_used=false)."

        # 2. Jika 0, reset semula semua kepada FALSE
        print("🔄 [AUTO-RESET] Semua produk Shopee telah digunakan (TRUE). Mengemas kini semula kepada FALSE...")
        reset_url = f"{supabase_url}/rest/v1/shopee_affiliate_links?shopee_status_used=eq.true"
        payload = {"shopee_status_used": False}
        patch_res = requests.patch(reset_url, json=payload, headers=headers, timeout=25)
        
        if patch_res.status_code in [200, 204]:
            return True, "Semua produk Shopee berjaya di-reset semula kepada status_used=false."
        else:
            return False, f"Gagal reset status: HTTP {patch_res.status_code} | {patch_res.text}"

    except Exception as e:
        return False, f"Ralat rangkaian semasa semakan/reset status: {str(e)}"


def fetch_shopee_candidates(limit: int = 300, offset: int = 0) -> Tuple[bool, List[Dict[str, Any]], str]:
    """
    Menarik kelompok calon produk Shopee yang belum digunakan (shopee_status_used = false).
    Menyusun produk secara automatik:
    - Kelompok Utama: Jualan >= 10 disusun mengikut jualan tertinggi (Descending).
    - Kelompok Sandaran: Jualan < 10 disusun selepasnya.
    """
    # 1. Semak & reset status jika perlu
    reset_ok, reset_msg = check_and_reset_shopee_status()
    if not reset_ok:
        print(f"⚠️ [WARN] {reset_msg}")

    supabase_url, api_key, err = get_supabase_config()
    if err:
        return False, [], err

    headers = {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # Tarik kelompok mengikut limit & offset
    endpoint = (
        f"{supabase_url}/rest/v1/shopee_affiliate_links"
        f"?shopee_status_used=eq.false"
        f"&order=id.asc"
        f"&limit={limit}"
        f"&offset={offset}"
    )

    try:
        res = requests.get(endpoint, headers=headers, timeout=20)
        if res.status_code != 200:
            return False, [], f"Supabase Fetch Error (HTTP {res.status_code}): {res.text}"

        raw_records = res.json()
        if not isinstance(raw_records, list) or len(raw_records) == 0:
            return True, [], "Tiada calon produk dijumpai pada offset ini."

        # 2. Proses dan susun mengikut jualan (Parsed Sales Count)
        for item in raw_records:
            item["_parsed_sales"] = parse_sales_count(item.get("shopee_sales_count", "0"))

        # Bahagikan kepada 2 tier: Jualan >= 10 dan Jualan < 10
        high_sales = [item for item in raw_records if item["_parsed_sales"] >= 10]
        low_sales = [item for item in raw_records if item["_parsed_sales"] < 10]

        # Susun kedua-dua tier dari nombor jualan tertinggi ke terendah
        high_sales.sort(key=lambda x: x["_parsed_sales"], reverse=True)
        low_sales.sort(key=lambda x: x["_parsed_sales"], reverse=True)

        # Gabungkan: Keutamaan sentiasa kepada tier jualan >= 10
        sorted_candidates = high_sales + low_sales

        return True, sorted_candidates, f"Berjaya menarik & menyusun {len(sorted_candidates)} calon produk (Tinggi: {len(high_sales)}, Rendah: {len(low_sales)})."

    except Exception as e:
        return False, [], f"Ralat sambungan Supabase: {str(e)}"


def mark_shopee_product_as_used(product_id: str) -> Tuple[bool, str]:
    """
    Menandakan shopee_status_used = true untuk shopee_product_id tertentu
    di Supabase selepas sekurang-kurangnya satu platform berjaya membuat hantaran.
    """
    supabase_url, api_key, err = get_supabase_config()
    if err:
        return False, err

    clean_id = str(product_id).strip()
    if not clean_id:
        return False, "Product ID tidak sah."

    endpoint = f"{supabase_url}/rest/v1/shopee_affiliate_links?shopee_product_id=eq.{clean_id}"
    headers = {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    payload = {"shopee_status_used": True}

    try:
        res = requests.patch(endpoint, json=payload, headers=headers, timeout=15)
        if res.status_code in [200, 204]:
            return True, f"Produk Shopee ID {clean_id} berjaya ditandakan shopee_status_used=true di Supabase."
        else:
            return False, f"Supabase Update Error (HTTP {res.status_code}): {res.text}"
    except Exception as e:
        return False, f"Ralat sambungan Supabase: {str(e)}"