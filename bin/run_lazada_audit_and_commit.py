#!/usr/bin/env python3
"""
Lazada Feed Auto-Poster: Step 4, 5, 6, 7 & 8 (Audit & Commit Module)
Workflow Runner:
1. Read 'temp/lazada_payload.json'.
2. Step 4: Send comprehensive audit report to Telegram (Summary Card + AI Captions).
3. Check Safety Gatekeeper: Ensure at least ONE (1) social media platform succeeded.
   - If ALL failed: Stop immediately without committing data to avoid wasting the product.
4. Step 5: Commit product ID to Upstash Redis (Key: 'lazada:product:<id>', TTL 30 Days).
5. Step 6: Commit product title to Upstash Vector DB (ID: 'lz_<id>', Platform: 'lazada').
6. Step 7: Update Supabase table 'affiliate_links' (status_used = true).
7. Step 8: Clean up temporary payload file 'temp/lazada_payload.json'.
"""

import os
import sys
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

# 1. Konfigurasi Laluan Projek & Environment
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

env_local = PROJECT_ROOT / ".env.local"
if env_local.exists():
    load_dotenv(dotenv_path=env_local)
else:
    load_dotenv()

# 2. Import Modul Teras dari src/
from src.lazada_telegram_audit import send_lazada_audit_report, has_successful_post
from src.lazada_redis_filter import mark_lazada_product_posted
from src.lazada_vector_filter import mark_lazada_vector_posted

PAYLOAD_FILE = PROJECT_ROOT / "temp" / "lazada_payload.json"


def get_supabase_config():
    """Membaca konfigurasi sambungan Supabase daripada persekitaran."""
    supabase_url = os.getenv("SUPABASE_URL", "").strip() or os.getenv("NEXT_PUBLIC_SUPABASE_URL", "").strip()
    service_role_key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip() or 
        os.getenv("SUPABASE_SECRET_KEY", "").strip() or 
        os.getenv("SUPABASE_ANON_KEY", "").strip()
    )
    return supabase_url.rstrip("/"), service_role_key


def mark_lazada_product_as_used(product_id: str):
    """
    Menandakan status_used = true untuk product_id tertentu di jadual 'affiliate_links' Supabase.
    """
    supabase_url, api_key = get_supabase_config()
    if not supabase_url or not api_key:
        return False, "Konfigurasi Supabase tidak lengkap dalam persekitaran."

    clean_id = str(product_id).strip()
    if not clean_id:
        return False, "Product ID tidak sah."

    endpoint = f"{supabase_url}/rest/v1/affiliate_links?product_id=eq.{clean_id}"
    headers = {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    payload = {"status_used": True}

    try:
        res = requests.patch(endpoint, json=payload, headers=headers, timeout=15)
        if res.status_code == 200:
            return True, f"Produk Lazada ID {clean_id} berjaya ditandakan status_used=true di Supabase."
        else:
            return False, f"Ralat Supabase (HTTP {res.status_code}): {res.text}"
    except Exception as e:
        return False, f"Ralat sambungan Supabase: {str(e)}"


def cleanup_temp_files():
    """Memadam fail sementara payload selepas semua langkah transaksi selesai."""
    try:
        if PAYLOAD_FILE.exists():
            PAYLOAD_FILE.unlink()
            print(f"🧹 [STEP 8 CLEANUP] Fail sementara '{PAYLOAD_FILE.name}' berjaya dipadam.")
    except Exception as e:
        print(f"⚠️ [CLEANUP WARN] Gagal memadam fail payload sementara: {e}")


def run_audit_and_commit():
    print("\n" + "=" * 70)
    print("📊 [START] MEMULAKAN AUDIT TELEGRAM & KOMIT TRANSAKSI LAZADA")
    print("=" * 70)

    # 1. Semak kewujudan fail payload sementara
    if not PAYLOAD_FILE.exists():
        print(f"❌ [ABORT] Fail payload '{PAYLOAD_FILE}' tidak dijumpai. Tiada data untuk diaudit.")
        sys.exit(1)

    try:
        with open(PAYLOAD_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception as e:
        print(f"❌ [ABORT] Gagal membaca fail payload: {e}")
        sys.exit(1)

    product_id = str(payload.get("product_id") or "").strip()
    product_name = str(payload.get("product_name") or payload.get("title") or "Produk Lazada").strip()
    post_results = payload.get("post_results", {})

    print(f"📦 Produk : {product_name} (ID: {product_id})")

    # =========================================================================
    # STEP 4: HANTAR LAPORAN AUDIT LENGKAP KE TELEGRAM
    # =========================================================================
    print("\n📢 [STEP 4] Menghantar laporan audit terperinci ke Telegram Bot...")
    audit_ok, audit_msg = send_lazada_audit_report(payload)
    if audit_ok:
        print("✅ [AUDIT SUCCESS] Laporan berjaya dihantar ke saluran Telegram.")
    else:
        print(f"⚠️ [AUDIT WARN] Telegram Audit: {audit_msg}")

    # =========================================================================
    # PINTU KESELAMATAN (SAFETY GATEKEEPER)
    # =========================================================================
    success_any = has_successful_post(payload)

    if not success_any:
        print("\n" + "!" * 70)
        print("❌ [GATEKEEPER BLOCKED] Semua platform media sosial gagal membuat hantaran!")
        print("🛑 Transaksi ke Redis, Vector DB, dan Supabase DIBATALKAN.")
        print("ℹ️  Produk ini TIDAK akan ditandakan 'used' supaya boleh dicuba semula pada sesi hadapan.")
        print("!" * 70)

        # Cetak senarai ralat platform untuk rujukan log GitHub Actions
        for platform, res in post_results.items():
            err_detail = res.get("error", "Status bukan success") if isinstance(res, dict) else "Tiada maklumat"
            print(f"   • {platform.capitalize()}: {err_detail}")

        # Jangan padam fail jika gagal supaya ada bahan rujukan debug tempatan
        sys.exit(1)

    print("\n✅ [GATEKEEPER PASSED] Sekurang-kurangnya 1 platform berjaya pos. Meneruskan transaksi...")

    # =========================================================================
    # STEP 5: REKOD KUNCI KE UPSTASH REDIS (30 HARI TTL)
    # =========================================================================
    print(f"\n💾 [STEP 5] Merekodkan kunci ID produk ke Upstash Redis...")
    redis_ok = mark_lazada_product_posted(product_id)
    if redis_ok:
        print(f"✅ Redis: Kunci 'lazada:product:{product_id}' dikunci selama 30 hari.")
    else:
        print(f"⚠️ [REDIS WARN] Gagal merekodkan kunci ke Redis.")

    # =========================================================================
    # STEP 6: REKOD EMBEDDING KE UPSTASH VECTOR DB (3 HARI WINDOW)
    # =========================================================================
    print(f"\n🟢 [STEP 6] Menyimpan embedding tajuk ke Upstash Vector DB...")
    vector_ok = mark_lazada_vector_posted(product_id, product_name)
    if vector_ok:
        print(f"✅ Vector: Embedding 'lz_{product_id}' (Metadata: 'lazada') berjaya direkodkan.")
    else:
        print(f"⚠️ [VECTOR WARN] Gagal merekodkan embedding ke Vector DB.")

    # =========================================================================
    # STEP 7: TANDAKAN STATUS DI SUPABASE (status_used = true)
    # =========================================================================
    print(f"\n⚡ [STEP 7] Mengemas kini status rekod di Supabase Cloud...")
    sb_ok, sb_msg = mark_lazada_product_as_used(product_id)
    if sb_ok:
        print(f"✅ Supabase: {sb_msg}")
    else:
        print(f"⚠️ [SUPABASE WARN] {sb_msg}")

    # =========================================================================
    # STEP 8: PADAM FAIL SEMENTARA PAYLOAD
    # =========================================================================
    print(f"\n🧹 [STEP 8] Membersihkan fail sementara...")
    cleanup_temp_files()

    print("\n" + "=" * 70)
    print("🎉 [SUCCESS] Seluruh aliran pemposan Feed automatik selesai dengan jayanya!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    run_audit_and_commit()