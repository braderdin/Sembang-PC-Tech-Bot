#!/usr/bin/env python3
"""
Instagram AI Persona Engine (Brader Din Style)
Sembang PC & Tech Ecosystem
Optimized for Gemma / Gemini Models with positive contextual prompting.
"""

import os
import re
from typing import Dict, Any, Optional
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Konfigurasi Model AI
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
MODEL_NAME = os.getenv("GEMMA_MODEL_NAME", "gemini-1.5-flash")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


# Panduan Persona Positif Gaya "Brader Din" Khas Instagram
IG_PERSONA_PROMPT = """
Anda adalah "Brader Din", pencipta kandungan teknologi dan ulasan perkakasan komputer yang ramah dan berilmu di komuniti Sembang PC & Tech Malaysia.

GAYA PENULISAN INSTAGRAM YANG DIMINATI:
1. Nada Suara: Santai, mesra komuniti (Bahasa Melayu harian yang kemas, guna panggilan 'bro', 'korang', 'geng tech').
2. Visual & Formatting: 
   - Gunakan perenggan pendek yang mudah dibaca di skrin telefon.
   - Susun ciri utama menggunakan bullet points yang kemas bersama emoji berkaitan.
   - Sediakan pembuka kata yang menarik minat (Hook).
3. Pautan & CTA Instagram:
   - Instagram tidak membenarkan link diklik terus di dalam kapsyen.
   - Arahkan pembaca dengan mesra ke pautan di Bio profil atau Telegram kita: (Contoh: "🔗 Link pembelian padu abang dah pin di Bio profil!")
4. Hashtags:
   - Sertakan 6 hingga 10 hashtag berkaitan teknologi, PC setup, dan gajet Malaysia yang relevan di penghujung kapsyen.
"""


class InstagramAIPersona:
    """Enjin AI untuk menjana kapsyen Instagram affiliate dan lifestyle."""

    def __init__(self, model_name: str = MODEL_NAME):
        self.model_name = model_name
        self.model = None
        if GEMINI_API_KEY:
            try:
                self.model = genai.GenerativeModel(
                    model_name=self.model_name,
                    system_instruction=IG_PERSONA_PROMPT
                )
            except Exception as e:
                print(f"⚠️ [Instagram Persona] Amaran inisialisasi AI: {e}")

    def generate_affiliate_caption(self, product_data: Dict[str, Any]) -> str:
        """
        Menjana kapsyen ulasan produk racun gajet yang memikat untuk feed Instagram.
        """
        title = product_data.get("title", "Gajet Padu Pilihan")
        price = product_data.get("price", "")
        features = product_data.get("features", "")
        link = product_data.get("affiliate_link", "")

        prompt = f"""
Sila hasilkan kapsyen hantaran Instagram ulasan produk berbaloi:

Nama Produk: {title}
Harga/Tawaran: {price}
Ciri-ciri Utama: {features}
Pautan Affiliate Asal: {link}

STRUKTUR KANDUNGAN:
- Hook santai yang menarik perhatian kaki PC & setup meja.
- Ulasan ringkas kenapa barang ini berbaloi dimiliki / praktikal.
- 3 ke 4 bullet point kelebihan gajet ini.
- Call To Action (CTA): Jemput follower semak link pembelian di Bio atau pautan ringkas.
- 8 hashtag trending teknologi tempatan.

Hasilkan kapsyen yang terus sedia disiarkan tanpa teks pengenalan sistem.
"""
        if not self.model:
            return self._fallback_affiliate_caption(title, price, link)

        try:
            response = self.model.generate_content(prompt)
            caption = response.text.strip()
            return self._clean_markdown(caption)
        except Exception as e:
            print(f"⚠️ [Instagram Persona] Ralat penjanaan kapsyen: {e}")
            return self._fallback_affiliate_caption(title, price, link)

    def generate_lifestyle_caption(self, topic: str, key_points: Optional[str] = None) -> str:
        """
        Menjana kapsyen gaya hidup, tips susun atur meja, dan perkongsian IT harian.
        """
        prompt = f"""
Sila hasilkan kapsyen Instagram santai bertemakan gaya hidup teknologi & inspirasi setup meja:

Topik: {topic}
Poin Tambahan: {key_points or 'Tips meja kemas & produktiviti'}

STRUKTUR KANDUNGAN:
- Pembuka kata inspiratif tentang dunia setup & teknologi.
- Perkongsian santai 3 tips atau pandangan bernas.
- Soalan santai untuk galakkan follower komen & bersembang.
- CTA jemput follow @braderdin360 & komuniti Sembang PC & Tech.
- 6 hingga 8 hashtag santai desk setup & tech Malaysia.

Hasilkan kapsyen kemas yang sedia untuk disiarkan.
"""
        if not self.model:
            return self._fallback_lifestyle_caption(topic)

        try:
            response = self.model.generate_content(prompt)
            caption = response.text.strip()
            return self._clean_markdown(caption)
        except Exception as e:
            print(f"⚠️ [Instagram Persona] Ralat penjanaan lifestyle: {e}")
            return self._fallback_lifestyle_caption(topic)

    def _clean_markdown(self, text: str) -> str:
        """Membersihkan format yang tidak disokong kemas di Instagram."""
        # Menukar format bold markdown berganda kepada teks biasa/kemas jika perlu
        text = text.replace("```", "").strip()
        return text

    def _fallback_affiliate_caption(self, title: str, price: str, link: str) -> str:
        """Kapsyen simpanan jika tiada sambungan AI."""
        price_line = f"\n💰 Harga Tawaran: {price}" if price else ""
        return f"""Racun gajet padu pilihan Brader Din harini! ⚡💻

📦 {title}{price_line}

Setup meja lebih kemas dan produktif bila ada gajet yang memudahkan kerja macam ni. Memang puas hati! 🔥

🔗 Link pembelian rasmi ada di Bio profil atau terus di Telegram Sembang PC & Tech ya geng! 👇

#SembangPCTech #TechMalaysia #PCSetup #RacunGajet #DeskSetup #WorkspaceMalaysia #ShopeeMY #LazadaMY"""

    def _fallback_lifestyle_caption(self, topic: str) -> str:
        """Kapsyen simpanan lifestyle."""
        return f"""Inspirasi setup meja & sembang santai hari ini: {topic} 🖥️✨

Meja yang kemas dan pencahayaan yang sedap mata memandang secara automatik buat semangat buat kerja atau layan game makin padu.

Korang jenis suka setup minimalis bersih atau penuh dengan lampu RGB? Cuba drop komen sikit di bawah! 👇

#SembangPCTech #TechMalaysia #DeskSetupGoals #PCGaming #MinimalistDesk #WorkspaceInspiration"""


# Instance sedia guna
instagram_ai = InstagramAIPersona()