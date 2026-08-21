#!/usr/bin/env python3
"""
Shopee Instagram & Pinterest AI Persona Engine (Abang Din Style)
Lokasi Fail: src/shopee_instagram_Ai_persona.py

Ciri-ciri Penambahbaikan (Tuned):
1. Sistem Dual-Model Failover: Mencuba model utama (SHOPEE_OPENROUTER_MODEL / OPENROUTER_MODEL)
   dan beralih secara automatik ke model sandaran (FALLBACK) jika berlaku HTTP 429 / 503.
2. Exponential Backoff & Pacing Delay: Menambah jeda masa rehat automatik apabila menerima
   respons 429/503 sebelum mencuba pusingan seterusnya bagi mengelakkan sekatan OpenRouter.
3. Sifar Penalti Inferens: Membuang frequency_penalty dan presence_penalty untuk kestabilan model.
4. Penapis Anti-Thinking & Glitch Scrubber: Menapis blok pemikiran (<think>...</think>), draf analisis,
   dan token rosak sebelum membina ulasan.
5. Footer Terkunci Rasmi: Ulasan padat 180-240 aksara + pautan/kata kunci Telegram + hashtags (380-460 aksara).
"""

import os
import re
import time
import requests
from collections import Counter
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from dotenv import load_dotenv

# 1. Konfigurasi Laluan Projek & Environment
PROJECT_ROOT = Path(__file__).resolve().parent.parent
env_local = PROJECT_ROOT / ".env.local"
if env_local.exists():
    load_dotenv(dotenv_path=env_local)
else:
    load_dotenv()

# Kata dasar Bahasa Melayu untuk pengesahan kualiti teks (Guardrail)
MALAY_ANCHOR_WORDS = {
    "yang", "dan", "di", "ke", "kat", "ni", "tu", "dah", "nak", "ada",
    "kita", "korang", "saya", "buat", "bila", "dengan", "pun", "rasa",
    "meja", "setup", "pc", "kerja", "santai", "tengok", "dalam", "untuk",
    "tak", "bukan", "memang", "lagi", "padu", "kemas", "hujung", "minggu",
    "malam", "pagi", "petang", "gajet", "murah", "berbaloi", "sesuai"
}

FORBIDDEN_WORDS = {
    "bisa", "banget", "nggak", "ngak", "gimana", "komputer jinjing",
    "unduh", "unggah", "ponsel", "kamu", "anda"
}

SYSTEM_PROMPT = """
Anda adalah "Abang Din", pencipta kandungan teknologi di Instagram & Pinterest Sembang PC & Tech Malaysia.
Tugas anda HANYA menghasilkan badan ulasan produk yang padu, meyakinkan dan santai.

STRUKTUR WAJIB BADAN ULASAN (HAD KETAT: 180 HINGGA 240 AKSARA SAHAJA):
1. Fasa 1 (Hook & Nilai Tambah): 1 hingga 2 ayat menerangkan fungsi produk untuk kemaskan ruang setup meja/gaya hidup harian.
2. Fasa 2 (Poin Kelebihan): Senaraikan TEPAT 2 kelebihan spesifikasi atau binaan menggunakan simbol bullet point (•).

ARAHAN PANTANGAN KETAT:
- DILARANG letak sebarang pautan URL, arahan Bio/Telegram, atau tanda pagar (#hashtag). Semua ini akan dipasang secara automatik oleh sistem.
- DILARANG menggunakan perkataan Bahasa Indonesia ("bisa", "banget", "nggak", "kamu", "anda").
- TERUS TULIS AYAT ULASAN TANPA sebarang mukadimah AI (DILARANG tulis "Berikut ulasan...", "Caption:", proses pemikiran, dll).
"""


def clean_glitches_and_meta_chatter(text: str) -> str:
    """Membersihkan tag pemikiran, token LLM, simbol mojibake, pautan, dan mukadimah bot."""
    if not text:
        return ""

    # 1. Buang sebarang blok pemikiran model reasoning
    text = re.sub(r'<think>[\s\S]*?</think>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'(?i)here\'?s\s+a\s+thinking\s+process[\s\S]*?\n\n', '', text)
    text = re.sub(r'(?i)^\s*analyze\s+the\s+request[\s\S]*?\n\n', '', text)

    # 2. Buang token khas LLM
    text = re.sub(r'<pad>|<unk>|<s>|</s>|\[PAD\]|\[UNK\]|<\|.*?\|>', '', text, flags=re.IGNORECASE)

    # 3. Buang simbol mojibake / glitch encoding
    text = re.sub(r'[ðâ][\x80-\xbf]{1,4}', '', text)
    text = re.sub(r'[\x80-\x9f]', '', text)

    # 4. Standardkan simbol bullet point
    for sym in ["❖", "◆", "◇", "►", "▪", "▲", "★", "➡", "➢", "*", "-"]:
        text = text.replace(sym, "•")

    # 5. Buang mukadimah pembantu AI di awal teks
    text = re.sub(r'(?i)^\s*(?:yo|hai|salam|hello)?[^\n]*?(?:cadangan|kapsyen|caption|post|hantaran|ulasan)[^\n]*?\n+', '', text)
    text = re.sub(r'(?i)\*\*caption\s*(?:instagram)?\s*:\*\*', '', text)

    # 6. Buang sebarang pautan URL, teks telegram/bio, dan hashtag jika model AI terlepas pandang
    text = re.sub(r'https?://[^\s]+', '', text)
    text = re.sub(r'#\w+', '', text)
    text = re.sub(r'(?i)🔗\s*pautan\s*rasmi\s*:?[^\n]*', '', text)
    text = re.sub(r'(?i)👉\s*(?:atau\s*tekan\s*link|link\s*di\s*bio)[^\n]*', '', text)
    text = re.sub(r'(?i)\n+\s*\*{0,2}tips\s*tambahan[^\n]*\*{0,2}[\s\S]*$', '', text)
    text = re.sub(r'\*\*\*', '', text)

    # 7. Susun baris perenggan yang kemas
    lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in text.splitlines()]
    return "\n".join([line for line in lines if line]).strip()


def extract_search_keyword(title: str, max_words: int = 3) -> str:
    """Mengekstrak 2-3 kata kunci penting daripada tajuk produk untuk Telegram Catalog Bot."""
    if not title:
        return "Gajet"

    clean = re.sub(r'^[\[【][^\]】]*[\]】]\s*', '', str(title))
    clean = re.sub(r'[\[\]\(\)\#\|\/\-\+\:\,\.【】]', ' ', clean)
    words = [w.strip() for w in clean.split() if len(w.strip()) > 1 and not w.strip().isdigit()]

    stop_words = {
        'original', 'ready', 'stock', 'new', 'pro', 'set', 'hot', 'offer',
        'murah', 'padu', 'high', 'quality', 'fast', 'delivery', 'warranty',
        'compatible', 'for', 'system', 'free', 'shipping', 'flagship', 'store',
        'official', 'shopee', 'lazada'
    }

    filtered = []
    for w in words:
        if w.lower() not in stop_words or len(filtered) == 0:
            filtered.append(w)
        if len(filtered) >= max_words:
            break

    return " ".join(filtered) if filtered else str(title)[:15]


def is_valid_ig_body(text: str, min_len: int = 80, max_len: int = 320) -> bool:
    """Menyemak kualiti badan ulasan AI sebelum dicantumkan dengan footer."""
    if not text or len(text.strip()) < min_len or len(text.strip()) > max_len:
        return False
    if "<pad>" in text.lower() or "<unk>" in text.lower():
        return False

    # Mengesan jika ada perkataan berulang lebih 3 kali berturut-turut
    if re.search(r'(\b\w+\b)(?:\s+\1){2,}', text, flags=re.IGNORECASE):
        return False

    lower_text = text.lower()
    for forbidden in FORBIDDEN_WORDS:
        if re.search(r'\b' + re.escape(forbidden) + r'\b', lower_text):
            return False

    words = [w.lower() for w in re.findall(r'\b[a-zA-Z]+\b', text)]
    total_words = len(words)
    if total_words < 12:
        return False

    unique_words = set(words)
    if len(unique_words) / total_words < 0.40:
        return False

    word_counts = Counter(words)
    for word, count in word_counts.items():
        if len(word) >= 4 and (count / total_words) > 0.25:
            return False

    matching_anchors = unique_words.intersection(MALAY_ANCHOR_WORDS)
    if len(matching_anchors) < 2:
        return False

    return True


class ShopeeInstagramAIPersona:
    """Enjin AI Persona Instagram & Pinterest khusus untuk produk affiliate Shopee dengan Failover."""

    def __init__(self):
        self.base_url = (os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1").strip().rstrip("/")
        self.model_primary = (
            os.getenv("SHOPEE_OPENROUTER_MODEL", "").strip()
            or os.getenv("OPENROUTER_MODEL", "").strip()
        )
        self.model_fallback = (
            os.getenv("SHOPEE_OPENROUTER_MODEL_FALLBACK", "").strip()
            or os.getenv("OPENROUTER_MODEL_FALLBACK", "").strip()
        )
        self.api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        self.temperature = 0.65
        self.max_tokens = 350
        self.cooldown_delay = 3.5

    def _call_llm_api(self, model_name: str, system_prompt: str, user_prompt: str) -> Tuple[bool, Optional[str], str]:
        """Memanggil endpoint OpenRouter API dengan mekanisme auto-backoff rehat."""
        if not self.base_url or not self.api_key or not model_name:
            return False, None, "Konfigurasi OpenRouter (Base URL, API Key, Model) tidak lengkap."

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json; charset=utf-8",
            "HTTP-Referer": "https://sembangpctech.local",
            "X-Title": "Sembang PC & Tech Shopee Instagram Storyteller",
        }

        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt.strip()},
                {"role": "user", "content": user_prompt.strip()},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        url = f"{self.base_url}/chat/completions"

        for attempt in range(2):
            try:
                res = requests.post(url, headers=headers, json=payload, timeout=25)
                res.encoding = "utf-8"

                if res.status_code in [429, 502, 503]:
                    wait_sec = 6 * (attempt + 1)
                    print(f"  ⚠️ [SHOPEE IG AI {res.status_code}] Model '{model_name}' sesak/rehat. Menunggu {wait_sec}s...")
                    time.sleep(wait_sec)
                    continue

                if res.status_code == 200:
                    data = res.json()
                    if "choices" in data and len(data["choices"]) > 0:
                        content = data["choices"][0]["message"]["content"].strip()
                        time.sleep(self.cooldown_delay)
                        return True, content, "Berjaya"
                else:
                    err_snippet = res.text[:120]
                    print(f"  ⚠️ [SHOPEE IG AI HTTP {res.status_code}]: {err_snippet}")
                    time.sleep(2)

            except Exception as e:
                print(f"  ⚠️ [SHOPEE IG AI EXCEPTION]: {e}")
                time.sleep(2)

        return False, None, f"Gagal mendapatkan respon daripada model {model_name}"

    def generate_caption(self, product_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Menjana kapsyen Instagram Feed & Pinterest Sync (380 - 460 Aksara)
        dengan mencantumkan ulasan AI secara programatik bersama footer rasmi terkunci.
        """
        raw_title = str(
            product_data.get("product_name")
            or product_data.get("shopee_product_name")
            or product_data.get("title")
            or "Aksesori Komputer Pilihan"
        ).strip()

        clean_title = re.sub(r'\s+', ' ', raw_title)[:60].strip()
        price = product_data.get("price") or product_data.get("shopee_price") or ""
        category = product_data.get("category") or product_data.get("shopee_category") or "Aksesori PC & Gajet"
        brand = str(product_data.get("brand") or product_data.get("shopee_brand") or "").strip()
        aff_link = str(
            product_data.get("affiliate_link")
            or product_data.get("shopee_affiliate_link")
            or product_data.get("promo_short_link")
            or ""
        ).strip()

        search_kw = extract_search_keyword(raw_title)
        price_str = f"RM {float(price):.2f}" if price and str(price).replace('.', '', 1).isdigit() else ""

        # Struktur Footer Terkunci Rasmi
        link_line = f"🔗 Pautan Rasmi: {aff_link}" if aff_link else "🔗 Pautan Rasmi: Dapatkan di Shopee sekarang"
        telegram_cta = f"👉 Link di Bio / taip \"{search_kw}\" di Telegram Bot: lubuk_barang_murah_padu_bot"
        hashtags = "#RacunGajet #SembangPCTech #ShopeeMY"
        locked_footer = f"{link_line}\n{telegram_cta}\n\n{hashtags}"

        # Badan ulasan sandaran diperluas
        price_display = f" ({price_str})" if price_str else ""
        brand_tag = f" daripada {brand}" if brand else ""
        fallback_body = (
            f"Korang yang tengah nak kemaskan ruang setup meja atau cari barang praktikal, tengok {clean_title}{brand_tag}{price_display} ni!\n\n"
            f"• Kualiti binaan kemas, tahan lasak & sangat memudahkan kegunaan harian.\n"
            f"• Nilai terbaik dan sangat berbaloi untuk setup kerja mahupun gaming."
        )
        fallback_full = f"{fallback_body}\n\n{locked_footer}"

        if not self.api_key:
            print("⚠️ [SHOPEE IG AI WARN] Kunci OpenRouter tiada, menggunakan kapsyen sandaran.")
            return True, fallback_full

        user_prompt = f"""
Sila hasilkan 1 ulasan padu (180 - 240 aksara) untuk produk ini:
- Produk: {clean_title}
- Jenama: {brand if brand else 'Pilihan Ramai'}
- Kategori: {category}
- Harga: {price_str if price_str else 'Promosi Berbaloi'}

Format:
Baris 1: 1-2 ayat hook ulasan fungsi atau solusi masalah setup.
Baris 2 & 3: Tepat 2 poin kelebihan utama menggunakan simbol bullet (•).

Peringatan: JANGAN letak pautan atau hashtag. Tulis badan ulasan sahaja.
"""

        models_queue = [m for m in [self.model_primary, self.model_fallback] if m]

        for model_idx, current_model in enumerate(models_queue, 1):
            print(f"📸 [SHOPEE IG AI] Mencuba Model {model_idx}/{len(models_queue)}: '{current_model}'...")
            ok_call, raw_content, msg = self._call_llm_api(current_model, SYSTEM_PROMPT, user_prompt)

            if ok_call and raw_content:
                cleaned_body = clean_glitches_and_meta_chatter(raw_content)

                if is_valid_ig_body(cleaned_body):
                    full_caption = f"{cleaned_body}\n\n{locked_footer}"

                    # Perlindungan had siling ketat (Maksimum 480 aksara)
                    if len(full_caption) > 480:
                        max_body = 480 - len(locked_footer) - 6
                        trimmed_body = cleaned_body[:max_body].rsplit(" ", 1)[0] + "..."
                        full_caption = f"{trimmed_body}\n\n{locked_footer}"

                    print(f"✅ [SHOPEE IG AI SUCCESS] Kapsyen Instagram berjaya dijana ({len(full_caption)} aksara | Model: '{current_model}').")
                    return True, full_caption
                else:
                    print(f"⚠️ [SHOPEE IG AI GUARDRAIL REJECT]: Teks ulasan tidak melepasi kriteria kualiti.")

        print("🛡️ [SHOPEE IG AI FALLBACK] Mengaktifkan kapsyen Instagram sandaran bersih.")
        return True, fallback_full

    def generate_affiliate_caption(self, product_data: Dict[str, Any]) -> str:
        """Fungsi pembungkus keserasian ke belakang."""
        _, caption = self.generate_caption(product_data)
        return caption


# Singleton instance & alias keserasian
shopee_instagram_ai = ShopeeInstagramAIPersona()
instagram_ai = shopee_instagram_ai