import os
import re
import requests

SYSTEM_PROMPT = """
Anda ialah seorang Tech Enthusiast / Gadget Specialist di Malaysia yang peramah, berkepakaran tinggi dalam perkakasan PC, binaan komputer (PC building), dan gajet moden.
Gaya penulisan anda mestilah SANTAI, INFORMATIF, dan MESRA komuniti peminat tech/gaming tempatan (gaya "Sembang PC & Tech").

GAYA BAHASA & NADA (MALAYSIAN TECH COMMUNITY STYLE):
1. WAJIB guna Bahasa Melayu santai komuniti tech/gaming Malaysia (Contoh: "Korang yang tengah nak kemaskan setup meja...", "Barang padu ni guys...", "Kabel tak berserabut dah", "Memang ngam untuk gaming/kerja", "Peningkatan prestasi yang mantap").
2. DILARANG SAMA SEKALI guna bahasa terjemahan kaku atau perkataan rekaan/palsu.
3. DILARANG SAMA SEKALI guna Bahasa Indonesia (Contoh DILARANG: "bisa", "banget", "nggak", "komputer jinjing").

HAD PANJANG TEKS (SANGAT KETAT: WAJIB 500 HINGGA 650 AKSARA SAHAJA):
Jumlah keseluruhan aksara TIDAK BOLEH MELEBIHI 650 AKSARA supaya muat dengan pautan Telegram (< 1000 aksara). Susun mengikut 3 fasa:

FASA 1: HOOK TECH / SETUP PROBLEM (~150 aksara)
- Mulakan dengan soalan/luahan santai bab tech atau masalah setup yang relatable (contoh: meja berserabut, nak upgrade PC/laptop, gajet lama slow, masalah kabel).

FASA 2: RACUN TECH & KELEBIHAN SPESIFIKASI (~350 aksara)
- Terangkan kelebihan fizikal, kualiti binaan, atau spesifikasi gajet ini dengan ringkas, padat, dan meyakinkan.

FASA 3: CALL TO ACTION MESRA & HASHTAGS (~120 aksara)
- Ajak komuniti tengok/dapatkan secara santai (*soft-sell*) dan sertakan 3-4 hashtag tech tempatan di akhir ayat.

ARAHAN KETAT (NEGATIVE CONSTRAINTS):
- Jangan keluarkan sebarang sintaks kod (seperti ```markdown, JSON, console.log).
- Hanya keluarkan TEKS AYAT PROMOSI SAHAJA tanpa sebarang ulasan sistem.
"""

def remove_emojis_and_special_symbols(text):
    """
    Membersihkan teks daripada emoji, simbol khas, kod token LLM (<pad>),
    dan aksara bukan Rumi (untuk elak isu token drift / glitch bahasa asing).
    """
    if not text:
        return ""

    # 1. Buang token khas LLM
    text = re.sub(r'<pad>|<unk>|<s>|</s>|\[PAD\]|\[UNK\]', '', text, flags=re.IGNORECASE)

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

def smart_trim_text(text, max_chars=750):
    """
    Memotong teks secara pintar pada tanda baca terakhir.
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

def is_valid_caption_text(text):
    """
    Menyemak kesahan kualiti teks bagi menghalang kebocoran teks rosak atau perkataan merapu.
    """
    if not text or len(text.strip()) < 80:
        return False
    if "<pad>" in text.lower() or "<unk>" in text.lower():
        return False

    words = text.split()
    # Semak jika perkataan yang sama berulang tanpa kawalan
    if len(words) > 15 and len(set(words)) < 8:
        return False
    return True

def generate_caption(base_url, model, api_key, product_title, product_desc):
    """Menjana kapsyen promosi penceritaan tech yang berkualiti, selamat dan stabil."""
    fallback_caption = (
        f"Korang yang tengah nak upgrade setup atau cari barang tech berkualiti, "
        f"tengok {product_title[:60]} ni! "
        f"Kualiti binaan memang solid, prestasi mantap dan sangat berbaloi untuk kegunaan harian.\n\n"
        f"Jom grab satu untuk lengkapkan setup korang sekarang!\n\n"
        f"#TechMalaysia #PCGamingMalaysia #SetupGaming #GadgetMurah"
    )

    if not base_url or not model or not api_key:
        return False, "Maklumat pengesahan OpenRouter API tidak lengkap."

    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json; charset=utf-8"
    }

    prompt_user = (
        f"Sila buatkan ayat promosi santai gaya Tech Specialist Malaysia (500-650 aksara sahaja) untuk produk ini:\n"
        f"Nama Produk: {product_title}\n"
        f"Deskripsi/Info: {product_desc}"
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT.strip()},
            {"role": "user", "content": prompt_user}
        ],
        "temperature": 0.70,   # Suhu seimbang & stabil
        "max_tokens": 1000     # Ruang penjanaan yang selesa
    }

    # Lakukan percubaan maksimum 2 kali sekiranya berlaku glitch LLM
    for attempt in range(2):
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.encoding = 'utf-8'

            if response.status_code == 200:
                data = response.json()
                if "choices" in data and len(data["choices"]) > 0:
                    raw_content = data['choices'][0]['message']['content'].strip()
                    cleaned_caption = remove_emojis_and_special_symbols(raw_content)
                    final_caption = smart_trim_text(cleaned_caption, max_chars=750)

                    if is_valid_caption_text(final_caption):
                        return True, final_caption
                    else:
                        print(f"⚠️ [PRODUCT AI GLITCH DETECTED - ATTEMPT {attempt+1}] Teks merapu/rosak dikesan. Menjana semula...")
            else:
                print(f"⚠️ [OPENROUTER PRODUCT WARN]: HTTP {response.status_code} - {response.text}")

        except Exception as e:
            print(f"⚠️ [PRODUCT AI EXCEPTION - ATTEMPT {attempt+1}]: {e}")

    # Jika kedua-dua percubaan gagal, gunakan ayat sandaran selamat
    print("🛡️ [SAFETY FALLBACK] Mengaktifkan kapsyen produk sandaran bersih.")
    return True, fallback_caption