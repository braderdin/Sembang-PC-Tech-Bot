#!/usr/bin/env python3
"""
OpenRouter AI Persona Model Evaluation & Benchmark Tester
Lokasi Fail: experiments/test_openrouter_Ai_persona.py

Fungsi Utama:
1. Menarik 50 kelompok produk terkini daripada Supabase (Bypass tapisan Redis & Vector DB).
2. Memilih 1 produk calon secara rawak/terpilih untuk dijadikan sampel ujian.
3. Menguji 4 model OpenRouter berbeza secara berturut-turut (TEST01, TEST02, TEST03, TEST04).
4. Menjana ulasan penceritaan panjang Abang Din (Sasaran: 800 - 1000 aksara).
5. Menyokong 2x Percubaan Auto-Retry jika sesak/429 dan jeda keselamatan 5 saat antara permintaan.
6. Memaparkan metrik perbandingan (Masa Respons, Panjang Aksara, Kualiti Bahasa) di terminal.
"""

import os
import re
import sys
import time
import random
import requests
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from dotenv import load_dotenv

# 1. Konfigurasi Laluan Projek & Environment (.env.local)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

env_local = PROJECT_ROOT / ".env.local"
if env_local.exists():
    load_dotenv(dotenv_path=env_local)
else:
    load_dotenv()

# Import modul Supabase daripada src/
from src.shopee_supabase import fetch_shopee_candidates

# ANSI Colors untuk Visual Terminal Benchmark
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
RESET = "\033[0m"

SYSTEM_PROMPT = """
Anda ialah "Abang Din", pengasas dan tech specialist utama untuk "Sembang PC & Tech Malaysia".
Gaya penulisan anda mestilah SANTAI, BERCERITA (Storytelling Mendalam), INFORMATIF, KELAKAR SEMPOI, dan MESRA komuniti tech/gaming Malaysia.

PANDUAN PENULISAN ULASAN PANJANG (HAD SASARAN KETAT: 800 HINGGA 1000 AKSARA):
1. BAHASA: 100% Bahasa Melayu santai harian Malaysia ("Korang yang ada meja kerja...", "Bila tengok gajet ni...", "Memang padu gila", "Kemas habis susun atur ni").
2. DILARANG SAMA SEKALI menggunakan perkataan Bahasa Indonesia ("bisa", "banget", "nggak", "ngak", "kamu", "anda", "komputer jinjing").
3. STRUKTUR TEKS:
   - Fasa 1 (Hook & Masalah Harian): Mulakan dengan situasi masalah biasa pengguna PC/meja kerja (meja berselerak, kabel serabut, port USB tak cukup, atau barang rosak).
   - Fasa 2 (Penceritaan & Pengalaman): Ceritakan kenapa barang ini penyelamat dan bagaimana ia selesaikan masalah tersebut.
   - Fasa 3 (Ulasan Spesifikasi Padu): Senaraikan TEPAT 3 hingga 4 poin kelebihan utama menggunakan simbol bullet point (•).
   - Fasa 4 (Target Pengguna & Nilai): Terangkan siapa yang paling sesuai beli produk ini (student, streamer, gamer, orang kerja ofis).
   - Fasa 5 (Call To Action Ruangan Komen): 
     "👉 Pautan belian rasmi Shopee abang dah sediakan di ruangan komen pertama di bawah ya! 👇"
   - Fasa 6 (Hashtags Rasmi):
     #SembangPCTech #TechMalaysia #PCSetup #RacunGajet #ShopeeMY

ARAHAN PANTANGAN KETAT:
- DILARANG letak sebarang pautan URL di dalam teks janaan.
- TERUS TULIS AYAT KANDUNGAN TANPA sebarang mukadimah AI seperti "Berikut ulasan...", "Caption:", atau tag pemikiran (<think>).
"""


def clean_glitches_and_reasoning(text: str) -> str:
    """Membersihkan tag reasoning, token LLM, dan mukadimah AI."""
    if not text:
        return ""

    # 1. Buang tag pemikiran reasoning model AI (<think>...</think>)
    text = re.sub(r'<think>[\s\S]*?</think>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'(?i)here\'?s\s+a\s+thinking\s+process[\s\S]*?\n\n', '', text)
    text = re.sub(r'(?i)^\s*analyze\s+the\s+request[\s\S]*?\n\n', '', text)

    # 2. Buang token khas LLM
    text = re.sub(r'<pad>|<unk>|<s>|</s>|\[PAD\]|\[UNK\]|<\|.*?\|>', '', text, flags=re.IGNORECASE)

    # 3. Standardkan bullet points
    for sym in ["❖", "◆", "◇", "►", "▪", "▲", "★", "➡", "➢", "*", "-"]:
        text = text.replace(sym, "•")

    # 4. Buang mukadimah pembantu AI
    text = re.sub(r'(?i)^\s*(?:yo|hai|salam|hello)?[^\n]*?(?:cadangan|kapsyen|caption|ulasan)[^\n]*?\n+', '', text)
    text = re.sub(r'(?i)\*\*caption\s*(?:facebook)?\s*:\*\*', '', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'\*\*\*', '', text)

    # 5. Susun baris perenggan yang kemas
    lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in text.splitlines()]
    return "\n".join([line for line in lines if line]).strip()


def call_openrouter_model(
    base_url: str,
    api_key: str,
    model_name: str,
    product_data: Dict[str, Any],
    temperature: float = 0.65,
    max_tokens: int = 1000
) -> Tuple[bool, Optional[str], float, str]:
    """
    Memanggil satu model spesifik di OpenRouter dengan 2x percubaan.
    Memulangkan: (success_bool, generated_text, response_time_seconds, status_message)
    """
    if not model_name:
        return False, None, 0.0, "Nama model kosong / tidak dikonfigurasi dalam .env.local"

    title = product_data.get("title", "Aksesori PC")
    brand = product_data.get("brand", "Pilihan Ramai")
    category = product_data.get("category", "Aksesori PC & Gajet")
    price = product_data.get("price", 0.0)
    price_str = f"RM {price:.2f}" if price > 0 else "Tawaran Menarik"
    image_url = product_data.get("picture_url", "")

    user_prompt = f"""
Sila hasilkan 1 ulasan mendalam & bercerita santai Abang Din (Sasaran: 800 - 1000 aksara) untuk produk ini:
- Tajuk Produk: {title}
- Jenama: {brand}
- Kategori: {category}
- Harga Jualan: {price_str}
- Rujukan Gambar Produk: {image_url}

Sila teliti fungsi produk daripada tajuk & kategori di atas. Hasilkan penceritaan yang padu mengikut semua peraturan sistem prompt!
"""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json; charset=utf-8",
        "HTTP-Referer": "https://sembangpctech.local",
        "X-Title": "Sembang PC & Tech Persona Benchmark",
    }

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT.strip()},
            {"role": "user", "content": user_prompt.strip()},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    endpoint = f"{base_url.rstrip('/')}/chat/completions"

    for attempt in range(2):
        start_time = time.time()
        try:
            res = requests.post(endpoint, json=payload, headers=headers, timeout=35)
            elapsed = time.time() - start_time
            res.encoding = "utf-8"

            if res.status_code == 200:
                data = res.json()
                if "choices" in data and len(data["choices"]) > 0:
                    raw_text = data["choices"][0]["message"]["content"].strip()
                    cleaned_text = clean_glitches_and_reasoning(raw_text)
                    return True, cleaned_text, elapsed, f"HTTP 200 (Percubaan {attempt + 1})"

            # Jika terkena 429 atau 502/503, lakukan jeda rehat sebelum percubaan ke-2
            if res.status_code in [429, 502, 503]:
                wait_sec = 6 * (attempt + 1)
                print(f"    {YELLOW}⚠️ [HTTP {res.status_code}] Model sesak. Rehat {wait_sec}s sebelum percubaan {attempt + 2}...{RESET}")
                time.sleep(wait_sec)
            else:
                err_msg = res.text[:120]
                print(f"    {RED}⚠️ [HTTP {res.status_code}] Ralat: {err_msg}{RESET}")
                if attempt == 0:
                    time.sleep(3)

        except Exception as e:
            elapsed = time.time() - start_time
            print(f"    {RED}⚠️ [EXCEPTION] {str(e)}{RESET}")
            if attempt == 0:
                time.sleep(3)

    return False, None, 0.0, "Gagal selepas 2x percubaan (Rate Limit / Timeout)"


def run_persona_benchmark():
    print(f"\n{BOLD}{CYAN}{'=' * 80}")
    print(f" 🧪 OPENROUTER AI PERSONA BENCHMARK & MODEL DEBUGGER (800 - 1000 AKSARA)")
    print(f"{'=' * 80}{RESET}\n")

    # 1. Baca Konfigurasi daripada .env.local
    base_url = (os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1").strip()
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()

    test_models = [
        ("MODEL_TEST01", os.getenv("OPENROUTER_MODEL_TEST01", "").strip()),
        ("MODEL_TEST02", os.getenv("OPENROUTER_MODEL_TEST02", "").strip()),
        ("MODEL_TEST03", os.getenv("OPENROUTER_MODEL_TEST03", "").strip()),
        ("MODEL_TEST04", os.getenv("OPENROUTER_MODEL_TEST04", "").strip()),
    ]

    print(f"⚙️  {BOLD}Konfigurasi Ujian:{RESET}")
    print(f"   • Base URL    : {base_url}")
    print(f"   • API Key     : {'✔ Dikesan' if api_key else '❌ Kunci Tiada'}")
    for label, m_name in test_models:
        print(f"   • {label:<15}: {m_name if m_name else '(Kosong / Tidak Ditetapkan)'}")

    if not api_key:
        print(f"\n{RED}❌ [ABORT] OPENROUTER_API_KEY tidak dijumpai dalam .env.local!{RESET}\n")
        return

    # 2. Tarik 50 Calon Produk daripada Supabase (Tanpa Tapisan Redis/Vector)
    print(f"\n📦 {BOLD}Menarik 50 Calon Produk daripada Supabase...{RESET}")
    ok_fetch, candidates, msg = fetch_shopee_candidates(limit=50, offset=0)

    if not ok_fetch or not candidates:
        print(f"{RED}❌ Gagal menarik produk daripada Supabase: {msg}{RESET}\n")
        return

    print(f"{GREEN}✅ Berjaya memuat turun {len(candidates)} calon produk daripada pangkalan data.{RESET}")

    # 3. Pilih 1 Produk Calon
    selected_raw = random.choice(candidates)
    product_id = str(selected_raw.get("shopee_product_id") or selected_raw.get("product_id") or "N/A").strip()
    title = str(selected_raw.get("shopee_product_name") or selected_raw.get("product_name") or selected_raw.get("title") or "Produk Shopee").strip()
    brand = str(selected_raw.get("shopee_brand") or selected_raw.get("brand") or "Pilihan Ramai").strip()
    category = str(selected_raw.get("shopee_category") or selected_raw.get("category") or "Aksesori PC & Gajet").strip()
    raw_price = selected_raw.get("shopee_price") or selected_raw.get("price") or 0.0
    try:
        clean_price = float(raw_price)
    except Exception:
        clean_price = 0.0
    image_url = str(selected_raw.get("shopee_picture_url") or selected_raw.get("picture_url") or "").strip()

    product_data = {
        "product_id": product_id,
        "title": title,
        "brand": brand,
        "category": category,
        "price": clean_price,
        "picture_url": image_url,
    }

    print(f"\n🎯 {BOLD}{MAGENTA}[PRODUK UJIAN TERPILIH]:{RESET}")
    print(f"   🆔 {BOLD}ID Produk{RESET} : {product_id}")
    print(f"   📦 {BOLD}Tajuk    {RESET} : {title}")
    print(f"   🏷️ {BOLD}Kategori {RESET} : {category} (Jenama: {brand})")
    print(f"   💰 {BOLD}Harga    {RESET} : RM {clean_price:.2f}" if clean_price > 0 else "   💰 Harga    : Tawaran Menarik")
    print(f"   🖼️ {BOLD}Gambar   {RESET} : {image_url}")

    # 4. Larian Ujian Merentasi 4 Model Terpilih
    benchmark_summary = []

    for idx, (label, model_name) in enumerate(test_models, 1):
        print(f"\n{BOLD}{CYAN}{'─' * 80}")
        print(f" 🚀 PUSINGAN {idx}/4: Menguji {label} ➔ '{model_name}'")
        print(f"{'─' * 80}{RESET}")

        if not model_name:
            print(f"{YELLOW}⚠️  {label} tidak ditetapkan dalam .env.local. Melangkau ujian ini.{RESET}")
            benchmark_summary.append({
                "label": label,
                "model": "KOSONG",
                "status": "SKIPPED",
                "chars": 0,
                "time": 0.0,
            })
            continue

        print(f"🤖 Menghantar prompt ke {model_name} (Temp: 0.65, Max Tokens: 1000)...")
        ok_call, generated_text, response_time, status_info = call_openrouter_model(
            base_url=base_url,
            api_key=api_key,
            model_name=model_name,
            product_data=product_data,
            temperature=0.65,
            max_tokens=1000,
        )

        if ok_call and generated_text:
            char_count = len(generated_text)
            status_badge = f"{GREEN}BERJAYA ({char_count} aksara){RESET}"
            
            print(f"\n{GREEN}✔ [HASIL JANAAN AI - {model_name} ({char_count} aksara | {response_time:.2f}s)]:{RESET}")
            print(f"{'┄' * 70}")
            print(generated_text)
            print(f"{'┄' * 70}")

            # Semakan kriteria panjang teks sasaran (800 - 1000 aksara)
            if 800 <= char_count <= 1000:
                print(f"🎯 {GREEN}Kualiti Panjang: SEMPURNA (Dalam Zon 800 - 1000 aksara){RESET}")
            elif char_count < 800:
                print(f"⚠️  {YELLOW}Kualiti Panjang: AGAK PENDEK ({char_count}/800 aksara){RESET}")
            else:
                print(f"⚠️  {YELLOW}Kualiti Panjang: TERLEBIH SASARAN ({char_count}/1000 aksara){RESET}")

            benchmark_summary.append({
                "label": label,
                "model": model_name,
                "status": "SUCCESS",
                "chars": char_count,
                "time": response_time,
            })
        else:
            print(f"\n{RED}✖ [GAGAL] {status_info}{RESET}")
            benchmark_summary.append({
                "label": label,
                "model": model_name,
                "status": "FAILED",
                "chars": 0,
                "time": 0.0,
            })

        # Jeda masa 5 saat antara setiap permintaan model bagi mengelakkan sekatan OpenRouter
        if idx < len(test_models):
            print(f"\n⏳ {YELLOW}Berehat 5 saat sebelum memanggil model seterusnya bagi mengelakkan Burst Limit...{RESET}")
            time.sleep(5)

    # 5. Ringkasan Skor & Keputusan Benchmark
    print(f"\n{BOLD}{GREEN}{'=' * 80}")
    print(f" 📊 JADUAL KEPUTUSAN BENCHMARK MODEL OPENROUTER")
    print(f"{'=' * 80}{RESET}\n")

    print(f" {'LABEL':<16} | {'MODEL NAME':<34} | {'STATUS':<10} | {'AKSARA':<10} | {'MASA (s)':<8}")
    print(f" {'-' * 16}-+-{'-' * 34}-+-{'-' * 10}-+-{'-' * 10}-+-{'-' * 8}")

    for row in benchmark_summary:
        st_color = GREEN if row['status'] == "SUCCESS" else (YELLOW if row['status'] == "SKIPPED" else RED)
        char_display = f"{row['chars']} aksara" if row['chars'] > 0 else "-"
        time_display = f"{row['time']:.2f}s" if row['time'] > 0 else "-"
        print(f" {row['label']:<16} | {row['model'][:34]:<34} | {st_color}{row['status']:<10}{RESET} | {char_display:<10} | {time_display:<8}")

    print(f"\n{BOLD}{'=' * 80}{RESET}\n")


if __name__ == "__main__":
    run_persona_benchmark()