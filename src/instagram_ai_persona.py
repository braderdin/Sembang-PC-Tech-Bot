#!/usr/bin/env python3
"""
Instagram AI Persona Engine (Brader Din Style - Pinterest & Telegram Optimized)
Sembang PC & Tech Ecosystem (100% Dynamic OpenRouter & Glitch-Proof)
Features:
- Dual-Action Call-To-Action (Direct Affiliate URL for Pinterest Sync + Bio / Telegram Search Hook)
- Glitch & Repetition Guardrails (Rejects gibberish & token-loop errors)
- Target Character Window: 350 - 450 Characters (Fits perfectly in Pinterest 500-char limit)
- Instagram & Pinterest SEO Optimization (Product title in first 2 lines)
- Standardized Clean Hashtag Strategy (#RacunGajet, #SembangPCTech, #LazadaMY)
"""

import os
import re
import requests
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

# Kata dasar Bahasa Melayu untuk pengesahan kualiti teks (Guardrails)
MALAY_ANCHOR_WORDS = {
    "yang", "dan", "di", "ke", "kat", "ni", "tu", "dah", "nak", "ada",
    "kita", "korang", "saya", "buat", "bila", "dengan", "pun", "rasa",
    "meja", "setup", "pc", "kerja", "santai", "tengok", "dalam", "untuk",
    "tak", "bukan", "memang", "lagi", "hujung", "minggu", "malam", "pagi", "petang"
}


def clean_glitches_and_meta_chatter(text: str) -> str:
    """Membersihkan token LLM, simbol mojibake, dan mukadimah bot."""
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
    """Mengekstrak 2-3 kata kunci penting daripada tajuk produk untuk Telegram Catalog Bot."""
    if not title:
        return "Gajet"

    clean = re.sub(r'[\[\]\(\)\#\|\/\-\+\:\,\.]', ' ', str(title))
    words = [w.strip() for w in clean.split() if len(w.strip()) > 1 and not w.strip().isdigit()]

    stop_words = {
        'original', 'ready', 'stock', 'new', 'pro', 'set', 'hot', 'offer',
        'murah', 'padu', 'high', 'quality', 'fast', 'delivery', 'warranty'
    }

    filtered = []
    for w in words:
        if w.lower() not in stop_words or len(filtered) == 0:
            filtered.append(w)
        if len(filtered) >= max_words:
            break

    return " ".join(filtered) if filtered else str(title)[:15]


def is_valid_ig_caption(text: str) -> bool:
    """Menyemak kualiti teks bagi mengelakkan ayat rosak atau token berulang."""
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
    # Jika nisbah kepelbagaian perkataan terlalu rendah (tanda teks merepek)
    if len(unique_words) / len(words) < 0.40:
        return False

    matching_anchors = unique_words.intersection(MALAY_ANCHOR_WORDS)
    if len(matching_anchors) < 2:
        return False

    return True


class InstagramAIPersona:
    """Enjin AI Persona Instagram berteraskan model OpenRouter / Gemma."""

    def __init__(self):
        self.base_url = (os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1").strip().rstrip("/")
        self.model = os.getenv("OPENROUTER_MODEL", "").strip()
        self.api_key = os.getenv("OPENROUTER_API_KEY", "").strip()

    def _call_openrouter(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Panggilan AI terus ke OpenRouter API dengan kawalan ralat & cubaan semula."""
        if not self.api_key or not self.model:
            return None

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json; charset=utf-8",
            "HTTP-Referer": "https://sembangpctech.local",
            "X-Title": "Sembang PC & Tech Bot",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt.strip()},
                {"role": "user", "content": user_prompt.strip()},
            ],
            "temperature": 0.65,
            "max_tokens": 450,
            "frequency_penalty": 0.3,
            "presence_penalty": 0.1,
        }

        for attempt in range(2):
            try:
                res = requests.post(f"{self.base_url}/chat/completions", headers=headers, json=payload, timeout=25)
                res.encoding = "utf-8"
                if res.status_code == 200:
                    data = res.json()
                    if "choices" in data and len(data["choices"]) > 0:
                        raw_text = data["choices"][0]["message"]["content"].strip()
                        cleaned_text = clean_glitches_and_meta_chatter(raw_text)
                        if is_valid_ig_caption(cleaned_text):
                            return cleaned_text
            except Exception as e:
                print(f"⚠️ [Instagram AI Attempt {attempt + 1} Error]: {e}")

        return None

    def generate_affiliate_caption(self, product_data: Dict[str, Any]) -> str:
        """
        Menjana kapsyen Instagram Feed & Pinterest Sync (350 - 450 Aksara)
        mengandungi pautan affiliate terus (boleh klik di Pinterest) & CTA Telegram/Bio.
        """
        raw_title = str(product_data.get("title", "Gajet Pilihan")).strip()
        # Bersihkan tajuk panjang & buang perkataan bertindih
        clean_title = re.sub(r'\s+', ' ', raw_title)[:65].strip()
        price = product_data.get("price", "")
        category = product_data.get("category", "Gajet & Komputer")
        aff_link = str(product_data.get("affiliate_link") or product_data.get("promo_short_link") or "").strip()
        search_kw = extract_search_keyword(raw_title)

        system_prompt = f"""
Anda adalah "Brader Din", pencipta kandungan teknologi di Instagram & Pinterest Sembang PC & Tech Malaysia.
Hantaran ini akan disegerakkan secara automatik dari Instagram ke papan Pinterest.

STRUKTUR WAJIB KAPSYEN (ZON EMAS: 350 HINGGA 450 AKSARA):
1. Fasa 1 (Hook & Tajuk Produk):
   - Sebut nama produk dengan ringkas dan jelas di awal teks.
2. Fasa 2 (Ulasan Padat):
   - 1 perenggan ulasan ringkas dan senaraikan tepat 2 kelebihan utama menggunakan simbol bullet point (•).
3. Fasa 3 (Call To Action Dwi-Fungsi Pinterest & Instagram Bio - WAJIB):
   - Letakkan pautan belian rasmi:
     "🔗 Pautan Rasmi: {aff_link}"
   - Tambah panduan carian Bio & Telegram (JANGAN letak '@' sebelum nama bot):
     "👉 Atau tekan link di Bio & taip \"{search_kw}\" di Telegram Bot: lubuk_barang_murah_padu_bot"
4. Fasa 4 (Hashtags):
   - #RacunGajet #BarangMurahPadu #SembangPCTech #TechMalaysia #PCSetup #LazadaMY

PANDUAN KETAT:
- WAJIB kekalkan panjang keseluruhan teks di antara 350 HINGGA 450 AKSARA (agar tidak terpotong di Pinterest).
- DILARANG letak simbol '@' pada perkataan nama bot Telegram.
- TERUS TULIS AYAT KANDUNGAN TANPA sebarang mukadimah AI.
"""
        user_prompt = f"""
Sila hasilkan kapsyen lengkap untuk produk ini:
Produk: {clean_title}
Kategori: {category}
Harga / Anggaran: RM {price if price else 'Promosi Berbaloi'}
Pautan Affiliate: {aff_link}
Kata Kunci Carian: {search_kw}

Tuliskan teks lengkap (350-450 aksara) sekarang:
"""
        caption = self._call_openrouter(system_prompt, user_prompt)

        # Fallback Berstruktur & Bersih jika AI gagal melepasi tapisan
        if not caption or aff_link not in caption:
            price_display = f"\n💰 Tawaran: RM {price}" if price else ""
            caption = (
                f"Korang yang tengah nak upgrade setup meja, tengok yang ni! ⚡\n\n"
                f"📦 {clean_title}{price_display}\n\n"
                f"• Kualiti binaan kemas & sangat praktikal\n"
                f"• Nilai berbaloi untuk ruang kerja selesa\n\n"
                f"🔗 Pautan Rasmi: {aff_link}\n"
                f"👉 Atau tekan link di Bio & taip \"{search_kw}\" di Telegram Bot: lubuk_barang_murah_padu_bot\n\n"
                f"#RacunGajet #BarangMurahPadu #SembangPCTech #TechMalaysia #PCSetup #LazadaMY"
            )
        return caption

    def generate_lifestyle_caption(self, topic: str, key_points: Optional[str] = None) -> str:
        """Menjana kapsyen lifestyle & inspirasi setup meja (350 - 450 Aksara)."""
        system_prompt = """
Anda adalah "Brader Din", berkongsi inspirasi ruang kerja dan gaya hidup komputer di Instagram & Pinterest Sembang PC & Tech.

GAYA BAHASA & STRUKTUR KAPSYEN:
1. Nada: Santai, tenang, mesra komuniti tech tempatan.
2. Fasa 1: Pembuka kata yang selari dengan topik dan visual hantaran.
3. Fasa 2: Penceritaan santai tentang ketenangan ruang kerja yang kemas atau fokus harian.
4. Fasa 3: Satu soalan santai untuk interaksi komuniti di ruang komen.
5. Fasa 4: 4 hingga 5 hashtag santai (#SembangPCTech #DeskSetup #WorkspaceAesthetic #TechMalaysia #PCSetup).
6. PANJANG TEKS: Antara 350 hingga 450 aksara.

ARAHAN PANTANGAN KETAT:
- TERUS TULIS AYAT HANTARAN TANPA mukadimah AI.
- DILARANG letak bahagian tips tambahan/rekaan kamera di hujung teks.
"""
        user_prompt = f"""
Hasilkan kapsyen lifestyle bertemakan '{topic}'.
Konteks / Mood: {key_points or 'Suasana meja kemas dan produktiviti'}

Tuliskan teks hantaran lengkap sekarang:
"""
        caption = self._call_openrouter(system_prompt, user_prompt)
        if not caption:
            caption = (
                f"Bila ruang kerja kemas dan teratur, rasa tenang sangat nak duduk lama depan skrin. 🖥️✨\n\n"
                f"Pencahayaan yang sedap mata memandang ditambah susun atur meja bebas serabut memang buat fokus kerja jadi lebih nikmat.\n\n"
                f"Korang jenis suka setup minimalis bersih atau penuh lampu ambient? Jom kongsi di komen! 👇\n\n"
                f"#SembangPCTech #TechMalaysia #DeskSetup #WorkspaceAesthetic #MinimalistSetup #PCSetup"
            )
        return caption


# Singleton instance
instagram_ai = InstagramAIPersona()