import os
import re
import requests
from typing import Dict, Any, Optional, Tuple

# Senarai kata sauh Bahasa Melayu untuk pengesahan kualiti Bluesky
MALAY_ANCHOR_WORDS = {
    "yang", "dan", "di", "ke", "kat", "ni", "tu", "dah", "nak", "ada",
    "kita", "korang", "saya", "buat", "bila", "dengan", "pun", "rasa",
    "meja", "setup", "pc", "kerja", "santai", "tengok", "dalam", "untuk",
    "tak", "bukan", "memang", "lagi", "padu", "mantap", "kemas", "berbaloi"
}

SYSTEM_PROMPT = """
Anda ialah Tech Specialist yang menulis ulasan padat gajet/PC di Bluesky untuk "Sembang PC & Tech Malaysia".
Format penulisan ialah MIKRO-BLOG SANGAT PADAT: Terus ke inti pati, fakta perkakasan pantas, dan santai.

GAYA BAHASA & STRUKTUR:
1. BAHASA: 100% Bahasa Melayu santai komuniti tech ("Barang padu ni...", "Korang yang nak kemaskan setup...", "Berbaloi gila harga ni").
2. DILARANG SAMA SEKALI guna bahasa kaku atau perkataan Indonesia ("bisa", "banget", "nggak").
3. STRUKTUR TEKS (HAD KETAT: 100 HINGGA 160 AKSARA SAHAJA UNTUK BADAN TEKS):
   - Nyatakan 1 fungsi/kelebihan utama barang dengan pantas dan ringkas.
4. ARAHAN PANTANGAN KETAT:
   - DILARANG letak sebarang pautan/link atau hashtag di dalam respon AI (pautan dan hashtag akan dipasang automatik oleh skrip).
   - TERUS TULIS AYAT KANDUNGAN tanpa sebarang mukadimah AI.
"""


def clean_bluesky_text(text: str) -> str:
    """
    Membersihkan teks daripada token LLM, simbol rosak, dan mukadimah bot.
    """
    if not text:
        return ""

    # 1. Buang token khas LLM
    text = re.sub(r'<pad>|<unk>|<s>|</s>|\[PAD\]|\[UNK\]|<\|.*?\|>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'[ðâ][\x80-\xbf]{1,4}', '', text)
    text = re.sub(r'[\x80-\x9f]', '', text)

    # 2. Buang mukadimah pembantu AI
    text = re.sub(r'(?i)^\s*(?:yo|hai|salam|hello)?[^\n]*?(?:cadangan|kapsyen|caption|post)[^\n]*?\n+', '', text)
    text = re.sub(r'(?i)\*\*caption\s*(?:bluesky)?\s*:\*\*', '', text)
    text = re.sub(r'(?i)\n+\s*\*{0,2}tips\s*tambahan[^\n]*\*{0,2}[\s\S]*$', '', text)
    text = re.sub(r'\*\*\*', '', text)

    # 3. Kemaskan ruang kosong
    lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in text.splitlines()]
    return " ".join([line for line in lines if line]).strip()


def smart_trim_bluesky(text: str, max_chars: int = 160) -> str:
    """
    Memotong teks ulasan secara pintar pada tanda baca atau ruang kosong.
    """
    if not text or len(text) <= max_chars:
        return text

    trimmed = text[:max_chars]
    last_punc = max(trimmed.rfind('.'), trimmed.rfind('!'), trimmed.rfind('?'))

    if last_punc != -1 and last_punc > 50:
        return trimmed[:last_punc + 1].strip()

    last_space = trimmed.rfind(' ')
    if last_space != -1:
        return trimmed[:last_space].strip() + "..."

    return trimmed[:max_chars - 3] + "..."


def is_valid_bluesky_caption(text: str, min_len: int = 30) -> bool:
    """
    Menyemak kualiti teks, mengelakkan token gelung dan memastikan ketepatan Bahasa Melayu.
    """
    if not text or len(text.strip()) < min_len:
        return False
    if "<pad>" in text.lower() or "<unk>" in text.lower():
        return False

    if re.search(r'(\b\w+\b)(?:\s+\1){2,}', text, flags=re.IGNORECASE):
        return False

    words = [w.lower() for w in re.findall(r'\b[a-zA-Z]+\b', text)]
    if len(words) < 6:
        return False

    unique_words = set(words)
    if len(unique_words) / len(words) < 0.40:
        return False

    matching_anchors = unique_words.intersection(MALAY_ANCHOR_WORDS)
    if len(matching_anchors) < 2:
        return False

    return True


class ShopeeBlueskyAIPersona:
    """Enjin AI Persona Bluesky khusus untuk hantaran produk Shopee pantas (Hard Limit <= 300 Chars)."""

    def __init__(self):
        self.base_url = (os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1").strip().rstrip("/")
        self.model = os.getenv("OPENROUTER_MODEL", "").strip()
        self.api_key = os.getenv("OPENROUTER_API_KEY", "").strip()

    def generate_caption(self, product_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Menjana kapsyen penuh Bluesky Feed bersama pautan Shopee (Maksimum TEGAS <= 295 aksara).
        Memulangkan: (success_bool, full_bluesky_text)
        """
        raw_title = str(product_data.get("shopee_product_name") or product_data.get("title") or "Gajet Pilihan").strip()
        clean_title = re.sub(r'\s+', ' ', raw_title)[:55].strip()
        brand = product_data.get("shopee_brand") or product_data.get("brand") or "Shopee Preferred"
        price = product_data.get("shopee_price") or product_data.get("price") or ""
        aff_link = str(product_data.get("shopee_affiliate_link") or product_data.get("affiliate_link") or "").strip()

        price_str = f"RM {float(price):.2f}" if price and str(price).replace('.', '', 1).isdigit() else ""

        # Bina komponen pautan & hashtag di penghujung teks
        link_part = f"\n\n🛒 Shopee: {aff_link}" if aff_link else ""
        hashtag_part = "\n\n#SembangPCTech #ShopeeMY"
        footer = f"{link_part}{hashtag_part}"

        # Had maksimum ketat keseluruhan Bluesky ialah 300 aksara. Kita sasarkan 290 aksara untuk zon selamat.
        max_body_allowed = 290 - len(footer)
        if max_body_allowed > 160:
            max_body_allowed = 160
        elif max_body_allowed < 60:
            max_body_allowed = 90

        fallback_body = (
            f"Korang yang tengah nak kemaskan ruang meja atau cari gajet praktikal, tengok {clean_title} ni! "
            f"Kualiti solid dan sangat berbaloi."
        )

        if not self.base_url or not self.model or not self.api_key:
            print("⚠️ [BLUESKY AI WARN] Kunci OpenRouter tidak lengkap, menggunakan kapsyen sandaran.")
            full_text = f"{fallback_body[:max_body_allowed]}{footer}".strip()
            return True, full_text[:295]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json; charset=utf-8",
            "HTTP-Referer": "https://sembangpctech.local",
            "X-Title": "Sembang PC & Tech Bluesky Bot",
        }

        user_prompt = f"""
Sila hasilkan 1 ulasan pantas Bluesky (100 - 150 aksara sahaja) untuk produk ini:
- Nama Produk: {clean_title}
- Jenama: {brand}
- Harga: {price_str if price_str else 'Harga Berbaloi'}

Peringatan: JANGAN letak link atau hashtag. Tulis ayat ulasan padat sahaja.
"""

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT.strip()},
                {"role": "user", "content": user_prompt.strip()},
            ],
            "temperature": 0.65,
            "max_tokens": 200,
        }

        url = f"{self.base_url}/chat/completions"

        # Mekanisme 3x Percubaan (Retry)
        for attempt in range(3):
            try:
                print(f"🤖 [BLUESKY AI GENERATION] Menjana kapsyen Bluesky (Percubaan {attempt + 1}/3)...")
                res = requests.post(url, json=payload, headers=headers, timeout=20)
                res.encoding = "utf-8"

                if res.status_code == 200:
                    data = res.json()
                    if "choices" in data and len(data["choices"]) > 0:
                        raw_content = data["choices"][0]["message"]["content"].strip()
                        cleaned_body = clean_bluesky_text(raw_content)
                        final_body = smart_trim_bluesky(cleaned_body, max_chars=max_body_allowed)

                        if is_valid_bluesky_caption(final_body, min_len=25):
                            full_post = f"{final_body}{footer}".strip()
                            if len(full_post) > 295:
                                excess = len(full_post) - 295
                                final_body = smart_trim_bluesky(final_body, max_chars=len(final_body) - excess - 5)
                                full_post = f"{final_body}{footer}".strip()

                            print(f"✅ [BLUESKY AI SUCCESS] Kapsyen Bluesky berjaya dijana ({len(full_post)}/295 aksara).")
                            return True, full_post
                        else:
                            print(f"⚠️ [BLUESKY AI GLITCH] Teks gagal tapisan kualiti pada percubaan {attempt + 1}. Mencuba semula...")
                else:
                    print(f"⚠️ [BLUESKY AI HTTP ERROR] HTTP {res.status_code}: {res.text}")

            except Exception as e:
                print(f"⚠️ [BLUESKY AI EXCEPTION - ATTEMPT {attempt + 1}]: {str(e)}")

        print("🛡️ [BLUESKY AI FALLBACK] Mengaktifkan kapsyen Bluesky sandaran bersih.")
        trimmed_fallback_body = smart_trim_bluesky(fallback_body, max_chars=max_body_allowed)
        full_fallback = f"{trimmed_fallback_body}{footer}".strip()
        return True, full_fallback[:295]


# Singleton instance untuk kegunaan modular
shopee_bluesky_ai = ShopeeBlueskyAIPersona()