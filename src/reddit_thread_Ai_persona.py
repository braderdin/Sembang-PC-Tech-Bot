#!/usr/bin/env python3
"""
Reddit Tech Storyteller Engine: Meta Threads AI Persona Module
Lokasi Fail: src/reddit_thread_Ai_persona.py

Ciri-ciri Penambahbaikan (Tuned):
1. Dinamik 100% (Sifar Hardcode Model): Membaca REDDIT_OPENROUTER_MODEL, REDDIT_OPENROUTER_MODEL_FALLBACK, dan fallback am OPENROUTER_MODEL daripada persekitaran.
2. Penapis Anti-Thinking & Reasoning Scrubber: Membuang tag <think>...</think>, perenggan analisis draf (e.g. "Here's a thinking process"), dan token LLM rosak secara agresif.
3. Penyingkiran Penalti Inferens: Membuang parameter presence_penalty dan frequency_penalty untuk keserasian optimum pelayan Gemma 4 di OpenRouter.
4. Kawalan Had Siling Ketat (<= 480 Aksara): Menjamin mikro-blog padat, spontan, dan berbisa tanpa terpotong di Meta Threads.
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
    "tak", "bukan", "memang", "lagi", "padu", "kemas", "hujung", "minggu",
    "malam", "pagi", "petang", "gajet", "murah", "berbaloi", "cerita", "abang"
}

FORBIDDEN_WORDS = {
    "bisa", "banget", "nggak", "ngak", "gimana", "komputer jinjing",
    "unduh", "unggah", "ponsel", "kamu", "anda"
}


def get_current_myt_details() -> Dict[str, Any]:
    """Membina format terperinci masa semasa di Malaysia (MYT / UTC+8)."""
    now = datetime.now(MYT_TIMEZONE)
    day_en = now.strftime("%A")
    day_my = NAMA_HARI_MALAY.get(day_en, day_en)
    month_my = NAMA_BULAN_MALAY.get(now.month, now.strftime("%B"))

    hour = now.hour
    if 4 <= hour < 12:
        slot_desc = "Pagi (Mood Produktif & Segar)"
    elif 12 <= hour < 17:
        slot_desc = "Petang (Mood IT & Aliran Kerja)"
    elif 17 <= hour < 21:
        slot_desc = "Malam (Mood Santai Borak Tech)"
    else:
        slot_desc = "Larut Malam (Mood Santai Kopi & Setup)"

    return {
        "full_date_str": f"{now.day} {month_my} {now.year}",
        "time_str": now.strftime("%I:%M %p"),
        "day_my": day_my,
        "year": now.year,
        "slot_desc": slot_desc,
        "formatted_context": f"{day_my}, {now.day} {month_my} {now.year}, {now.strftime('%I:%M %p')} MYT ({slot_desc})"
    }


def clean_threads_text(text: str) -> str:
    """
    Membersihkan token LLM, tag pemikiran reasoning (<think>),
    mojibake, dan merapikan susunan teks Threads.
    """
    if not text:
        return ""

    # 1. Buang sebarang blok pemikiran model reasoning
    text = re.sub(r'<think>[\s\S]*?</think>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'(?i)here\'?s\s+a\s+thinking\s+process[\s\S]*?\n\n', '', text)
    text = re.sub(r'(?i)^\s*analyze\s+the\s+request[\s\S]*?\n\n', '', text)
    text = re.sub(r'(?i)^\s*1\.\s*\*\*analyze\s+the\s+request\*\*[\s\S]*?\n\n', '', text)

    # 2. Buang token khas LLM
    text = re.sub(r'<pad>|<unk>|<s>|</s>|\[PAD\]|\[UNK\]|<\|.*?\|>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'[ðâ][\x80-\xbf]{1,4}', '', text)
    text = re.sub(r'[\x80-\x9f]', '', text)

    # 3. Buang mukadimah dan header templat
    text = re.sub(r'(?i)^\s*(?:yo|hai|salam|hello)?[^\n]*?(?:cadangan|kapsyen|caption|post|threads)[^\n]*?\n+', '', text)
    text = re.sub(r'(?i)\*\*caption\s*(?:threads)?\s*:\*\*', '', text)
    text = re.sub(r'\*\*\*', '', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'[^\x00-\x7F\u00C0-\u024F\s.,!?:;\'"()/\-#@+•]', '', text)

    lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in text.splitlines()]
    return "\n".join([line for line in lines if line]).strip()


def smart_trim_threads_body(text: str, max_chars: int = 440) -> str:
    """Memotong teks Threads secara pintar pada tanda baca terakhir."""
    if not text or len(text) <= max_chars:
        return text

    trimmed = text[:max_chars]
    last_punc = max(trimmed.rfind('.'), trimmed.rfind('?'), trimmed.rfind('!'), trimmed.rfind('\n'))

    if last_punc != -1 and last_punc > 100:
        return trimmed[:last_punc + 1].strip()

    last_space = trimmed.rfind(' ')
    if last_space != -1:
        return trimmed[:last_space].strip() + "..."
    return trimmed[:max_chars - 3].strip() + "..."


def is_valid_threads_caption(text: str, min_len: int = 80) -> Tuple[bool, str]:
    """Menyemak kualiti mikro-blog Threads dan sifar pengulangan perkataan berlebihan."""
    if not text or len(text.strip()) < min_len:
        return False, "Teks terlalu pendek."
    if len(text.strip()) > 490:
        return False, f"Teks melebihi had Threads ({len(text.strip())}/480 aksara)."

    if re.search(r'(\b\w+\b)(?:\s+\1){2,}', text, flags=re.IGNORECASE):
        return False, "Dikesan pengulangan perkataan berturut-turut."

    lower_text = text.lower()
    for forbidden in FORBIDDEN_WORDS:
        if re.search(r'\b' + re.escape(forbidden) + r'\b', lower_text):
            return False, f"Dikesan perkataan terlarang: '{forbidden}'."

    words = [w.lower() for w in re.findall(r'\b[a-zA-Z]+\b', text)]
    total_words = len(words)
    if total_words < 12:
        return False, "Jumlah perkataan terlalu sedikit."

    word_counts = Counter(words)
    for word, count in word_counts.items():
        if len(word) >= 3 and count >= 8:
            return False, f"Perkataan '{word}' berulang {count} kali."

    unique_words = set(words)
    if len(unique_words) / total_words < 0.45:
        return False, "Kosa kata kurang bervariasi."

    matching_anchors = unique_words.intersection(MALAY_ANCHOR_WORDS)
    if len(matching_anchors) < 2:
        return False, "Kekurangan kata sauh Bahasa Melayu."

    return True, "Kualiti Sah"


# =============================================================================
# 2. KELAS ENJIN AI PERSONA THREADS
# =============================================================================
class RedditThreadsAIPersona:
    """Enjin AI Persona Threads khusus untuk ulasan mikro-blog santai & berbisa."""

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
        self.max_tokens = 400
        self.cooldown_delay = 3.5

    def _call_llm_api(self, model_name: str, system_prompt: str, user_prompt: str) -> Tuple[bool, Optional[str], str]:
        if not self.base_url or not self.api_key or not model_name:
            return False, None, "Konfigurasi OpenRouter (Base URL, API Key, Model) tidak lengkap dalam persekitaran."

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json; charset=utf-8",
            "HTTP-Referer": "https://sembangpctech.local",
            "X-Title": "Sembang PC & Tech Reddit Threads Storyteller",
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
                    print(f"  ⚠️ [THREADS AI 429] Model '{model_name}' sesak. Menunggu {wait_sec}s...")
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
                    print(f"  ⚠️ [THREADS AI HTTP {res.status_code}]: {err_snippet}")
                    time.sleep(2)

            except Exception as e:
                print(f"  ⚠️ [THREADS AI EXCEPTION]: {e}")
                time.sleep(2)

        return False, None, f"Gagal mendapatkan respon daripada model {model_name}"

    def generate_caption(self, post_data: Dict[str, Any], temporal_ctx: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        """
        Menjana kapsyen mikro-blog Threads (Had Siling <= 480 Aksara)
        dengan kawalan masa Malaysia dan model failover.
        """
        raw_title = str(post_data.get("title") or "Topik PC Pilihan").strip()
        clean_title = re.sub(r'\s+', ' ', raw_title)[:80].strip()
        cleaned_text = str(post_data.get("cleaned_text") or "").strip()
        subreddit = str(post_data.get("subreddit") or "tech").strip()

        time_info = temporal_ctx if temporal_ctx else get_current_myt_details()
        formatted_time = time_info.get("formatted_context", "Waktu Malaysia (MYT)")

        hashtags_block = "\n\n#SembangPCTech #TechMY"
        max_body_allowed = 480 - len(hashtags_block) - 5  # ~450 aksara untuk teks

        fallback_body = (
            f"Tengok perkongsian daripada komuniti r/{subreddit} ni pasal {clean_title[:35]}, memang kreatif betul idea dorang. "
            f"Kadang benda simple macam ni yang buat setup kita rasa lain macam kepuasannya. "
            f"Korang pernah cuba buat modding kreatif macam ni tak kat setup sendiri?"
        )
        fallback_full = f"{fallback_body}{hashtags_block}".strip()

        if not self.api_key:
            print("⚠️ [THREADS AI WARN] Kunci OpenRouter tiada. Mengaktifkan kapsyen sandaran.")
            return True, fallback_full[:480]

        system_prompt = f"""
Anda ialah "Abang Din" di Meta Threads untuk "Sembang PC & Tech Malaysia".
Format: MIKRO-BLOG SPONTAN (Ringkas, Padat, Santai, dan Berbisa).

MAKLUMAT MASA SEMASA (MALAYSIA):
{formatted_time}

PANDUAN PENULISAN THREADS (HAD KETAT KESELURUHAN <= 450 AKSARA):
1. BAHASA: 100% Bahasa Melayu santai harian komuniti PC/tech tempatan ("Tengok perkongsian ni...", "Korang rasa berbaloi ke...", "Padu teruk idea ni").
2. DILARANG SAMA SEKALI menggunakan perkataan Bahasa Indonesia ("bisa", "banget", "nggak", "kamu", "anda").
3. STRUKTUR:
   - 2 hingga 3 ayat mengulas topik Reddit dengan reaksi spontan & bersahaja.
   - Akhiri dengan 1 soalan santai untuk memancing interaksi dan komen pengikut Threads.
4. ARAHAN PANTANGAN KETAT:
   - DILARANG letak link/URL.
   - DILARANG tulis proses pemikiran, analisis draf, atau sebarang teks sebelum ayat mikro-blog.
   - TERUS TULIS AYAT KANDUNGAN tanpa mukadimah AI.
   - Had panjang teks badan WAJIB di antara 150 hingga 380 aksara sahaja.
"""

        user_prompt = f"""
Topik Reddit r/{subreddit}:
- Tajuk: {clean_title}
- Kisah: {cleaned_text[:300] if cleaned_text else 'Kongsian inovasi visual perkakasan/setup'}

Tulis 1 hantaran mikro Threads spontan (Maksimum 380 aksara badan):
"""

        models_queue = [m for m in [self.model_primary, self.model_fallback] if m]

        for model_idx, current_model in enumerate(models_queue, 1):
            print(f"🧵 [THREADS AI] Mencuba Model {model_idx}/{len(models_queue)}: '{current_model}'...")
            ok_call, raw_content, msg = self._call_llm_api(current_model, system_prompt, user_prompt)

            if ok_call and raw_content:
                cleaned_body = clean_threads_text(raw_content)
                trimmed_body = smart_trim_threads_body(cleaned_body, max_chars=max_body_allowed)

                if "#SembangPCTech" not in trimmed_body:
                    full_post = f"{trimmed_body}{hashtags_block}".strip()
                else:
                    full_post = trimmed_body

                if len(full_post) > 480:
                    excess = len(full_post) - 480
                    trimmed_body = smart_trim_threads_body(trimmed_body, max_chars=len(trimmed_body) - excess - 5)
                    full_post = f"{trimmed_body}{hashtags_block}".strip()

                is_valid, reason = is_valid_threads_caption(full_post)

                if is_valid:
                    print(f"✅ [THREADS AI SUCCESS] Kapsyen Threads berjaya dijana ({len(full_post)}/480 aksara | Model: '{current_model}').")
                    return True, full_post
                else:
                    print(f"⚠️ [THREADS AI GUARDRAIL REJECT]: {reason}. Mencuba pusingan seterusnya...")

        print("🛡️ [THREADS AI FALLBACK] Mengaktifkan kapsyen Threads sandaran selamat.")
        return True, fallback_full[:480]


# Singleton instance untuk kegunaan modular
reddit_threads_ai = RedditThreadsAIPersona()