#!/usr/bin/env python3
"""
Reddit Tech Storyteller Engine: Telegram Audit & Gatekeeper Module
Lokasi Fail: src/reddit_telegram_audit.py

Fungsi Utama:
1. Membaca konfigurasi Telegram Bot (TELEGRAM_BOT_TOKEN & TELEGRAM_CHAT_ID).
2. Menghantar Kad Ringkasan Visual (Foto produk/setup + Konteks MYT + Info Pos Reddit + Status 4 Platform Sosial).
3. Menghantar Mesej Audit Teks (Salinan penuh teks janaan AI bagi Facebook, Threads, Instagram, dan Bluesky).
4. Pintu Keselamatan (Safety Gatekeeper): Menyemak sama ada sekurang-kurangnya 1 platform berjaya membuat hantaran sebelum transaksi pangkalan data dibenarkan.
"""

import os
import html
import requests
from io import BytesIO
from typing import Dict, Any, Tuple, Optional


def get_telegram_config() -> Tuple[Optional[str], Optional[str], str]:
    """
    Membaca tetapan sambungan Bot Telegram daripada persekitaran (env).
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    if not token or not chat_id:
        return None, None, "Kunci TELEGRAM_BOT_TOKEN atau TELEGRAM_CHAT_ID tidak lengkap dalam persekitaran."

    return token, chat_id, ""


def send_telegram_message(
    text: str,
    token: Optional[str] = None,
    chat_id: Optional[str] = None,
    parse_mode: str = "HTML"
) -> Tuple[bool, Any]:
    """
    Menghantar mesej teks ke Telegram dengan format HTML.
    Menyokong pemecahan mesej automatik jika melebihi had 4096 aksara Telegram.
    """
    if not token or not chat_id:
        t_token, t_chat, err = get_telegram_config()
        if err:
            return False, err
        token, chat_id = t_token, t_chat

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    max_chunk = 4000
    text_chunks = [text[i:i + max_chunk] for i in range(0, len(text), max_chunk)]
    last_res = None

    for chunk in text_chunks:
        payload = {
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }
        try:
            res = requests.post(url, json=payload, timeout=20)
            last_res = res.json()
            if res.status_code != 200 or not last_res.get("ok"):
                return False, f"HTTP {res.status_code}: {res.text}"
        except Exception as e:
            return False, f"Ralat rangkaian Telegram: {str(e)}"

    return True, last_res


def send_telegram_photo(
    image_url: str,
    caption: str = "",
    token: Optional[str] = None,
    chat_id: Optional[str] = None,
    parse_mode: str = "HTML"
) -> Tuple[bool, Any]:
    """
    Menghantar gambar bersama kapsyen ringkas (< 1024 aksara) ke Telegram.
    Menggunakan kaedah binary buffer dengan fallback kepada image_url terus.
    """
    if not token or not chat_id:
        t_token, t_chat, err = get_telegram_config()
        if err:
            return False, err
        token, chat_id = t_token, t_chat

    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    safe_caption = caption[:1020] if caption else ""

    # 1. Muat turun binary imej
    img_bytes = None
    if image_url and image_url.startswith("http"):
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            res_dl = requests.get(image_url, headers=headers, timeout=15)
            if res_dl.status_code == 200 and len(res_dl.content) > 100:
                img_bytes = BytesIO(res_dl.content)
                img_bytes.name = "reddit_story.jpg"
        except Exception as e:
            print(f"⚠️ [TELEGRAM AUDIT WARN] Gagal muat turun binary imej: {e}")

    # 2. Hantar binary atau URL terus
    try:
        if img_bytes:
            files = {"photo": ("reddit_story.jpg", img_bytes.getvalue(), "image/jpeg")}
            data = {"chat_id": chat_id, "caption": safe_caption, "parse_mode": parse_mode}
            res = requests.post(url, data=data, files=files, timeout=30)
        else:
            payload = {"chat_id": chat_id, "photo": image_url, "caption": safe_caption, "parse_mode": parse_mode}
            res = requests.post(url, json=payload, timeout=20)

        res_json = res.json()
        if res.status_code == 200 and res_json.get("ok"):
            return True, res_json
        else:
            return False, f"HTTP {res.status_code}: {res.text}"
    except Exception as e:
        return False, f"Ralat rangkaian Telegram sendPhoto: {str(e)}"


def has_successful_post(payload: Dict[str, Any]) -> bool:
    """
    Pintu Keselamatan (Safety Gatekeeper):
    Menyemak sama ada sekurang-kurangnya SATU (1) platform berjaya membuat hantaran.
    Memulangkan True jika ada sekurang-kurangnya 1 kejayaan, False jika semua gagal.
    """
    post_results = payload.get("post_results", {})
    for platform, res in post_results.items():
        if isinstance(res, dict) and res.get("status") == "success":
            return True
    return False


def format_platform_status(res: Dict[str, Any]) -> str:
    """Membina status visual ringkas untuk setiap platform media sosial."""
    if not isinstance(res, dict):
        return "⚪ <i>Belum diproses</i>"

    status = res.get("status", "").lower()
    post_id = res.get("post_id") or res.get("thread_post_id") or res.get("media_id") or res.get("uri") or res.get("rkey")
    post_url = res.get("post_url") or res.get("permalink") or ""
    error_msg = res.get("error", "Ralat tidak diketahui")

    if status == "success":
        link_str = f' (<a href="{post_url}">Pautan Pos</a>)' if post_url else ""
        id_str = f" | ID: <code>{html.escape(str(post_id))}</code>" if post_id else ""
        return f"✅ <b>BERJAYA</b>{id_str}{link_str}"
    elif status == "failed":
        return f"❌ <b>GAGAL</b> (<code>{html.escape(str(error_msg)[:60])}</code>)"
    else:
        return "⚪ <i>Dilangkau / Tiada tindakan</i>"


def send_reddit_audit_report(payload: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Menghantar laporan audit lengkap aliran kerja Reddit Storyteller ke Telegram:
    1. Kad Ringkasan Gambar (Foto Visual + Info Pos Reddit + Konteks MYT + Status 4 Platform).
    2. Mesej Audit Teks (Kesemua 4 Kapsyen Janaan AI untuk semakan kualiti).
    """
    token, chat_id, err = get_telegram_config()
    if err:
        return False, err

    post_id = html.escape(str(payload.get("post_id", "N/A")))
    title = html.escape(str(payload.get("title", "Topik Reddit Tech")))
    subreddit = html.escape(str(payload.get("subreddit", "tech")))
    score = payload.get("score", 0)
    permalink = payload.get("permalink", "")
    pic_url = payload.get("picture_url", "")
    img_source = payload.get("image_source", "REDDIT_DIRECT")
    
    temporal_ctx = payload.get("temporal_context", {})
    slot_label = html.escape(str(temporal_ctx.get("slot_label", "Waktu Malaysia")))
    date_display = html.escape(str(temporal_ctx.get("date_display", "")))
    
    post_results = payload.get("post_results", {})
    ai_captions = payload.get("ai_captions", {})

    img_source_label = "Reddit Original" if "REDDIT" in img_source.upper() else "Unsplash Fallback (Anti-Face)"

    # 1. BINA KAD RINGKASAN STATUS
    summary_card = (
        f"🤖 <b>[AUDIT] LAPORAN REDDIT STORYTELLER</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🕒 <b>Sesi:</b> {slot_label} ({date_display})\n"
        f"📌 <b>Subreddit:</b> <code>r/{subreddit}</code>\n"
        f"📖 <b>Tajuk:</b> {title}\n"
        f"🆔 <b>Post ID:</b> <code>{post_id}</code>\n"
        f"👍 <b>Undian:</b> ~{score} Upvotes\n"
        f"🖼️ <b>Sumber Imej:</b> {img_source_label}\n"
        f"🔗 <b>Pautan Sumber:</b> <a href=\"{permalink}\">Buka di Reddit</a>\n\n"
        f"🚀 <b>STATUS MEDIA SOSIAL:</b>\n"
        f"• <b>Facebook:</b> {format_platform_status(post_results.get('facebook', {}))}\n"
        f"• <b>Threads:</b> {format_platform_status(post_results.get('threads', {}))}\n"
        f"• <b>Instagram:</b> {format_platform_status(post_results.get('instagram', {}))}\n"
        f"• <b>Bluesky:</b> {format_platform_status(post_results.get('bluesky', {}))}\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )

    # Hantar gambar bersama ringkasan kad
    photo_ok, _ = send_telegram_photo(pic_url, caption=summary_card, token=token, chat_id=chat_id)
    if not photo_ok:
        # Fallback hantar sebagai teks biasa jika gambar gagal
        send_telegram_message(summary_card, token=token, chat_id=chat_id)

    # 2. BINA MESEJ AUDIT TEKS JANAAN AI
    fb_cap = html.escape(ai_captions.get("facebook", "Tiada teks FB"))
    th_cap = html.escape(ai_captions.get("threads", "Tiada teks Threads"))
    ig_cap = html.escape(ai_captions.get("instagram", "Tiada teks Instagram"))
    bs_cap = html.escape(ai_captions.get("bluesky", "Tiada teks Bluesky"))

    captions_audit_msg = (
        f"📝 <b>AUDIT JANAAN AYAT AI (ID: <code>{post_id}</code> | r/{subreddit})</b>\n\n"
        f"🔵 <b>Facebook Page Feed:</b>\n<blockquote>{fb_cap}</blockquote>\n\n"
        f"🧵 <b>Meta Threads Feed:</b>\n<blockquote>{th_cap}</blockquote>\n\n"
        f"📸 <b>Instagram Feed:</b>\n<blockquote>{ig_cap}</blockquote>\n\n"
        f"🦋 <b>Bluesky Social Feed:</b>\n<blockquote>{bs_cap}</blockquote>"
    )

    send_telegram_message(captions_audit_msg, token=token, chat_id=chat_id)

    # Semak status keseluruhan pintu keselamatan
    is_success = has_successful_post(payload)
    if is_success:
        print("📢 [TELEGRAM AUDIT SUCCESS] Laporan berjaya dihantar ke saluran Telegram.")
        return True, "Laporan audit berjaya dihantar."
    else:
        print("⚠️ [TELEGRAM AUDIT WARN] Semua platform gagal pos. Sila semak pautan & token.")
        return False, "Semua platform gagal membuat hantaran."