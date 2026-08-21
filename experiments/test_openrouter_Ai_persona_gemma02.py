#!/usr/bin/env python3
"""
Gemma Character Boundary & Special Symbol Diagnostic Tester
Lokasi Fail: experiments/test_openrouter_Ai_persona_gemma.py

Objektif:
1. Menghapuskan penetapan 'max_tokens' dalam payload (hanya gunakan arahan had aksara dalam prompt).
2. Menguji sama ada simbol khas, emoji, tag kod, atau aksara mojibake mengganggu inferens Gemma.
3. Menguji 2 model Gemma sasaran (31B & 26B MoE) dengan jeda masa 5 saat per request.
"""

import os
import sys
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

# 1. Konfigurasi Laluan Projek & Environment
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

env_local = PROJECT_ROOT / ".env.local"
load_dotenv(dotenv_path=env_local if env_local.exists() else None)

BASE_URL = (os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1").rstrip("/")
API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()

# Dua Model Gemma Sasaran
GEMMA_MODELS = [
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free"
]

# ANSI Colors
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Senarai Ujian Simbol & Beban Aksara
TEST_CASES = [
    {
        "name": "Ujian 1: Teks Standard (300-500 Aksara)",
        "prompt": "Anda ialah Abang Din. Tulis 1 ulasan santai tentang Logitech M240 RM70 dalam 300 hingga 500 aksara sahaja dalam Bahasa Melayu. Tanpa emoji dan tanpa pautan."
    },
    {
        "name": "Ujian 2: Ujian Emoji (🎧, 🛒, 💻, 🔥, 👉)",
        "prompt": "Anda ialah Abang Din 💻🎧. Ulas Logitech M240 RM70 🔥. Guna perkataan santai, hadkan 300-500 aksara dan sertakan emoji 👉🛒 di hujung teks."
    },
    {
        "name": "Ujian 3: Simbol Bullet Khas & Unicode (❖, ◆, •, ★, ➔, ±)",
        "prompt": "Anda ialah Abang Din. Ulas Logitech M240 RM70 (300-500 aksara). Senaraikan 2 kelebihan guna simbol ❖ dan ★. Uji kestabilan simbol: ➔ ± 50% •."
    },
    {
        "name": "Ujian 4: Tag Pemikiran & Sintaks Kod (<think>, ```json, { })",
        "prompt": "Arahan: <think>analisis produk</think> Tulis ulasan santai Logitech M240 RM70 dalam 300-500 aksara. Jangan keluarkan blok ```json atau tag kod."
    },
    {
        "name": "Ujian 5: Teks dengan Glitch Encoding / Corrupted Chars (â, ð, ™, ®)",
        "prompt": "Produk: Logitech M240â¢ Silent Mouse® (ð\x9f\x94\xa5). Sila abaikan aksara pelik tersebut dan tulis ulasan santai bersih dalam 300 hingga 500 aksara."
    }
]


def send_payload_without_max_tokens(model_name: str, user_prompt: str) -> dict:
    """Menghantar permintaan API tanpa pembolehubah 'max_tokens'."""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json; charset=utf-8",
        "HTTP-Referer": "https://sembangpctech.local",
        "X-Title": "Gemma Symbol Diagnostics"
    }

    # Payload bersih: TIADA max_tokens
    payload = {
        "model": model_name,
        "messages": [
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.65
    }

    start_time = time.time()
    try:
        res = requests.post(f"{BASE_URL}/chat/completions", json=payload, headers=headers, timeout=35)
        elapsed = time.time() - start_time
        res.encoding = "utf-8"

        if res.status_code == 200:
            data = res.json()
            choices = data.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content", "") or ""
                finish_reason = choices[0].get("finish_reason", "unknown")
                return {
                    "ok": True,
                    "status_code": 200,
                    "elapsed": elapsed,
                    "chars": len(content.strip()),
                    "content": content.strip(),
                    "finish_reason": finish_reason,
                    "error": None
                }
            return {
                "ok": False,
                "status_code": 200,
                "elapsed": elapsed,
                "chars": 0,
                "content": "",
                "finish_reason": "no_choices",
                "error": "Respons 'choices' kosong dari pelayan."
            }
        else:
            return {
                "ok": False,
                "status_code": res.status_code,
                "elapsed": elapsed,
                "chars": 0,
                "content": "",
                "finish_reason": "http_error",
                "error": res.text[:160]
            }

    except Exception as e:
        elapsed = time.time() - start_time
        return {
            "ok": False,
            "status_code": 0,
            "elapsed": elapsed,
            "chars": 0,
            "content": "",
            "finish_reason": "exception",
            "error": str(e)
        }


def run_gemma_symbol_diagnostics():
    print(f"\n{BOLD}{CYAN}{'=' * 85}")
    print(" 🔬 UJIAN DIAGNOSTIK GEMMA: BEBAS MAX_TOKENS & UJIAN SIMBOL/GLITCH")
    print(f"{'=' * 85}{RESET}")
    print(f"📡 Base URL : {BASE_URL}")
    print(f"🔑 API Key  : {'Dikesan (' + API_KEY[:8] + '...)' if API_KEY else 'TIADA'}")
    print("⚙️  Format   : max_tokens DIKELUARKAN (100% bergantung pada arahan aksara prompt)")
    print("⏱️  Jeda     : 5 saat antara setiap permintaan\n")

    if not API_KEY:
        print(f"{RED}❌ [ABORT] OPENROUTER_API_KEY tidak dijumpai dalam .env.local{RESET}\n")
        return

    summary_table = []

    for model in GEMMA_MODELS:
        print(f"\n{BOLD}{MAGENTA}{'━' * 85}")
        print(f" 🎯 MENGUJI MODEL: {model}")
        print(f"{'━' * 85}{RESET}\n")

        for idx, test in enumerate(TEST_CASES, 1):
            print(f"  👉 [{idx}/{len(TEST_CASES)}] {test['name']}...", end=" ", flush=True)

            res = send_payload_without_max_tokens(model, test["prompt"])

            if res["ok"]:
                print(f"{GREEN}✔ [HTTP 200]{RESET} ({res['elapsed']:.2f}s | {res['chars']} aksara | Stop: {res['finish_reason']})")
                clean_preview = res["content"][:100].replace("\n", " ")
                print(f"     Preview: \"{clean_preview}...\"")
                status_badge = "PASS"
            else:
                print(f"{RED}✖ [HTTP {res['status_code']}]{RESET} ({res['elapsed']:.2f}s)")
                print(f"     Punca  : {res['error']}")
                status_badge = f"FAIL ({res['status_code']})"

            summary_table.append({
                "model": model,
                "test": test["name"].split(":")[0],
                "status": status_badge,
                "time": f"{res['elapsed']:.2f}s",
                "chars": res["chars"]
            })

            # Jeda tepat 5 saat
            print("     ⏳ Menunggu 5 saat...")
            time.sleep(5)

    # Ringkasan Keputusan Ujian
    print(f"\n{BOLD}{GREEN}{'=' * 85}")
    print(" 📊 JADUAL KEPUTUSAN DIAGNOSTIK GEMMA TANPA MAX_TOKENS")
    print(f"{'=' * 85}{RESET}\n")
    print(f" {'MODEL':<33} | {'JENIS UJIAN':<16} | {'STATUS':<12} | {'MASA':<8} | {'SAIZ AKSARA'}")
    print(f" {'-' * 33}-+-{'-' * 16}-+-{'-' * 12}-+-{'-' * 8}-+-{'-' * 12}")

    for r in summary_table:
        st_color = GREEN if "PASS" in r["status"] else RED
        chars_txt = f"{r['chars']} aksara" if r["chars"] > 0 else "-"
        print(f" {r['model'][:33]:<33} | {r['test']:<16} | {st_color}{r['status']:<12}{RESET} | {r['time']:<8} | {chars_txt}")

    print(f"\n{BOLD}{'=' * 85}{RESET}\n")


if __name__ == "__main__":
    run_gemma_symbol_diagnostics()