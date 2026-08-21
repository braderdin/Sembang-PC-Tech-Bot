#!/usr/bin/env python3
"""
Shopee Auto-Poster Pipeline: Comprehensive Local Test Runner
Lokasi Fail: bin/run_shopee_all_step_test.py

Aliran Larian Ujian (Sequential Debugging Steps):
- Step 0: Semakan ketersediaan pembolehubah persekitaran (.env.local) termasuk Backblaze B2 Bridge.
- Step 1 & 2: Pemilihan produk Supabase, penapisan Redis/Vector & janaan kapsyen 4 platform AI.
- Step 3A - 3D: Larian pemposan media sosial (Facebook Page, Meta Threads, Instagram via B2 Bridge, Bluesky).
- Step 4 - 8: Laporan audit Telegram, semakan Safety Gatekeeper, komit kunci Redis, embedding Vector DB, kemas kini Supabase & pembersihan payload.
"""

import os
import sys
import json
import time
import traceback
from pathlib import Path
from dotenv import load_dotenv

# 1. Konfigurasi Laluan Projek & Muat Turun Persekitaran Tempatan
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

env_local = PROJECT_ROOT / ".env.local"
if env_local.exists():
    load_dotenv(dotenv_path=env_local)
else:
    load_dotenv()

TEMP_DIR = PROJECT_ROOT / "temp"
PAYLOAD_FILE = TEMP_DIR / "shopee_payload.json"

# ANSI Colors untuk Visual Terminal di WSL Ubuntu
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_banner(title: str, color: str = CYAN):
    width = 75
    print(f"\n{color}{BOLD}{'=' * width}")
    print(f" {title.center(width - 2)} ")
    print(f"{'=' * width}{RESET}")


def check_environment_variables() -> bool:
    """Menyemak status ketersediaan semua kunci API penting sebelum memulakan ujian."""
    print_banner("STEP 0: PRE-FLIGHT ENVIRONMENT & CONFIG CHECK", YELLOW)
    
    required_keys = {
        "Supabase Database": ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"],
        "Upstash Redis": ["UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN"],
        "Upstash Vector": ["UPSTASH_VECTOR_REST_URL", "UPSTASH_VECTOR_REST_TOKEN"],
        "OpenRouter AI": ["OPENROUTER_BASE_URL", "OPENROUTER_MODEL", "OPENROUTER_API_KEY"],
        "Telegram Audit": ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"],
        "Facebook Page": ["FACEBOOK_PAGE_ID", "FACEBOOK_PAGE_ACCESS_TOKEN"],
        "Meta Threads": ["THREADS_USER_ID", "THREADS_ACCESS_TOKEN"],
        "Instagram Business": ["INSTAGRAM_ACCOUNT_ID", "INSTAGRAM_ACCESS_TOKEN"],
        "Backblaze B2 (IG Bridge)": ["B2_ACC1_KEY_ID", "B2_ACC1_APPLICATION_KEY", "B2_ACC1_BUCKET_ID", "B2_ACC1_BUCKET_NAME"],
        "Bluesky Social": ["BLUESKY_HANDLE", "BLUESKY_APP_PASSWORD"]
    }

    all_ok = True
    for service, keys in required_keys.items():
        missing = []
        for k in keys:
            # Semak kunci utama atau alternatif
            val = os.getenv(k, "").strip()
            if not val:
                if k == "FACEBOOK_PAGE_ACCESS_TOKEN":
                    val = os.getenv("FB_PAGE_ACCESS_TOKEN", "").strip() or os.getenv("META_PAGE_ACCESS_TOKEN", "").strip()
                elif k == "FACEBOOK_PAGE_ID":
                    val = os.getenv("META_PAGE_ID", "").strip()
                elif k == "UPSTASH_REDIS_REST_URL":
                    val = os.getenv("UPSTASH_REDIS_URL", "").strip()
                elif k == "UPSTASH_REDIS_REST_TOKEN":
                    val = os.getenv("UPSTASH_API_KEY", "").strip()
                elif k == "B2_ACC1_KEY_ID":
                    val = os.getenv("B2_KEY_ID", "").strip()
                elif k == "B2_ACC1_APPLICATION_KEY":
                    val = os.getenv("B2_APPLICATION_KEY", "").strip()
                elif k == "B2_ACC1_BUCKET_ID":
                    val = os.getenv("B2_BUCKET_ID", "").strip()
                elif k == "B2_ACC1_BUCKET_NAME":
                    val = os.getenv("B2_BUCKET_NAME", "").strip()
            
            if not val:
                missing.append(k)

        if not missing:
            print(f"  {GREEN}✔ [{service}]{RESET} Kunci lengkap.")
        else:
            print(f"  {YELLOW}⚠ [{service}]{RESET} Kunci tidak lengkap: {', '.join(missing)}")
            if service in ["Supabase Database", "Upstash Redis", "Upstash Vector", "OpenRouter AI"]:
                all_ok = False

    return all_ok


def run_full_pipeline_test():
    start_total_time = time.time()
    print_banner("🧪 SHOPEE FEED AUTO-POSTER: END-TO-END PIPELINE TEST", BOLD + CYAN)

    # 1. Semakan Awal Persekitaran
    env_ready = check_environment_variables()
    if not env_ready:
        print(f"\n{RED}❌ [ABORT] Kunci pangkalan data atau AI teras tidak lengkap dalam .env.local!{RESET}")
        sys.exit(1)

    step_results = {}

    # =========================================================================
    # STEP 1 & 2: PENYEDIAAN CALON PRODUK & JANAAN AI
    # =========================================================================
    print_banner("STEP 1 & 2: FETCH, FILTER & AI CAPTIONS GENERATION", CYAN)
    try:
        from bin.run_shopee_prepare_and_generate import run_preparation_and_generation
        run_preparation_and_generation()

        if PAYLOAD_FILE.exists():
            with open(PAYLOAD_FILE, "r", encoding="utf-8") as f:
                payload = json.load(f)
            
            print(f"\n{GREEN}✔ [STEP 1 & 2 SUCCESS]{RESET} Payload sementara berjaya dijana:")
            print(f"   🆔 ID       : {payload.get('product_id')}")
            print(f"   📦 Nama     : {payload.get('product_name')}")
            print(f"   💰 Harga    : RM {payload.get('price', 0):.2f}")
            print(f"   🔗 Pautan   : {payload.get('affiliate_link')}")
            step_results["Step 1 & 2 (Prepare & Generate)"] = "SUCCESS"
        else:
            raise FileNotFoundError("Fail temp/shopee_payload.json tidak wujud selepas Step 1 & 2.")

    except Exception as e:
        print(f"\n{RED}❌ [STEP 1 & 2 FAILED] Ralat dikesan:{RESET}\n{traceback.format_exc()}")
        step_results["Step 1 & 2 (Prepare & Generate)"] = f"FAILED: {str(e)}"
        print_banner("UJIAN DIBATALKAN KERANA KEGAGALAN LANGKAH UTAMA", RED)
        return

    # =========================================================================
    # STEP 3A: POSTING KE FACEBOOK PAGE FEED
    # =========================================================================
    print_banner("STEP 3A: FACEBOOK PAGE FEED POSTING", CYAN)
    try:
        from bin.run_shopee_post_facebook import run_facebook_posting
        run_facebook_posting()
        
        with open(PAYLOAD_FILE, "r", encoding="utf-8") as f:
            fb_status = json.load(f).get("post_results", {}).get("facebook", {}).get("status")
        step_results["Step 3A (Facebook)"] = "SUCCESS" if fb_status == "success" else f"FAILED ({fb_status})"
    except Exception as e:
        print(f"{RED}❌ [FB POST EXCEPTION]:{RESET} {e}")
        step_results["Step 3A (Facebook)"] = f"FAILED: {str(e)}"

    # =========================================================================
    # STEP 3B: POSTING KE META THREADS FEED
    # =========================================================================
    print_banner("STEP 3B: META THREADS FEED POSTING", CYAN)
    try:
        from bin.run_shopee_post_threads import run_threads_posting
        run_threads_posting()
        
        with open(PAYLOAD_FILE, "r", encoding="utf-8") as f:
            th_status = json.load(f).get("post_results", {}).get("threads", {}).get("status")
        step_results["Step 3B (Threads)"] = "SUCCESS" if th_status == "success" else f"FAILED ({th_status})"
    except Exception as e:
        print(f"{RED}❌ [THREADS POST EXCEPTION]:{RESET} {e}")
        step_results["Step 3B (Threads)"] = f"FAILED: {str(e)}"

    # =========================================================================
    # STEP 3C: POSTING KE INSTAGRAM FEED VIA BACKBLAZE B2 BRIDGE
    # =========================================================================
    print_banner("STEP 3C: INSTAGRAM FEED POSTING (VIA B2 BRIDGE)", CYAN)
    try:
        from bin.run_shopee_post_instagram import run_instagram_posting
        run_instagram_posting()
        
        with open(PAYLOAD_FILE, "r", encoding="utf-8") as f:
            ig_status = json.load(f).get("post_results", {}).get("instagram", {}).get("status")
        step_results["Step 3C (Instagram)"] = "SUCCESS" if ig_status == "success" else f"FAILED ({ig_status})"
    except Exception as e:
        print(f"{RED}❌ [INSTAGRAM POST EXCEPTION]:{RESET} {e}")
        step_results["Step 3C (Instagram)"] = f"FAILED: {str(e)}"

    # =========================================================================
    # STEP 3D: POSTING KE BLUESKY FEED
    # =========================================================================
    print_banner("STEP 3D: BLUESKY FEED POSTING", CYAN)
    try:
        from bin.run_shopee_post_bluesky import run_bluesky_posting
        run_bluesky_posting()
        
        with open(PAYLOAD_FILE, "r", encoding="utf-8") as f:
            bs_status = json.load(f).get("post_results", {}).get("bluesky", {}).get("status")
        step_results["Step 3D (Bluesky)"] = "SUCCESS" if bs_status == "success" else f"FAILED ({bs_status})"
    except Exception as e:
        print(f"{RED}❌ [BLUESKY POST EXCEPTION]:{RESET} {e}")
        step_results["Step 3D (Bluesky)"] = f"FAILED: {str(e)}"

    # =========================================================================
    # STEP 4 HINGGA 8: AUDIT TELEGRAM, GATEKEEPER & TRANSAKSI KOMIT
    # =========================================================================
    print_banner("STEP 4 - 8: AUDIT TELEGRAM & TRANSACTION COMMIT", CYAN)
    try:
        from bin.run_shopee_audit_and_commit import run_audit_and_commit
        run_audit_and_commit()
        step_results["Step 4-8 (Audit & Commit)"] = "SUCCESS"
    except SystemExit as se:
        if se.code == 0:
            step_results["Step 4-8 (Audit & Commit)"] = "SUCCESS"
        else:
            step_results["Step 4-8 (Audit & Commit)"] = f"BLOCKED (Exit Code: {se.code})"
    except Exception as e:
        print(f"{RED}❌ [AUDIT & COMMIT EXCEPTION]:{RESET} {e}")
        step_results["Step 4-8 (Audit & Commit)"] = f"FAILED: {str(e)}"

    # =========================================================================
    # RINGKASAN AKHIR UJIAN (TEST SUMMARY)
    # =========================================================================
    elapsed = time.time() - start_total_time
    print_banner("📊 LAPORAN KEPUTUSAN UJIAN KESELURUHAN", BOLD + GREEN)
    print(f"⏱️ Masa Larian Keseluruhan: {elapsed:.2f} saat\n")

    for step_name, status in step_results.items():
        if "SUCCESS" in status:
            status_badge = f"{GREEN}✔ {status}{RESET}"
        elif "BLOCKED" in status:
            status_badge = f"{YELLOW}⚠ {status}{RESET}"
        else:
            status_badge = f"{RED}✖ {status}{RESET}"
        print(f"  • {BOLD}{step_name:<35}{RESET} : {status_badge}")

    print(f"\n{BOLD}{'=' * 75}{RESET}\n")


if __name__ == "__main__":
    run_full_pipeline_test()