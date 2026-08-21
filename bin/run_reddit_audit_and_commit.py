#!/usr/bin/env python3
"""
Reddit Tech Storyteller Engine: Step 4, 5, 6 & 7 (Audit & Commit Module)
Lokasi Fail: bin/run_reddit_audit_and_commit.py

Aliran Kerja (Workflow Runner):
1. Membaca fail 'temp/reddit_payload.json'.
2. Step 4: Menghantar laporan audit komprehensif ke saluran Telegram (Kad Ringkasan Visual + 4 Kapsyen Teks AI).
3. Semakan Pintu Keselamatan (Safety Gatekeeper):
   - Memastikan sekurang-kurangnya SATU (1) platform media sosial berjaya membuat hantaran.
   - Jika SEMUA platform gagal: Batalkan transaksi serta-merta tanpa merekodkan ID pos ke pangkalan data supaya topik ini tidak terbakar dan boleh dicuba semula.
4. Step 5: Merekodkan ID pos Reddit ke Upstash Redis (Kunci: 'reddit:post:<id>', TTL 30 Hari).
5. Step 6: Merekodkan embedding tajuk cerita ke Upstash Vector DB (ID: 'rd_<id>', Metadata: 'reddit').
6. Step 7: Membersihkan dan memadam fail payload sementara 'temp/reddit_payload.json'.
"""

import os
import sys
import json
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
from src.reddit_telegram_audit import send_reddit_audit_report, has_successful_post
from src.reddit_redis_filter import mark_reddit_post_processed
from src.reddit_vector_filter import mark_reddit_vector_posted

PAYLOAD_FILE = PROJECT_ROOT / "temp" / "reddit_payload.json"


def cleanup_temp_files():
    """Memadam fail sementara payload selepas semua langkah transaksi berjaya disempurnakan."""
    try:
        if PAYLOAD_FILE.exists():
            PAYLOAD_FILE.unlink()
            print(f"🧹 [CLEANUP] Fail sementara '{PAYLOAD_FILE.name}' berjaya dibersihkan.")
    except Exception as e:
        print(f"⚠️ [CLEANUP WARN] Gagal memadam fail payload sementara: {e}")


def run_audit_and_commit():
    print("\n" + "=" * 70)
    print("📊 [START] MEMULAKAN AUDIT TELEGRAM & KOMIT TRANSAKSI REDDIT STORYTELLER")
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

    post_id = str(payload.get("post_id") or "").strip()
    title = str(payload.get("title") or "Topik Reddit Tech").strip()
    subreddit = str(payload.get("subreddit") or "tech").strip()
    post_results = payload.get("post_results", {})

    print(f"📌 Subreddit : r/{subreddit}")
    print(f"📖 Tajuk     : {title}")
    print(f"🆔 Post ID   : {post_id}")

    # =========================================================================
    # STEP 4: HANTAR LAPORAN AUDIT LENGKAP KE BOT TELEGRAM
    # =========================================================================
    print("\n📢 [STEP 4] Menghantar laporan audit terperinci ke Telegram Bot...")
    audit_ok, audit_msg = send_reddit_audit_report(payload)
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
        print("🛑 Transaksi ke Upstash Redis dan Vector DB DIBATALKAN.")
        print("ℹ️  Pos Reddit ini TIDAK akan direkodkan sebagai pernah digunakan supaya boleh dicuba semula.")
        print("!" * 70)

        # Paparkan senarai ralat platform untuk rujukan log debugging
        for platform, res in post_results.items():
            err_detail = res.get("error", "Status bukan success") if isinstance(res, dict) else "Tiada maklumat"
            print(f"   • {platform.capitalize()}: {err_detail}")

        sys.exit(1)

    print("\n✅ [GATEKEEPER PASSED] Sekurang-kurangnya 1 platform berjaya membuat hantaran. Meneruskan komit...")

    # =========================================================================
    # STEP 5: REKOD KUNCI KE UPSTASH REDIS (TTL 30 HARI)
    # =========================================================================
    print(f"\n💾 [STEP 5] Merekodkan kunci ID pos ke Upstash Redis...")
    redis_ok = mark_reddit_post_processed(post_id)
    if redis_ok:
        print(f"✅ Redis: Kunci 'reddit:post:{post_id}' dikunci selama 30 hari.")
    else:
        print(f"⚠️ [REDIS WARN] Gagal merekodkan kunci pos ke Redis.")

    # =========================================================================
    # STEP 6: REKOD EMBEDDING KE UPSTASH VECTOR DB (72 JAM WINDOW)
    # =========================================================================
    print(f"\n🟢 [STEP 6] Menyimpan embedding tajuk ke Upstash Vector DB...")
    vector_ok = mark_reddit_vector_posted(post_id, title)
    if vector_ok:
        print(f"✅ Vector DB: Embedding 'rd_{post_id}' (Metadata: 'reddit') berjaya direkodkan.")
    else:
        print(f"⚠️ [VECTOR WARN] Gagal merekodkan embedding cerita ke Vector DB.")

    # =========================================================================
    # STEP 7: PADAM FAIL SEMENTARA PAYLOAD
    # =========================================================================
    print(f"\n🧹 [STEP 7] Membersihkan fail sementara...")
    cleanup_temp_files()

    print("\n" + "=" * 70)
    print("🎉 [SUCCESS] Seluruh aliran penceritaan Reddit Feed selesai dengan jayanya!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    run_audit_and_commit()