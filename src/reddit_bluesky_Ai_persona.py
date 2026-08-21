#!/usr/bin/env python3
"""
Reddit Tech Storyteller Engine: Bluesky Social AI Persona Module
Lokasi Fail: src/reddit_bluesky_Ai_persona.py

Ciri-ciri Penambahbaikan (Tuned):
1. Dinamik 100% (Sifar Hardcode Model): Membaca REDDIT_OPENROUTER_MODEL, REDDIT_OPENROUTER_MODEL_FALLBACK, dan fallback am OPENROUTER_MODEL secara telus daripada persekitaran.
2. Penyingkiran Penalti Inferens: Membuang parameter presence_penalty dan frequency_penalty untuk menjamin kestabilan model Gemma 4 di pelayan percuma OpenRouter.
3. Penapis Anti-Thinking & Reasoning Scrubber: Membuang tag <think>...</think>, perenggan analisis draf, mojibake, dan token LLM rosak secara agresif.
4. Had Siling Ketat (<= 295 Aksara): Mengukuhkan persona Abang Din untuk menghasilkan anekdot tech padat, tajam, dan santai (Sasaran Selamat: 240 – 285 Aksara).
"""

import os
import re
import time
import requests
from collections import Counter
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Tuple, Optional

# =============================================================================
# 1. TETAPAN TEMPORAL MYT & GUARDRAILS BAHASA
# =============================================================================
MYT_TIMEZONE = timezone(timedelta(hours=8))

NAMA_HARI_MALAY = {
    "Monday": "Isnin", "Tuesday": "Selasa", "Wednesday": "Rabu",
    "Thursday": "Khamis", "Friday": "Jumaat", "Saturday": "Sabtu", "Sunday": "Ahad"
}

NAMA_BULAN_MALAY = {
    1: "Januari", 2: "Februari", 3: "Mac", 4: "April",
    5: "Mei", 6: "Jun", 7: "Julai", 8: "Ogos",
    9: "September", 10: "Oktober", 11: "November", 12: "Disember"
}

MALAY_ANCHOR_WORDS = {
    "yang", "dan", "di", "ke", "kat", "ni", "tu", "dah", "nak", "ada",
    "kita", "korang", "saya", "buat", "bila", "dengan", "pun", "rasa",
    "meja", "setup", "pc", "kerja", "santai", "tengok", "dalam", "untuk",
    "tak", "bukan", "memang", "lagi", "padu", "kemas", "gajet", "berbaloi"
}

FORBIDDEN_WORDS = {
    "bisa", "banget", "nggak", "ngak", "gimana", "komputer jinjing",
    "unduh", "unggah", "ponsel", "kamu", "anda"
}


def get_current_myt_details() -> Dict[str, Any]:
    """Membina format ringkas konteks masa Malaysia (MYT / UTC+8)."""
    now = datetime.now(MYT_TIMEZONE)
    day_en = now.strftime("%A")
    day_my = NAMA_HARI_MALAY.get(day_en, day_en)
    month_my = NAMA_BULAN_MALAY.get(now.month, now.strftime("%B"))

    return {
        "full_date_str": f"{now.day} {month_my} {now.year}",
        "time_str": now.strftime("%I:%M %p"),
        "day_my": day_my,
        "formatted_context": f"{day_my}, {now.day} {month_my} {now.year}, {now.strftime('%I:%M %p')} MYT"
    }


def clean_bluesky_text(text: str) -> str:
    """
    Membersihkan token LLM, tag pemikiran reasoning (<think>),
    simbol mojibake, dan merapikan susunan teks Bluesky.
    """
    if not text:
        return ""

    # 1. Buang sebarang blok pemikiran model reasoning
    text = re.sub(r'<think>[\s\S]*?</think>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'(?i)here\'?s\s+a\s+thinking\s+process[\s\S]*?\n\n', '', text)
    text = re.sub(r'(?i)^\s*analyze\s+the\s+request[\s\S]*?\n\n', '', text)

    # 2. Buang token khas LLM
    text = re.sub(r'<pad>|<unk>|<s>|</s>|\[PAD\]|\[UNK\]|<\|.*?\|>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'[ðâ][\x80-\xbf]{1,4}', '', text)
    text = re.sub(r'[\x80-\x9f]', '', text)

    # 3. Buang mukadimah dan header templat
    text = re.sub(r'(?i)^\s*(?:yo|hai|salam|hello)?[^\n]*?(?:cadangan|kapsyen|caption|post|bluesky)[^\n]*?\n+', '', text)
    text = re.sub(r'(?i)\*\*caption\s*(?:bluesky)?\s*:\*\*', '', text)
    text = re.sub(r'\*\*\*', '', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'[^\x00-\x7F\u00C0-\u024F\s.,!?:;\'"()/\-#@+•]', '', text)

    lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in text.splitlines()]
    return " ".join([line for line in lines if line]).strip()


def smart_trim_bluesky(text: str, max_chars: int = 250) -> str:
    """Memotong teks ulasan secara pintar pada tanda baca atau ruang kosong."""
    if not text or len(text) <= max_chars:
        return text

    trimmed = text[:max_chars]
    last_punc = max(trimmed.rfind('.'), trimmed.rfind('!'), trimmed.rfind('?'))

    if last_punc != -1 and last_punc > 80:
        return trimmed[:last_punc + 1].strip()

    last_space = trimmed.rfind(' ')
    if last_space != -1:
        return trimmed[:last_space].strip() + "..."

    return trimmed[:max_chars - 3].strip() + "..."


def is_valid_bluesky_caption(text: str, min_len: int = 50) -> Tuple[bool, str]:
    """Menyemak kualiti teks Bluesky dan memastikan sifar pengulangan perkataan."""
    if not text or len(text.strip()) < min_len:
        return False, "Teks terlalu pendek."
    if len(text.strip()) > 295:
        return False, f"Teks melebihi had ketat Bluesky ({len(text.strip())}/295 aksara)."

    if re.search(r'(\b\w+\b)(?:\s+\1){2,}', text, flags=re.IGNORECASE):
        return False, "Dikesan pengulangan perkataan berturut-turut."

    lower_text = text.lower()
    for forbidden in FORBIDDEN_WORDS:
        if re.search(r'\b' + re.escape(forbidden) + r'\b', lower_text):
            return False, f"Dikesan perkataan terlarang: '{forbidden}'."

    words = [w.lower() for w in re.findall(r'\b[a-zA-Z]+\b', text)]
    if len(words) < 8:
        return False, "Jumlah perkataan terlalu sedikit."

    word_counts = Counter(words)
    for word, count in word_counts.items():
        if len(word) >= 3 and count >= 6:
            return False, f"Perkataan '{word}' berulang {count} kali."

    unique_words = set(words)
    if len(unique_words) / len(words) < 0.40:
        return False, "Kosa kata kurang bervariasi."

    matching_anchors = unique_words.intersection(MALAY_ANCHOR_WORDS)
    if len(matching_anchors) < 2:
        return False, "Kekurangan kata sauh Bahasa Melayu."

    return True, "Kualiti Sah"


# =============================================================================
# 2. KELAS ENJIN AI PERSONA BLUESKY
# =============================================================================
class RedditBlueskyAIPersona:
    """Enjin AI Persona Bluesky khusus untuk anekdot tech padat (Hard Limit <= 295 Aksara)."""

    def __init__(self):
        self.base_url = (os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1").strip().rstrip("/")
        self.model_primary = (
            os.getenv("REDDIT_OPENROUTER_MODEL", "").strip()
            or os.getenv("OPENROUTER_MODEL", "").strip()
        )
        self.model_fallback = (
            os.getenv("REDDIT_OPENROUTER_MODEL_FALLBACK", "").strip()
            or os.getenv("OPENROUTER_MODEL_FALLBACK", "").strip()
        )
        self.api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        self.temperature = 0.65
        self.max_tokens = 250
        self.cooldown_delay = 3.5

    def _call_llm_api(self, model_name: str, system_prompt: str, user_prompt: str) -> Tuple[bool, Optional[str], str]:
        if not self.base_url or not self.api_key or not model_name:
            return False, None, "Konfigurasi OpenRouter (Base URL, API Key, Model) tidak lengkap dalam persekitaran."

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json; charset=utf-8",
            "HTTP-Referer": "https://sembangpctech.local",
            "X-Title": "Sembang PC & Tech Reddit Bluesky Storyteller",
        }

        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt.strip()},
                {"role": "user", "content": user_prompt.strip()},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }

        url = f"{self.base_url}/chat/completions"

        for attempt in range(2):
            try:
                res = requests.post(url, json=payload, headers=headers, timeout=25)
                res.encoding = "utf-8"

                if res.status_code == 429:
                    wait_sec = 6 * (attempt + 1)
                    print(f"  ⚠️ [BLUESKY AI 429] Model '{model_name}' sesak. Menunggu {wait_sec}s...")
                    time.sleep(wait_sec)
                    continue

                if res.status_code == 200:
                    data = res.json()
                    if "choices" in data and len(data["choices"]) > 0:
                        content = data["choices"][0]["message"]["content"].strip()
                        time.sleep(self.cooldown_delay)
                        return True, content, "Berjaya"
                else:
                    err_snippet = res.text[:100]
                    print(f"  ⚠️ [BLUESKY AI HTTP {res.status_code}]: {err_snippet}")
                    time.sleep(2)

            except Exception as e:
                print(f"  ⚠️ [BLUESKY AI EXCEPTION]: {e}")
                time.sleep(2)

        return False, None, f"Gagal mendapatkan respon daripada model {model_name}"

    def generate_caption(self, post_data: Dict[str, Any], temporal_ctx: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        """
        Menjana kapsyen Bluesky Feed yang padat dan tajam (Maksimum TEGAS <= 295 aksara).
        """
        raw_title = str(post_data.get("title") or "Topik PC Pilihan").strip()
        clean_title = re.sub(r'\s+', ' ', raw_title)[:70].strip()
        cleaned_text = str(post_data.get("cleaned_text") or "").strip()
        subreddit = str(post_data.get("subreddit") or "tech").strip()

        time_info = temporal_ctx if temporal_ctx else get_current_myt_details()
        formatted_time = time_info.get("formatted_context", "Waktu Malaysia (MYT)")

        hashtags_block = "\n\n#SembangPCTech #TechMY"
        max_body_allowed = 290 - len(hashtags_block)  # ~260 aksara untuk teks

        fallback_body = (
            f"Kreatif betul perkongsian komuniti r/{subreddit} pasal {clean_title[:35]} ni. "
            f"Bila tech jumpa seni dan modding, memang lain macam hasilnya!"
        )
        fallback_full = f"{fallback_body[:max_body_allowed]}{hashtags_block}".strip()

        if not self.api_key:
            print("⚠️ [BLUESKY AI WARN] Kunci OpenRouter tiada. Mengaktifkan kapsyen sandaran.")
            return True, fallback_full[:295]

        system_prompt = f"""
Anda ialah "Abang Din" di Bluesky Social untuk "Sembang PC & Tech Malaysia".
Format: ANEKDOT TECH SANGAT PADAT: Terus ke inti pati cerita, tajam, padu, dan santai.

MAKLUMAT MASA SEMASA (MALAYSIA):
{formatted_time}

PANDUAN PENULISAN BLUESKY (HAD KETAT: 100 HINGGA 180 AKSARA UNTUK BADAN TEKS):
1. BAHASA: 100% Bahasa Melayu santai komuniti tech tempatan.
2. DILARANG SAMA SEKALI menggunakan perkataan Bahasa Indonesia ("bisa", "banget", "nggak", "kamu", "anda").
3. STRUKTUR:
   - Nyatakan 1 inti pati menarik daripada topik Reddit ini dengan pantas dan santai.
4. ARAHAN PANTANGAN KETAT:
   - DILARANG letak link URL atau hashtag di dalam respon AI (hashtag dipasang secara automatik).
   - DILARANG tulis proses pemikiran, analisis draf, atau mukadimah AI.
   - TERUS TULIS AYAT KANDUNGAN tanpa mukadimah.
"""

        user_prompt = f"""
Topik Reddit r/{subreddit}:
- Tajuk: {clean_title}
- Ringkasan: {cleaned_text[:200] if cleaned_text else 'Kongsian inovasi perkakasan tech'}

Tulis 1 ulasan pantas Bluesky (100 - 180 aksara sahaja):
"""

        models_queue = [m for m in [self.model_primary, self.model_fallback] if m]

        for model_idx, current_model in enumerate(models_queue, 1):
            print(f"🦋 [BLUESKY AI] Mencuba Model {model_idx}/{len(models_queue)}: '{current_model}'...")
            ok_call, raw_content, msg = self._call_llm_api(current_model, system_prompt, user_prompt)

            if ok_call and raw_content:
                cleaned_body = clean_bluesky_text(raw_content)
                trimmed_body = smart_trim_bluesky(cleaned_body, max_chars=max_body_allowed)

                if "#SembangPCTech" not in trimmed_body:
                    full_post = f"{trimmed_body}{hashtags_block}".strip()
                else:
                    full_post = trimmed_body

                if len(full_post) > 295:
                    excess = len(full_post) - 295
                    trimmed_body = smart_trim_bluesky(trimmed_body, max_chars=len(trimmed_body) - excess - 5)
                    full_post = f"{trimmed_body}{hashtags_block}".strip()

                is_valid, reason = is_valid_bluesky_caption(full_post)

                if is_valid:
                    print(f"✅ [BLUESKY AI SUCCESS] Kapsyen Bluesky berjaya dijana ({len(full_post)}/295 aksara | Model: '{current_model}').")
                    return True, full_post
                else:
                    print(f"⚠️ [BLUESKY AI GUARDRAIL REJECT]: {reason}. Mencuba pusingan seterusnya...")

        print("🛡️ [BLUESKY AI FALLBACK] Mengaktifkan kapsyen Bluesky sandaran selamat.")
        return True, fallback_full[:295]


# Singleton instance untuk kegunaan modular
reddit_bluesky_ai = RedditBlueskyAIPersona()