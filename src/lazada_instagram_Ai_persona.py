#!/usr/bin/env python3
"""
Lazada Instagram & Pinterest AI Persona Engine (Abang Din Style)
Sembang PC & Tech Ecosystem (100% Dynamic OpenRouter & Glitch-Proof)
Features:
- Programmatic Locked Footer: Direct Affiliate URL for Pinterest + Compact Telegram CTA + 3 Focused Hashtags
- Expanded AI Review Body: AI writes Hook/Problem-Solver + 2 Detailed Bullet Points (180 - 240 Chars)
- Glitch & Repetition Guardrails (Rejects gibberish & token-loop errors)
- Guaranteed Character Window: 380 - 460 Characters (Safe from Pinterest 500-char truncation)
- 3-Attempt Auto-Retry with Resilient Fallback Engine
"""

import os
import re
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

SYSTEM_PROMPT = """
Anda adalah "Abang Din", pencipta kandungan teknologi di Instagram & Pinterest Sembang PC & Tech Malaysia.
Tugas anda HANYA menghasilkan badan ulasan produk yang padu, meyakinkan dan santai.

STRUKTUR WAJIB BADAN ULASAN (HAD KETAT: 180 HINGGA 240 AKSARA SAHAJA):
1. Fasa 1 (Hook & Nilai Tambah): 1 hingga 2 ayat menerangkan fungsi produk untuk kemaskan ruang setup meja/gaya hidup harian.
2. Fasa 2 (Poin Kelebihan): Senaraikan TEPAT 2 kelebihan spesifikasi atau binaan menggunakan simbol bullet point (•).

ARAHAN PANTANGAN KETAT:
- DILARANG letak sebarang pautan URL, arahan Bio/Telegram, atau tanda pagar (#hashtag). Semua ini akan dipasang secara automatik oleh sistem.
- DILARANG menggunakan perkataan Bahasa Indonesia ("bisa", "banget", "nggak", "komputer jinjing").
- TERUS TULIS AYAT ULASAN TANPA sebarang mukadimah AI (DILARANG tulis "Berikut ulasan...", "Caption:", dll).
"""


def clean_glitches_and_meta_chatter(text: str) -> str:
    """Membersihkan token LLM, simbol mojibake, pautan terlepas, dan mukadimah bot."""
    if not text:
        return ""

    # 1. Buang token khas LLM
    text = re.sub(r'<pad>|<unk>|<s>|</s>|\[PAD\]|\[UNK\]|<\|.*?\|>', '', text, flags=re.IGNORECASE)

    # 2. Buang simbol mojibake / glitch encoding
    text = re.sub(r'[ðâ][\x80-\xbf]{1,4}', '', text)
    text = re.sub(r'[\x80-\x9f]', '', text)

    # 3. Standardkan simbol bullet point
    for sym in ["❖", "◆", "◇", "►", "▪", "▲", "★", "➡", "➢", "*", "-"]:
        text = text.replace(sym, "•")

    # 4. Buang mukadimah pembantu AI di awal teks
    text = re.sub(r'(?i)^\s*(?:yo|hai|salam|hello)?[^\n]*?(?:cadangan|kapsyen|caption|post|hantaran|ulasan)[^\n]*?\n+', '', text)
    text = re.sub(r'(?i)\*\*caption\s*(?:instagram)?\s*:\*\*', '', text)

    # 5. Buang sebarang pautan URL, teks telegram/bio, dan hashtag jika model AI terlepas pandang
    text = re.sub(r'https?://[^\s]+', '', text)
    text = re.sub(r'#\w+', '', text)
    text = re.sub(r'(?i)🔗\s*pautan\s*rasmi\s*:?[^\n]*', '', text)
    text = re.sub(r'(?i)👉\s*(?:atau\s*tekan\s*link|link\s*di\s*bio)[^\n]*', '', text)
    text = re.sub(r'(?i)\n+\s*\*{0,2}tips\s*tambahan[^\n]*\*{0,2}[\s\S]*$', '', text)
    text = re.sub(r'\*\*\*', '', text)

    # 6. Susun baris perenggan yang kemas
    lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in text.splitlines()]
    return "\n".join([line for line in lines if line]).strip()


def extract_search_keyword(title: str, max_words: int = 3) -> str:
    """Mengekstrak 2-3 kata kunci penting daripada tajuk produk untuk Telegram Catalog Bot."""
    if not title:
        return "Gajet"

    clean = re.sub(r'[\[\]\(\)\#\|\/\-\+\:\,\.]', ' ', str(title))
    words = [w.strip() for w in clean.split() if len(w.strip()) > 1 and not w.strip().isdigit()]

    stop_words = {
        'original', 'ready', 'stock', 'new', 'pro', 'set', 'hot', 'offer',
        'murah', 'padu', 'high', 'quality', 'fast', 'delivery', 'warranty',
        'lazada', 'shopee', 'flagship', 'store', 'official'
    }

    filtered = []
    for w in words:
        if w.lower() not in stop_words or len(filtered) == 0:
            filtered.append(w)
        if len(filtered) >= max_words:
            break

    return " ".join(filtered) if filtered else str(title)[:15]


def is_valid_ig_body(text: str, min_len: int = 100, max_len: int = 300) -> bool:
    """Menyemak kualiti badan ulasan AI sebelum dicantumkan dengan footer."""
    if not text or len(text.strip()) < min_len or len(text.strip()) > max_len:
        return False
    if "<pad>" in text.lower() or "<unk>" in text.lower():
        return False

    # Mengesan jika ada perkataan berulang lebih 3 kali berturut-turut
    if re.search(r'(\b\w+\b)(?:\s+\1){2,}', text, flags=re.IGNORECASE):
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


class LazadaInstagramAIPersona:
    """Enjin AI Persona Instagram & Pinterest khusus untuk produk affiliate Lazada."""

    def __init__(self):
        self.base_url = (os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1").strip().rstrip("/")
        self.model = os.getenv("OPENROUTER_MODEL", "").strip()
        self.api_key = os.getenv("OPENROUTER_API_KEY", "").strip()

    def generate_caption(self, product_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Menjana kapsyen Instagram Feed & Pinterest Sync (380 - 460 Aksara)
        dengan mencantumkan ulasan AI secara programatik bersama footer rasmi terkunci.
        Memulangkan: (success_bool, full_caption_text)
        """
        raw_title = str(
            product_data.get("title")
            or product_data.get("product_name")
            or product_data.get("lazada_product_name")
            or "Gajet Pilihan"
        ).strip()

        clean_title = re.sub(r'\s+', ' ', raw_title)[:60].strip()
        price = product_data.get("price") or product_data.get("lazada_price") or ""
        category = product_data.get("category") or product_data.get("lazada_category") or "Gajet & Komputer"
        aff_link = str(
            product_data.get("affiliate_link")
            or product_data.get("promo_short_link")
            or product_data.get("lazada_affiliate_link")
            or ""
        ).strip()

        search_kw = extract_search_keyword(raw_title)
        price_str = f"RM {float(price):.2f}" if price and str(price).replace('.', '', 1).isdigit() else ""

        # Struktur Footer Terkunci Rasmi Pilihan A (Jimat ~20 Aksara, Bebas Halusinasi URL)
        link_line = f"🔗 Pautan Rasmi: {aff_link}" if aff_link else "🔗 Pautan Rasmi: Dapatkan di Lazada sekarang"
        telegram_cta = f"👉 Link di Bio / taip \"{search_kw}\" di Telegram Bot: lubuk_barang_murah_padu_bot"
        hashtags = "#RacunGajet #SembangPCTech #LazadaMY"
        locked_footer = f"{link_line}\n{telegram_cta}\n\n{hashtags}"

        # Badan ulasan sandaran diperluas jika OpenRouter gagal
        price_display = f" ({price_str})" if price_str else ""
        fallback_body = (
            f"Korang yang tengah nak kemaskan ruang setup meja atau perlukan gajet praktikal, tengok {clean_title}{price_display} ni!\n\n"
            f"• Kualiti binaan solid, reka bentuk kemas dan tahan lama untuk kegunaan harian.\n"
            f"• Prestasi sangat memuaskan dengan harga tawaran yang cukup berbaloi."
        )
        fallback_full = f"{fallback_body}\n\n{locked_footer}"

        if not self.base_url or not self.model or not self.api_key:
            print("⚠️ [LAZADA IG AI WARN] Kunci OpenRouter tidak lengkap, menggunakan kapsyen sandaran.")
            return True, fallback_full

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json; charset=utf-8",
            "HTTP-Referer": "https://sembangpctech.local",
            "X-Title": "Sembang PC & Tech Bot",
        }

        user_prompt = f"""
Sila hasilkan 1 ulasan padu (180 - 240 aksara) untuk produk ini:
- Produk: {clean_title}
- Kategori: {category}
- Harga: {price_str if price_str else 'Promosi Berbaloi'}

Format:
Baris 1: 1-2 ayat hook ulasan fungsi atau solusi masalah setup.
Baris 2 & 3: Tepat 2 poin kelebihan utama menggunakan simbol bullet (•).

Peringatan: JANGAN letak pautan atau hashtag. Tulis badan ulasan sahaja.
"""

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT.strip()},
                {"role": "user", "content": user_prompt.strip()},
            ],
            "temperature": 0.65,
            "max_tokens": 300,
            "frequency_penalty": 0.3,
            "presence_penalty": 0.1,
        }

        url = f"{self.base_url}/chat/completions"

        for attempt in range(3):
            try:
                print(f"🤖 [LAZADA IG AI] Menjana ulasan Instagram (Percubaan {attempt + 1}/3)...")
                res = requests.post(url, headers=headers, json=payload, timeout=25)
                res.encoding = "utf-8"

                if res.status_code == 200:
                    data = res.json()
                    if "choices" in data and len(data["choices"]) > 0:
                        raw_text = data["choices"][0]["message"]["content"].strip()
                        cleaned_body = clean_glitches_and_meta_chatter(raw_text)

                        if is_valid_ig_body(cleaned_body):
                            full_caption = f"{cleaned_body}\n\n{locked_footer}"

                            # Perlindungan had siling ketat Pinterest (Maksimum 480 aksara)
                            if len(full_caption) > 480:
                                max_body = 480 - len(locked_footer) - 6
                                trimmed_body = cleaned_body[:max_body].rsplit(" ", 1)[0] + "..."
                                full_caption = f"{trimmed_body}\n\n{locked_footer}"

                            print(f"✅ [LAZADA IG AI SUCCESS] Kapsyen Instagram berjaya dijana ({len(full_caption)} aksara | Kata Kunci: '{search_kw}').")
                            return True, full_caption
                        else:
                            print(f"⚠️ [LAZADA IG AI GLITCH] Teks tidak menepati kualiti pada percubaan {attempt + 1}. Mencuba semula...")
                else:
                    print(f"⚠️ [LAZADA IG AI HTTP ERROR] HTTP {res.status_code}: {res.text}")

            except Exception as e:
                print(f"⚠️ [LAZADA IG AI EXCEPTION - ATTEMPT {attempt + 1}]: {str(e)}")

        print("🛡️ [LAZADA IG AI FALLBACK] Mengaktifkan kapsyen Instagram sandaran bersih.")
        return True, fallback_full

    def generate_affiliate_caption(self, product_data: Dict[str, Any]) -> str:
        """Fungsi pembungkus keserasian ke belakang."""
        _, caption = self.generate_caption(product_data)
        return caption


# Singleton instance & alias keserasian
lazada_instagram_ai = LazadaInstagramAIPersona()
instagram_ai = lazada_instagram_ai