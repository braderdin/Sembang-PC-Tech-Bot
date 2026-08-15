#!/usr/bin/env python3
"""
Instagram AI Persona Engine (Brader Din Style - Telegram Funnel Optimized)
Sembang PC & Tech Ecosystem (100% Dynamic OpenRouter & Glitch-Proof)
Features:
- Smart Search Keyword Extraction for Telegram Catalog Bot
- High-Converting Bio & Telegram Search Call-To-Action (No Broken @ tags)
- Instagram SEO Optimization (Product title in first 2 lines)
- Category & Viral Hashtag Strategy (#RacunGajet, #BarangMurahPadu, etc.)
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
    """
    Membersihkan teks daripada:
    1. Token rosak LLM (<pad>, <unk>).
    2. Karakter rosak / encoding glitch (mojibake: ð, â).
    3. Mukadimah AI ("Berikut adalah...", "**Caption Instagram:**") dan nota tips tambahan.
    """
    if not text:
        return ""

    # 1. Buang token khas LLM
    text = re.sub(r'<pad>|<unk>|<s>|</s>|\[PAD\]|\[UNK\]|<\|.*?\|>', '', text, flags=re.IGNORECASE)

    # 2. Buang simbol mojibake / glitch encoding
    text = re.sub(r'[ðâ][\x80-\xbf]{1,4}', '', text)
    text = re.sub(r'[\x80-\x9f]', '', text)

    # 3. Standardkan simbol bullet point
    special_bullets = ["❖", "◆", "◇", "►", "▪", "▲", "★", "➡", "➢"]
    for sym in special_bullets:
        text = text.replace(sym, "•")

    # 4. Buang mukadimah pembantu AI di awal teks
    text = re.sub(r'(?i)^\s*(?:yo|hai|salam|hello)?[^\n]*?(?:cadangan|kapsyen|caption)[^\n]*?\n+', '', text)
    text = re.sub(r'(?i)\*\*caption\s*(?:instagram)?\s*:\*\*', '', text)

    # 5. Buang bahagian "Tips Tambahan" di penghujung teks
    text = re.sub(r'(?i)\n+\s*\*{0,2}tips\s*tambahan[^\n]*\*{0,2}[\s\S]*$', '', text)
    text = re.sub(r'\*\*\*', '', text)

    # 6. Susun baris perenggan yang kemas
    lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in text.splitlines()]
    cleaned = "\n".join([line for line in lines if line]).strip()

    return cleaned


def extract_search_keyword(title: str, max_words: int = 3) -> str:
    """
    Mengekstrak 2 hingga 3 perkataan terpenting daripada tajuk produk
    untuk dijadikan kata kunci carian pantas di Telegram Bot.
    """
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
    """Menyemak kualiti teks bagi mengelakkan teks terputus atau rosak."""
    if not text or len(text.strip()) < 80:
        return False
    if "<pad>" in text.lower() or "<unk>" in text.lower():
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
            "max_tokens": 850,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0,
        }

        for attempt in range(2):
            try:
                res = requests.post(f"{self.base_url}/chat/completions", headers=headers, json=payload, timeout=30)
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
        Menjana kapsyen ulasan racun gajet padu untuk Instagram
        dengan Call-To-Action (CTA) tepat ke Link Bio (Sifar Broken Tag).
        """
        title = product_data.get("title", "Gajet Pilihan")
        price = product_data.get("price", "")
        category = product_data.get("category", "Gajet & Komputer")
        search_kw = extract_search_keyword(title)

        system_prompt = """
Anda adalah "Brader Din", pencipta kandungan teknologi, ulasan perkakasan komputer, dan barang bajet berkualiti di Instagram Sembang PC & Tech Malaysia.

STRUKTUR WAJIB KAPSYEN INSTAGRAM:
1. Fasa 1 (Hook & Tajuk Produk SEO):
   - Mulakan baris pertama dengan hook santai & sebut nama produk dengan jelas di 2 baris terawal.
2. Fasa 2 (Ulasan Ringkas):
   - 1 perenggan pendek tentang fungsi dan kenapa barang ini berbaloi dimiliki.
   - Sertakan 3 kelebihan utama produk menggunakan simbol bullet point (•).
3. Fasa 3 (Call To Action & Search Keyword Hook - WAJIB):
   - Ajak pembaca untuk tekan pautan di Bio profil atau cari di Telegram katalog.
   - Gunakan format ayat ini secara tepat (JANGAN letak simbol '@' sebelum perkataan bot Telegram untuk elak broken tag di Instagram):
     "👉 Nak link tawaran rasmi? Tekan link di Bio kami (atau buka Telegram Bot: lubuk_barang_murah_padu_bot) dan taip carian: \"[KATA_KUNCI]\" untuk terus dapat kad info & link belian pantas! 👇"
4. Fasa 4 (Hashtags Rasmi):
   - Wajib sertakan kombinasi hashtag ini:
     #RacunGajet #BarangMurahPadu #SembangPCTech #TechMalaysia #PCSetup #LazadaMY #ShopeeMY #SetupMeja

ARAHAN PANTANGAN KETAT:
- DILARANG letak simbol '@' pada perkataan nama bot Telegram (kerana Instagram akan anggap itu akaun IG).
- DILARANG letak link URL mentah dalam kapsyen (kerana IG tidak boleh klik link).
- TERUS TULIS AYAT HANTARAN TANPA sebarang mukadimah AI (DILARANG: "Berikut adalah...", "Yo apa khabar...").
- DILARANG letak nota tips tambahan di bahagian bawah.
"""
        user_prompt = f"""
Sila hasilkan kapsyen Instagram untuk produk ini:
Nama Penuh Produk: {title}
Kategori: {category}
Harga / Anggaran: RM {price if price else 'Promosi'}
Kata Kunci Carian Telegram: {search_kw}

Tuliskan kapsyen lengkap sekarang:
"""
        caption = self._call_openrouter(system_prompt, user_prompt)
        
        # Fallback Pintar jika API OpenRouter sibuk
        if not caption:
            price_display = f"\n💰 Anggaran Tawaran: RM {price}" if price else ""
            caption = (
                f"Korang yang tengah cari kelengkapan baru yang padu, tengok yang ni! ⚡\n\n"
                f"📦 {title}{price_display}\n\n"
                f"Kualiti binaan memang kemas dan praktikal untuk kegunaan harian. Setup atau ruang bilik korang pasti nampak makin selesa bila ada barang ni.\n\n"
                f"• Rekaan moden & sedap dipandang mata\n"
                f"• Material tahan lasak & kualiti terjamin\n"
                f"• Nilai terbaik untuk bajet korang\n\n"
                f"👉 Nak link pembelian rasmi? Tekan link di Bio kami (atau buka Telegram Bot: lubuk_barang_murah_padu_bot) dan taip carian: \"{search_kw}\" untuk terus dapat kad info & link belian pantas! 👇\n\n"
                f"#RacunGajet #BarangMurahPadu #SembangPCTech #TechMalaysia #PCSetup #LazadaMY #ShopeeMY #SetupMeja"
            )
        return caption

    def generate_lifestyle_caption(self, topic: str, key_points: Optional[str] = None) -> str:
        """Menjana kapsyen lifestyle & inspirasi setup meja."""
        system_prompt = """
Anda adalah "Brader Din", berkongsi inspirasi ruang kerja, desk setup minimalis, dan gaya hidup komputer di Instagram Sembang PC & Tech.

GAYA BAHASA & STRUKTUR KAPSYEN INSTAGRAM:
1. Nada: Santai, tenang, mesra komuniti tech tempatan.
2. Fasa 1: Pembuka kata yang selari dengan topik dan visual hantaran.
3. Fasa 2: Penceritaan santai tentang ketenangan ruang kerja yang teratur atau hobi teknologi.
4. Fasa 3: Satu soalan santai untuk mengajak rakan komuniti berkongsi pendapat di ruang komen.
5. Fasa 4: 6 hingga 8 hashtag santai setup & tech Malaysia.

ARAHAN PANTANGAN KETAT:
- TERUS TULIS AYAT HANTARAN TANPA mukadimah AI (DILARANG: "Yo apa khabar...", "Ini caption...").
- DILARANG letak bahagian tips tambahan/rekaan kamera di hujung teks.
"""
        user_prompt = f"""
Hasilkan kapsyen Instagram lifestyle bertemakan '{topic}'.
Konteks / Mood: {key_points or 'Suasana meja kemas dan produktiviti'}

Tuliskan teks hantaran lengkap sekarang:
"""
        caption = self._call_openrouter(system_prompt, user_prompt)
        if not caption:
            caption = (
                f"Bila ruang kerja kemas dan teratur, rasa tenang sangat nak duduk lama depan skrin. 🖥️✨\n\n"
                f"Pencahayaan yang sedap mata memandang ditambah pula dengan susun atur meja yang bebas serabut memang buat fokus kerja dan santai jadi lebih nikmat.\n\n"
                f"Korang jenis suka suasana setup minimalis bersih atau penuh dengan lampu ambient? Cuba kongsikan sikit di ruang komen! 👇\n\n"
                f"#SembangPCTech #TechMalaysia #DeskSetup #WorkspaceInspiration #MinimalistSetup #PCGaming"
            )
        return caption


# Singleton instance
instagram_ai = InstagramAIPersona()