#!/usr/bin/env python3
"""
Instagram AI Persona Engine (Brader Din Style)
Sembang PC & Tech Ecosystem (100% Dynamic OpenRouter & Glitch-Proof)
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
    2. Karakter rosak / encoding glitch (mojibake: ð, â, â).
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
        """Menjana kapsyen ulasan racun gajet kemas untuk feed Instagram."""
        title = product_data.get("title", "Gajet Pilihan")
        price = product_data.get("price", "")
        features = product_data.get("features", "")

        system_prompt = """
Anda adalah "Brader Din", pencipta kandungan teknologi dan ulasan perkakasan komputer di komuniti Sembang PC & Tech Malaysia.

GAYA BAHASA & STRUKTUR KAPSYEN INSTAGRAM:
1. Nada: Santai, mesra komuniti PC/tech Malaysia (gunakan panggilan 'korang', 'geng tech', 'memang padu', 'ngam sangat').
2. Fasa 1 (Hook): Mulakan terus dengan soalan atau situasi setup harian yang menarik minat.
3. Fasa 2 (Ulasan): Terangkan 3 kelebihan utama produk menggunakan bullet point simbol (•) yang tersusun.
4. Fasa 3 (Call To Action): Beritahu pembaca bahawa link pembelian rasmi boleh didapati di Bio profil atau Telegram Sembang PC & Tech.
5. Fasa 4 (Hashtags): Akhiri dengan 6 hingga 8 hashtag teknologi tempatan.

ARAHAN PANTANGAN KETAT:
- TERUS TULIS AYAT HANTARAN TANPA sebarang mukadimah (DILARANG: "Yo apa khabar...", "Berikut adalah cadangan kapsyen...").
- DILARANG letak nota tips tambahan di bahagian bawah.
- DILARANG guna simbol bukan Rumi atau teks merapu.
"""
        user_prompt = f"""
Sila hasilkan kapsyen ulasan Instagram untuk produk ini:
Nama Produk: {title}
Harga / Tawaran: {price}
Ciri-ciri: {features}

Tuliskan teks hantaran lengkap sekarang:
"""
        caption = self._call_openrouter(system_prompt, user_prompt)
        if not caption:
            price_tag = f"\n💰 Tawaran: {price}" if price else ""
            caption = (
                f"Korang yang tengah cari barang baru untuk kemaskan setup, tengok yang ni! ⚡💻\n\n"
                f"📦 {title}{price_tag}\n\n"
                f"Kualiti binaan memang padu dan praktikal untuk kegunaan harian. Setup meja nampak makin kemas dan selesa bila ada kelengkapan macam ni.\n\n"
                f"• Rekaan moden & sedap dipandang\n"
                f"• Material tahan lasak untuk kegunaan harian\n"
                f"• Sangat berbaloi untuk nilai harga\n\n"
                f"🔗 Link pembelian rasmi abang dah pin di Bio profil atau terus ke Telegram Sembang PC & Tech ya geng! 👇\n\n"
                f"#SembangPCTech #TechMalaysia #PCSetup #DeskSetup #RacunGajet #SetupGoals"
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