#!/usr/bin/env python3
"""
Reddit Tech Storyteller Engine: Comprehensive Local Test Runner
Lokasi Fail: bin/run_reddit_all_step_test.py

Ciri-ciri Penambahbaikan (Tuned):
1. Pre-flight Check Khusus Reddit: Mengesahkan kewujudan REDDIT_OPENROUTER_MODEL & REDDIT_OPENROUTER_MODEL_FALLBACK dengan fallback am OPENROUTER_MODEL.
2. Paparan Status Model Aktif: Memaparkan model AI utama dan sandaran yang sedang digunakan secara telus di terminal sebelum ujian bermula.
3. Aliran End-to-End Kalis Ralat: Menguji janaan kapsyen 4 platform, posting ke Facebook, Threads, Instagram, Bluesky, serta audit Telegram dan komit DB (Step 0 - 8).
"""

import os
import sys
import json
import time
import traceback
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

TEMP_DIR = PROJECT_ROOT / "temp"
PAYLOAD_FILE = TEMP_DIR / "reddit_payload.json"

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
    """Menyemak ketersediaan semua kunci API penting sebelum memulakan ujian."""
    print_banner("STEP 0: PRE-FLIGHT ENVIRONMENT & CONFIG CHECK", YELLOW)

    # 1. Semak Kunci Model OpenRouter Khusus Reddit / Am
    model_primary = (
        os.getenv("REDDIT_OPENROUTER_MODEL", "").strip()
        or os.getenv("OPENROUTER_MODEL", "").strip()
    )
    model_fallback = (
        os.getenv("REDDIT_OPENROUTER_MODEL_FALLBACK", "").strip()
        or os.getenv("OPENROUTER_MODEL_FALLBACK", "").strip()
    )
    base_url = (os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1").strip()
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()

    required_keys = {
        "Upstash Redis": ["UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN"],
        "Upstash Vector": ["UPSTASH_VECTOR_REST_URL", "UPSTASH_VECTOR_REST_TOKEN"],
        "Unsplash Media (Fallback)": ["UNSPLASH_ACCESS_KEY"],
        "Telegram Audit": ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"],
        "Facebook Page": ["FACEBOOK_PAGE_ID", "FACEBOOK_PAGE_ACCESS_TOKEN"],
        "Meta Threads": ["THREADS_USER_ID", "THREADS_ACCESS_TOKEN"],
        "Instagram Business": ["INSTAGRAM_ACCOUNT_ID", "INSTAGRAM_ACCESS_TOKEN"],
        "Bluesky Social": ["BLUESKY_HANDLE", "BLUESKY_APP_PASSWORD"]
    }

    all_ok = True

    # Pengesahan OpenRouter AI Engine
    if api_key and model_primary:
        print(f"  {GREEN}✔ [OpenRouter AI]{RESET} Kunci lengkap.")
        print(f"     • Base URL : {base_url}")
        print(f"     • Model Utama   : {BOLD}{model_primary}{RESET}")
        print(f"     • Model Sandaran: {model_fallback if model_fallback else '(Tiada)'}")
    else:
        missing_ai = []
        if not api_key:
            missing_ai.append("OPENROUTER_API_KEY")
        if not model_primary:
            missing_ai.append("REDDIT_OPENROUTER_MODEL / OPENROUTER_MODEL")
        print(f"  {RED}✖ [OpenRouter AI]{RESET} Kunci tidak lengkap: {', '.join(missing_ai)}")
        all_ok = False

    # Pengesahan Perkhidmatan Lain
    for service, keys in required_keys.items():
        missing = []
        for k in keys:
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

            if not val:
                missing.append(k)

        if not missing:
            print(f"  {GREEN}✔ [{service}]{RESET} Kunci lengkap.")
        else:
            print(f"  {YELLOW}⚠ [{service}]{RESET} Kunci tidak lengkap: {', '.join(missing)}")
            if service in ["Upstash Redis", "Upstash Vector"]:
                all_ok = False

    return all_ok


def run_full_pipeline_test():
    start_total_time = time.time()
    print_banner("🧪 REDDIT STORYTELLER: END-TO-END LOCAL PIPELINE TEST", BOLD + CYAN)

    # 1. Semakan Awal Persekitaran
    env_ready = check_environment_variables()
    if not env_ready:
        print(f"\n{RED}❌ [ABORT] Kunci pangkalan data atau AI teras tidak lengkap dalam .env.local!{RESET}")
        sys.exit(1)

    step_results = {}

    # =========================================================================
    # STEP 1 & 2: PENYEDIAAN CALON REDDIT & JANAAN AI 4 PLATFORM
    # =========================================================================
    print_banner("STEP 1 & 2: REDDIT INGESTION, IMAGE ENGINE & AI PERSONA", CYAN)
    try:
        from bin.run_reddit_prepare_and_generate import run_preparation_and_generation
        run_preparation_and_generation()

        if PAYLOAD_FILE.exists():
            with open(PAYLOAD_FILE, "r", encoding="utf-8") as f:
                payload = json.load(f)

            print(f"\n{GREEN}✔ [STEP 1 & 2 SUCCESS]{RESET} Payload sementara berjaya dicipta:")
            print(f"   🆔 Post ID   : {payload.get('post_id')}")
            print(f"   📌 Subreddit : r/{payload.get('subreddit')}")
            print(f"   📖 Tajuk     : {payload.get('title')}")
            print(f"   🖼️ Imej      : {payload.get('picture_url')} ({payload.get('image_source')})")
            step_results["Step 1 & 2 (Prepare & Generate)"] = "SUCCESS"
        else:
            raise FileNotFoundError("Fail temp/reddit_payload.json tidak dijumpai selepas Step 1 & 2.")

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
        from bin.run_reddit_post_facebook import run_facebook_posting
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
        from bin.run_reddit_post_threads import run_threads_posting
        run_threads_posting()

        with open(PAYLOAD_FILE, "r", encoding="utf-8") as f:
            th_status = json.load(f).get("post_results", {}).get("threads", {}).get("status")
        step_results["Step 3B (Threads)"] = "SUCCESS" if th_status == "success" else f"FAILED ({th_status})"
    except Exception as e:
        print(f"{RED}❌ [THREADS POST EXCEPTION]:{RESET} {e}")
        step_results["Step 3B (Threads)"] = f"FAILED: {str(e)}"

    # =========================================================================
    # STEP 3C: POSTING KE INSTAGRAM FEED
    # =========================================================================
    print_banner("STEP 3C: INSTAGRAM FEED POSTING", CYAN)
    try:
        from bin.run_reddit_post_instagram import run_instagram_posting
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
        from bin.run_reddit_post_bluesky import run_bluesky_posting
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
    print_banner("STEP 4 - 8: TELEGRAM AUDIT, GATEKEEPER & DB COMMIT", CYAN)
    try:
        from bin.run_reddit_audit_and_commit import run_audit_and_commit
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
    print_banner("📊 LAPORAN KEPUTUSAN UJIAN REDDIT STORYTELLER", BOLD + GREEN)
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