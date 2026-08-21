#!/usr/bin/env python3
"""
Reddit Tech Storyteller Engine: Facebook Page AI Persona Module
Lokasi Fail: src/reddit_fb_Ai_persona.py

Ciri-ciri Penambahbaikan (Tuned):
1. Penceritaan Manusia Sebenar (Organic Storytelling): Membuang kekangan templat tegar (seperti syarat wajib tepat 2 bullet points) dan memberi kebebasan gaya naratif yang lebih hidup, beremosi, dan bersahaja.
2. Dinamik 100% (Sifar Hardcode Model): Membaca REDDIT_OPENROUTER_MODEL, REDDIT_OPENROUTER_MODEL_FALLBACK, dan fallback am OPENROUTER_MODEL secara telus daripada persekitaran.
3. Penyingkiran Penalti Inferens: Membuang parameter presence_penalty dan frequency_penalty untuk keserasian optimum pelayan OpenRouter.
4. Penapis Anti-Thinking & Glitch Scrubber: Menapis blok pemikiran (<think>...</think>), draf analisis AI, mojibake, dan token LLM rosak.
5. Kawalan Siling & Guardrail (500 – 750 Aksara): Menjamin panjang hantaran optimum bersama pengesahan kosa kata Bahasa Melayu santai.
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
    "malam", "pagi", "petang", "gajet", "murah", "berbaloi", "cerita", "abang", "lepak"
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
        slot_desc = "Pagi (Mood Semangat, Ruang Meja Segar & Produktiviti Mula Hari)"
    elif 12 <= hour < 17:
        slot_desc = "Petang (Mood Aliran Kerja IT, Eksperimen & Sembang Komputer)"
    elif 17 <= hour < 21:
        slot_desc = "Malam Awal (Mood Lepak Santai, Borak Gajet & Review)"
    else:
        slot_desc = "Larut Malam (Mood Tenang, Kopi, Setup Estetik & Cerita Nostalgia)"

    return {
        "full_date_str": f"{now.day} {month_my} {now.year}",
        "time_str": now.strftime("%I:%M %p"),
        "day_my": day_my,
        "year": now.year,
        "slot_desc": slot_desc,
        "formatted_context": f"Hari {day_my}, {now.day} {month_my} {now.year}, Jam {now.strftime('%I:%M %p')} MYT ({slot_desc})"
    }


def clean_glitches_and_meta(text: str) -> str:
    """
    Membersihkan token LLM, simbol mojibake, tag pemikiran reasoning (<think>),
    serta mukadimah templat AI.
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

    # 3. Standardkan simbol bullet points jika ada
    for sym in ["❖", "◆", "◇", "►", "▪", "▲", "★", "➡", "➢", "*", "-"]:
        text = text.replace(sym, "•")

    # 4. Buang mukadimah dan header templat
    text = re.sub(r'(?i)^\s*(?:yo|hai|salam|hello)?[^\n]*?(?:cadangan|kapsyen|caption|post|hantaran|cerita|kisah|ulasan|facebook)[^\n]*?\n+', '', text)
    text = re.sub(r'(?i)\*\*caption\s*(?:facebook)?\s*:\*\*', '', text)
    text = re.sub(r'\*\*\*', '', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'[^\x00-\x7F\u00C0-\u024F\s.,!?:;\'"()/\-#@+•]', '', text)

    lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in text.splitlines()]
    return "\n".join([line for line in lines if line]).strip()


def smart_trim_fb_story(text: str, max_chars: int = 750) -> str:
    """Memotong teks pada tanda baca terakhir jika melebihi had siling 750 aksara."""
    if not text or len(text) <= max_chars:
        return text

    trimmed = text[:max_chars]
    last_punc = max(trimmed.rfind('.'), trimmed.rfind('!'), trimmed.rfind('?'), trimmed.rfind('\n'))

    if last_punc != -1 and last_punc > 450:
        return trimmed[:last_punc + 1].strip()

    last_space = trimmed.rfind(' ')
    if last_space != -1:
        return trimmed[:last_space].strip() + "..."
    return trimmed[:max_chars - 3].strip() + "..."


def is_valid_fb_story(text: str) -> Tuple[bool, str]:
    """Menyemak kualiti penceritaan, kepelbagaian perkataan, dan keaslian Bahasa Melayu."""
    if not text or len(text.strip()) < 350:
        return False, f"Teks terlalu pendek ({len(text.strip()) if text else 0} aksara)."
    if len(text.strip()) > 770:
        return False, f"Teks melebihi had maksimum ({len(text.strip())}/750 aksara)."

    if re.search(r'(\b\w+\b)(?:\s+\1){2,}', text, flags=re.IGNORECASE):
        return False, "Dikesan pengulangan perkataan berturut-turut."

    lower_text = text.lower()
    for forbidden in FORBIDDEN_WORDS:
        if re.search(r'\b' + re.escape(forbidden) + r'\b', lower_text):
            return False, f"Dikesan perkataan terlarang: '{forbidden}'."

    words = [w.lower() for w in re.findall(r'\b[a-zA-Z]+\b', text)]
    total_words = len(words)
    if total_words < 30:
        return False, "Jumlah perkataan tidak mencukupi untuk format Facebook."

    word_counts = Counter(words)
    for word, count in word_counts.items():
        if len(word) >= 3 and count >= 10:
            return False, f"Perkataan '{word}' berulang sebanyak {count} kali (Had maks: 9x)."
        if len(word) >= 4 and (count / total_words) > 0.16:
            return False, f"Kekerapan perkataan '{word}' terlalu tinggi."

    unique_words = set(words)
    if len(unique_words) / total_words < 0.42:
        return False, "Kosa kata kurang bervariasi."

    matching_anchors = unique_words.intersection(MALAY_ANCHOR_WORDS)
    if len(matching_anchors) < 3:
        return False, f"Teks tidak memenuhi standard Bahasa Melayu tempatan (Sauh: {len(matching_anchors)})."

    return True, "Kualiti Sah"


# =============================================================================
# 2. KELAS ENJIN AI PERSONA FACEBOOK
# =============================================================================
class RedditFBAIPersona:
    """Enjin Penceritaan Facebook Abang Din berasaskan topik Reddit dengan Failover Model Dinamik."""

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
        self.temperature = 0.7
        self.max_tokens = 900
        self.cooldown_delay = 3.5

    def _call_llm_api(self, model_name: str, system_prompt: str, user_prompt: str) -> Tuple[bool, Optional[str], str]:
        if not self.base_url or not self.api_key or not model_name:
            return False, None, "Konfigurasi OpenRouter (Base URL, API Key, Model) tidak lengkap dalam persekitaran."

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json; charset=utf-8",
            "HTTP-Referer": "https://sembangpctech.local",
            "X-Title": "Sembang PC & Tech Reddit Facebook Storyteller",
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
                res = requests.post(url, json=payload, headers=headers, timeout=30)
                res.encoding = "utf-8"

                if res.status_code == 429:
                    wait_sec = 6 * (attempt + 1)
                    print(f"  ⚠️ [FB AI 429] Model '{model_name}' sesak. Menunggu {wait_sec}s...")
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
                    print(f"  ⚠️ [FB AI HTTP {res.status_code}]: {err_snippet}")
                    time.sleep(2)

            except Exception as e:
                print(f"  ⚠️ [FB AI EXCEPTION]: {e}")
                time.sleep(2)

        return False, None, f"Gagal mendapatkan respon daripada model {model_name}"

    def generate_caption(self, post_data: Dict[str, Any], temporal_ctx: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        """
        Menjana penceritaan Facebook santai, bervariasi dan hidup (500 - 750 Aksara)
        dengan kawalan masa Malaysia dan model failover.
        """
        raw_title = str(post_data.get("title") or "Topik PC & Tech Pilihan").strip()
        clean_title = re.sub(r'\s+', ' ', raw_title)[:100].strip()
        cleaned_text = str(post_data.get("cleaned_text") or "").strip()
        subreddit = str(post_data.get("subreddit") or "tech").strip()

        time_info = temporal_ctx if temporal_ctx else get_current_myt_details()
        formatted_time = time_info.get("formatted_context", "Waktu Malaysia (MYT)")

        hashtags_block = "\n\n#SembangPCTech #TechMalaysia #PCSetup #KisahTech"

        fallback_story = (
            f"Tengah lepak santai waktu ni, terjumpa satu perkongsian menarik dari komuniti r/{subreddit}. "
            f"Bila tengok projek dan hasil kerja macam ni, memang terasa vibe kepuasan peminat tech yang sanggup luang masa kemaskan ruang setup.\n\n"
            f"Bukan pasal barang mahal semata-mata, tapi kreativiti susun atur dan penyelesaian masalah yang buat kita rasa terinspirasi nak upgrade meja sendiri.\n\n"
            f"Korang yang tengah layan setup sekarang, apa bahagian paling mencabar bila nak buat cable management atau pasang part baru? Cerita sikit kat bawah! 👇{hashtags_block}"
        )

        if not self.api_key:
            print("⚠️ [FB AI WARN] Kunci OpenRouter tiada. Mengaktifkan penceritaan sandaran.")
            return True, fallback_story

        system_prompt = f"""
Anda adalah "Abang Din", pengasas dan pencerita utama Facebook Page "Sembang PC & Tech Malaysia".
Personaliti anda: Peminat tegar PC & gajet yang mesra, bersahaja, kelakar sempoi, dan bercerita seperti seorang kawan lama yang sedang lepak mengeteh borak teknologi.

MAKLUMAT MASA SEMASA (MALAYSIA):
{formatted_time}

PANDUAN PENCERITAAN FACEBOOK (HAD KETAT: 500 HINGGA 750 AKSARA):
1. GAYA BAHASA: 100% Bahasa Melayu santai harian komuniti PC tempatan ("Korang yang tengah lepak...", "Bila Abang tengok projek ni...", "Memang salute betul cara dia buat...", "Fuh, rasa puas tengok susunan ni").
2. DILARANG SAMA SEKALI menggunakan perkataan Bahasa Indonesia ("bisa", "banget", "nggak", "ngak", "gimana", "komputer jinjing", "ponsel", "kamu", "anda").
3. STRUKTUR NARRATIVE HIDUP (BEBAS DARI TEMPLAT KAKU):
   - Mulakan dengan reaksi spontan mengaitkan topik Reddit dengan mood waktu sekarang (pagi/petang/malam).
   - Ceritakan intipati atau perkara menarik/pelik/inspirasi di sebalik gambar & kisah ini dengan gaya ulasan peribadi yang ada "jiwa".
   - Boleh ditulis dalam 2-3 perenggan santai atau gabungan ayat penceritaan yang mengalir lancar. JANGAN paksa diri menggunakan format template kaku atau senarai bernombor jika tidak sesuai.
   - Akhiri dengan pandangan jujur Abang Din dan satu soalan santai untuk ajak komuniti bersembang di ruangan komen.
4. PANTANGAN KETAT:
   - DILARANG letak sebarang pautan URL di dalam teks.
   - DILARANG letak mukadimah AI (DILARANG tulis "Berikut adalah...", "Caption Facebook:", dsb.).
   - TERUS TULIS AYAT KANDUNGAN. Panjang teks keseluruhan (termasuk hashtags) WAJIB berada dalam julat 500 hingga 750 aksara.
"""

        user_prompt = f"""
Kisah / Topik Reddit daripada r/{subreddit}:
- Tajuk Pos: {clean_title}
- Intipati Kisah/Visual: {cleaned_text[:600] if cleaned_text else 'Perkongsian visual perkakasan, reka bentuk setup meja, atau ulasan teknologi menarik.'}

Olah menjadi 1 kapsyen Facebook yang hidup, santai dan memikat (500 - 750 aksara):
"""

        models_queue = [m for m in [self.model_primary, self.model_fallback] if m]

        for model_idx, current_model in enumerate(models_queue, 1):
            print(f"🤖 [FB AI] Mencuba Model {model_idx}/{len(models_queue)}: '{current_model}'...")
            ok_call, raw_content, msg = self._call_llm_api(current_model, system_prompt, user_prompt)

            if ok_call and raw_content:
                cleaned_body = clean_glitches_and_meta(raw_content)

                if "#SembangPCTech" not in cleaned_body:
                    cleaned_body = f"{cleaned_body}{hashtags_block}".strip()

                final_story = smart_trim_fb_story(cleaned_body, max_chars=750)
                is_valid, reason = is_valid_fb_story(final_story)

                if is_valid:
                    print(f"✅ [FB AI SUCCESS] Kapsyen Facebook berjaya dijana ({len(final_story)} aksara | Model: '{current_model}').")
                    return True, final_story
                else:
                    print(f"⚠️ [FB AI GUARDRAIL REJECT]: {reason}. Mencuba pusingan seterusnya...")

        print("🛡️ [FB AI FALLBACK] Mengaktifkan kapsyen Facebook sandaran selamat.")
        return True, fallback_story


# Singleton instance untuk kegunaan modular
reddit_fb_ai = RedditFBAIPersona()