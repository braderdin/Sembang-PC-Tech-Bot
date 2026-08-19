import os
import re
import requests
from typing import Dict, Any, Optional, Tuple

# Senarai kata sauh Bahasa Melayu untuk pengesahan kualiti teks (Guardrail)
MALAY_ANCHOR_WORDS = {
    "yang", "dan", "di", "ke", "kat", "ni", "tu", "dah", "nak", "ada",
    "kita", "korang", "saya", "buat", "bila", "dengan", "pun", "rasa",
    "meja", "setup", "pc", "kerja", "santai", "tengok", "dalam", "untuk",
    "tak", "bukan", "memang", "lagi", "padu", "mantap", "kemas", "berbaloi"
}

SYSTEM_PROMPT = """
Anda ialah Penulis Kandungan Rasmi untuk Instagram & Pinterest "Sembang PC & Tech Malaysia".
Tugas anda HANYA menulis ulasan padat produk (Hook Pembuka & 2 Poin Kelebihan Sahaja).

STRUKTUR TEKS YANG DIMINTA (ZON PADAT: 150 HINGGA 200 AKSARA):
1. Baris 1-2 (Hook & Nama Produk):
   - Nyatakan nama produk / jenama dengan jelas dan menarik di awal ayat (contoh: "UGREEN USB-C Fast Charging Cable! Upgrade setup kabel korang...").
   - DILARANG SAMA SEKALI guna frasa generik seperti "Gajet Pilihan:".
2. Baris 3-4 (Tepat 2 Kelebihan Utama):
   - Senaraikan TEPAT 2 poin kelebihan utama produk menggunakan simbol bullet point (•).

PANTANGAN SANGAT KETAT:
- DILARANG letak sebarang pautan (URL/Link). Pautan rasmi akan dipasang secara automatik oleh sistem.
- DILARANG letak arahan Telegram, CTA bio, atau pautan bot.
- DILARANG letak sebarang tanda pagar (#hashtag).
- DILARANG guna bahasa kaku atau perkataan Indonesia (bisa, banget, dll).
- TERUS TULIS AYAT ULASAN & 2 POIN BULLET SAHAJA tanpa sebarang mukadimah AI.
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
    for sym in ["❖", "◆", "◇", "►", "▪", "▲", "★", "➡", "➢", "*"]:
        text = text.replace(sym, "•")

    # 4. Buang mukadimah pembantu AI di awal teks
    text = re.sub(r'(?i)^\s*(?:yo|hai|salam|hello)?[^\n]*?(?:cadangan|kapsyen|caption)[^\n]*?\n+', '', text)
    text = re.sub(r'(?i)\*\*caption\s*(?:instagram)?\s*:\*\*', '', text)

    # 5. Buang sebarang frasa generik 'Gajet Pilihan:'
    text = re.sub(r'(?i)🎧?\s*gajet\s*pilihan\s*:\s*', '', text)

    # 6. Buang pautan, CTA telegram atau hashtag jika AI terlepas pandang
    text = re.sub(r'https?://[^\s]+', '', text)
    text = re.sub(r'(?i)👉\s*Atau\s*tekan\s*link[^\n]*', '', text)
    text = re.sub(r'#[a-zA-Z0-9_\u00C0-\u024F]+', '', text)

    # 7. Susun baris perenggan yang kemas
    lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in text.splitlines()]
    return "\n".join([line for line in lines if line]).strip()


def extract_search_keyword(title: str, max_words: int = 3) -> str:
    """
    Mengekstrak 2-3 perkataan berturutan yang paling relevan daripada tajuk produk
    untuk carian 'ilike' yang 100% tepat di Supabase Telegram Catalog Bot.
    """
    if not title:
        return "Gajet Pilihan"

    # Buang kurungan di hadapan seperti [NEW], 【Nexode】, dll
    clean = re.sub(r'^[\[【][^\]】]*[\]】]\s*', '', str(title))
    clean = re.sub(r'[\[\]\(\)\#\|\:\,\.【】\+]', ' ', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()

    stop_words = {
        'original', 'ready', 'stock', 'new', 'pro', 'set', 'hot', 'offer',
        'murah', 'padu', 'high', 'quality', 'fast', 'delivery', 'warranty',
        'compatible', 'for', 'system', 'free', 'shipping', 'flagship', 'store',
        'official', 'and', 'with', 'from', 'best', 'sale', 'promo', 'shopee', 'lazada'
    }

    words = clean.split(' ')
    selected = []

    for w in words:
        w_clean = w.strip()
        if not w_clean or len(w_clean) < 2:
            continue
        if w_clean.lower() in stop_words:
            if not selected:
                continue
            else:
                break  # Hentikan pengekstrakan untuk mengekalkan frasa berturutan
        selected.append(w_clean)
        if len(selected) >= max_words:
            break

    if selected:
        return " ".join(selected)

    fallback_words = [w for w in words if len(w) > 1][:max_words]
    return " ".join(fallback_words) if fallback_words else str(title)[:20].strip()


def is_valid_ig_body(text: str) -> bool:
    """
    Menyemak kualiti teks ulasan AI sebelum digabungkan dengan komponen footer.
    """
    if not text or len(text.strip()) < 50:
        return False
    if "<pad>" in text.lower() or "<unk>" in text.lower():
        return False

    # Mengesan jika ada perkataan berulang lebih 3 kali berturut-turut
    if re.search(r'(\b\w+\b)(?:\s+\1){2,}', text, flags=re.IGNORECASE):
        return False

    words = [w.lower() for w in re.findall(r'\b[a-zA-Z]+\b', text)]
    if len(words) < 8:
        return False

    unique_words = set(words)
    if len(unique_words) / len(words) < 0.40:
        return False

    matching_anchors = unique_words.intersection(MALAY_ANCHOR_WORDS)
    if len(matching_anchors) < 2:
        return False

    return True


class ShopeeInstagramAIPersona:
    """Enjin AI Persona Instagram & Pinterest khusus untuk produk affiliate Shopee."""

    def __init__(self):
        self.base_url = (os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1").strip().rstrip("/")
        self.model = os.getenv("OPENROUTER_MODEL", "").strip()
        self.api_key = os.getenv("OPENROUTER_API_KEY", "").strip()

    def generate_caption(self, product_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Menjana kapsyen Instagram Feed & Pinterest Sync (350 - 450 Aksara)
        dengan jaminan sifar pautan bertindih dan kata kunci carian Telegram yang tepat.
        Memulangkan: (success_bool, caption_text)
        """
        # Menyokong pelbagai format kunci data secara seragam
        raw_title = str(
            product_data.get("product_name")
            or product_data.get("shopee_product_name")
            or product_data.get("title")
            or "Aksesori Komputer"
        ).strip()

        clean_title = re.sub(r'\s+', ' ', raw_title)[:65].strip()
        brand = str(product_data.get("brand") or product_data.get("shopee_brand") or "Pilihan Ramai").strip()
        price = product_data.get("price") or product_data.get("shopee_price") or ""
        category = product_data.get("category") or product_data.get("shopee_category") or "Aksesori PC & Gajet"
        aff_link = str(
            product_data.get("affiliate_link")
            or product_data.get("shopee_affiliate_link")
            or product_data.get("promo_short_link")
            or ""
        ).strip()

        # Ekstrak kata kunci carian berturutan (contoh: "UGREEN USB-A USB-C" atau "UGREEN Car Phone")
        search_kw = extract_search_keyword(raw_title)

        price_str = f"RM {float(price):.2f}" if price and str(price).replace('.', '', 1).isdigit() else ""
        price_info = f" ({price_str})" if price_str else ""

        # 1. BINA FOOTER PROGRAMATIK (Pautan Rasmi & CTA Telegram Dijamin Selamat)
        link_line = f"🔗 Pautan Rasmi: {aff_link}" if aff_link else ""
        cta_telegram = f"👉 Atau tekan link di Bio & taip \"{search_kw}\" di Telegram Bot: lubuk_barang_murah_padu_bot"
        hashtags = "#RacunGajet #BarangMurahPadu #SembangPCTech #TechMalaysia #PCSetup #ShopeeMY"

        footer_elements = [el for el in [link_line, cta_telegram, hashtags] if el]
        footer_block = "\n".join(footer_elements)

        # 2. AYAT SANDARAN BADAN JIKA AI GAGAL
        fallback_body = (
            f"{clean_title}! Upgrade setup meja atau ruang kerja korang dengan pilihan mantap daripada {brand}{price_info}.\n\n"
            f"• Kualiti binaan kemas & tahan lasak untuk kegunaan harian\n"
            f"• Rekaan praktikal yang sangat memudahkan urusan kerja dan santai"
        )

        if not self.base_url or not self.model or not self.api_key:
            print("⚠️ [IG AI WARN] Kunci OpenRouter tidak lengkap, menggunakan kapsyen sandaran.")
            full_fallback = f"{fallback_body}\n\n{footer_block}".strip()
            return True, full_fallback

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json; charset=utf-8",
            "HTTP-Referer": "https://sembangpctech.local",
            "X-Title": "Sembang PC & Tech Bot",
        }

        user_prompt = f"""
Sila hasilkan ulasan padat (Hook + 2 Poin Bullets sahaja) untuk produk ini:
- Produk: {clean_title}
- Jenama: {brand}
- Kategori: {category}
- Harga: {price_str if price_str else 'Promosi Berbaloi'}

Peringatan: JANGAN letak sebarang link, hashtag, atau CTA Telegram. Tulis teks ulasan dan 2 poin bullet sahaja.
"""

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT.strip()},
                {"role": "user", "content": user_prompt.strip()},
            ],
            "temperature": 0.65,
            "max_tokens": 250,
            "frequency_penalty": 0.3,
            "presence_penalty": 0.1,
        }

        url = f"{self.base_url}/chat/completions"

        # Mekanisme 3x Percubaan (Retry)
        for attempt in range(3):
            try:
                print(f"🤖 [IG AI GENERATION] Menjana ulasan Instagram (Percubaan {attempt + 1}/3)...")
                res = requests.post(url, headers=headers, json=payload, timeout=25)
                res.encoding = "utf-8"

                if res.status_code == 200:
                    data = res.json()
                    if "choices" in data and len(data["choices"]) > 0:
                        raw_text = data["choices"][0]["message"]["content"].strip()
                        cleaned_body = clean_glitches_and_meta_chatter(raw_text)

                        if is_valid_ig_body(cleaned_body):
                            # Gabungkan ulasan AI bersama Footer Programatik
                            final_caption = f"{cleaned_body}\n\n{footer_block}".strip()
                            print(f"✅ [IG AI SUCCESS] Kapsyen Instagram berjaya dijana ({len(final_caption)} aksara | Kata Kunci: '{search_kw}').")
                            return True, final_caption
                        else:
                            print(f"⚠️ [IG AI GLITCH] Teks tidak menepati kualiti pada percubaan {attempt + 1}. Mencuba semula...")
                else:
                    print(f"⚠️ [IG AI HTTP ERROR] HTTP {res.status_code}: {res.text}")

            except Exception as e:
                print(f"⚠️ [IG AI EXCEPTION - ATTEMPT {attempt + 1}]: {str(e)}")

        print("🛡️ [IG AI FALLBACK] Mengaktifkan kapsyen Instagram sandaran bersih.")
        full_fallback = f"{fallback_body}\n\n{footer_block}".strip()
        return True, full_fallback


# Singleton instance untuk kegunaan modular
shopee_instagram_ai = ShopeeInstagramAIPersona()