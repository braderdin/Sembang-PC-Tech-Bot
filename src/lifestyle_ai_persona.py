import os
import re
import json
import random
import requests
from collections import Counter
from datetime import datetime, timezone, timedelta

# Senarai 40 Kata Kunci Tema Induk Unsplash (Pendek: 2-3 Perkataan, Pelbagai Sub-Niche Tech & Kaya Gambar)
TECH_VISUAL_SEEDS = [
    "mechanical keyboard",
    "minimalist workspace",
    "dark coding setup",
    "datacenter server",
    "cable management desk",
    "audiophile studio desk",
    "vintage retro computer",
    "custom pc build",
    "ultrawide monitor setup",
    "server hardware rack",
    "coffee laptop workspace",
    "electronics circuit board",
    "scandinavian workspace",
    "screenbar desk light",
    "gaming room neon",
    "standing desk setup",
    "espresso laptop desk",
    "racing simulator cockpit",
    "dual monitor workspace",
    "pc water cooling",
    "programmer dark room",
    "cyberpunk desk setup",
    "mini itx pc",
    "clean office desk",
    "studio monitor speakers",
    "keycaps macro shot",
    "rgb gaming battlestation",
    "laptop wooden table",
    "triple monitor setup",
    "creative designer workspace",
    "software developer desk",
    "ambient room lighting",
    "curved gaming monitor",
    "ipad desk setup",
    "ergonomic office chair",
    "synthwave neon desk",
    "modern workstation tech",
    "cozy night desk",
    "pc gaming hardware",
    "linux terminal screen"
]

# Senarai Kata Dasar Anchor Bahasa Melayu untuk Pengesahan Kualiti (Guardrails)
MALAY_ANCHOR_WORDS = {
    "yang", "dan", "di", "ke", "kat", "ni", "tu", "dah", "nak", "ada",
    "kita", "korang", "saya", "buat", "bila", "dengan", "pun", "rasa",
    "meja", "setup", "pc", "kerja", "santai", "tengok", "dalam", "untuk",
    "tak", "bukan", "memang", "lagi", "hujung", "minggu", "malam", "pagi", "petang"
}

def clean_unsplash_description(raw_desc):
    """
    Membersihkan deskripsi mentah Unsplash daripada tag kamera, nama jurugambar,
    atau metadata teknikal yang boleh mengelirukan model AI.
    """
    if not raw_desc:
        return "Setup ruang kerja komputer dan teknologi"

    # Buang rujukan jurugambar dan kamera (cth: photo by, shot on, nikon, sony, iso)
    cleaned = re.sub(r'(photo by|shot on|taken by|image by|camera|lens|iso\s*\d+|f/\d+(\.\d+)?|unsplash|wallpaper)[\w\s\.\,\-\_]*', '', raw_desc, flags=re.IGNORECASE)
    cleaned = re.sub(r'[\r\n\t]+', ' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    if len(cleaned) < 5:
        return "Setup ruang kerja komputer dan teknologi"
    return cleaned[:120]

def remove_emojis_and_special_symbols(text):
    """
    Membersihkan teks daripada emoji, simbol khas, kod token LLM (<pad>),
    dan aksara bukan Rumi (untuk elak isu token drift/glitch bahasa asing).
    """
    if not text:
        return ""
    
    # 1. Buang token khas LLM
    text = re.sub(r'<pad>|<unk>|<s>|</s>|\[PAD\]|\[UNK\]|<\|.*?\|>', '', text, flags=re.IGNORECASE)

    # 2. Buang simbol bullet khas
    special_bullets = ["❖", "◆", "◇", "►", "•", "▪", "▲", "★", "➡", "➢"]
    for sym in special_bullets:
        text = text.replace(sym, "-")

    # 3. Buang emoji
    emoji_pattern = re.compile(
        "["
        "\U0001f600-\U0001f64f"
        "\U0001f300-\U0001f5ff"
        "\U0001f680-\U0001f6ff"
        "\U0001f1e0-\U0001f1ff"
        "\U00002702-\U000027b0"
        "\U000024c2-\U000025ca"
        "\U0001f900-\U0001f9ff"
        "\U0001fa70-\U0001faff"
        "]+",
        flags=re.UNICODE,
    )
    text = emoji_pattern.sub("", text)

    # 4. Tapis aksara asing bukan Rumi (buang huruf Hindi, Arab, Cyrillic, Gujerat dsb jika LLM glitch)
    text = re.sub(r'[^\x00-\x7F\u00C0-\u024F\s.,!?:;\'"()/\-#@+]', '', text)

    lines = [re.sub(r'\s+', ' ', line).strip() for line in text.splitlines()]
    return "\n".join([line for line in lines if line]).strip()

def smart_trim_text(text, max_chars=800):
    """
    Memotong teks secara pintar pada tanda baca terakhir
    supaya ayat tidak terputus di tengah-tengah perkataan.
    """
    if not text or len(text) <= max_chars:
        return text

    trimmed = text[:max_chars]
    last_punc = max(trimmed.rfind('.'), trimmed.rfind('?'), trimmed.rfind('!'))
    
    if last_punc != -1 and last_punc > 100:
        return trimmed[:last_punc + 1].strip()
    else:
        last_space = trimmed.rfind(' ')
        if last_space != -1:
            return trimmed[:last_space].strip() + "..."
        return trimmed + "..."

def is_valid_story_text(text):
    """
    Menyemak kesahan kualiti cerita AI (Guardrails):
    - Memastikan tiada token rosak / <pad>.
    - Memastikan ayat mengandungi kata dasar Bahasa Melayu yang mencukupi (menghalang token drift bahasa asing).
    - Menghalang gelung pengulangan perkataan (autoregressive loop).
    """
    if not text or len(text.strip()) < 80:
        return False
    if "<pad>" in text.lower() or "<unk>" in text.lower():
        return False

    # 1. Semak Pengulangan Berturut-turut (Contoh: "frontsi frontsi frontsi")
    if re.search(r'(\b\w+\b)(?:\s+\1){2,}', text, flags=re.IGNORECASE):
        return False

    words = [w.lower() for w in re.findall(r'\b[a-zA-Z]+\b', text)]
    total_words = len(words)
    if total_words < 18:
        return False

    # 2. Semak Nisbah Kepelbagaian Perkataan (Unique Words Ratio)
    unique_words = set(words)
    if len(unique_words) / total_words < 0.45:
        return False

    # 3. Semak Kekerapan Perkataan Tunggal (Maksimum 15% untuk perkataan panjang >= 4 huruf)
    word_counts = Counter(words)
    for word, count in word_counts.items():
        if len(word) >= 4 and (count / total_words) > 0.15:
            return False

    # 4. Semakan Pengesahan Bahasa Melayu (Malay Anchor Check)
    # Teks mesti mengandungi sekurang-kurangnya 3 kata dasar Melayu lazim
    matching_anchors = unique_words.intersection(MALAY_ANCHOR_WORDS)
    if len(matching_anchors) < 3:
        print(f"⚠️ [GUARDRAIL WARN] Teks dikesan bukan Bahasa Melayu natural (Anchor dikesan: {len(matching_anchors)}). Ditolak.")
        return False

    return True

def detect_current_time_slot():
    """
    Mengenal pasti slot masa semasa dan mood hari mengikut zon masa Malaysia (MYT = UTC+8).
    Suhu (temperature) ditala stabil pada 0.65 untuk model Gemma (mengelakkan halusinasi perkataan asing).
    """
    myt_time = datetime.now(timezone.utc) + timedelta(hours=8)
    hour = myt_time.hour
    day_name = myt_time.strftime("%A")

    day_mood_map = {
        "Monday": "Isnin (Mood Hustle, Fokus, Produktiviti & Semangat Mula Minggu)",
        "Tuesday": "Selasa (Mood Mengemas Aliran Kerja, Tips Perkakasan & Ergonomik)",
        "Wednesday": "Rabu (Mood Mid-week Tech, Pengalaman Kod, Bug & Penyelesaian)",
        "Thursday": "Khamis (Mood Persiapan Hujung Minggu, Eksperimen Software & Linux)",
        "Friday": "Jumaat (Mood TGIF, Santai, Perancangan Gaming & Sembang Gajet)",
        "Saturday": "Sabtu (Mood Hujung Minggu, Meja Kerja Estetik & Hobi Tech)",
        "Sunday": "Ahad (Mood Refleksi, Ketenangan Ruang Kerja & Kopi)"
    }
    current_day_mood = day_mood_map.get(day_name, "Hari Biasa Tech")

    stable_temp = 0.65  # Suhu selamat dan stabil untuk Gemma 26B

    if 4 <= hour < 8:
        return "morning_early", "Pagi / Subuh (Kopi, Ketenangan Setup & Fikiran Produktif)", current_day_mood, stable_temp
    elif 8 <= hour < 12:
        return "morning_work", "Pagi / Waktu Kerja (Mula Kerja, Perkakasan PC & Ergonomik)", current_day_mood, stable_temp
    elif 12 <= hour < 18:
        return "afternoon_tech", "Petang / Waktu IT (Software, Linux, Tips Coding & Aliran Kerja)", current_day_mood, stable_temp
    else:
        return "night_chill", "Malam / Santai (Pencahayaan Ambient, Gaming & Gajet Idaman)", current_day_mood, stable_temp

def generate_lifestyle_theme_keyword(base_url, model, api_key, slot_override=None):
    """
    Menjana kata kunci carian Unsplash pendek (2-3 perkataan) yang sentiasa segar dan berkualiti.
    """
    slot_id, slot_desc, day_mood, _ = detect_current_time_slot()
    if slot_override:
        slot_id = slot_override

    # Pilih 1 sudut inspirasi rawak daripada senarai tema
    visual_seed = random.choice(TECH_VISUAL_SEEDS)

    if not base_url or not model or not api_key:
        return visual_seed

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json; charset=utf-8",
    }

    system_prompt = f"""
Anda ialah AI Tech Specialist yang kreatif.
WAKTU MALAYSIA: {slot_desc}
MOOD HARI: {day_mood}
INSPIRASI VISUAL: '{visual_seed}'

TUGAS ANDA:
Hasilkan TEPAT 2 hingga 3 patah perkataan carian foto Unsplash dalam Bahasa Inggeris (Short keyword search).
DILARANG buat ayat panjang atau melebihi 3 perkataan supaya carian sentiasa menjumpai gambar di Unsplash.

CONTOH KATA KUNCI PENDEK:
- minimalist desk
- coding dark room
- mechanical keyboard
- server hardware
- gaming ambient light

FORMAT OUTPUT:
Kembalikan HANYA 2-3 perkataan tanpa sebarang tanda petik atau ayat tambahan.
"""

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": "Beri 1 kata kunci carian Unsplash (2-3 perkataan sahaja)."},
        ],
        "temperature": 0.65,
        "max_tokens": 20,
        "frequency_penalty": 0.0,
        "presence_penalty": 0.0
    }

    url = f"{base_url.rstrip('/')}/chat/completions"

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        response.encoding = "utf-8"
        if response.status_code == 200:
            res_json = response.json()
            query_text = res_json["choices"][0]["message"]["content"].strip()
            query_text = re.sub(r'["\']', '', query_text).strip()
            query_text = re.sub(r'<pad>|<unk>', '', query_text, flags=re.IGNORECASE).strip()
            
            # Kunci ketat: ambil maksimum 3 perkataan terawal
            words = query_text.split()
            if words:
                clean_short_keyword = " ".join(words[:3])
                if len(clean_short_keyword) >= 4:
                    return clean_short_keyword
    except Exception as e:
        print(f"⚠️ [AI KEYWORD GEN ERROR]: {e}")

    return visual_seed

def generate_lifestyle_story(base_url, model, api_key, image_descriptions_list, previous_memories=None, slot_override=None):
    """
    Menjana penceritaan AI Tech Specialist untuk Facebook Page & Telegram
    dengan penegasan Bahasa Melayu Malaysia (Strict Language Lock) dan ketiadaan penalti pengulangan.
    """
    slot_id, slot_desc, day_mood, dynamic_temp = detect_current_time_slot()
    if slot_override:
        slot_id = slot_override

    fallback_story = (
        "Salam kawan-kawan! Selesai satu hari yang produktif di hadapan monitor. "
        "Bila meja kerja kemas dan susun atur teratur, rasa tenang sikit nak rehatkan minda. "
        "Korang macam mana hari ni, setup meja dah sedia untuk aktiviti santai malam ni?"
    )

    if not base_url or not model or not api_key:
        return True, fallback_story

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json; charset=utf-8",
    }

    # Bersihkan deskripsi setiap gambar sebelum disuapkan ke prompt
    cleaned_descs = [clean_unsplash_description(desc) for desc in image_descriptions_list]
    images_context = "\n".join([f"- Gambar {i+1}: Suasana bertema {desc}" for i, desc in enumerate(cleaned_descs)])

    memory_context = ""
    if previous_memories and isinstance(previous_memories, list) and len(previous_memories) > 0:
        formatted_memories = "\n".join([f"- {mem[:120]}..." for mem in previous_memories])
        memory_context = f"""
INGATAN CERITA LEPAS ANDA (JANGAN ULANG AYAT PEMBUKA, PLOT, ATAU TOPIK YANG SAMA):
{formatted_memories}
"""

    system_prompt = f"""
Anda ialah seorang AI Tech Specialist di Malaysia yang bijak, berpengalaman, peramah, dan santai di Facebook Page 'Sembang PC & Tech Malaysia'.

WAKTU HANTARAN (MALAYSIA): {slot_desc}
MOOD SUASANA HARI INI: {day_mood}

SUASANA GAMBAR YANG DITAMPILKAN DALAM ALBUM:
{images_context}
{memory_context}
PANDUAN PENULISAN (SANGAT KETAT):
1. BAHASA & TATABAHASA (LANGUAGE LOCK): WAJIB 100% menggunakan Bahasa Melayu harian/santai Malaysia yang natural. DILARANG menggunakan perkataan bahasa asing selain istilah IT/komputer yang lazim (seperti setup, keyboard, monitor, coding, cable management). DILARANG mereka perkataan rojak yang tidak wujud.
2. HUBUNGAN VISUAL: Tulis penceritaan santai (Maksimum 600 aksara) yang selari dengan suasana gambar di atas dan mood waktu sekarang.
3. JANGAN ulang ayat pembuka atau plot yang sama dengan ingatan cerita lepas.
4. PERATURAN BEBAS EMOJI (STRICT 0% EMOJI): Dilarang menggunakan sebarang emoji atau simbol khas pelik.
5. DILARANG meletakkan sebarang pautan (link), harga produk, atau mengajak membeli barang (ini adalah hantaran sembang santai/lifestyle).
6. Akhiri hantaran dengan 1 soalan santai untuk mengajak komuniti berbincang di ruang komen Facebook.
"""

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": "Tuliskan penceritaan Facebook santai yang natural dan bijak berasaskan suasana gambar dan waktu sekarang."},
        ],
        "temperature": dynamic_temp,
        "max_tokens": 900,
        "frequency_penalty": 0.0,  # Ditetapkan 0.0 untuk elak token drift / glitch tatabahasa
        "presence_penalty": 0.0    # Ditetapkan 0.0 untuk mengekalkan keaslian ayat Bahasa Melayu
    }

    url = f"{base_url.rstrip('/')}/chat/completions"

    # Cubaan janaan sehingga 2 kali dengan semakan kualiti Guardrails
    for attempt in range(2):
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.encoding = "utf-8"

            if response.status_code == 200:
                res_json = response.json()
                if "choices" in res_json and len(res_json["choices"]) > 0:
                    raw_content = res_json["choices"][0]["message"]["content"].strip()
                    cleaned_text = remove_emojis_and_special_symbols(raw_content)
                    final_story = smart_trim_text(cleaned_text, max_chars=900)

                    if is_valid_story_text(final_story):
                        return True, final_story
                    else:
                        print(f"⚠️ [GLITCH/INVALID TEXT DETECTED - ATTEMPT {attempt+1}] Teks gagal tapisan kualiti/bahasa. Menjana semula...")
            else:
                print(f"⚠️ [OPENROUTER WARN]: HTTP {response.status_code} - {response.text}")

        except Exception as e:
            print(f"⚠️ [AI GENERATION EXCEPTION - ATTEMPT {attempt+1}]: {e}")

    print("🛡️ [SAFETY FALLBACK] Mengaktifkan cerita sandaran bersih demi keselamatan media sosial.")
    return True, fallback_story