import os
import re
import time
import requests
from typing import Dict, Any, Optional, Tuple

# Senarai kata sauh Bahasa Melayu untuk pengesahan kualiti teks (Guardrail)
MALAY_ANCHOR_WORDS = {
    "yang", "dan", "di", "ke", "kat", "ni", "tu", "dah", "nak", "ada",
    "kita", "korang", "saya", "buat", "bila", "dengan", "pun", "rasa",
    "meja", "setup", "pc", "kerja", "santai", "tengok", "dalam", "untuk",
    "tak", "bukan", "memang", "lagi", "padu", "mantap", "kemas", "berbaloi"
}

SYSTEM_PROMPT = """
Anda ialah Penulis & Tech Specialist rasmi untuk Facebook Page "Sembang PC & Tech Malaysia".
Gaya penulisan anda mestilah SANTAI, BERCERITA (Storytelling), INFORMATIF, dan MESRA komuniti tech/gaming Malaysia.

GAYA BAHASA & STRUKTUR KAPSYEN:
1. BAHASA: 100% Bahasa Melayu santai komuniti tech tempatan ("Korang yang tengah nak upgrade setup...", "Barang ni memang padu...", "Kabel tak berserabut dah", "Sangat berbaloi").
2. DILARANG SAMA SEKALI guna bahasa kaku atau Bahasa Indonesia ("bisa", "banget", "nggak", "komputer jinjing").
3. STRUKTUR TEKS (ZON EMAS: 500 HINGGA 700 AKSARA):
   - Fasa 1 (Hook & Masalah Setup): Mulakan dengan situasi berkaitan masalah setup meja, keperluan upgrade perkakasan PC, atau gajet harian.
   - Fasa 2 (Ulasan & Kelebihan): Huraikan kelebihan produk dan senaraikan 2 hingga 3 poin utama menggunakan simbol bullet point (•).
   - Fasa 3 (Call To Action Ruangan Komen - WAJIB):
     "👉 Pautan belian rasmi Shopee abang dah sediakan di ruangan komen pertama di bawah ya! 👇"
   - Fasa 4 (Hashtags Rasmi):
     #SembangPCTech #TechMalaysia #PCSetup #RacunGajet #ShopeeMY

ARAHAN PANTANGAN KETAT:
- DILARANG meletakkan pautan (URL/Link) di dalam teks ini (kerana link diletakkan di ruangan komen).
- TERUS TULIS AYAT KANDUNGAN TANPA sebarang mukadimah AI seperti "Berikut adalah kapsyen...".
- Panjang teks WAJIB di antara 500 hingga 700 aksara.
"""


def clean_glitches_and_meta(text: str) -> str:
    """
    Membersihkan teks daripada token LLM, simbol asing, dan mukadimah bot.
    """
    if not text:
        return ""

    # 1. Buang tag pemikiran reasoning model AI
    text = re.sub(r'<think>[\s\S]*?</think>', '', text, flags=re.IGNORECASE)

    # 2. Buang token khas LLM
    text = re.sub(r'<pad>|<unk>|<s>|</s>|\[PAD\]|\[UNK\]|<\|.*?\|>', '', text, flags=re.IGNORECASE)

    # 3. Standardkan bullet points
    for sym in ["❖", "◆", "◇", "►", "▪", "▲", "★", "➡", "➢", "*"]:
        text = text.replace(sym, "•")

    # 4. Buang teks pembuka / penutup AI
    text = re.sub(r'(?i)^\s*(?:yo|hai|salam|hello)?[^\n]*?(?:cadangan|kapsyen|caption)[^\n]*?\n+', '', text)
    text = re.sub(r'(?i)\*\*caption\s*(?:facebook)?\s*:\*\*', '', text)
    text = re.sub(r'\*\*\*', '', text)

    # 5. Tapis aksara bukan Rumi jika berlaku glitch model
    text = re.sub(r'[^\x00-\x7F\u00C0-\u024F\s.,!?:;\'"()/\-#@+•]', '', text)

    # 6. Susun baris perenggan
    lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in text.splitlines()]
    return "\n".join([line for line in lines if line]).strip()


def smart_trim_fb_text(text: str, max_chars: int = 700) -> str:
    """
    Memotong teks secara kemas pada noktah atau tanda seru terakhir
    sekiranya panjang teks melebihi had maksimum 700 aksara.
    """
    if not text or len(text) <= max_chars:
        return text

    trimmed = text[:max_chars]
    last_punc = max(trimmed.rfind('.'), trimmed.rfind('!'), trimmed.rfind('?'), trimmed.rfind('\n'))

    if last_punc != -1 and last_punc > 400:
        return trimmed[:last_punc + 1].strip()

    last_space = trimmed.rfind(' ')
    if last_space != -1:
        return trimmed[:last_space].strip() + "..."
    return trimmed + "..."


def is_valid_fb_caption(text: str) -> bool:
    """
    Menyemak kualiti teks, kepelbagaian perkataan, dan ketepatan Bahasa Melayu.
    """
    if not text or len(text.strip()) < 250:
        return False
    if "<pad>" in text.lower() or "<unk>" in text.lower():
        return False

    # Semak jika terdapat pengulangan perkataan berturut-turut
    if re.search(r'(\b\w+\b)(?:\s+\1){2,}', text, flags=re.IGNORECASE):
        return False

    words = [w.lower() for w in re.findall(r'\b[a-zA-Z]+\b', text)]
    if len(words) < 30:
        return False

    unique_words = set(words)
    if len(unique_words) / len(words) < 0.45:
        return False

    matching_anchors = unique_words.intersection(MALAY_ANCHOR_WORDS)
    if len(matching_anchors) < 3:
        return False

    return True


class ShopeeFBAIPersona:
    """Enjin AI Persona Facebook khusus untuk ekosistem Sembang PC & Tech Malaysia."""

    def __init__(self):
        self.base_url = (os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1").strip().rstrip("/")
        self.model_primary = (
            os.getenv("SHOPEE_OPENROUTER_MODEL", "").strip()
            or os.getenv("OPENROUTER_MODEL", "").strip()
        )
        self.model_fallback = (
            os.getenv("SHOPEE_OPENROUTER_MODEL_FALLBACK", "").strip()
            or os.getenv("OPENROUTER_MODEL_FALLBACK", "").strip()
        )
        self.api_key = os.getenv("OPENROUTER_API_KEY", "").strip()

    def _call_llm_api(self, model_name: str, system_prompt: str, user_prompt: str) -> Tuple[bool, Optional[str], str]:
        """Memanggil endpoint OpenRouter API dengan mekanisme auto-backoff rehat jika terkena 429/503."""
        if not self.base_url or not self.api_key or not model_name:
            return False, None, "Konfigurasi OpenRouter (Base URL, API Key, Model) tidak lengkap."

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json; charset=utf-8",
            "HTTP-Referer": "https://sembangpctech.local",
            "X-Title": "Sembang PC & Tech Bot",
        }

        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt.strip()},
                {"role": "user", "content": user_prompt.strip()},
            ],
            "temperature": 0.68,
            "max_tokens": 600,
        }

        url = f"{self.base_url}/chat/completions"

        for attempt in range(2):
            try:
                res = requests.post(url, json=payload, headers=headers, timeout=25)
                res.encoding = "utf-8"

                if res.status_code in [429, 502, 503]:
                    wait_sec = 6 * (attempt + 1)
                    print(f"  ⚠️ [FB AI {res.status_code}] Model '{model_name}' sesak/rehat. Menunggu {wait_sec}s...")
                    time.sleep(wait_sec)
                    continue

                if res.status_code == 200:
                    data = res.json()
                    if "choices" in data and len(data["choices"]) > 0:
                        content = data["choices"][0]["message"]["content"].strip()
                        return True, content, "Berjaya"
                else:
                    err_snippet = res.text[:120]
                    print(f"  ⚠️ [FB AI HTTP {res.status_code}]: {err_snippet}")
                    time.sleep(2)

            except Exception as e:
                print(f"  ⚠️ [FB AI EXCEPTION]: {e}")
                time.sleep(2)

        return False, None, f"Gagal mendapatkan respon daripada model {model_name}"

    def generate_caption(self, product_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Menjana kapsyen Facebook Feed (500 - 700 Aksara) dengan mekanisme failover & retry.
        Memulangkan: (success_bool, caption_text)
        """
        raw_title = str(product_data.get("shopee_product_name") or product_data.get("title") or "Gajet Pilihan").strip()
        clean_title = re.sub(r'\s+', ' ', raw_title)[:75].strip()
        brand = product_data.get("shopee_brand") or product_data.get("brand") or "Pilihan Komuniti"
        price = product_data.get("shopee_price") or product_data.get("price") or ""
        category = product_data.get("shopee_category") or product_data.get("category") or "Aksesori PC & Gajet"

        price_str = f"RM {float(price):.2f}" if price and str(price).replace('.', '', 1).isdigit() else "Tawaran Berbaloi"

        fallback_caption = (
            f"Korang yang tengah nak kemaskan setup meja atau upgrade barang PC, wajib tengok {clean_title} ni! "
            f"Bila ruang kerja teratur, baru lah selesa nak layan game atau buat kerja lama-lama.\n\n"
            f"Antara kelebihan utama yang padu:\n"
            f"• Kualiti binaan kemas & tahan lasak ({brand})\n"
            f"• Prestasi mantap dan padan dengan harga {price_str}\n"
            f"• Menjadikan ruang meja nampak lebih moden & tersusun\n\n"
            f"👉 Pautan belian rasmi Shopee abang dah sediakan di ruangan komen pertama di bawah ya! 👇\n\n"
            f"#SembangPCTech #TechMalaysia #PCSetup #RacunGajet #ShopeeMY"
        )

        if not self.base_url or not self.api_key:
            print("⚠️ [FB AI WARN] Kunci OpenRouter tidak lengkap, menggunakan kapsyen sandaran.")
            return True, fallback_caption

        user_prompt = f"""
Sila hasilkan 1 kapsyen Facebook ulasan santai gaya Sembang PC & Tech Malaysia (500 - 700 aksara) untuk produk ini:
- Nama Produk: {clean_title}
- Jenama / Kualiti: {brand}
- Kategori: {category}
- Anggaran Harga: {price_str}

Peringatan: JANGAN letak sebarang link. Pastikan ayat CTA ruangan komen disertakan di akhir ayat.
"""

        models_queue = [m for m in [self.model_primary, self.model_fallback] if m]
        if not models_queue:
            print("⚠️ [FB AI WARN] Tiada model OpenRouter dikonfigurasi, menggunakan kapsyen sandaran.")
            return True, fallback_caption

        for model_idx, current_model in enumerate(models_queue, 1):
            print(f"🤖 [FB AI GENERATION] Mencuba Model {model_idx}/{len(models_queue)}: '{current_model}'...")
            ok_call, raw_content, msg = self._call_llm_api(current_model, SYSTEM_PROMPT, user_prompt)

            if ok_call and raw_content:
                cleaned_content = clean_glitches_and_meta(raw_content)
                final_caption = smart_trim_fb_text(cleaned_content, max_chars=700)

                if is_valid_fb_caption(final_caption):
                    # Pastikan ayat CTA komen wujud
                    if "komen pertama" not in final_caption.lower():
                        final_caption += "\n\n👉 Pautan belian rasmi Shopee abang dah sediakan di ruangan komen pertama di bawah ya! 👇"
                    
                    print(f"✅ [FB AI SUCCESS] Kapsyen Facebook berjaya dijana ({len(final_caption)} aksara | Model: '{current_model}').")
                    return True, final_caption
                else:
                    print(f"⚠️ [FB AI GLITCH] Teks tidak menepati syarat kualiti untuk model '{current_model}'.")

        print("🛡️ [FB AI FALLBACK] Mengaktifkan kapsyen Facebook sandaran bersih.")
        return True, fallback_caption


# Singleton instance untuk kegunaan modular
shopee_fb_ai = ShopeeFBAIPersona()