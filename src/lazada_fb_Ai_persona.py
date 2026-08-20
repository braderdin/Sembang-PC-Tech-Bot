#!/usr/bin/env python3
"""
Lazada Facebook AI Persona Engine (Brader Din Style - Sembang PC & Tech)
Sembang PC & Tech Ecosystem (100% Dynamic OpenRouter & Glitch-Proof)
Features:
- Facebook Feed Copywriting (Target: 500 - 700 Characters)
- 3-Phase Structure: Hook Masalah Setup -> Ulasan & 3 Poin Kelebihan -> CTA Komen Pertama Lazada
- Guardrails: Malay Anchor Words, Anti-Repetition Loop, Token Glitch Filtering
- 3-Attempt Auto-Retry with Resilient Fallback Engine
"""

import os
import re
import requests
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

# Senarai kata sauh Bahasa Melayu untuk pengesahan kualiti teks (Guardrail)
MALAY_ANCHOR_WORDS = {
    "yang", "dan", "di", "ke", "kat", "ni", "tu", "dah", "nak", "ada",
    "kita", "korang", "saya", "buat", "bila", "dengan", "pun", "rasa",
    "meja", "setup", "pc", "kerja", "santai", "tengok", "dalam", "untuk",
    "tak", "bukan", "memang", "lagi", "padu", "mantap", "kemas", "berbaloi",
    "bawah", "gajet", "dengar", "tahan", "lasak"
}

SYSTEM_PROMPT = """
Anda ialah Penulis Kandungan Rasmi untuk Facebook Page "Sembang PC & Tech Malaysia" (Gaya santai, mesra komuniti, berpengalaman bab perkakasan komputer & gajet).

STRUKTUR WAJIB KAPSYEN FACEBOOK (ZON EMAS: 500 HINGGA 700 AKSARA):
1. Fasa 1 (Hook Masalah Setup / Tech Relatable - 2 hingga 3 Baris):
   - Mulakan dengan situasi atau luahan santai yang selalu dihadapi peminat tech/gamer (contoh: meja berserabut, nak upgrade PC/laptop bajet ketat, wayar rimas, gajet lama rosak).
2. Fasa 2 (Penceritaan & Tepat 3 Poin Kelebihan):
   - Perkenalkan produk dengan ringkas dan sebut jenama sebenar (DILARANG guna frasa generik seperti "Gajet Pilihan:").
   - Senaraikan TEPAT 3 kelebihan utama produk menggunakan simbol bullet point (•).
3. Fasa 3 (Call To Action Komen Pertama - WAJIB):
   - Akhiri hantaran dengan ayat rasmi CTA Facebook:
     "👉 Pautan belian rasmi Lazada abang dah sediakan di ruangan komen pertama di bawah ya! 👇"

PANDUAN KETAT:
- WAJIB kekalkan panjang keseluruhan teks di antara 500 HINGGA 700 AKSARA.
- DILARANG letak sebarang pautan URL mentah di dalam kapsyen teks (pautan akan dipos automatik di ruangan komen).
- DILARANG gunakan perkataan Bahasa Indonesia ("bisa", "banget", "nggak", "komputer jinjing").
- TERUS TULIS AYAT KANDUNGAN TANPA sebarang mukadimah AI (DILARANG tulis "Berikut kapsyen...", "Caption Facebook:", dll).
"""


def clean_glitches_and_meta_chatter(text: str) -> str:
    """
    Membersihkan token LLM, simbol mojibake, dan mukadimah pembantu AI.
    """
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
    text = re.sub(r'(?i)^\s*(?:yo|hai|salam|hello)?[^\n]*?(?:cadangan|kapsyen|caption|hantaran)[^\n]*?\n+', '', text)
    text = re.sub(r'(?i)\*\*caption\s*(?:facebook)?\s*:\*\*', '', text)

    # 5. Buang sebarang frasa generik 'Gajet Pilihan:'
    text = re.sub(r'(?i)🎧?\s*gajet\s*pilihan\s*:\s*', '', text)

    # 6. Buang pautan URL jika AI terlepas pandang
    text = re.sub(r'https?://[^\s]+', '', text)

    # 7. Susun baris perenggan yang kemas
    lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in text.splitlines()]
    return "\n".join([line for line in lines if line]).strip()


def is_valid_fb_caption(text: str, min_len: int = 400, max_len: int = 800) -> bool:
    """
    Menyemak kesahan kualiti teks bagi menghalang kebocoran teks rosak, perkataan merapu,
    atau token loop (contoh: 'eradication amantes tritium').
    """
    if not text or len(text.strip()) < min_len or len(text.strip()) > max_len:
        return False
    if "<pad>" in text.lower() or "<unk>" in text.lower():
        return False

    # Mengesan jika ada perkataan berulang lebih 3 kali berturut-turut (Degenerasi Token)
    if re.search(r'(\b\w+\b)(?:\s+\1){2,}', text, flags=re.IGNORECASE):
        return False

    words = [w.lower() for w in re.findall(r'\b[a-zA-Z]+\b', text)]
    total_words = len(words)
    if total_words < 25:
        return False

    unique_words = set(words)
    # Jika nisbah kepelbagaian perkataan terlalu rendah (tanda teks rosak)
    if len(unique_words) / total_words < 0.40:
        return False

    matching_anchors = unique_words.intersection(MALAY_ANCHOR_WORDS)
    if len(matching_anchors) < 3:
        return False

    return True


class LazadaFacebookAIPersona:
    """Enjin AI Persona Facebook Page khusus untuk produk affiliate Lazada."""

    def __init__(self):
        self.base_url = (os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1").strip().rstrip("/")
        self.model = os.getenv("OPENROUTER_MODEL", "").strip()
        self.api_key = os.getenv("OPENROUTER_API_KEY", "").strip()

    def generate_caption(self, product_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Menjana kapsyen Facebook Page Feed (500 - 700 Aksara)
        dengan arahan CTA rasmi ke ruangan komen pertama.
        Memulangkan: (success_bool, caption_text)
        """
        raw_title = str(
            product_data.get("title")
            or product_data.get("product_name")
            or product_data.get("lazada_product_name")
            or "Aksesori Komputer Pilihan"
        ).strip()

        clean_title = re.sub(r'\s+', ' ', raw_title)[:75].strip()
        brand = str(product_data.get("brand") or product_data.get("lazada_brand") or "").strip()
        price = product_data.get("price") or product_data.get("lazada_price") or ""
        category = product_data.get("category") or product_data.get("lazada_category") or "Aksesori Komputer & Gajet"

        price_str = f"RM {float(price):.2f}" if price and str(price).replace('.', '', 1).isdigit() else ""
        price_info = f" ({price_str})" if price_str else ""
        brand_name = brand if brand else "Pilihan Ramai"

        cta_line = "👉 Pautan belian rasmi Lazada abang dah sediakan di ruangan komen pertama di bawah ya! 👇"

        # Kapsyen sandaran bersih jika OpenRouter gagal
        fallback_caption = (
            f"Korang yang tengah sibuk nak upgrade atau kemaskan setup meja kerja tapi bajet tengah ketat, tengok ni! "
            f"Kadang-kadang kita nak barang yang tahan lasak dan tak cepat rosak supaya kerja harian jadi lebih lancar.\n\n"
            f"Abang nak racun satu pilihan padu daripada {brand_name} iaitu {clean_title}{price_info}.\n\n"
            f"Kenapa barang ni berbaloi untuk setup korang?\n"
            f"• Kualiti binaan kukuh, kemas dan tahan lama untuk kegunaan harian.\n"
            f"• Prestasi sangat stabil dan memudahkan urusan kerja mahupun gaming.\n"
            f"• Nilai terbaik dengan harga yang cukup mesra poket!\n\n"
            f"{cta_line}"
        )

        if not self.base_url or not self.model or not self.api_key:
            print("⚠️ [LAZADA FB AI WARN] Kunci OpenRouter tidak lengkap, menggunakan kapsyen sandaran.")
            return True, fallback_caption

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json; charset=utf-8",
            "HTTP-Referer": "https://sembangpctech.local",
            "X-Title": "Sembang PC & Tech Bot",
        }

        user_prompt = f"""
Sila hasilkan kapsyen lengkap Facebook Page (500 - 700 aksara) untuk produk ini:
- Nama Produk: {clean_title}
- Jenama: {brand_name}
- Kategori: {category}
- Harga / Tawaran: {price_str if price_str else 'Promosi Berbaloi'}

Peringatan: 
- Senaraikan tepat 3 poin kelebihan (•).
- Akhiri perenggan terakhir dengan TEPAT:
{cta_line}

Tuliskan teks lengkap sekarang:
"""

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT.strip()},
                {"role": "user", "content": user_prompt.strip()},
            ],
            "temperature": 0.65,
            "max_tokens": 550,
            "frequency_penalty": 0.3,
            "presence_penalty": 0.1,
        }

        url = f"{self.base_url}/chat/completions"

        # Mekanisme 3x Percubaan (Retry)
        for attempt in range(3):
            try:
                print(f"🤖 [LAZADA FB AI] Menjana kapsyen Facebook (Percubaan {attempt + 1}/3)...")
                res = requests.post(url, headers=headers, json=payload, timeout=25)
                res.encoding = "utf-8"

                if res.status_code == 200:
                    data = res.json()
                    if "choices" in data and len(data["choices"]) > 0:
                        raw_text = data["choices"][0]["message"]["content"].strip()
                        cleaned_text = clean_glitches_and_meta_chatter(raw_text)

                        # Pastikan baris CTA komen pertama sentiasa ada
                        if "ruangan komen pertama" not in cleaned_text:
                            cleaned_text += f"\n\n{cta_line}"

                        if is_valid_fb_caption(cleaned_text):
                            print(f"✅ [LAZADA FB AI SUCCESS] Kapsyen Facebook berjaya dijana ({len(cleaned_text)} aksara).")
                            return True, cleaned_text
                        else:
                            print(f"⚠️ [LAZADA FB AI GLITCH] Teks tidak menepati kualiti pada percubaan {attempt + 1}. Mencuba semula...")
                else:
                    print(f"⚠️ [LAZADA FB AI HTTP ERROR] HTTP {res.status_code}: {res.text}")

            except Exception as e:
                print(f"⚠️ [LAZADA FB AI EXCEPTION - ATTEMPT {attempt + 1}]: {str(e)}")

        print("🛡️ [LAZADA FB AI FALLBACK] Mengaktifkan kapsyen Facebook sandaran bersih.")
        return True, fallback_caption


# Singleton instance & alias keserasian
lazada_fb_ai = LazadaFacebookAIPersona()
generate_caption = lazada_fb_ai.generate_caption