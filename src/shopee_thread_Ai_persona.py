import os
import re
import requests
from typing import Dict, Any, Optional, Tuple

# Senarai kata sauh Bahasa Melayu untuk pengesahan kualiti Threads
MALAY_ANCHOR_WORDS = {
    "yang", "dan", "di", "ke", "kat", "ni", "tu", "dah", "nak", "ada",
    "kita", "korang", "saya", "buat", "bila", "dengan", "pun", "rasa",
    "meja", "setup", "pc", "kerja", "santai", "tengok", "dalam", "untuk",
    "tak", "bukan", "memang", "lagi", "padu", "mantap", "kemas", "berbaloi"
}

SYSTEM_PROMPT = """
Anda ialah Tech Specialist Malaysia yang menulis ulasan pantas (quick racun tech) di Meta Threads untuk "Sembang PC & Tech Malaysia".
Format penulisan anda ialah MIKRO-BLOG: Ringkas, Padat, Santai, Spontan, dan Berbisa.

GAYA BAHASA & STRUKTUR KAPSYEN:
1. BAHASA: 100% Bahasa Melayu santai harian komuniti PC/Tech tempatan ("Barang padu ni guys...", "Korang yang tengah nak upgrade meja...", "Kemas gila setup lepas pasang ni").
2. DILARANG SAMA SEKALI guna bahasa kaku atau perkataan Indonesia ("bisa", "banget", "nggak").
3. STRUKTUR TEKS (HAD KETAT: 180 HINGGA 260 AKSARA SAHAJA):
   - Ulas 1 hingga 2 kelebihan utama produk ini dengan pantas.
   - Akhiri teks dengan 1 soalan santai untuk memancing interaksi & komen pengikut di Threads.
4. ARAHAN PANTANGAN KETAT:
   - DILARANG meletakkan link/URL di dalam jawapan AI (link akan dimasukkan secara automatik oleh skrip).
   - DILARANG letak sebarang hashtag di dalam teks janaan AI.
   - TERUS TULIS AYAT KANDUNGAN tanpa sebarang mukadimah pembantu AI.
"""


def clean_threads_text(text: str) -> str:
    """
    Membersihkan token LLM, simbol mojibake, dan merapikan susunan teks Threads.
    """
    if not text:
        return ""

    # 1. Buang token khas LLM
    text = re.sub(r'<pad>|<unk>|<s>|</s>|\[PAD\]|\[UNK\]|<\|.*?\|>', '', text, flags=re.IGNORECASE)

    # 2. Buang simbol mojibake / glitch encoding
    text = re.sub(r'[ðâ][\x80-\xbf]{1,4}', '', text)
    text = re.sub(r'[\x80-\x9f]', '', text)

    # 3. Buang mukadimah pembantu AI
    text = re.sub(r'(?i)^\s*(?:yo|hai|salam|hello)?[^\n]*?(?:cadangan|kapsyen|caption)[^\n]*?\n+', '', text)
    text = re.sub(r'(?i)\*\*caption\s*(?:threads)?\s*:\*\*', '', text)
    text = re.sub(r'\*\*\*', '', text)

    # 4. Tapis aksara bukan Rumi jika berlaku glitch
    text = re.sub(r'[^\x00-\x7F\u00C0-\u024F\s.,!?:;\'"()/\-#@+•]', '', text)

    # 5. Susun baris perenggan
    lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in text.splitlines()]
    return "\n".join([line for line in lines if line]).strip()


def smart_trim_threads_body(text: str, max_chars: int = 260) -> str:
    """
    Memotong teks ulasan Threads secara pintar pada tanda baca terakhir.
    """
    if not text or len(text) <= max_chars:
        return text

    trimmed = text[:max_chars]
    last_punc = max(trimmed.rfind('.'), trimmed.rfind('?'), trimmed.rfind('!'))

    if last_punc != -1 and last_punc > 80:
        return trimmed[:last_punc + 1].strip()

    last_space = trimmed.rfind(' ')
    if last_space != -1:
        return trimmed[:last_space].strip() + "..."
    return trimmed + "..."


def is_valid_threads_caption(text: str, min_len: int = 40) -> bool:
    """
    Memastikan teks dijana menepati kualiti Bahasa Melayu dan sifar perkataan berulang.
    """
    if not text or len(text.strip()) < min_len:
        return False
    if "<pad>" in text.lower() or "<unk>" in text.lower():
        return False

    # Semak pengulangan perkataan berturut-turut
    if re.search(r'(\b\w+\b)(?:\s+\1){2,}', text, flags=re.IGNORECASE):
        return False

    words = [w.lower() for w in re.findall(r'\b[a-zA-Z]+\b', text)]
    if len(words) < 8:
        return False

    unique_words = set(words)
    if len(unique_words) / len(words) < 0.45:
        return False

    matching_anchors = unique_words.intersection(MALAY_ANCHOR_WORDS)
    if len(matching_anchors) < 2:
        return False

    return True


class ShopeeThreadsAIPersona:
    """Enjin AI Persona Threads khusus untuk hantaran racun mikro-blog Shopee."""

    def __init__(self):
        self.base_url = (os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1").strip().rstrip("/")
        self.model = os.getenv("OPENROUTER_MODEL", "").strip()
        self.api_key = os.getenv("OPENROUTER_API_KEY", "").strip()

    def generate_caption(self, product_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Menjana kapsyen penuh Threads bersama pautan Shopee (Jumlah WAJIB <= 480 aksara).
        Memulangkan: (success_bool, full_threads_post_text)
        """
        raw_title = str(product_data.get("shopee_product_name") or product_data.get("title") or "Gajet Pilihan").strip()
        clean_title = re.sub(r'\s+', ' ', raw_title)[:60].strip()
        brand = product_data.get("shopee_brand") or product_data.get("brand") or "Shopee Preferred"
        price = product_data.get("shopee_price") or product_data.get("price") or ""
        aff_link = str(product_data.get("shopee_affiliate_link") or product_data.get("affiliate_link") or "").strip()

        price_str = f"RM {float(price):.2f}" if price and str(price).replace('.', '', 1).isdigit() else ""

        # Bina komponen pautan & hashtag di hujung teks
        link_part = f"\n\n🛒 Dapatkan di Shopee: {aff_link}" if aff_link else ""
        hashtag_part = "\n\n#SembangPCTech #ShopeeMY"
        footer = f"{link_part}{hashtag_part}"

        # Hitung baki aksara maksimum untuk badan teks AI (Maksimum keseluruhan Threads = 480 aksara)
        max_body_allowed = 480 - len(footer) - 5
        if max_body_allowed > 260:
            max_body_allowed = 260
        elif max_body_allowed < 100:
            max_body_allowed = 180

        fallback_body = (
            f"Korang yang tengah nak kemaskan setup meja atau cari barang tech padu, tengok {clean_title} ni! "
            f"Kualiti mantap dan sangat berbaloi untuk kegunaan harian. Korang dah upgrade setup meja belum?"
        )

        if not self.base_url or not self.model or not self.api_key:
            print("⚠️ [THREADS AI WARN] Kunci OpenRouter tidak lengkap, menggunakan kapsyen sandaran.")
            full_text = f"{fallback_body}{footer}".strip()
            return True, full_text[:480]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json; charset=utf-8",
            "HTTP-Referer": "https://sembangpctech.local",
            "X-Title": "Sembang PC & Tech Bot",
        }

        user_prompt = f"""
Sila buatkan 1 hantaran mikro-blog Threads santai gaya Sembang PC & Tech (180 - 240 aksara sahaja) untuk produk ini:
- Produk: {clean_title}
- Jenama: {brand}
- Info Harga: {price_str if price_str else 'Harga Berbaloi'}

Peringatan: JANGAN letak pautan/link. Akhiri dengan 1 soalan santai untuk interaksi pembaca.
"""

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT.strip()},
                {"role": "user", "content": user_prompt.strip()},
            ],
            "temperature": 0.68,
            "max_tokens": 300,
        }

        url = f"{self.base_url}/chat/completions"

        # Mekanisme 3x Percubaan (Retry)
        for attempt in range(3):
            try:
                print(f"🤖 [THREADS AI GENERATION] Menjana kapsyen Threads (Percubaan {attempt + 1}/3)...")
                res = requests.post(url, json=payload, headers=headers, timeout=20)
                res.encoding = "utf-8"

                if res.status_code == 200:
                    data = res.json()
                    if "choices" in data and len(data["choices"]) > 0:
                        raw_content = data["choices"][0]["message"]["content"].strip()
                        cleaned_body = clean_threads_text(raw_content)
                        final_body = smart_trim_threads_body(cleaned_body, max_chars=max_body_allowed)

                        if is_valid_threads_caption(final_body, min_len=40):
                            full_post = f"{final_body}{footer}".strip()
                            if len(full_post) > 480:
                                # Jika masih terlajak, potong badan teks dengan cermat
                                excess = len(full_post) - 480
                                final_body = smart_trim_threads_body(final_body, max_chars=len(final_body) - excess - 5)
                                full_post = f"{final_body}{footer}".strip()

                            print(f"✅ [THREADS AI SUCCESS] Kapsyen Threads berjaya dijana ({len(full_post)}/480 aksara).")
                            return True, full_post
                        else:
                            print(f"⚠️ [THREADS AI GLITCH] Teks gagal tapisan kualiti pada percubaan {attempt + 1}. Mencuba semula...")
                else:
                    print(f"⚠️ [THREADS AI HTTP ERROR] HTTP {res.status_code}: {res.text}")

            except Exception as e:
                print(f"⚠️ [THREADS AI EXCEPTION - ATTEMPT {attempt + 1}]: {str(e)}")

        print("🛡️ [THREADS AI FALLBACK] Mengaktifkan kapsyen Threads sandaran bersih.")
        full_fallback = f"{fallback_body}{footer}".strip()
        return True, full_fallback[:480]


# Singleton instance untuk kegunaan modular
shopee_threads_ai = ShopeeThreadsAIPersona()