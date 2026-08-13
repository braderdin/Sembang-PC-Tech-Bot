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

def detect_current_time_slot():
    """
    Mengenal pasti slot masa semasa mengikut zon masa Malaysia (MYT = UTC+8).
    
    Slot:
    - morning_early (6:30 AM): Kopi pagi, ketenangan meja kerja, produktiviti subuh.
    - morning_work  (9:30 AM): Mula kerja, ergonomik, kelebihan perkakasan (hardware/monitors).
    - afternoon_tech(2:30 PM): Dunia perisian (software), Linux, tips IT, bug & programming.
    - night_chill   (8:30 PM): Ambient light, RGB, gaming malam, sembang santai dunia gajet.
    """
    myt_time = datetime.now(timezone.utc) + timedelta(hours=8)
    hour = myt_time.hour

    if 4 <= hour < 8:
        return "morning_early", "Pagi / Subuh (Kopi, Ketenangan Setup & Fikiran Produktif)"
    elif 8 <= hour < 12:
        return "morning_work", "Pagi / Waktu Kerja (Mula Kerja, Perkakasan PC & Ergonomik)"
    elif 12 <= hour < 18:
        return "afternoon_tech", "Petang / Waktu IT (Software, Linux, Tips Coding & Aliran Kerja)"
    else:
        return "night_chill", "Malam / Santai (Pencahayaan Ambient, Gaming & Gajet Idaman)"

def generate_lifestyle_theme_keyword(base_url, model, api_key, slot_override=None):
    """
    Jana 1 kata kunci carian utama (Core Theme Query) dalam Bahasa Inggeris untuk Unsplash API.
    Satu kata kunci induk akan menghasilkan 10 gambar yang konsisten dan bertema serupa.
    """
    slot_id, slot_desc = detect_current_time_slot()
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

TUGAS ANDA:
Jana TEPAT 1 kata kunci carian gambar Unsplash dalam Bahasa Inggeris (English search query) yang fokus kepada tema meja kerja, gajet, perkakasan PC, ekosistem IT, atau suasana teknologi yang estetik dan bersesuaian dengan waktu tersebut.

CONTOH KATA KUNCI MENGIKUT WAKTU:
- Pagi Subuh: "cozy morning coffee clean desk setup aesthetic"
- Pagi Kerja: "minimalist dual monitor workspace setup sunlight"
- Petang Tech: "developer workspace laptop code terminal screen"
- Malam Gaming: "dark room neon RGB mechanical keyboard ambient setup"

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
            # Pembersihan tanda petik jika ada
            query_text = re.sub(r'["\']', '', query_text).strip()
            if query_text:
                return query_text
    except Exception as e:
        print(f"⚠️ [AI KEYWORD GEN ERROR]: {e}")

    return "minimalist modern tech workspace setup"

def generate_lifestyle_story(base_url, model, api_key, image_descriptions_list, slot_override=None):
    """
    Menjana penceritaan AI Tech Specialist yang bijak, humoris, dan berinformasi
    berdasarkan senarai huraian gambar yang dipilih dan slot masa semasa.
    """
    slot_id, slot_desc = detect_current_time_slot()
    if slot_override:
        slot_id = slot_override

    if not base_url or not model or not api_key:
        return False, "Kunci OpenRouter API / Base URL / Model tidak lengkap."

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json; charset=utf-8",
    }

    images_context = "\n".join([f"- Gambar {i+1}: {desc}" for i, desc in enumerate(image_descriptions_list)])

    system_prompt = f"""
Anda ialah seorang AI Tech Specialist di Malaysia yang bijak, berpengalaman, peramah, dan kelakar. Anda suka berkongsi pandangan tentang dunia komputer, perkakasan PC, ekosistem Linux/Open Source, petua produktiviti, dan trend IT semasa secara santai di Facebook Page 'Sembang PC & Tech Malaysia'.

WAKTU HANTARAN (MALAYSIA): {slot_desc}

GAMBAR-GAMBAR YANG DITAMPILKAN DALAM HANTARAN:
{images_context}

GAYA & SYARAT PENULISAN:
1. Tulis penceritaan santai (Antara 350 hingga 550 aksara) yang selari dengan suasana waktu hantaran dan gambar di atas.
2. Selitkan elemen kebijaksanaan pakar tech (seperti tips perkakasan, pandangan tentang Linux/OS, produktiviti, atau seloroh bab bug/setup) mengikut slot masa.
3. DILARANG SAMA SEKALI meletakkan sebarang pautan (link), harga, atau mengajak membeli produk! Ini adalah hantaran perkongsian ilmu dan gaya hidup tech.
4. PERATURAN BEBAS EMOJI (STRICT 0% EMOJI): Dilarang menggunakan sebarang emoji, simbol bintang, atau bullet khas. Luahkan kehangatan cerita melalui susunan ayat yang menarik.
5. Akhiri hantaran dengan soalan mesra untuk mengajak komuniti Tech berdiskusi di ruang komen.
"""

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": "Tuliskan penceritaan Facebook yang bijak dan menarik untuk slot ini."},
        ],
        "temperature": 0.8,
        "max_tokens": 450,
    }

    url = f"{base_url.rstrip('/')}/chat/completions"

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=25)
        response.encoding = "utf-8"

        if response.status_code == 200:
            res_json = response.json()
            if "choices" in res_json and len(res_json["choices"]) > 0:
                raw_content = res_json["choices"][0]["message"]["content"].strip()
                story_text = remove_emojis_and_special_symbols(raw_content)

                if len(story_text) > 700:
                    story_text = story_text[:697] + "..."

                return True, story_text
            return False, "Format respon OpenRouter tidak sah."
        else:
            return False, f"OpenRouter API Error (Status {response.status_code}): {response.text}"

    except Exception as e:
        return False, f"Ralat Rangkaian OpenRouter API: {str(e)}"