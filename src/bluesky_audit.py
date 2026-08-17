#!/usr/bin/env python3
"""
Dedicated Telegram Audit Engine for Bluesky Posts
Sembang PC & Tech Ecosystem (100% Dynamic OpenRouter & Telegram API)
Features:
- Instant Telegram notification for every published Bluesky post
- Displays Post Type, Formatted Caption, Direct Bluesky Permalink & Reply Links
- Supports Text, Product Embed Cards, Lifestyle Images & Video Reels
"""

import os
import requests
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from pathlib import Path
from dotenv import load_dotenv

# Set Project Root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
env_local = PROJECT_ROOT / ".env.local"
if env_local.exists():
    load_dotenv(dotenv_path=env_local)
else:
    load_dotenv()


def get_myt_timestamp() -> str:
    """Mendapatkan format masa Malaysia (MYT = UTC+8)."""
    myt = datetime.now(timezone.utc) + timedelta(hours=8)
    return myt.strftime("%d/%m/%Y, %I:%M %p")


def send_bluesky_audit_to_telegram(
    token: Optional[str] = None,
    chat_id: Optional[str] = None,
    caption: str = "",
    permalink: str = "",
    post_type: str = "Bluesky Post",
    image_url: str = "",
    reply_permalink: str = "",
    affiliate_link: str = "",
) -> bool:
    """
    Menghantar kad laporan audit pos Bluesky ke Telegram peribadi/admin.
    """
    bot_token = token or os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    target_chat = chat_id or os.getenv("TELEGRAM_CHAT_ID", "").strip()

    if not bot_token or not target_chat:
        print("⚠️ [BLUESKY AUDIT WARN] Kunci TELEGRAM_BOT_TOKEN atau TELEGRAM_CHAT_ID tidak lengkap.")
        return False

    time_str = get_myt_timestamp()
    clean_caption = caption.strip()

    # Bina Mesej Audit Terperinci
    lines = [
        "🦋 <b>[BLUESKY AUDIT REPORT]</b>",
        f"⏰ <b>Waktu (MYT):</b> {time_str}",
        f"📌 <b>Kategori:</b> <code>{post_type}</code>",
        "──────────────────────────────",
        "✍️ <b>Kapsyen Dijana (AI Persona):</b>",
        f"<i>{clean_caption}</i>",
        "──────────────────────────────",
    ]

    if permalink:
        lines.append(f"🔗 <b>Pautan Pos Bluesky:</b>\n<a href='{permalink}'>{permalink}</a>")

    if reply_permalink:
        lines.append(f"💬 <b>Pautan Auto-Reply Komen:</b>\n<a href='{reply_permalink}'>{reply_permalink}</a>")

    if affiliate_link:
        lines.append(f"🛒 <b>Pautan Affiliate Disertakan:</b>\n<code>{affiliate_link}</code>")

    full_message = "\n".join(lines)

    # Hantar Gambar (jika ada thumbnail) atau Mesej Teks Biasa
    url_send_photo = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    url_send_message = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    headers = {"Content-Type": "application/json"}

    # Cuba hantar gambar thumbnail jika URL sah
    if image_url and image_url.startswith("http"):
        photo_payload = {
            "chat_id": target_chat,
            "photo": image_url,
            "caption": full_message,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }
        try:
            res = requests.post(url_send_photo, json=photo_payload, timeout=20)
            if res.status_code == 200:
                print("  🔍 [TELEGRAM AUDIT] Laporan bergambar berjaya dihantar ke Telegram!")
                return True
        except Exception as e:
            print(f"⚠️ [TELEGRAM AUDIT WARN] Gagal hantar photo audit, mencuba teks: {e}")

    # Fallback: Hantar sebagai mesej teks HTML
    text_payload = {
        "chat_id": target_chat,
        "text": full_message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }

    try:
        res = requests.post(url_send_message, json=text_payload, timeout=20)
        if res.status_code == 200:
            print("  🔍 [TELEGRAM AUDIT] Laporan teks berjaya dihantar ke Telegram!")
            return True
        else:
            print(f"❌ [TELEGRAM AUDIT ERROR] HTTP {res.status_code}: {res.text}")
            return False
    except Exception as e:
        print(f"❌ [TELEGRAM AUDIT EXCEPTION] {e}")
        return False