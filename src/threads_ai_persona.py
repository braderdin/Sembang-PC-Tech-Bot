import os
import re
import requests

def clean_threads_text(text):
    """
    Membersihkan teks daripada token glitch LLM, simbol asing yang tidak sah,
    dan memastikan format perenggan kemas untuk Meta Threads.
    """
    if not text:
        return ""

    # 1. Buang token khas LLM
    text = re.sub(r'<pad>|<unk>|<s>|</s>|\[PAD\]|\[UNK\]', '', text, flags=re.IGNORECASE)

    # 2. Buang aksara bukan Rumi / simbol ganjil (contoh: huruf Arab/Gujerat/Jerman)
    text = re.sub(r'[^\w\s.,!?:;\'"()/\-#@+]', '', text)

    # 3. Kemaskan ruang kosong yang bertindih
    lines = [re.sub(r'\s+', ' ', line).strip() for line in text.splitlines()]
    cleaned = "\n".join([line for line in lines if line])
    return cleaned.strip()

def is_threads_text_valid(text, min_len=40):
    """
    Memastikan teks dijana dengan kualiti yang sah sebelum dihantar ke Threads.
    """
    if not text or len(text.strip()) < min_len:
        return False
    if "<pad>" in text.lower() or "<unk>" in text.lower():
        return False
    return True

# =====================================================================
# 1. PERSONA THREADS: LIFESTYLE & TECH CASUAL (Berasaskan 1 Gambar Sahaja)
# =====================================================================
def generate_threads_lifestyle_caption(base_url, model, api_key, image_description, slot_desc="Santai Tech", day_mood="Santai"):
    """
    Menjana kapsyen mikro-blog santai untuk Threads (200 - 350 aksara)
    yang HANYA merujuk kepada 1 gambar utama.
    """
    fallback_lifestyle = (
        "Setup yang kemas macam ni memang buat mood kerja atau santai rasa lebih tenang. "
        "Bila ruang meja teratur, fikiran pun kurang serabut nak hadap kerja tech seharian. "
        "Korang punya setup meja jenis minimalis macam ni juga ke?"
    )

    if not base_url or not model or not api_key:
        return fallback_lifestyle

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json; charset=utf-8",
    }

    system_prompt = f"""
Anda ialah seorang AI Tech Specialist di Malaysia yang menulis di Meta Threads (@braderdin360 / Sembang PC & Tech).
Format penulisan anda ialah MICRO-BLOGGING (Ringkas, Padat, Santai, dan Kelakar).

WAKTU SEMASA: {slot_desc}
MOOD HARI: {day_mood}
VISUAL 1 GAMBAR UTAMA: "{image_description}"

SYARAT PENULISAN THREADS (SANGAT KETAT):
1. WAJIB rujuk kepada SATU gambar ini sahaja. DILARANG SAMA SEKALI sebut "gambar kedua", "gambar ketiga", atau "album"!
2. HAD PANJANG TEKS: Antara 200 HINGGA 350 AKSARA SAHAJA.
3. GAYA BAHASA: Bahasa Melayu santai komuniti tech Malaysia (Contoh: "Kemas betul setup ni...", "Bila meja teratur...", "Rasa tenang nak layan projek...").
4. DILARANG guna Bahasa Indonesia atau bahasa kaku terjemahan.
5. Sifar pautan (No links), sifar ajakan membeli (100% sembang santai/lifestyle).
6. Akhiri dengan 1 soalan santai untuk interaksi pengikut.
"""

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": "Tuliskan 1 hantaran Threads yang ringkas dan padat tentang gambar ini."},
        ],
        "temperature": 0.70, # Suhu stabil untuk elak percampuran bahasa asing
        "max_tokens": 300,
    }

    url = f"{base_url.rstrip('/')}/chat/completions"

    for attempt in range(2):
        try:
            res = requests.post(url, json=payload, headers=headers, timeout=20)
            res.encoding = "utf-8"
            if res.status_code == 200:
                data = res.json()
                raw_text = data["choices"][0]["message"]["content"].strip()
                cleaned_text = clean_threads_text(raw_text)

                if is_threads_text_valid(cleaned_text):
                    # Potong selamat jika terlebih
                    if len(cleaned_text) > 420:
                        cleaned_text = cleaned_text[:415] + "..."
                    return cleaned_text
        except Exception as e:
            print(f"⚠️ [THREADS LIFESTYLE AI ERROR - ATTEMPT {attempt+1}]: {e}")

    return fallback_lifestyle

# =====================================================================
# 2. PERSONA THREADS: PRODUK AFFILIATE & RACUN HARDWARE (Padat & Ringkas)
# =====================================================================
def generate_threads_affiliate_caption(base_url, model, api_key, product_title, product_desc):
    """
    Menjana ulasan produk pantas untuk Threads (200 - 300 aksara)
    supaya baki aksara muat untuk pautan affiliate di bawah 500 aksara.
    """
    fallback_affiliate = (
        f"Korang yang tengah cari {product_title[:50]}, barang ni memang padu untuk upgrade setup korang. "
        "Kualiti mantap dan sangat berbaloi untuk kemaskan ruang kerja!"
    )

    if not base_url or not model or not api_key:
        return fallback_affiliate

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json; charset=utf-8",
    }

    system_prompt = f"""
Anda ialah Tech Specialist Malaysia yang membuat ulasan pantas (quick racun tech) di Meta Threads.

PRODUK: {product_title}
INFO: {product_desc}

SYARAT PENULISAN (SANGAT KETAT):
1. Tulis ulasan padat antara 180 HINGGA 280 AKSARA SAHAJA.
2. Fokus kepada 1-2 kelebihan utama produk ini (contoh: selesaikan masalah kabel serabut, kelajuan laju, reka bentuk kemas).
3. GAYA BAHASA: Santai Malaysia ("Barang padu ni...", "Korang yang nak upgrade...", "Memang berbaloi...").
4. JANGAN letak pautan/link di dalam teks ini (pautan akan dimasukkan oleh sistem).
5. Letakkan 2-3 hashtag tech di hujung ayat (Contoh: #TechMalaysia #DeskSetup).
"""

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": "Tuliskan ulasan pantas Threads untuk produk ini."},
        ],
        "temperature": 0.70,
        "max_tokens": 250,
    }

    url = f"{base_url.rstrip('/')}/chat/completions"

    for attempt in range(2):
        try:
            res = requests.post(url, json=payload, headers=headers, timeout=20)
            res.encoding = "utf-8"
            if res.status_code == 200:
                data = res.json()
                raw_text = data["choices"][0]["message"]["content"].strip()
                cleaned_text = clean_threads_text(raw_text)

                if is_threads_text_valid(cleaned_text):
                    if len(cleaned_text) > 320:
                        cleaned_text = cleaned_text[:315] + "..."
                    return cleaned_text
        except Exception as e:
            print(f"⚠️ [THREADS AFFILIATE AI ERROR - ATTEMPT {attempt+1}]: {e}")

    return fallback_affiliate