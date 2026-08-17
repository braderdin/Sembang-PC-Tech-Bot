#!/usr/bin/env python3
"""
Dedicated Bluesky AI Persona Engine (Brader Din Style - AT-Protocol Optimized)
Sembang PC & Tech Ecosystem (100% Dynamic OpenRouter & Glitch-Proof)
Features:
- Micro-Blogging & High-Engagement Persona for Bluesky Feed (Strict < 280 Chars)
- Dynamic Malaysian Time-Slot & Mood Awareness (MYT = UTC+8)
- 4 Specialized Formats:
    1. Affiliate Product Review (Card Embed Ready)
    2. Lifestyle Workspace Story (Unsplash Visuals)
    3. Vertical Video Post (Pexels + Smart Music Metadata)
    4. Auto-Reply Affiliate Comment Generator (Thread Funnel)
- Strict Anti-Glitch & Malay Language Anchor Guardrails
- 2-Attempt Auto-Retry Loop with Resilient Fallback Engine
"""

import os
import re
import requests
from collections import Counter
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Tuple, Dict, Any, Union
from pathlib import Path
from dotenv import load_dotenv

# Set Project Root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
env_local = PROJECT_ROOT / ".env.local"
if env_local.exists():
    load_dotenv(dotenv_path=env_local)
else:
    load_dotenv()

# Kata dasar Bahasa Melayu untuk pengesahan kualiti teks (Guardrails)
MALAY_ANCHOR_WORDS = {
    "yang", "dan", "di", "ke", "kat", "ni", "tu", "dah", "nak", "ada",
    "kita", "korang", "saya", "buat", "bila", "dengan", "pun", "rasa",
    "meja", "setup", "pc", "kerja", "santai", "tengok", "dalam", "untuk",
    "tak", "bukan", "memang", "lagi", "padu", "mantap", "kemas", "layan"
}


def clean_bluesky_text(text: str) -> str:
    """Membersihkan teks daripada token LLM, simbol rosak, dan mukadimah bot."""
    if not text:
        return ""

    # 1. Buang token khas LLM
    text = re.sub(r'<pad>|<unk>|<s>|</s>|\[PAD\]|\[UNK\]|<\|.*?\|>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'[ðâ][\x80-\xbf]{1,4}', '', text)
    text = re.sub(r'[\x80-\x9f]', '', text)

    # 2. Buang mukadimah pembantu AI
    text = re.sub(r'(?i)^\s*(?:yo|hai|salam|hello)?[^\n]*?(?:cadangan|kapsyen|caption|post)[^\n]*?\n+', '', text)
    text = re.sub(r'(?i)\*\*caption\s*(?:bluesky)?\s*:\*\*', '', text)
    text = re.sub(r'(?i)\n+\s*\*{0,2}tips\s*tambahan[^\n]*\*{0,2}[\s\S]*$', '', text)
    text = re.sub(r'\*\*\*', '', text)

    # 3. Kemaskan baris dan ruang kosong
    lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in text.splitlines()]
    return "\n".join([line for line in lines if line]).strip()


def smart_trim_bluesky(text: str, max_chars: int = 280) -> str:
    """
    Memotong teks secara pintar di bawah had ketat 300 aksara Bluesky
    supaya ayat tidak terpotong di tengah-tengah perkataan.
    """
    if not text or len(text) <= max_chars:
        return text

    trimmed = text[:max_chars]
    last_punc = max(trimmed.rfind("."), trimmed.rfind("?"), trimmed.rfind("!"))

    if last_punc != -1 and last_punc > 80:
        return trimmed[: last_punc + 1].strip()

    last_space = trimmed.rfind(" ")
    if last_space != -1:
        return trimmed[:last_space].strip() + "..."

    return trimmed[: max_chars - 3] + "..."


def is_valid_bluesky_caption(text: str, min_len: int = 30, max_len: int = 295) -> bool:
    """Menyemak kualiti teks bagi memastikan kapsyen Bluesky menepati standard ketat."""
    if not text or len(text.strip()) < min_len or len(text.strip()) > max_len:
        return False
    if "<pad>" in text.lower() or "<unk>" in text.lower():
        return False

    if re.search(r'(\b\w+\b)(?:\s+\1){2,}', text, flags=re.IGNORECASE):
        return False

    words = [w.lower() for w in re.findall(r'\b[a-zA-Z]+\b', text)]
    total_words = len(words)
    if total_words < 6:
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


def detect_bluesky_time_slot() -> Tuple[str, str, str, float]:
    """Mengenal pasti slot masa semasa dan mood hari mengikut zon masa Malaysia (MYT = UTC+8)."""
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


class BlueskyAIPersona:
    """Enjin AI Persona khusus untuk mikro-blogging Bluesky."""

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
            "X-Title": "Sembang PC & Tech Bluesky Bot",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt.strip()},
                {"role": "user", "content": user_prompt.strip()},
            ],
            "temperature": temperature,
            "max_tokens": 300,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0,
        }

        for attempt in range(2):
            try:
                res = requests.post(f"{self.base_url}/chat/completions", headers=headers, json=payload, timeout=20)
                res.encoding = "utf-8"
                if res.status_code == 200:
                    data = res.json()
                    if "choices" in data and len(data["choices"]) > 0:
                        raw_text = data["choices"][0]["message"]["content"].strip()
                        cleaned_text = clean_bluesky_text(raw_text)
                        final_text = smart_trim_bluesky(cleaned_text, max_chars=280)
                        if is_valid_bluesky_caption(final_text):
                            return final_text
            except Exception as e:
                print(f"⚠️ [Bluesky AI Attempt {attempt + 1} Warn]: {e}")

        return None

    # -------------------------------------------------------------------------
    # 1. POS PRODUK AFFILIATE (UNTUK KAD PAUTAN BOLEH KLIK)
    # -------------------------------------------------------------------------
    def generate_affiliate_post(self, product_data: Dict[str, Any]) -> str:
        """
        Menjana ulasan produk ringkas & padat (180–250 aksara) untuk Bluesky.
        Disertakan dengan kad pautan produk di bahagian bawah.
        """
        title = product_data.get("title", "Aksesori Komputer & Gajet")
        price = product_data.get("price", "")

        price_info = f" (Anggaran: RM {price})" if price else ""

        system_prompt = f"""
Anda adalah "Brader Din", pencipta kandungan teknologi di Bluesky (@sembangpctech.bsky.social).
Format penulisan ialah MIKRO-BLOG (Sangat Ringkas, Padat, Padu & Menarik).

SYARAT PENULISAN BLUESKY (SANGAT KETAT):
1. Panjang Teks: WAJIB ANTARA 180 HINGGA 250 AKSARA SAHAJA (Maksimum 270 aksara).
2. Bahasa: Bahasa Melayu santai komuniti tech Malaysia ("Barang padu ni...", "Korang yang nak kemaskan setup...", "Berbaloi sangat...").
3. Struktur: 
   - 1 ayat hook ulasan fungsi barang.
   - 1 ayat ajak tengok kad pautan di bawah.
   - 2 hashtag tech di hujung (#SembangPCTech #RacunGajet).
4. DILARANG letak link URL mentah dalam teks (kad pautan embed sudah disediakan).
5. DILARANG sebarang mukadimah bot (TERUS TULIS AYAT KANDUNGAN).
"""

        user_prompt = f"""
Hasilkan pos Bluesky untuk produk: {title}{price_info}
Tulis teks lengkap sekarang:
"""

        caption = self._call_openrouter(system_prompt, user_prompt, temperature=0.65)
        if not caption:
            caption = smart_trim_bluesky(
                f"Korang yang tengah nak kemaskan ruang meja atau upgrade barang kerja, tengok yang ni! ⚡ Rekaan kemas dan sangat berbaloi untuk kegunaan harian. Tekan kad di bawah untuk info lanjut! 👇\n\n#SembangPCTech #RacunGajet",
                max_chars=270
            )

        return caption

    # -------------------------------------------------------------------------
    # 2. POS LIFESTYLE SETUP (UNTUK ALBUM GAMBAR UNSPLASH)
    # -------------------------------------------------------------------------
    def generate_lifestyle_post(
        self,
        topic_keyword: str,
        image_context: Optional[str] = None,
        previous_memories: Optional[List[str]] = None
    ) -> str:
        """
        Menjana kapsyen santai inspirasi meja kerja & gaya hidup komputer (180–260 aksara).
        """
        slot_id, slot_desc, day_mood, temp = detect_bluesky_time_slot()

        memory_context = ""
        if previous_memories and len(previous_memories) > 0:
            formatted_memories = "\n".join([f"- {m[:80]}..." for m in previous_memories[:3]])
            memory_context = f"\nINGATAN POS LEPAS (JANGAN ULANG AYAT SAMA):\n{formatted_memories}\n"

        system_prompt = f"""
Anda adalah "Brader Din", berkongsi gambar inspirasi setup meja kerja dan lifestyle teknologi di Bluesky.

WAKTU MALAYSIA: {slot_desc}
MOOD HARI: {day_mood}
TEMA VISUAL: '{topic_keyword}' ({image_context or 'Ruang meja kemas & fokus'})
{memory_context}
SYARAT PENULISAN (SANGAT KETAT):
1. Panjang Teks: ANTARA 180 HINGGA 260 AKSARA SAHAJA.
2. Nada: Tenang, santai, mesra komuniti tech.
3. Struktur:
   - 1-2 ayat tentang ketenangan meja kemas atau fokus kerja.
   - 1 soalan santai untuk interaksi warga Bluesky.
   - 2 hashtag (#SembangPCTech #DeskSetup).
4. DILARANG letak link jualan atau perkataan iklan.
5. DILARANG mukadimah AI.
"""

        user_prompt = f"""
Hasilkan 1 pos Bluesky santai tentang suasana '{topic_keyword}'.
Tuliskan teks sekarang:
"""

        caption = self._call_openrouter(system_prompt, user_prompt, temperature=temp)
        if not caption:
            caption = smart_trim_bluesky(
                f"Bila ruang kerja kemas dan bebas serabut macam ni, rasa tenang sangat nak duduk lama siapkan projek. ☕🖥️ Korang jenis suka setup minimalis atau penuh lampu ambient? Cer share sikit!\n\n#SembangPCTech #DeskSetup",
                max_chars=270
            )

        return caption

    # -------------------------------------------------------------------------
    # 3. POS VIDEO REELS (PEXELS + METADATA MUZIK)
    # -------------------------------------------------------------------------
    def generate_video_post(
        self,
        topic_keyword: str,
        music_info: Optional[Union[Dict[str, Any], str]] = None,
        video_duration: Optional[int] = None,
        previous_memories: Optional[List[str]] = None
    ) -> str:
        """
        Menjana kapsyen video pendek berserta sebutan lagu latar (200–270 aksara).
        """
        slot_id, slot_desc, day_mood, temp = detect_bluesky_time_slot()

        if isinstance(music_info, dict):
            song_title = music_info.get("title", "Original Audio")
            song_artist = music_info.get("artist", "")
        elif isinstance(music_info, str):
            song_title = music_info
            song_artist = ""
        else:
            song_title = "Original Audio"
            song_artist = ""

        has_music = song_title and song_title not in ["Original Audio", ""]
        music_hint = f"Video diiringi trek santai '{song_title}'." if has_music else "Fokus pada visual santai."

        system_prompt = f"""
Anda adalah "Brader Din", menyiarkan klip video 9:16 di Bluesky Video Feed.

WAKTU: {slot_desc} | MOOD: {day_mood}
TEMA VIDEO: '{topic_keyword}' | {music_hint}

SYARAT PENULISAN (SANGAT KETAT):
1. Panjang Teks: WAJIB ANTARA 200 HINGGA 270 AKSARA SAHAJA.
2. Selitkan santai nama lagu '{song_title}' jika sesuai bersama mood visual teknologi.
3. 1 soalan santai untuk berbalas komen + 2 hashtag (#SembangPCTech #ReelsTech).
4. DILARANG melebihi 280 aksara.
"""

        user_prompt = f"""
Hasilkan kapsyen video Bluesky bertemakan '{topic_keyword}'.
Tuliskan teks lengkap:
"""

        caption = self._call_openrouter(system_prompt, user_prompt, temperature=temp)
        if not caption:
            music_part = f" sambil layan trek '{song_title}'" if has_music else ""
            caption = smart_trim_bluesky(
                f"Layan visual setup ni{music_part}, memang terapi minda lepas seharian mengadap skrin. 🛠️✨ Korang kalau buat kerja suka suasana sunyi atau wajib ada muzik latar? Jom sembang di komen! 👇\n\n#SembangPCTech #ReelsTech",
                max_chars=275
            )

        return caption

    # -------------------------------------------------------------------------
    # 4. BALASAN KOMEN PERTAMA AFFILIATE (THREAD AUTO-REPLY)
    # -------------------------------------------------------------------------
    def generate_affiliate_comment(self, product_title: str, affiliate_link: str) -> str:
        """
        Menjana teks komen pertama yang padat (60–120 aksara) untuk memautkan
        pautan affiliate di bawah pos gambar / video.
        """
        short_title = product_title[:45].strip()
        return f"👉 Nak usha tawaran rasmi {short_title}? Boleh tengok info & link promosi di sini: {affiliate_link} 🔥"


# Singleton instance
bluesky_ai = BlueskyAIPersona()