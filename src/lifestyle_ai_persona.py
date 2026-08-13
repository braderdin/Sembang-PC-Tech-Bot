import os
import re
import json
import requests
from datetime import datetime, timezone, timedelta

def remove_emojis_and_special_symbols(text):
    """
    Membersihkan teks daripada emoji dan simbol khas untuk mengekalkan mutu penulisan yang kemas.
    """
    if not text:
        return ""
    
    special_bullets = ["❖", "◆", "◇", "►", "•", "▪", "▲", "★", "➡", "➢"]
    for sym in special_bullets:
        text = text.replace(sym, "-")

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
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(lines).strip()

def smart_trim_text(text, max_chars=1000):
    """
    Memotong teks secara pintar pada noktah, tanda soal, atau tanda seru terakhir
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

def detect_current_time_slot():
    """
    Mengenal pasti slot masa semasa dan mood hari mengikut zon masa Malaysia (MYT = UTC+8).
    """
    myt_time = datetime.now(timezone.utc) + timedelta(hours=8)
    hour = myt_time.hour
    day_name = myt_time.strftime("%A") # Isnin - Ahad

    # Matriks Mood Mengikut Hari
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

    if 4 <= hour < 8:
        return "morning_early", "Pagi / Subuh (Kopi, Ketenangan Setup & Fikiran Produktif)", current_day_mood, 0.75
    elif 8 <= hour < 12:
        return "morning_work", "Pagi / Waktu Kerja (Mula Kerja, Perkakasan PC & Ergonomik)", current_day_mood, 0.75
    elif 12 <= hour < 18:
        return "afternoon_tech", "Petang / Waktu IT (Software, Linux, Tips Coding & Aliran Kerja)", current_day_mood, 0.80
    else:
        return "night_chill", "Malam / Santai (Pencahayaan Ambient, Gaming & Gajet Idaman)", current_day_mood, 0.90

def generate_lifestyle_theme_keyword(base_url, model, api_key, slot_override=None):
    """
    Jana 1 kata kunci carian utama (Core Theme Query) dalam Bahasa Inggeris untuk Unsplash API.
    """
    slot_id, slot_desc, day_mood, temp_val = detect_current_time_slot()
    if slot_override:
        slot_id = slot_override

    if not base_url or not model or not api_key:
        fallback_map = {
            "morning_early": "cozy morning coffee desk setup aesthetic",
            "morning_work": "clean minimalist dual monitor workspace setup",
            "afternoon_tech": "programmer coding setup linux terminal screen",
            "night_chill": "dark room RGB mechanical keyboard ambient setup"
        }
        return fallback_map.get(slot_id, "clean modern PC setup workspace")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json; charset=utf-8",
    }

    system_prompt = f"""
Anda ialah seorang AI Tech Specialist yang pintar, kreatif, dan peka waktu.
WAKTU SEMASA DI MALAYSIA: {slot_desc}
MOOD HARI SEMASA: {day_mood}

TUGAS ANDA:
Jana TEPAT 1 kata kunci carian gambar Unsplash dalam Bahasa Inggeris (English search query) yang fokus kepada tema meja kerja, gajet, perkakasan PC, ekosistem IT, atau suasana teknologi yang estetik dan bersesuaian dengan waktu tersebut.

FORMAT OUTPUT WAJIB:
Kembalikan HANYA teks kata kunci carian tanpa sebarang tanda petik, tanda baca, atau penerangan tambahan.
"""

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": "Jana 1 kata kunci carian Unsplash untuk waktu ini."},
        ],
        "temperature": 0.85,
        "max_tokens": 50,
    }

    url = f"{base_url.rstrip('/')}/chat/completions"

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        response.encoding = "utf-8"
        if response.status_code == 200:
            res_json = response.json()
            query_text = res_json["choices"][0]["message"]["content"].strip()
            query_text = re.sub(r'["\']', '', query_text).strip()
            if query_text:
                return query_text
    except Exception as e:
        print(f"⚠️ [AI KEYWORD GEN ERROR]: {e}")

    return "minimalist modern tech workspace setup"

def generate_lifestyle_story(base_url, model, api_key, image_descriptions_list, previous_memories=None, slot_override=None):
    """
    Menjana penceritaan AI Tech Specialist dengan suntikan Bank Ingatan (Memory Bank) & Mood Dinamik.
    """
    slot_id, slot_desc, day_mood, dynamic_temp = detect_current_time_slot()
    if slot_override:
        slot_id = slot_override

    if not base_url or not model or not api_key:
        return False, "Kunci OpenRouter API / Base URL / Model tidak lengkap."

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json; charset=utf-8",
    }

    images_context = "\n".join([f"- Gambar {i+1}: {desc}" for i, desc in enumerate(image_descriptions_list)])

    # Formatkan Bank Ingatan
    memory_context = ""
    if previous_memories and isinstance(previous_memories, list) and len(previous_memories) > 0:
        formatted_memories = "\n".join([f"- {mem[:120]}..." for mem in previous_memories])
        memory_context = f"""
INGATAN CERITA LEPAS ANDA (JANGAN ULANG AYAT PEMBUKA, PLOT, ATAL TOPIK YANG SAMA):
{formatted_memories}
"""

    system_prompt = f"""
Anda ialah seorang AI Tech Specialist di Malaysia yang bijak, berpengalaman, peramah, dan kelakar. Anda suka berkongsi pandangan tentang dunia komputer, perkakasan PC, ekosistem Linux/Open Source, petua produktiviti, dan trend IT semasa secara santai di Facebook Page 'Sembang PC & Tech Malaysia'.

WAKTU HANTARAN (MALAYSIA): {slot_desc}
MOOD SUASANA HARI INI: {day_mood}

GAMBAR-GAMBAR YANG DITAMPILKAN DALAM HANTARAN:
{images_context}
{memory_context}
GAYA & SYARAT PENULISAN:
1. Tulis penceritaan santai (Maksimum 800 aksara) yang selari dengan suasana waktu hantaran, mood hari, dan gambar di atas.
2. JANGAN guna ayat pembuka yang klise atau sama dengan ingatan cerita lepas! Variasikan intonasi pembuka anda.
3. Selitkan elemen kebijaksanaan pakar tech (seperti tips perkakasan, pandangan tentang Linux/OS, produktiviti, atau seloroh bab bug/setup) mengikut slot masa.
4. DILARANG SAMA SEKALI meletakkan sebarang pautan (link), harga, atau mengajak membeli produk!
5. PERATURAN BEBAS EMOJI (STRICT 0% EMOJI): Dilarang menggunakan sebarang emoji, simbol bintang, atau bullet khas.
6. Akhiri hantaran dengan soalan mesra untuk mengajak komuniti Tech berdiskusi di ruang komen.
"""

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": "Tuliskan penceritaan Facebook yang bijak dan segar berdasarkan gambar dan ingatan lalu."},
        ],
        "temperature": dynamic_temp, # Temperature Dinamik mengikut slot masa
        "max_tokens": 1000,
    }

    url = f"{base_url.rstrip('/')}/chat/completions"

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.encoding = "utf-8"

        if response.status_code == 200:
            res_json = response.json()
            if "choices" in res_json and len(res_json["choices"]) > 0:
                raw_content = res_json["choices"][0]["message"]["content"].strip()
                story_text = remove_emojis_and_special_symbols(raw_content)
                story_text = smart_trim_text(story_text, max_chars=1000)

                return True, story_text
            return False, "Format respon OpenRouter tidak sah."
        else:
            return False, f"OpenRouter API Error (Status {response.status_code}): {response.text}"

    except Exception as e:
        return False, f"Ralat Rangkaian OpenRouter API: {str(e)}"