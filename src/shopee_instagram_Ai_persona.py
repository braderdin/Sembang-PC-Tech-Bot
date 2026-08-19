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
Hantaran ini akan disegerakkan secara automatik dari Instagram terus ke papan Pinterest.

STRUKTUR WAJIB KAPSYEN (ZON EMAS PINTEREST: 350 HINGGA 450 AKSARA):
1. Fasa 1 (Tajuk Produk & Hook Pantas - 2 Baris Awal untuk Pinterest SEO):
   - Nyatakan nama produk dengan jelas dan kemas di baris pertama/kedua.
2. Fasa 2 (Ulasan Ringkas & 2 Poin Kelebihan):
   - Senaraikan tepat 2 kelebihan utama menggunakan simbol bullet point (•).
3. Fasa 3 (Call To Action Dwi-Fungsi Pinterest & Instagram Bio - WAJIB):
   - Letakkan pautan belian rasmi Shopee:
     "🔗 Pautan Rasmi: <affiliate_link>"
   - Tambah panduan carian Bio & Telegram (DILARANG letak simbol '@' sebelum nama bot):
     "👉 Atau tekan link di Bio & taip \"<kata_kunci>\" di Telegram Bot: lubuk_barang_murah_padu_bot"
4. Fasa 4 (Hashtags Rasmi):
   - #RacunGajet #SembangPCTech #ShopeeMY #PCSetup #TechMalaysia

PANDUAN KETAT:
- WAJIB kekalkan panjang keseluruhan teks di antara 350 HINGGA 450 AKSARA (agar teks tidak terpotong di Pinterest).
- DILARANG letak simbol '@' pada perkataan nama bot Telegram.
- DILARANG gunakan bahasa kaku atau Bahasa Indonesia.
- TERUS TULIS AYAT KANDUNGAN TANPA sebarang mukadimah AI.
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

    # 5. Buang bahagian tips tambahan di penghujung teks
    text = re.sub(r'(?i)\n+\s*\*{0,2}tips\s*tambahan[^\n]*\*{0,2}[\s\S]*$', '', text)
    text = re.sub(r'\*\*\*', '', text)

    # 6. Susun baris perenggan yang kemas
    lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in text.splitlines()]
    return "\n".join([line for line in lines if line]).strip()


def extract_search_keyword(title: str, max_words: int = 3) -> str:
    """
    Mengekstrak 2-3 kata kunci penting daripada tajuk produk untuk Telegram Catalog Bot.
    """
    if not title:
        return "Gajet"

    clean = re.sub(r'[\[\]\(\)\#\|\/\-\+\:\,\.]', ' ', str(title))
    words = [w.strip() for w in clean.split() if len(w.strip()) > 1 and not w.strip().isdigit()]

    stop_words = {
        'original', 'ready', 'stock', 'new', 'pro', 'set', 'hot', 'offer',
        'murah', 'padu', 'high', 'quality', 'fast', 'delivery', 'warranty', 'shopee'
    }

    filtered = []
    for w in words:
        if w.lower() not in stop_words or len(filtered) == 0:
            filtered.append(w)
        if len(filtered) >= max_words:
            break

    return " ".join(filtered) if filtered else str(title)[:15]


def is_valid_ig_caption(text: str) -> bool:
    """
    Menyemak kualiti teks bagi mengelakkan ayat rosak atau token berulang.
    """
    if not text or len(text.strip()) < 80:
        return False
    if "<pad>" in text.lower() or "<unk>" in text.lower():
        return False

    # Mengesan jika ada perkataan berulang lebih 3 kali berturut-turut
    if re.search(r'(\b\w+\b)(?:\s+\1){2,}', text, flags=re.IGNORECASE):
        return False

    words = [w.lower() for w in re.findall(r'\b[a-zA-Z]+\b', text)]
    if len(words) < 15:
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
        mengandungi pautan affiliate terus dan CTA bot carian Telegram.
        Memulangkan: (success_bool, caption_text)
        """
        raw_title = str(product_data.get("shopee_product_name") or product_data.get("title") or "Gajet Pilihan").strip()
        clean_title = re.sub(r'\s+', ' ', raw_title)[:65].strip()
        price = product_data.get("shopee_price") or product_data.get("price") or ""
        category = product_data.get("shopee_category") or product_data.get("category") or "Aksesori PC & Gajet"
        aff_link = str(product_data.get("shopee_affiliate_link") or product_data.get("affiliate_link") or "").strip()
        search_kw = extract_search_keyword(raw_title)

        price_str = f"RM {float(price):.2f}" if price and str(price).replace('.', '', 1).isdigit() else ""
        price_display = f"\n💰 Tawaran: {price_str}" if price_str else ""

        # Kapsyen sandaran jika OpenRouter gagal
        fallback_caption = (
            f"Korang yang tengah nak upgrade setup meja, tengok yang ni! ⚡\n\n"
            f"📦 {clean_title}{price_display}\n\n"
            f"• Kualiti binaan kemas & sangat praktikal\n"
            f"• Nilai berbaloi untuk ruang kerja selesa\n\n"
            f"🔗 Pautan Rasmi: {aff_link}\n"
            f"👉 Atau tekan link di Bio & taip \"{search_kw}\" di Telegram Bot: lubuk_barang_murah_padu_bot\n\n"
            f"#RacunGajet #SembangPCTech #ShopeeMY #PCSetup #TechMalaysia"
        )

        if not self.base_url or not self.model or not self.api_key:
            print("⚠️ [IG AI WARN] Kunci OpenRouter tidak lengkap, menggunakan kapsyen sandaran.")
            return True, fallback_caption

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json; charset=utf-8",
            "HTTP-Referer": "https://sembangpctech.local",
            "X-Title": "Sembang PC & Tech Bot",
        }

        user_prompt = f"""
Sila hasilkan kapsyen lengkap Instagram & Pinterest (350 - 450 aksara) untuk produk ini:
Produk: {clean_title}
Kategori: {category}
Harga: {price_str if price_str else 'Promosi Berbaloi'}
Pautan Affiliate: {aff_link}
Kata Kunci Carian: {search_kw}

Tuliskan teks lengkap sekarang:
"""

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT.strip()},
                {"role": "user", "content": user_prompt.strip()},
            ],
            "temperature": 0.65,
            "max_tokens": 450,
            "frequency_penalty": 0.3,
            "presence_penalty": 0.1,
        }

        url = f"{self.base_url}/chat/completions"

        # Mekanisme 3x Percubaan (Retry)
        for attempt in range(3):
            try:
                print(f"🤖 [IG AI GENERATION] Menjana kapsyen Instagram (Percubaan {attempt + 1}/3)...")
                res = requests.post(url, headers=headers, json=payload, timeout=25)
                res.encoding = "utf-8"

                if res.status_code == 200:
                    data = res.json()
                    if "choices" in data and len(data["choices"]) > 0:
                        raw_text = data["choices"][0]["message"]["content"].strip()
                        cleaned_text = clean_glitches_and_meta_chatter(raw_text)

                        # Pastikan pautan affiliate dan CTA bot ada di dalam teks
                        if is_valid_ig_caption(cleaned_text) and (aff_link in cleaned_text or not aff_link):
                            print(f"✅ [IG AI SUCCESS] Kapsyen Instagram berjaya dijana ({len(cleaned_text)} aksara).")
                            return True, cleaned_text
                        else:
                            print(f"⚠️ [IG AI GLITCH] Teks tidak menepati format/kualiti pada percubaan {attempt + 1}. Mencuba semula...")
                else:
                    print(f"⚠️ [IG AI HTTP ERROR] HTTP {res.status_code}: {res.text}")

            except Exception as e:
                print(f"⚠️ [IG AI EXCEPTION - ATTEMPT {attempt + 1}]: {str(e)}")

        print("🛡️ [IG AI FALLBACK] Mengaktifkan kapsyen Instagram sandaran bersih.")
        return True, fallback_caption


# Singleton instance untuk kegunaan modular
shopee_instagram_ai = ShopeeInstagramAIPersona()