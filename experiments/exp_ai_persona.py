#!/usr/bin/env python3
"""
Reddit Tech Storyteller Engine - Experiment 3: Rate-Limited Multi-Platform AI Persona
Lokasi Fail: experiments/exp_ai_persona.py

Ciri-ciri Utama:
1. Cooldown Pacing: Jeda masa 3-4 saat antara setiap panggilan API OpenRouter bagi mengelakkan sekatan kadar (Rate Limit / HTTP 429).
2. 429 Rate-Limit Auto-Recovery: Mengesan HTTP 429 dan menunggu secara automatik (Backoff) sebelum mencuba semula.
3. Penjanaan Mengikut Urutan: Memproses satu demi satu platform secara tersusun (FB -> Threads -> IG -> Bluesky).
4. Guardrails Kualiti: Menapis pengulangan perkataan >10x, mojibake, token rosak, dan bahasa asing.
"""

import os
import sys
import re
import json
import time
import requests
from pathlib import Path
from collections import Counter
from typing import Dict, Any, Tuple, Optional
from dotenv import load_dotenv

# 1. Konfigurasi Laluan Projek & Environment
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

env_local = PROJECT_ROOT / ".env.local"
if env_local.exists():
    load_dotenv(dotenv_path=env_local)
else:
    load_dotenv()

# Import enjin fetcher daripada Experiment 1 jika tersedia
try:
    from experiments.exp_reddit_fetch import select_best_reddit_story
except ImportError:
    select_best_reddit_story = None

# =============================================================================
# 2. GUARDRAILS & PERATURAN BAHASA MELAYU
# =============================================================================
MALAY_ANCHOR_WORDS = {
    "yang", "dan", "di", "ke", "kat", "ni", "tu", "dah", "nak", "ada",
    "kita", "korang", "saya", "buat", "bila", "dengan", "pun", "rasa",
    "meja", "setup", "pc", "kerja", "santai", "tengok", "dalam", "untuk",
    "tak", "bukan", "memang", "lagi", "padu", "kemas", "hujung", "minggu",
    "malam", "pagi", "petang", "gajet", "murah", "berbaloi", "cerita", "abang"
}

FORBIDDEN_WORDS = {
    "bisa", "banget", "nggak", "ngak", "gimana", "komputer jinjing",
    "unduh", "unggah", "ponsel", "kamu", "anda"
}


def clean_ai_text(text: str) -> str:
    """Membersihkan token LLM, simbol pelik, mojibake, dan mukadimah pembantu AI."""
    if not text:
        return ""

    text = re.sub(r'<pad>|<unk>|<s>|</s>|\[PAD\]|\[UNK\]|<\|.*?\|>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'[ðâ][\x80-\xbf]{1,4}', '', text)
    text = re.sub(r'[\x80-\x9f]', '', text)

    for sym in ["❖", "◆", "◇", "►", "▪", "▲", "★", "➡", "➢", "*", "-"]:
        text = text.replace(sym, "•")

    text = re.sub(r'(?i)^\s*(?:yo|hai|salam|hello)?[^\n]*?(?:cadangan|kapsyen|caption|post|hantaran|cerita|kisah|ulasan)[^\n]*?\n+', '', text)
    text = re.sub(r'(?i)\*\*caption\s*(?:facebook|threads|instagram|bluesky)?\s*:\*\*', '', text)
    text = re.sub(r'\*\*\*', '', text)
    text = re.sub(r'[^\x00-\x7F\u00C0-\u024F\s.,!?:;\'"()/\-#@+•]', '', text)

    lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in text.splitlines()]
    return "\n".join([line for line in lines if line]).strip()


def smart_trim_text(text: str, max_chars: int) -> str:
    """Memotong teks secara kemas pada tanda baca terakhir."""
    if not text or len(text) <= max_chars:
        return text

    trimmed = text[:max_chars]
    last_punc = max(trimmed.rfind('.'), trimmed.rfind('!'), trimmed.rfind('?'), trimmed.rfind('\n'))

    if last_punc != -1 and last_punc > (max_chars * 0.6):
        return trimmed[:last_punc + 1].strip()

    last_space = trimmed.rfind(' ')
    if last_space != -1:
        return trimmed[:last_space].strip() + "..."
    return trimmed[:max_chars - 3].strip() + "..."


def validate_story_quality(text: str, min_chars: int = 60, max_chars: int = 1000) -> Tuple[bool, str]:
    """Menyemak kesahan kualiti bahasa, kepelbagaian perkataan, dan bebas gelung rosak."""
    if not text or len(text.strip()) < min_chars:
        return False, f"Teks terlalu pendek ({len(text.strip())} aksara)."
    if len(text.strip()) > max_chars + 30:
        return False, f"Teks melebihi had siling ({len(text.strip())}/{max_chars} aksara)."

    if re.search(r'(\b\w+\b)(?:\s+\1){2,}', text, flags=re.IGNORECASE):
        return False, "Dikesan pengulangan perkataan berturut-turut."

    lower_text = text.lower()
    for forbidden in FORBIDDEN_WORDS:
        if re.search(r'\b' + re.escape(forbidden) + r'\b', lower_text):
            return False, f"Dikesan perkataan terlarang: '{forbidden}'."

    words = [w.lower() for w in re.findall(r'\b[a-zA-Z]+\b', text)]
    total_words = len(words)
    if total_words < 10:
        return False, "Jumlah perkataan tidak mencukupi."

    word_counts = Counter(words)
    for word, count in word_counts.items():
        if len(word) >= 3 and count >= 10:
            return False, f"Perkataan '{word}' berulang sebanyak {count} kali (Melebihi had 10x)."
        if len(word) >= 4 and (count / total_words) > 0.20:
            return False, f"Kekerapan perkataan '{word}' terlalu tinggi ({count}/{total_words})."

    unique_words = set(words)
    if len(unique_words) / total_words < 0.38:
        return False, "Kepelbagaian kosa kata terlalu rendah."

    matching_anchors = unique_words.intersection(MALAY_ANCHOR_WORDS)
    if len(matching_anchors) < 2:
        return False, f"Teks tidak memenuhi standard Bahasa Melayu (Sauh dikesan: {len(matching_anchors)})."

    return True, "Kualiti Teks Sah"


# =============================================================================
# 3. ENJIN AI PERSONA DENGAN JEDA MASA & AUTO-BACKOFF
# =============================================================================
class RedditStoryAIPersona:
    def __init__(self):
        self.base_url = (os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1").strip().rstrip("/")
        self.model = os.getenv("OPENROUTER_MODEL", "").strip()
        self.api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        self.temperature = 0.65
        self.max_tokens = 1000
        self.request_delay_seconds = 3.5  # Jeda masa selamat antara request

    def _call_openrouter_with_retry(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Menghantar permintaan ke OpenRouter dengan sokongan pengendalian HTTP 429."""
        if not self.base_url or not self.model or not self.api_key:
            print("  ⚠️ [AI WARN] Kunci OpenRouter tidak lengkap.")
            return None

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json; charset=utf-8",
            "HTTP-Referer": "https://sembangpctech.local",
            "X-Title": "Sembang PC & Tech Reddit Storyteller",
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt.strip()},
                {"role": "user", "content": user_prompt.strip()},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "presence_penalty": 0.1,
            "frequency_penalty": 0.2
        }

        url = f"{self.base_url}/chat/completions"

        for attempt in range(3):
            try:
                res = requests.post(url, json=payload, headers=headers, timeout=60)
                res.encoding = "utf-8"

                # Pengendalian Had Kadar (Rate Limit - HTTP 429)
                if res.status_code == 429:
                    wait_time = 5 * (attempt + 1)
                    print(f"  ⚠️ [RATE LIMIT 429] Pelayan OpenRouter sibuk. Menunggu {wait_time} saat sebelum cuba semula...")
                    time.sleep(wait_time)
                    continue

                if res.status_code == 200:
                    data = res.json()
                    if "choices" in data and len(data["choices"]) > 0:
                        content = data["choices"][0]["message"]["content"].strip()
                        # Rehatkan sambungan selepas berjaya
                        time.sleep(self.request_delay_seconds)
                        return content
                else:
                    print(f"  ⚠️ [AI HTTP {res.status_code}]: {res.text[:120]}")
                    time.sleep(3)

            except Exception as e:
                print(f"  ⚠️ [AI EXCEPTION]: {e}")
                time.sleep(3)

        return None

    # -------------------------------------------------------------------------
    # A. FACEBOOK PAGE PERSONA (500 - 750 AKSARA)
    # -------------------------------------------------------------------------
    def generate_facebook_story(self, post_data: Dict[str, Any], temporal_ctx: Dict[str, Any]) -> str:
        title = post_data.get("title", "")
        text = post_data.get("cleaned_text", "")
        sub = post_data.get("subreddit", "tech")
        slot_label = temporal_ctx.get("slot_label", "Malam Santai")
        slot_mood = temporal_ctx.get("slot_mood", "Santai lepak tech")

        system_prompt = f"""
Anda adalah "Abang Din", pengasas Facebook Page "Sembang PC & Tech Malaysia".
Gaya: Storytelling santai, kelakar sempoi, dan berkongsi ibrah tech bermanfaat.
KONTEKS MASA: Waktu {slot_label} ({slot_mood}).

SYARAT (500 - 750 AKSARA):
1. 100% Bahasa Melayu santai harian Malaysia. Dilarang guna Bahasa Indonesia.
2. Struktur: Hook penceritaan -> 2-3 poin ulasan menarik/tips -> 1 soalan santai di akhir ayat.
3. Sertakan hashtags rasmi: #SembangPCTech #TechMalaysia #PCSetup #KisahTech
4. DILARANG letak link URL.
"""

        user_prompt = f"""
Topik Reddit r/{sub}:
- Tajuk Asal: {title}
- Kandungan: {text[:500] if text else 'Kisah perkongsian inovasi/modding tech.'}

Tulis 1 kapsyen Facebook lengkap (500 - 750 aksara):
"""

        fallback = (
            f"Korang yang tengah layan setup meja atau rileks santai, jom tengok perkongsian daripada r/{sub} ni. "
            f"Bila sebut pasal inovasi tech, memang tak pernah habis idea kreatif yang muncul.\n\n"
            f"Antara perkara menarik yang kita boleh tengok:\n"
            f"• Kreativiti susun atur dan penyelesaian masalah praktikal\n"
            f"• Memberi inspirasi baru untuk kemaskan ruang kerja kita\n\n"
            f"Korang sendiri pernah buat modding atau setup pelik macam ni tak? Drop komen korang! 👇\n\n"
            f"#SembangPCTech #TechMalaysia #PCSetup #KisahTech"
        )

        print("🤖 [1/4] Menjana kapsyen Facebook Page Feed...")
        raw = self._call_openrouter_with_retry(system_prompt, user_prompt)
        if raw:
            cleaned = clean_ai_text(raw)
            trimmed = smart_trim_text(cleaned, max_chars=750)
            is_valid, _ = validate_story_quality(trimmed, min_chars=300, max_chars=750)
            if is_valid:
                if "#SembangPCTech" not in trimmed:
                    trimmed += "\n\n#SembangPCTech #TechMalaysia #PCSetup"
                return trimmed

        return fallback

    # -------------------------------------------------------------------------
    # B. META THREADS PERSONA (<= 480 AKSARA)
    # -------------------------------------------------------------------------
    def generate_threads_story(self, post_data: Dict[str, Any], temporal_ctx: Dict[str, Any]) -> str:
        title = post_data.get("title", "")
        text = post_data.get("cleaned_text", "")
        sub = post_data.get("subreddit", "tech")

        system_prompt = """
Anda ialah "Abang Din" di Meta Threads untuk "Sembang PC & Tech Malaysia".
Format: MIKRO-BLOG SPONTAN (Ringkas, Padat, Santai, dan Berbisa).

SYARAT (HAD KETAT <= 480 AKSARA):
1. 100% Bahasa Melayu santai komuniti tech.
2. 2-3 ayat ulasan spontan + 1 soalan santai memancing komen.
3. Hashtags: #SembangPCTech #TechMY
4. DILARANG letak link URL.
"""

        user_prompt = f"""
Topik Reddit r/{sub}:
- Tajuk: {title}
- Kisah: {text[:250] if text else 'Kongsian inovasi hardware/setup'}

Tulis 1 hantaran mikro Threads (Maksimum 450 aksara):
"""

        fallback = (
            f"Tengok perkongsian r/{sub} pasal {title[:40]} ni, memang kreatif betul idea dorang. "
            f"Kadang benda simple macam ni yang buat setup kita rasa puas lain macam. "
            f"Korang pernah cuba modding kreatif macam ni tak kat setup sendiri?\n\n"
            f"#SembangPCTech #TechMY"
        )

        print("🧵 [2/4] Menjana kapsyen Meta Threads Feed...")
        raw = self._call_openrouter_with_retry(system_prompt, user_prompt)
        if raw:
            cleaned = clean_ai_text(raw)
            trimmed = smart_trim_text(cleaned, max_chars=480)
            is_valid, _ = validate_story_quality(trimmed, min_chars=100, max_chars=480)
            if is_valid:
                if "#SembangPCTech" not in trimmed:
                    trimmed = smart_trim_text(trimmed, max_chars=440) + "\n\n#SembangPCTech #TechMY"
                return trimmed

        return fallback

    # -------------------------------------------------------------------------
    # C. INSTAGRAM PERSONA (500 - 750 AKSARA)
    # -------------------------------------------------------------------------
    def generate_instagram_story(self, post_data: Dict[str, Any], temporal_ctx: Dict[str, Any]) -> str:
        title = post_data.get("title", "")
        text = post_data.get("cleaned_text", "")
        sub = post_data.get("subreddit", "tech")

        system_prompt = """
Anda adalah "Abang Din" di Instagram @SembangPCTech Malaysia.
Gaya: Visual Storytelling yang santai, estetik, dan memberi inspirasi setup tech.

SYARAT (500 - 750 AKSARA):
1. 100% Bahasa Melayu santai. Dilarang guna Bahasa Indonesia.
2. Hook visual -> 2 poin kelebihan/ibrah guna bullet (•) -> Seruan komen di akhir.
3. Hashtags: #SembangPCTech #SetupInspirasi #PCGamerMY #RacunSetup #TechLifestyle
4. DILARANG letak sebarang URL.
"""

        user_prompt = f"""
Topik Reddit r/{sub}:
- Tajuk: {title}
- Kandungan: {text[:400] if text else 'Kongsian visual tech & setup'}

Hasilkan 1 kapsyen Instagram berkualiti (500 - 750 aksara):
"""

        fallback = (
            f"Kreativiti tanpa batas bila peminat teknologi berkongsi karya mereka di r/{sub}. "
            f"Bukan sekadar perkakasan, tapi kepuasan bila ruang kerja dan hobi kita bergabung kemas.\n\n"
            f"• Inspirasi susun atur yang lebih kemas & estetik\n"
            f"• Nilai kepuasan yang menaikkan mood produktiviti harian\n\n"
            f"Korang suka konsep macam ni atau lebih minat gaya klasik? Drop pandangan korang di bawah ya! 👇\n\n"
            f"#SembangPCTech #SetupInspirasi #PCGamerMY #RacunSetup #TechLifestyle"
        )

        print("📸 [3/4] Menjana kapsyen Instagram Feed...")
        raw = self._call_openrouter_with_retry(system_prompt, user_prompt)
        if raw:
            cleaned = clean_ai_text(raw)
            trimmed = smart_trim_text(cleaned, max_chars=750)
            is_valid, _ = validate_story_quality(trimmed, min_chars=300, max_chars=750)
            if is_valid:
                if "#SembangPCTech" not in trimmed:
                    trimmed += "\n\n#SembangPCTech #SetupInspirasi #PCGamerMY"
                return trimmed

        return fallback

    # -------------------------------------------------------------------------
    # D. BLUESKY SOCIAL PERSONA (<= 295 AKSARA)
    # -------------------------------------------------------------------------
    def generate_bluesky_story(self, post_data: Dict[str, Any], temporal_ctx: Dict[str, Any]) -> str:
        title = post_data.get("title", "")
        text = post_data.get("cleaned_text", "")
        sub = post_data.get("subreddit", "tech")

        system_prompt = """
Anda ialah "Abang Din" di Bluesky Social untuk "Sembang PC & Tech Malaysia".
Format: ANEKDOT PADAT & TAJAM (Hard Limit <= 295 Aksara).

SYARAT:
1. 100% Bahasa Melayu santai dan terus ke inti pati cerita.
2. Panjang badan ulasan: 100 hingga 180 aksara.
3. Wajib hashtag pendek di hujung: #SembangPCTech #TechMY
4. JUMLAH KESELURUHAN WAJIB <= 290 AKSARA.
"""

        user_prompt = f"""
Topik Reddit r/{sub}:
- Tajuk: {title}
- Ringkasan: {text[:180] if text else 'Kongsian inovasi hardware tech'}

Tulis 1 hantaran Bluesky padat (Maksimum 270 aksara):
"""

        fallback = (
            f"Kreatif betul perkongsian r/{sub} pasal {title[:35]} ni. "
            f"Bila tech jumpa seni, memang lain macam hasilnya!\n\n"
            f"#SembangPCTech #TechMY"
        )

        print("🦋 [4/4] Menjana ulasan Bluesky Feed...")
        raw = self._call_openrouter_with_retry(system_prompt, user_prompt)
        if raw:
            cleaned = clean_ai_text(raw)
            trimmed = smart_trim_text(cleaned, max_chars=295)
            is_valid, _ = validate_story_quality(trimmed, min_chars=50, max_chars=295)
            if is_valid:
                if "#SembangPCTech" not in trimmed:
                    trimmed = smart_trim_text(trimmed, max_chars=260) + "\n\n#SembangPCTech #TechMY"
                return trimmed

        return fallback


# =============================================================================
# 4. RUNNER UJIAN EKSPERIMEN 3
# =============================================================================
if __name__ == "__main__":
    print("\n" + "=" * 75)
    print("🚀 [EXPERIMENT 3] MEMULAKAN UJIAN MULTI-PLATFORM AI PERSONA (RATE-LIMITED)")
    print("=" * 75)

    story_data = None
    myt_context = {"slot_label": "Malam Santai (08:15 PM)", "slot_mood": "Santai lepak & modding"}

    if select_best_reddit_story:
        print("\n📡 Mengambil data pos Reddit langsung daripada Experiment 1...")
        ok_fetch, fetched_story, ctx, _ = select_best_reddit_story()
        if ok_fetch and fetched_story:
            story_data = fetched_story
            myt_context = ctx

    if not story_data:
        print("\nℹ️ Menggunakan data ujian mock...")
        story_data = {
            "post_id": "mock_dragon_k2",
            "subreddit": "MechanicalKeyboards",
            "title": "Dragon - Custom East Asian Keycaps on Keychron K2 Max",
            "cleaned_text": "Quadrilingual custom keycaps featuring East Asian languages: Chinese, Japanese, and Korean. Built on Keychron K2 Max.",
            "image_url": "https://i.redd.it/sk5mr5ifvgkh1.jpeg"
        }

    print("\n" + "-" * 75)
    print(f"📦 [DATA INPUT POS]:")
    print(f"   📌 Subreddit     : r/{story_data.get('subreddit')}")
    print(f"   📖 Tajuk         : {story_data.get('title')}")
    print(f"   🕒 Konteks Waktu : {myt_context.get('slot_label')}")
    print("-" * 75 + "\n")

    ai_persona = RedditStoryAIPersona()

    # Jalankan janaan satu demi satu dengan jeda masa
    fb_caption = ai_persona.generate_facebook_story(story_data, myt_context)
    threads_caption = ai_persona.generate_threads_story(story_data, myt_context)
    ig_caption = ai_persona.generate_instagram_story(story_data, myt_context)
    bluesky_caption = ai_persona.generate_bluesky_story(story_data, myt_context)

    # Paparan Hasil
    print("\n" + "=" * 75)
    print("📊 [HASIL JANAAN AI PERSONA BERJAYA (RATE-LIMITED & GLITCH-PROOF)]")
    print("=" * 75)

    print(f"\n📘 1. FACEBOOK PAGE FEED ({len(fb_caption)} Aksara):")
    print("-" * 75)
    print(fb_caption)

    print(f"\n🧵 2. META THREADS FEED ({len(threads_caption)} Aksara):")
    print("-" * 75)
    print(threads_caption)

    print(f"\n📸 3. INSTAGRAM FEED ({len(ig_caption)} Aksara):")
    print("-" * 75)
    print(ig_caption)

    print(f"\n🦋 4. BLUESKY SOCIAL FEED ({len(bluesky_caption)} Aksara):")
    print("-" * 75)
    print(bluesky_caption)

    print("\n" + "=" * 75)
    print("✨ Ujian 3 Selesai dengan Jayanya!\n")