#!/usr/bin/env python3
"""
Master Execution Runner for Affiliate Product Reels (Facebook, Instagram & Threads)
Sembang PC & Tech Ecosystem (3x Daily)
Features:
- Dedicated AI Personas tailored for Facebook Reels, Instagram Reels & Threads Video.
- 100% Strict Zero-Emoji & Glitch-Proof Filters (Prevents UTF-8 / Mojibake corruption).
- Direct Affiliate Link Injection in IG Reels Caption (Auto-syncs clickable URL to Pinterest).
- Tailored character limits (IG/Pinterest: 350-450 chars, Threads: <480 chars, FB: 350-500 chars).
- Local MoviePy MP4 stitching using original image size/ratio with background music.
- Multi-platform publishing (FB Reels + Comment link, IG Reels, Threads via Backblaze B2).
- Detailed Telegram audit report dispatch with all platform captions and status links.
"""

import os
import re
import sys
import time
import random
import tempfile
import requests
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
from dotenv import load_dotenv

# MoviePy v1.x & v2.x Compatibility Layer
try:
    from moviepy import ImageClip, AudioFileClip
except ImportError:
    from moviepy.editor import ImageClip, AudioFileClip

# Set Project Root Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load Environment Variables Dynamically
env_local = PROJECT_ROOT / ".env.local"
if env_local.exists():
    load_dotenv(dotenv_path=env_local)
else:
    load_dotenv()

# Import Project Modules
from src.supabase_db import fetch_unused_links, mark_link_as_used, get_supabase_config
from src.redis_db import is_product_posted, mark_product_posted
from src.vector_db import is_similar_product_posted, mark_vector_posted
from src.pexels_reel_bot import upload_reel_to_facebook
from src.pexels_reel_bot_instagram import instagram_reel_bot
from src.pexels_reel_bot_threads import threads_reel_bot


# =============================================================================
# 1. ENJIN PEMBERSIHAN TEKS (STRICT ZERO-EMOJI & MOJIBAKE GUARDRAILS)
# =============================================================================

def remove_emojis_and_glitches(text: str) -> str:
    """Membersihkan token LLM, mojibake dan 100% emoji Unicode."""
    if not text:
        return ""

    text = re.sub(r'<pad>|<unk>|<s>|</s>|\[PAD\]|\[UNK\]|<\|.*?\|>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'[ðâ][\x80-\xbf]{1,4}', '', text)
    text = re.sub(r'[\x80-\x9f]', '', text)

    for sym in ["❖", "◆", "◇", "►", "▪", "▲", "★", "➡", "➢", "*"]:
        text = text.replace(sym, "•")

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

    text = re.sub(r'(?i)^\s*(?:yo|hai|salam|hello)?[^\n]*?(?:cadangan|kapsyen|caption)[^\n]*?\n+', '', text)
    text = re.sub(r'(?i)\*\*caption\s*(?:reels?|instagram|threads)?\s*:\*\*', '', text)
    text = re.sub(r'(?i)\n+\s*\*{0,2}tips\s*tambahan[^\n]*\*{0,2}[\s\S]*$', '', text)
    text = re.sub(r'\*\*\*', '', text)

    text = re.sub(r'[^\x00-\x7F\u00C0-\u024F\s.,!?:;\'"()/\-#@+•]', '', text)

    lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in text.splitlines()]
    return "\n".join([line for line in lines if line]).strip()


def extract_search_keyword(title: str, max_words: int = 3) -> str:
    """Mengekstrak 2-3 kata kunci penting daripada tajuk produk untuk Telegram Search."""
    if not title:
        return "Gajet"
    clean = re.sub(r'[\[\]\(\)\#\|\/\-\+\:\,\.]', ' ', str(title))
    words = [w.strip() for w in clean.split() if len(w.strip()) > 1 and not w.strip().isdigit()]
    stop_words = {'original', 'ready', 'stock', 'new', 'pro', 'set', 'hot', 'offer', 'murah', 'padu', 'high', 'quality', 'fast', 'delivery', 'warranty'}
    filtered = [w for w in words if w.lower() not in stop_words]
    return " ".join(filtered[:max_words]) if filtered else " ".join(words[:max_words])


def clean_image_url(url: str) -> str:
    """Memperbetulkan sambungan fail gambar yang bertindih."""
    if not url:
        return ""
    cleaned = re.sub(r"(\.(jpg|jpeg|png|webp))\.\2$", r"\1", url, flags=re.I)
    cleaned = re.sub(r"(\.(jpg|jpeg|png|webp))\1$", r"\1", cleaned, flags=re.I)
    return cleaned


def is_image_valid(url: str) -> bool:
    """Memastikan URL gambar boleh diakses dan sah (HTTP 200)."""
    if not url:
        return False
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        res = requests.get(url, headers=headers, timeout=10)
        return res.status_code == 200 and len(res.content) > 500
    except Exception:
        return False


# =============================================================================
# 2. ENJIN MOVIEPY (IMAGE TO MP4 SAIS ASAL + LOCAL META MUSIC)
# =============================================================================

def get_random_local_music(music_dir: Path, target_duration: int = 8) -> Tuple[Optional[Any], str]:
    """Mengambil lagu latar rawak daripada folder assets/music/."""
    if not music_dir.exists():
        music_dir.mkdir(parents=True, exist_ok=True)
        return None, "Original Audio"

    audio_files = [f for f in os.listdir(music_dir) if f.lower().endswith((".mp3", ".wav", ".m4a", ".mp4"))]
    if not audio_files:
        return None, "Original Audio"

    selected_file = random.choice(audio_files)
    clean_title = re.sub(r'[_\-]+', ' ', os.path.splitext(selected_file)[0]).strip().title()
    song_path = str(music_dir / selected_file)

    try:
        audio = AudioFileClip(song_path)
        start = random.randint(0, max(0, int(audio.duration) - target_duration - 2)) if audio.duration > target_duration + 5 else 0
        end = start + target_duration

        if hasattr(audio, "subclipped"):
            cut_audio = audio.subclipped(start, end)
        else:
            cut_audio = audio.subclip(start, end)

        return cut_audio, clean_title
    except Exception as e:
        print(f"  ⚠️ [MUSIC WARN] Gagal memproses audio '{selected_file}': {e}")
        return None, "Original Audio"


def build_product_reel_video(image_url: str, music_dir: Path, duration: int = 8) -> Tuple[Optional[str], str]:
    """Memuat turun gambar produk dan menukarnya kepada video MP4 berserta audio menggunakan saiz asal gambar."""
    print(f"\n🎬 [MOVIEPY] Membina video Reel mengikut saiz asal gambar produk...")
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(image_url, headers=headers, timeout=20)
        if res.status_code != 200 or len(res.content) < 500:
            print("❌ Gagal memuat turun gambar produk untuk rendering.")
            return None, "Original Audio"

        with tempfile.NamedTemporaryFile(suffix=".jpg", prefix="prod_img_", delete=False) as temp_img:
            temp_img.write(res.content)
            temp_img_path = temp_img.name

        output_temp = tempfile.NamedTemporaryFile(suffix=".mp4", prefix="affiliate_reel_", delete=False)
        output_video_path = output_temp.name
        output_temp.close()

        clip = ImageClip(temp_img_path)
        if hasattr(clip, "with_duration"):
            clip = clip.with_duration(duration)
        else:
            clip = clip.set_duration(duration)

        # Kekalkan saiz dan nisbah asal (pastikan dimensi genap untuk keserasian H.264 / ffmpeg)
        w, h = clip.size
        if w % 2 != 0 or h % 2 != 0:
            even_w = w - (w % 2)
            even_h = h - (h % 2)
            if hasattr(clip, "resized"):
                clip = clip.resized((even_w, even_h))
            elif hasattr(clip, "resize"):
                clip = clip.resize((even_w, even_h))

        # Pasangkan muzik latar
        bg_audio, music_title = get_random_local_music(music_dir, target_duration=duration)
        if bg_audio:
            if hasattr(clip, "with_audio"):
                clip = clip.with_audio(bg_audio)
            else:
                clip = clip.set_audio(bg_audio)

        print(f"  🎵 [AUDIO] Lagu latar dipilih: '{music_title}'")
        print("  ⚙️ Menjana fail video MP4 (H.264 / AAC)...")
        clip.write_videofile(
            output_video_path,
            fps=24,
            codec="libx264",
            audio_codec="aac",
            preset="fast",
            threads=4,
            logger=None,
        )

        clip.close()
        if bg_audio:
            bg_audio.close()

        if os.path.exists(temp_img_path):
            os.remove(temp_img_path)

        return output_video_path, music_title

    except Exception as e:
        print(f"❌ [VIDEO RENDER ERROR] {e}")
        return None, "Original Audio"


# =============================================================================
# 3. ENJIN AI PERSONA KHAS MENGIKUT PLATFORM (ZERO EMOJI & TAILORED LENGTH)
# =============================================================================

def generate_fb_reel_caption(base_url: str, model: str, api_key: str, title: str, category: str, price: str, music_title: str) -> str:
    """
    Menjana kapsyen penceritaan masalah & solusi perkakasan untuk Facebook Reels.
    Panjang sasaran: 350 - 500 aksara | Sifar Emoji | CTA di ruangan komen.
    """
    fallback = (
        f"Korang yang tengah pening mencari kelengkapan kemas untuk upgrade setup meja, tengok {title[:50]} ni.\n\n"
        f"Kualiti binaan memang kukuh dan praktikal untuk kegunaan harian tanpa serabut. "
        f"Pilihan tepat untuk pastikan ruang kerja atau gaming korang kekal teratur dan selesa.\n\n"
        f"Pautan pembelian rasmi kami sediakan di ruangan komen di bawah.\n\n"
        f"#RacunGajet #BarangMurahPadu #SembangPCTech #TechMalaysia #PCSetup #LazadaMY"
    )

    if not base_url or not model or not api_key:
        return fallback

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json; charset=utf-8"}
    music_info = f" sambil diiringi trek '{music_title}'" if music_title and music_title != "Original Audio" else ""

    prompt = f"""
Anda adalah "Brader Din", Tech Enthusiast Malaysia di komuniti Facebook Sembang PC & Tech.
Video Reel produk ini memaparkan:
- Produk: {title}
- Kategori: {category}
- Tawaran: RM {price if price else 'Promosi Berbaloi'}

PANDUAN PENULISAN FACEBOOK REELS (SANGAT KETAT):
1. BAHASA: 100% Bahasa Melayu santai komuniti tech Malaysia.
2. LARANGAN MUTLAK EMOJI: DILARANG meletakkan sebarang emoji atau simbol pelik.
3. FASA 1: Hook santai berkaitan masalah ruang kerja atau gajet harian{music_info}.
4. FASA 2: Ulasan padat tentang kelebihan fizikal dan kualiti gajet ini.
5. FASA 3 (Call-To-Action): Ajak penonton menyemak pautan pembelian yang diletakkan di ruangan komen Reel.
6. FASA 4: Akhiri dengan 4-5 hashtag rasmi (#RacunGajet #BarangMurahPadu #SembangPCTech #TechMalaysia #PCSetup).
7. PANJANG TEKS: Wajib antara 350 HINGGA 500 AKSARA.
"""

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Tulis kapsyen Facebook Reel santai tanpa sebarang emoji."},
            {"role": "user", "content": prompt.strip()},
        ],
        "temperature": 0.65,
        "max_tokens": 400,
    }

    try:
        res = requests.post(f"{base_url.rstrip('/')}/chat/completions", headers=headers, json=payload, timeout=25)
        if res.status_code == 200:
            raw = res.json()["choices"][0]["message"]["content"].strip()
            clean = remove_emojis_and_glitches(raw)
            if len(clean) >= 120:
                return clean
    except Exception as e:
        print(f"⚠️ [FB REEL AI WARN] {e}")

    return fallback


def generate_ig_reel_caption(
    base_url: str,
    model: str,
    api_key: str,
    title: str,
    category: str,
    price: str,
    aff_link: str,
) -> str:
    """
    Menjana kapsyen Instagram Reels (350 - 450 aksara) berstruktur penuh,
    mengandungi pautan affiliate terus (boleh klik di Pinterest Sync) & Sifar Emoji.
    """
    search_kw = extract_search_keyword(title)
    clean_aff_link = aff_link.strip() if aff_link else ""

    fallback = (
        f"Korang yang tengah cari kelengkapan baru yang mantap, tengok barang ni!\n\n"
        f"Barang: {title[:50]}\n"
        f"Tawaran: RM {price if price else 'Promosi Berbaloi'}\n\n"
        f"• Kualiti binaan kemas & sangat praktikal\n"
        f"• Nilai terbaik untuk bajet upgrade korang\n\n"
        f"Pautan Rasmi: {clean_aff_link}\n"
        f"Atau taip \"{search_kw}\" di Telegram Bot: lubuk_barang_murah_padu_bot\n\n"
        f"#RacunGajet #BarangMurahPadu #SembangPCTech #TechMalaysia #PCSetup #LazadaMY"
    )

    if not base_url or not model or not api_key:
        return fallback

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json; charset=utf-8"}

    prompt = f"""
Anda adalah "Brader Din", pencipta kandungan Instagram & Pinterest Sembang PC & Tech Malaysia.
Hantaran Instagram Reel ini akan disegerakkan terus ke papan Pinterest.

MAKLUMAT PRODUK:
- Nama Produk: {title}
- Kategori: {category}
- Harga: RM {price if price else 'Promosi Berbaloi'}
- Pautan Affiliate Rasmi: {clean_aff_link}
- Kata Kunci Carian Telegram: {search_kw}

STRUKTUR WAJIB KAPSYEN INSTAGRAM (SANGAT KETAT):
1. LARANGAN MUTLAK EMOJI: Sifar emoji dan sifar simbol mojibake.
2. Fasa 1 (SEO Title): Sebut nama produk dengan jelas di 2 baris terawal.
3. Fasa 2 (Ulasan): 1 ulasan ringkas diikuti tepat 2 kelebihan produk menggunakan simbol bullet point (•).
4. Fasa 3 (Call-To-Action Dwi-Fungsi Pinterest & Telegram):
   - Letakkan pautan belian rasmi secara terus:
     "Pautan Rasmi: {clean_aff_link}"
   - Tambah panduan carian Telegram (JANGAN letak '@' sebelum nama bot):
     "Atau taip \"{search_kw}\" di Telegram Bot: lubuk_barang_murah_padu_bot"
5. Fasa 4 (Hashtags): #RacunGajet #BarangMurahPadu #SembangPCTech #TechMalaysia #PCSetup #LazadaMY
6. PANJANG TEKS: Wajib DI ANTARA 350 HINGGA 450 AKSARA (agar tidak terpotong di Pinterest).
"""

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Tulis kapsyen Instagram Reels mengikut format berstruktur 350-450 aksara tanpa sebarang emoji."},
            {"role": "user", "content": prompt.strip()},
        ],
        "temperature": 0.65,
        "max_tokens": 400,
    }

    try:
        res = requests.post(f"{base_url.rstrip('/')}/chat/completions", headers=headers, json=payload, timeout=25)
        if res.status_code == 200:
            raw = res.json()["choices"][0]["message"]["content"].strip()
            clean = remove_emojis_and_glitches(raw)
            if len(clean) >= 180:
                # Pastikan link tidak tertinggal
                if clean_aff_link and clean_aff_link not in clean:
                    clean = f"{clean}\n\nPautan Rasmi: {clean_aff_link}"
                return clean
    except Exception as e:
        print(f"⚠️ [IG REEL AI WARN] {e}")

    return fallback


def generate_threads_video_caption(base_url: str, model: str, api_key: str, title: str, aff_link: str) -> str:
    """
    Menjana kapsyen mikro-blog ringkas untuk Threads Video Feed.
    Panjang sasaran: 180 - 240 aksara (Teks) + Pautan Belian (Jumlah < 480 aksara) | Sifar Emoji.
    """
    clean_title = title[:50].strip()
    aff_text = f"\n\nPautan rasmi di sini: {aff_link}"
    fallback = f"Korang yang tengah cari {clean_title}, barang ni memang padu dan berbaloi untuk kemaskan ruang kerja.{aff_text}"

    if not base_url or not model or not api_key:
        return fallback

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json; charset=utf-8"}

    prompt = f"""
Tuliskan ulasan ringkas racun tech untuk video Threads Malaysia.
PRODUK: {title}

SYARAT PENULISAN:
1. Bahasa Melayu santai harian Malaysia.
2. LARANGAN MUTLAK EMOJI: Sifar emoji.
3. PANJANG TEKS: Antara 160 HINGGA 230 AKSARA SAHAJA (supaya muat baki pautan).
4. DILARANG letak link dalam teks yang dijana.
5. Letakkan 2 hashtag tech di hujung ayat (#TechMalaysia #DeskSetup).
"""

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Tulis ulasan mikro-blog Threads tanpa emoji."},
            {"role": "user", "content": prompt.strip()},
        ],
        "temperature": 0.65,
        "max_tokens": 180,
    }

    try:
        res = requests.post(f"{base_url.rstrip('/')}/chat/completions", headers=headers, json=payload, timeout=20)
        if res.status_code == 200:
            raw = res.json()["choices"][0]["message"]["content"].strip()
            clean = remove_emojis_and_glitches(raw)
            full_threads_text = f"{clean}{aff_text}".strip()
            if len(full_threads_text) <= 490:
                return full_threads_text
    except Exception as e:
        print(f"⚠️ [THREADS AI WARN] {e}")

    return fallback


# =============================================================================
# 4. TELEGRAM AUDIT DISPATCHER (LENGKAP SEMUA PLATFORM & KAPSYEN)
# =============================================================================

def send_full_telegram_audit(
    token: str,
    chat_id: str,
    product_title: str,
    product_id: str,
    aff_link: str,
    image_url: str,
    fb_res: dict,
    ig_res: dict,
    th_res: dict,
    fb_caption: str,
    ig_caption: str,
    th_caption: str,
):
    """Menghantar laporan audit terperinci ke Telegram merangkumi kesemua kapsyen platform."""
    if not token or not chat_id:
        return

    fb_ok = fb_res.get("ok", False)
    ig_ok = ig_res.get("ok", False)
    th_ok = th_res.get("ok", False)

    fb_status = f"✅ Berjaya (ID: {fb_res.get('id', '')})" if fb_ok else f"⚠️ Gagal/Langkau ({fb_res.get('error', '')})"
    ig_status = f"✅ <a href='{ig_res.get('permalink', '')}'>Buka IG Reel</a>" if ig_ok else f"❌ Gagal ({ig_res.get('error', '')})"
    th_status = f"✅ <a href='{th_res.get('permalink', '')}'>Buka Threads Video</a>" if th_ok else f"❌ Gagal ({th_res.get('error', '')})"

    # Mesej Ringkasan Status
    summary_message = (
        f"🎬 <b>[AUDIT PEMPOSAN AFFILIATE REELS 3X DAILY]</b> 🇲🇾\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 <b>Produk:</b> {product_title}\n"
        f"🆔 <b>ID Produk:</b> <code>{product_id}</code>\n"
        f"🛒 <b>Pautan Affiliate:</b> <a href='{aff_link}'>Buka Lazada/Shopee</a>\n\n"
        f"📊 <b>STATUS PLATFORM:</b>\n"
        f"• <b>Facebook Reels:</b> {fb_status}\n"
        f"• <b>Instagram Reels:</b> {ig_status}\n"
        f"• <b>Threads Video:</b> {th_status}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏰ <i>Waktu Larian: {time.strftime('%Y-%m-%d %H:%M:%S')} MYT</i>"
    )

    # Mesej Kapsyen FB, IG & Threads
    captions_message = (
        f"📝 <b>[AUDIT KAPSYEN FACEBOOK REELS]:</b>\n"
        f"<code>{fb_caption}</code>\n\n"
        f"📸 <b>[AUDIT KAPSYEN INSTAGRAM REELS]:</b>\n"
        f"<code>{ig_caption}</code>\n\n"
        f"🧵 <b>[AUDIT KAPSYEN THREADS VIDEO]:</b>\n"
        f"<code>{th_caption}</code>"
    )

    try:
        # Hantar gambar bersama ringkasan status
        if image_url:
            url_photo = f"https://api.telegram.org/bot{token}/sendPhoto"
            requests.post(url_photo, data={"chat_id": chat_id, "photo": image_url, "caption": summary_message[:1024], "parse_mode": "HTML"}, timeout=20)
        else:
            url_msg = f"https://api.telegram.org/bot{token}/sendMessage"
            requests.post(url_msg, data={"chat_id": chat_id, "text": summary_message, "parse_mode": "HTML"}, timeout=20)

        # Hantar teks audit kapsyen lengkap
        url_msg = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url_msg, data={"chat_id": chat_id, "text": captions_message, "parse_mode": "HTML", "disable_web_page_preview": True}, timeout=20)
    except Exception as e:
        print(f"⚠️ [TELEGRAM AUDIT ERROR] {e}")


# =============================================================================
# 5. ALIRAN UTAMA (MASTER RUNNER)
# =============================================================================

def run_affiliate_reel_job():
    print("\n" + "=" * 70)
    print("🎬 [START] ENJIN PEMPOSAN AFFILIATE REELS (FB + IG + THREADS)")
    print("=" * 70)

    # 1. Baca Konfigurasi Persekitaran (100% Dynamic Environment Driven)
    base_url = os.getenv("OPENROUTER_BASE_URL", "").strip()
    model = os.getenv("OPENROUTER_MODEL", "").strip()
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()

    redis_url = os.getenv("UPSTASH_REDIS_REST_URL", "").strip()
    redis_token = os.getenv("UPSTASH_REDIS_REST_TOKEN", "").strip()
    vector_url = os.getenv("UPSTASH_VECTOR_REST_URL", "").strip()
    vector_token = os.getenv("UPSTASH_VECTOR_REST_TOKEN", "").strip()

    tg_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    tg_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    fb_page_id = os.getenv("FACEBOOK_PAGE_ID", "").strip() or os.getenv("META_PAGE_ID", "").strip()
    fb_page_token = (
        os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN", "").strip()
        or os.getenv("FB_PAGE_ACCESS_TOKEN", "").strip()
        or os.getenv("META_PAGE_ACCESS_TOKEN", "").strip()
    )

    music_dir = PROJECT_ROOT / "assets" / "music"

    # 2. Ambil Calon Produk dari Supabase
    print("\n📦 [STEP 1] Membaca calon produk affiliate dari Supabase DB...")
    ok, candidate_list, err_msg = fetch_unused_links(limit=50)

    if not ok or not candidate_list:
        print("❌ [ABORT] Tiada produk berstatus status_used=false dijumpai di Supabase.")
        return

    random.shuffle(candidate_list)
    selected_product = None

    # 3. Tapis Duplikasi melalui Redis (15 Hari) & Vector DB (2 Hari)
    print("\n🔍 [STEP 2] Menyemak tapisan deduplikasi (Redis 15-Hari & Vector 2-Hari)...")
    for item in candidate_list:
        p_id = str(item.get("product_id") or item.get("id") or "").strip()
        title = str(item.get("title") or item.get("product_name") or "").strip()
        aff_link = str(item.get("affiliate_link") or item.get("promo_short_link") or "").strip()
        raw_img = str(item.get("image_url") or item.get("picture_url") or "").strip()

        img_url = clean_image_url(raw_img)

        if not p_id or not title or not aff_link or not img_url:
            continue

        if is_product_posted(redis_url, redis_token, p_id, title):
            print(f"  ⏭️ [REDIS SKIP] ID {p_id} ('{title[:30]}...') pernah dipos < 15 hari.")
            continue

        if is_similar_product_posted(vector_url, vector_token, title):
            print(f"  ⏭️ [VECTOR SKIP] Tajuk '{title[:30]}...' mirip dengan produk < 48 jam lepas.")
            continue

        if not is_image_valid(img_url):
            print(f"  ⏭️ [IMAGE BROKEN SKIP] ID {p_id} Gambar tidak sah. Langkau.")
            continue

        selected_product = {
            "product_id": p_id,
            "title": title,
            "affiliate_link": aff_link,
            "image_url": img_url,
            "category": item.get("category", "Gajet & Komputer"),
            "price": str(item.get("price", "")),
        }
        break

    if not selected_product:
        print("⚠️ Tiada produk yang melepasi tapisan keselamatan. Larian ditamatkan.")
        return

    p_id = selected_product["product_id"]
    title = selected_product["title"]
    aff_link = selected_product["affiliate_link"]
    img_url = selected_product["image_url"]
    category = selected_product["category"]
    price = selected_product["price"]

    print(f"\n🎯 [PRODUK TERPILIH] ID: {p_id}")
    print(f"   Tajuk   : {title}")
    print(f"   Kategori: {category}")
    print(f"   Link    : {aff_link}")

    # 4. Bina Video MP4 Mengikut Saiz Asal Gambar bersama Trek Muzik
    rendered_video_path, music_title = build_product_reel_video(
        image_url=img_url,
        music_dir=music_dir,
        duration=8,
    )

    if not rendered_video_path or not os.path.exists(rendered_video_path):
        print("❌ [ABORT] Gagal menjana fail video Reel produk.")
        return

    # 5. AI Persona Jana Kapsyen Berasingan bagi Setiap Platform (Termasuk Pautan Affiliate di IG Reel)
    print("\n✍️ [STEP 4] Menjana kapsyen tersuai bagi setiap platform (Zero-Emoji)...")
    fb_caption = generate_fb_reel_caption(
        base_url=base_url,
        model=model,
        api_key=api_key,
        title=title,
        category=category,
        price=price,
        music_title=music_title,
    )

    ig_caption = generate_ig_reel_caption(
        base_url=base_url,
        model=model,
        api_key=api_key,
        title=title,
        category=category,
        price=price,
        aff_link=aff_link,
    )

    threads_caption = generate_threads_video_caption(
        base_url=base_url,
        model=model,
        api_key=api_key,
        title=title,
        aff_link=aff_link,
    )

    print(f"✅ [KAPSYEN FB REELS]:\n{fb_caption}\n")
    print(f"✅ [KAPSYEN IG REELS]:\n{ig_caption}\n")
    print(f"✅ [KAPSYEN THREADS]:\n{threads_caption}\n")

    fb_res = {"ok": False, "error": "Skipped"}
    ig_res = {"ok": False, "error": "Skipped"}
    th_res = {"ok": False, "error": "Skipped"}

    try:
        # 6. Terbitkan ke Facebook Reels + Komen Affiliate Link
        print("🚀 [STEP 5] Memuat naik ke Facebook Reels...")
        fb_ok, res_fb_data = upload_reel_to_facebook(
            page_id=fb_page_id,
            page_token=fb_page_token,
            video_path=rendered_video_path,
            caption=fb_caption,
        )
        if fb_ok:
            fb_video_id = res_fb_data.get("video_id", "")
            fb_res = {"ok": True, "id": fb_video_id}
            if aff_link and fb_video_id:
                try:
                    time.sleep(3)
                    cmt_url = f"https://graph.facebook.com/v26.0/{fb_video_id}/comments"
                    cmt_payload = {
                        "message": f"Dapatkan tawaran rasmi di sini sekarang: {aff_link}",
                        "access_token": fb_page_token,
                    }
                    requests.post(cmt_url, data=cmt_payload, timeout=15)
                except Exception:
                    pass
        else:
            fb_res = {"ok": False, "error": res_fb_data.get("error", "Failed")}

        # 7. Terbitkan ke Instagram Reels (@braderdin360)
        if instagram_reel_bot.is_configured():
            print("\n📸 [STEP 6] Memuat naik ke Instagram Reels (@braderdin360)...")
            ig_ok, res_ig_data = instagram_reel_bot.upload_reel_to_instagram(
                video_path=rendered_video_path,
                caption=ig_caption,
            )
            if ig_ok:
                ig_res = {"ok": True, "permalink": res_ig_data.get("permalink", "")}
                print(f"  ✅ Berjaya dipos ke Instagram Reels! Pautan: {ig_res['permalink']}")
            else:
                ig_res = {"ok": False, "error": res_ig_data.get("error", "Failed")}

        # 8. Terbitkan ke Threads Video Feed (@braderdin360 via Backblaze B2)
        if threads_reel_bot.is_configured():
            print("\n🧵 [STEP 7] Memuat naik Video ke Threads Feed (@braderdin360 via B2)...")
            th_ok, res_th_data = threads_reel_bot.upload_video_to_threads(
                video_path=rendered_video_path,
                caption=threads_caption,
            )
            if th_ok:
                th_res = {"ok": True, "permalink": res_th_data.get("permalink", "")}
                print(f"  ✅ Berjaya dipos ke Threads Video! Pautan: {th_res['permalink']}")
            else:
                th_res = {"ok": False, "error": res_th_data.get("error", "Failed")}

        # 9. Rekod Status jika Sekurang-kurangnya 1 Platform Berjaya
        if fb_res["ok"] or ig_res["ok"] or th_res["ok"]:
            print("\n💾 [STEP 8] Merekodkan status & ingatan ke pangkalan data...")
            mark_product_posted(redis_url, redis_token, p_id, title)
            mark_vector_posted(vector_url, vector_token, p_id, title)
            mark_link_as_used(p_id)
            print("  ✅ Supabase, Redis & Vector DB dikemas kini dengan jayanya.")

        # 10. Hantar Laporan Audit Lengkap ke Telegram
        print("\n🔍 [STEP 9] Menghantar laporan audit terperinci ke Telegram...")
        send_full_telegram_audit(
            token=tg_token,
            chat_id=tg_chat_id,
            product_title=title,
            product_id=p_id,
            aff_link=aff_link,
            image_url=img_url,
            fb_res=fb_res,
            ig_res=ig_res,
            th_res=th_res,
            fb_caption=fb_caption,
            ig_caption=ig_caption,
            th_caption=threads_caption,
        )

        print("\n🎉 [SUCCESS] Kitaran Affiliate Reels selesai sepenuhnya!\n")

    finally:
        if os.path.exists(rendered_video_path):
            try:
                os.remove(rendered_video_path)
            except Exception:
                pass


if __name__ == "__main__":
    run_affiliate_reel_job()