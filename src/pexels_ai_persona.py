#!/usr/bin/env python3
"""
AI Persona Engine for Facebook Pexels Video Reels (Brader Din Style)
Sembang PC & Tech Ecosystem (100% Dynamic OpenRouter & Glitch-Proof)
Features:
- Micro-Hook & High-Engagement Question Generator for Short Video Reels
- Dynamic Malaysian Time-Slot & Mood Awareness (MYT = UTC+8)
- Anti-Glitch & Strict Malay Language Anchor Guardrails
- 2-Attempt Auto-Retry Loop with Clean Fallback
"""

import os
import re
import requests
from collections import Counter
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Tuple
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
    2. Simbol mojibake / glitch encoding.
    3. Mukadimah AI ("Berikut adalah...", "**Kapsyen:**") dan nota tips tambahan.
    """
    if not text:
        return ""

    # 1. Buang token khas LLM
    text = re.sub(r'<pad>|<unk>|<s>|</s>|\[PAD\]|\[UNK\]|<\|.*?\|>', '', text, flags=re.IGNORECASE)

    # 2. Buang simbol mojibake / glitch encoding
    text = re.sub(r'[ðâ][\x80-\xbf]{1,4}', '', text)
    text = re.sub(r'[\x80-\x9f]', '', text)

    # 3. Standardkan simbol bullet point
    special_bullets = ["❖", "◆", "◇", "►", "•", "▪", "▲", "★", "➡", "➢"]
    for sym in special_bullets:
        text = text.replace(sym, "-")

    # 4. Buang mukadimah AI di awal teks
    text = re.sub(r'(?i)^\s*(?:yo|hai|salam|hello)?[^\n]*?(?:cadangan|kapsyen|caption)[^\n]*?\n+', '', text)
    text = re.sub(r'(?i)\*\*caption\s*(?:reels?)?\s*:\*\*', '', text)

    # 5. Buang bahagian "Tips Tambahan" di penghujung teks
    text = re.sub(r'(?i)\n+\s*\*{0,2}tips\s*tambahan[^\n]*\*{0,2}[\s\S]*$', '', text)
    text = re.sub(r'\*\*\*', '', text)

    # 6. Susun baris perenggan yang kemas
    lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in text.splitlines()]
    return "\n".join([line for line in lines if line]).strip()


def is_valid_reel_caption(text: str) -> bool:
    """
    Menyemak kualiti teks bagi memastikan kapsyen Reel ringkas,
    menggunakan Bahasa Melayu semula jadi, dan bebas gelung autoregresif.
    """
    if not text or len(text.strip()) < 50:
        return False
    if "<pad>" in text.lower() or "<unk>" in text.lower():
        return False

    # 1. Semak Pengulangan Berturut-turut
    if re.search(r'(\b\w+\b)(?:\s+\1){2,}', text, flags=re.IGNORECASE):
        return False

    words = [w.lower() for w in re.findall(r'\b[a-zA-Z]+\b', text)]
    total_words = len(words)
    if total_words < 10:
        return False

    # 2. Semak Nisbah Kepelbagaian Perkataan (Unique Words Ratio)
    unique_words = set(words)
    if len(unique_words) / total_words < 0.40:
        return False

    # 3. Semak Kekerapan Perkataan Tunggal
    word_counts = Counter(words)
    for word, count in word_counts.items():
        if len(word) >= 4 and (count / total_words) > 0.20:
            return False

    # 4. Semakan Pengesahan Bahasa Melayu (Malay Anchor Check)
    matching_anchors = unique_words.intersection(MALAY_ANCHOR_WORDS)
    if len(matching_anchors) < 2:
        return False

    return True


def detect_reel_time_slot() -> Tuple[str, str, str, float]:
    """
    Mengenal pasti slot masa semasa dan mood hari mengikut zon masa Malaysia (MYT = UTC+8).
    """
    myt_time = datetime.now(timezone.utc) + timedelta(hours=8)
    hour = myt_time.hour
    day_name = myt_time.strftime("%A")

    day_mood_map = {
        "Monday": "Isnin (Mood Hustle, Produktiviti & Semangat Mula Minggu)",
        "Tuesday": "Selasa (Mood Mengemas Aliran Kerja & Ergonomik Setup)",
        "Wednesday": "Rabu (Mood Mid-week Tech & Tips Perkakasan PC)",
        "Thursday": "Khamis (Mood Persiapan Hujung Minggu & Eksperimen Tech)",
        "Friday": "Jumaat (Mood TGIF, Santai & Perancangan Gaming)",
        "Saturday": "Sabtu (Mood Hujung Minggu, Meja Kerja Estetik & Hobi Komputer)",
        "Sunday": "Ahad (Mood Refleksi, Ketenangan Ruang Kerja & Kopi)",
    }
    current_day_mood = day_mood_map.get(day_name, "Hari Biasa Tech")
    stable_temp = 0.65

    if 4 <= hour < 11:
        return "morning_focus", "Pagi (Kopi, Ketenangan Setup & Fikiran Produktif)", current_day_mood, stable_temp
    elif 11 <= hour < 17:
        return "afternoon_work", "Tengah Hari / Petang (Aliran Kerja, Setup Kemas & Tips IT)", current_day_mood, stable_temp
    else:
        return "night_gaming", "Malam (Pencahayaan Ambient, Gaming Battlestation & Santai)", current_day_mood, stable_temp


class PexelsAIPersona:
    """Enjin AI Persona khusus untuk Facebook Pexels Video Reels."""

    def __init__(self):
        self.base_url = (os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1").strip().rstrip("/")
        self.model = os.getenv("OPENROUTER_MODEL", "").strip()
        self.api_key = os.getenv("OPENROUTER_API_KEY", "").strip()

    def _call_openrouter(self, system_prompt: str, user_prompt: str, temperature: float = 0.65) -> Optional[str]:
        """Panggilan AI terus ke OpenRouter API dengan kawalan ralat & cubaan semula."""
        if not self.api_key or not self.model:
            return None

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json; charset=utf-8",
            "HTTP-Referer": "https://sembangpctech.local",
            "X-Title": "Sembang PC & Tech Reels Bot",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt.strip()},
                {"role": "user", "content": user_prompt.strip()},
            ],
            "temperature": temperature,
            "max_tokens": 400,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0,
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
                        if is_valid_reel_caption(cleaned_text):
                            return cleaned_text
            except Exception as e:
                print(f"⚠️ [Pexels Reel AI Attempt {attempt + 1} Warn]: {e}")

        return None

    def generate_reel_caption(
        self,
        topic_keyword: str,
        previous_memories: Optional[List[str]] = None,
        slot_override: Optional[str] = None,
    ) -> str:
        """
        Menjana kapsyen pendek (*micro-hook*) khusus untuk video Facebook Reels
        dengan fokus mencetuskan interaksi di ruangan komen.
        """
        slot_id, slot_desc, day_mood, temp = detect_reel_time_slot()
        if slot_override:
            slot_id = slot_override

        memory_context = ""
        if previous_memories and len(previous_memories) > 0:
            formatted_memories = "\n".join([f"- {m[:100]}..." for m in previous_memories[:4]])
            memory_context = f"""
INGATAN REELS LEPAS (JANGAN ULANG SOALAN ATAU AYAT SAMA):
{formatted_memories}
"""

        system_prompt = f"""
Anda adalah "Brader Din", pencipta kandungan Facebook Reels di komuniti Sembang PC & Tech Malaysia.
Video Reels ini memaparkan visual estetik bertemakan: '{topic_keyword}'.

WAKTU HANTARAN (MALAYSIA): {slot_desc}
MOOD HARI INI: {day_mood}
{memory_context}
PANDUAN PENULISAN REELS (SANGAT KETAT):
1. Panjang Kapsyen: WAJIB PENDEK (Maksimum 250 aksara) kerana video Reels memerlukan teks ringkas yang pantas dibaca penonton.
2. Fasa 1 (Hook Pantas): 1 atau 2 ayat santai tentang visual video tech ini.
3. Fasa 2 (Call to Engagement): 1 soalan santai & menarik untuk mengajak penonton berbalas komen (contoh: bandingkan cita rasa setup, switch keyboard, atau cara kerja).
4. Fasa 3 (Hashtags): Akhiri dengan 4 hingga 6 hashtag relevan (#SembangPCTech #TechMalaysia #ReelsMalaysia #PCSetup #Workspace).
5. DILARANG meletakkan link pautan belian (Reel ini adalah kandungan lifestyle / engagement organik).
6. DILARANG sebarang mukadimah AI (TERUS TULIS AYAT KANDUNGAN).
"""

        user_prompt = f"""
Hasilkan kapsyen Facebook Reel bertemakan visual '{topic_keyword}'.
Tuliskan teks kapsyen lengkap sekarang:
"""

        caption = self._call_openrouter(system_prompt, user_prompt, temperature=temp)
        if not caption:
            caption = (
                f"Bila susun atur meja kemas dan visual setup sedap mata memandang, semangat nak buat kerja terus naik level. ✨🖥️\n\n"
                f"Korang jenis suka setup minimalis ringkas atau penuh dengan lampu ambient waktu malam? Cuba kongsikan sikit di ruang komen! 👇\n\n"
                f"#SembangPCTech #TechMalaysia #ReelsMalaysia #PCSetup #WorkspaceInspiration"
            )

        return caption


# Singleton instance
pexels_ai = PexelsAIPersona()