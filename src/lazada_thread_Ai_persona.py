#!/usr/bin/env python3
"""
Lazada Meta Threads AI Persona Engine (Brader Din Style - Sembang PC & Tech)
Sembang PC & Tech Ecosystem (100% Dynamic OpenRouter & Glitch-Proof)
Features:
- Meta Threads Micro-Blogging (Hard Limit <= 480 Characters)
- Structure: Hook Pantas + Ulasan Padat (1-2 Poin) + Soalan Interaksi Komuniti + Pautan Rasmi Lazada + Hashtags
- Programmatic Link & Hashtag Injection (Guaranteed zero URL hallucination)
- Guardrails: Malay Anchor Words, Anti-Repetition Loop, Token Glitch Filtering
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

# Senarai kata sauh Bahasa Melayu untuk pengesahan kualiti Threads
MALAY_ANCHOR_WORDS = {
    "yang", "dan", "di", "ke", "kat", "ni", "tu", "dah", "nak", "ada",
    "kita", "korang", "saya", "buat", "bila", "dengan", "pun", "rasa",
    "meja", "setup", "pc", "kerja", "santai", "tengok", "dalam", "untuk",
    "tak", "bukan", "memang", "lagi", "padu", "mantap", "kemas", "murah",
    "berbaloi", "gila", "gaming", "racun"
}

SYSTEM_PROMPT = """
Anda ialah Penulis Kandungan Meta Threads (@braderdin360 / Sembang PC & Tech Malaysia).
Format penulisan anda ialah MIKRO-BLOG (Sangat Ringkas, Padat, Santai, Spontan & Interaktif).

STRUKTUR WAJIB TEKS THREADS (ZON EMAS: 150 HINGGA 250 AKSARA):
1. Fasa 1 (Hook & Ulasan Pantas):
   - Nyatakan kelebihan gajet/aksesori PC ini dengan gaya "racun tech" santai harian Malaysia.
   - Nyatakan jenama dan anggaran harga jika disediakan.
2. Fasa 2 (Soalan Interaktif):
   - Akhiri ayat dengan 1 soalan santai dan spontan untuk ajak pengikut berbalas komen di Threads (contoh: "Korang rasa berbaloi tak grab?", "Korang suka jenis minimalis macam ni ke?").

PANDUAN KETAT:
- WAJIB hasilkan teks ulasan antara 150 HINGGA 250 AKSARA SAHAJA.
- DILARANG letak sebarang pautan URL atau hashtag (pautan dan hashtag akan dimasukkan secara automatik oleh sistem).
- DILARANG gunakan perkataan Bahasa Indonesia ("bisa", "banget", "nggak", "komputer jinjing").
- TERUS TULIS AYAT KANDUNGAN TANPA sebarang mukadimah AI (DILARANG tulis "Berikut ulasan...", "Threads:", dll).
"""


def clean_threads_text(text: str) -> str:
    """Membersihkan token LLM, simbol asing, dan mukadimah AI."""
    if not text:
        return ""

    # 1. Buang token khas LLM
    text = re.sub(r'<pad>|<unk>|<s>|</s>|\[PAD\]|\[UNK\]|<\|.*?\|>', '', text, flags=re.IGNORECASE)

    # 2. Buang simbol mojibake / glitch encoding
    text = re.sub(r'[ðâ][\x80-\xbf]{1,4}', '', text)
    text = re.sub(r'[\x80-\x9f]', '', text)

    # 3. Buang mukadimah pembantu AI di awal teks
    text = re.sub(r'(?i)^\s*(?:yo|hai|salam|hello)?[^\n]*?(?:cadangan|kapsyen|caption|post|hantaran)[^\n]*?\n+', '', text)
    text = re.sub(r'(?i)\*\*caption\s*(?:threads)?\s*:\*\*', '', text)

    # 4. Buang sebarang link URL atau hashtag jika AI terlepas pandang
    text = re.sub(r'https?://[^\s]+', '', text)
    text = re.sub(r'#\w+', '', text)

    # 5. Kemaskan perenggan dan ruang kosong
    lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in text.splitlines()]
    return "\n".join([line for line in lines if line]).strip()


def is_valid_threads_body(text: str, min_len: int = 60, max_len: int = 320) -> bool:
    """Menyemak kualiti ulasan Threads bagi menghalang ralat degenerasi token."""
    if not text or len(text.strip()) < min_len or len(text.strip()) > max_len:
        return False
    if "<pad>" in text.lower() or "<unk>" in text.lower():
        return False

    # Mengesan perkataan berulang lebih 3 kali berturut-turut
    if re.search(r'(\b\w+\b)(?:\s+\1){2,}', text, flags=re.IGNORECASE):
        return False

    words = [w.lower() for w in re.findall(r'\b[a-zA-Z]+\b', text)]
    total_words = len(words)
    if total_words < 10:
        return False

    unique_words = set(words)
    if len(unique_words) / total_words < 0.45:
        return False

    word_counts = Counter(words)
    for word, count in word_counts.items():
        if len(word) >= 4 and (count / total_words) > 0.25:
            return False

    matching_anchors = unique_words.intersection(MALAY_ANCHOR_WORDS)
    if len(matching_anchors) < 2:
        return False

    return True


class LazadaThreadsAIPersona:
    """Enjin AI Persona Meta Threads khusus untuk produk affiliate Lazada."""

    def __init__(self):
        self.base_url = (os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1").strip().rstrip("/")
        self.model = os.getenv("OPENROUTER_MODEL", "").strip()
        self.api_key = os.getenv("OPENROUTER_API_KEY", "").strip()

    def generate_caption(self, product_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Menjana kapsyen Meta Threads lengkap dengan had ketat (Hard Limit <= 480 Aksara).
        Memulangkan: (success_bool, full_caption_text)
        """
        raw_title = str(
            product_data.get("title")
            or product_data.get("product_name")
            or product_data.get("lazada_product_name")
            or "Aksesori Komputer Pilihan"
        ).strip()

        clean_title = re.sub(r'\s+', ' ', raw_title)[:65].strip()
        brand = str(product_data.get("brand") or product_data.get("lazada_brand") or "").strip()
        price = product_data.get("price") or product_data.get("lazada_price") or ""
        aff_link = str(
            product_data.get("affiliate_link")
            or product_data.get("promo_short_link")
            or product_data.get("lazada_affiliate_link")
            or ""
        ).strip()

        price_str = f"RM {float(price):.2f}" if price and str(price).replace('.', '', 1).isdigit() else ""
        price_tag = f", harga cuma {price_str}" if price_str else ""
        brand_tag = f" dari {brand}" if brand else ""

        # Struktur footer pautan & hashtag standard
        link_footer = f"🛒 Dapatkan di Lazada: {aff_link}" if aff_link else "🛒 Dapatkan di Lazada sekarang!"
        hashtag_footer = "#SembangPCTech #LazadaMY"

        # Kapsyen sandaran jika OpenRouter gagal
        fallback_body = (
            f"Barang padu{brand_tag} ni memang tak mengecewakan{price_tag}! "
            f"Kualiti memang kemas untuk setup korang, jimat poket tapi kualiti mantap. "
            f"Korang rasa berbaloi tak sambar yang ni?"
        )
        fallback_full = f"{fallback_body}\n\n{link_footer}\n{hashtag_footer}"

        if not self.base_url or not self.model or not self.api_key:
            print("⚠️ [LAZADA THREADS AI WARN] Kunci OpenRouter tidak lengkap, menggunakan kapsyen sandaran.")
            return True, fallback_full

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json; charset=utf-8",
            "HTTP-Referer": "https://sembangpctech.local",
            "X-Title": "Sembang PC & Tech Bot",
        }

        user_prompt = f"""
Hasilkan 1 ulasan pantas Threads (150 - 250 aksara) untuk produk ini:
- Produk: {clean_title}
- Jenama: {brand if brand else 'Pilihan Ramai'}
- Harga: {price_str if price_str else 'Promosi Berbaloi'}

Peringatan: 
- Akhiri dengan 1 soalan santai.
- JANGAN sertakan link atau hashtag dalam ulasan ini.

Tulis ulasan sekarang:
"""

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT.strip()},
                {"role": "user", "content": user_prompt.strip()},
            ],
            "temperature": 0.65,
            "max_tokens": 280,
            "frequency_penalty": 0.3,
            "presence_penalty": 0.1,
        }

        url = f"{self.base_url}/chat/completions"

        for attempt in range(3):
            try:
                print(f"🤖 [LAZADA THREADS AI] Menjana kapsyen Threads (Percubaan {attempt + 1}/3)...")
                res = requests.post(url, headers=headers, json=payload, timeout=20)
                res.encoding = "utf-8"

                if res.status_code == 200:
                    data = res.json()
                    if "choices" in data and len(data["choices"]) > 0:
                        raw_text = data["choices"][0]["message"]["content"].strip()
                        cleaned_body = clean_threads_text(raw_text)

                        if is_valid_threads_body(cleaned_body):
                            full_caption = f"{cleaned_body}\n\n{link_footer}\n{hashtag_footer}"

                            # Semak had ketat 480 aksara Threads
                            if len(full_caption) > 480:
                                max_body_len = 480 - len(link_footer) - len(hashtag_footer) - 6
                                trimmed_body = cleaned_body[:max_body_len].rsplit(" ", 1)[0] + "..."
                                full_caption = f"{trimmed_body}\n\n{link_footer}\n{hashtag_footer}"

                            print(f"✅ [LAZADA THREADS AI SUCCESS] Kapsyen Threads berjaya dijana ({len(full_caption)}/480 aksara).")
                            return True, full_caption
                        else:
                            print(f"⚠️ [LAZADA THREADS AI GLITCH] Teks tidak menepati kualiti pada percubaan {attempt + 1}. Mencuba semula...")
                else:
                    print(f"⚠️ [LAZADA THREADS AI HTTP ERROR] HTTP {res.status_code}: {res.text}")

            except Exception as e:
                print(f"⚠️ [LAZADA THREADS AI EXCEPTION - ATTEMPT {attempt + 1}]: {str(e)}")

        print("🛡️ [LAZADA THREADS AI FALLBACK] Mengaktifkan kapsyen Threads sandaran bersih.")
        return True, fallback_full


# Singleton instance & alias keserasian
lazada_threads_ai = LazadaThreadsAIPersona()


def generate_threads_affiliate_caption(base_url, model, api_key, product_title, product_desc=""):
    """Fungsi pembungkus keserasian ke belakang."""
    product_data = {"title": product_title, "description": product_desc}
    _, caption = lazada_threads_ai.generate_caption(product_data)
    return caption