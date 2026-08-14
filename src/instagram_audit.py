#!/usr/bin/env python3
"""
Instagram Audit & Telegram Real-Time Notification Helper
Sembang PC & Tech Ecosystem
"""

import requests
import html
from typing import Optional


def send_instagram_audit_to_telegram(
    token: str,
    chat_id: str,
    caption: str,
    image_url: str,
    permalink: str,
    post_type: str = "Affiliate Product",
) -> bool:
    """
    Menghantar salinan hantaran Instagram ke Telegram khas untuk audit AI Persona & kualiti.
    """
    if not token or not chat_id:
        return False

    # Format header audit kemas berserta pautan Instagram
    clean_caption = html.escape(caption)
    audit_header = (
        f"📸 <b>[AUDIT HANTARAN INSTAGRAM]</b> 🇲🇾\n"
        f"🏷️ <b>Kategori:</b> {post_type}\n"
        f"🔗 <b>Pautan IG:</b> <a href='{permalink}'>{permalink}</a>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📝 <b>Kapsyen AI Persona IG:</b>\n"
    )

    full_message = f"{audit_header}\n{clean_caption}"

    try:
        # Telegram had kapsyen gambar ialah 1024 aksara
        if len(full_message) <= 1020 and image_url:
            url = f"https://api.telegram.org/bot{token}/sendPhoto"
            payload = {
                "chat_id": chat_id,
                "photo": image_url,
                "caption": full_message,
                "parse_mode": "HTML",
            }
            res = requests.post(url, data=payload, timeout=20)
            return res.status_code == 200
        else:
            # Jika teks panjang, hantar gambar dahulu kemudian hantar teks audit penuh
            if image_url:
                summary_caption = (
                    f"📸 <b>[AUDIT HANTARAN INSTAGRAM]</b>\n"
                    f"🏷️ <b>Kategori:</b> {post_type}\n"
                    f"🔗 <b>Pautan IG:</b> <a href='{permalink}'>{permalink}</a>"
                )
                requests.post(
                    f"https://api.telegram.org/bot{token}/sendPhoto",
                    data={
                        "chat_id": chat_id,
                        "photo": image_url,
                        "caption": summary_caption,
                        "parse_mode": "HTML",
                    },
                    timeout=15,
                )

            # Hantar teks kapsyen penuh
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": full_message,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            }
            res = requests.post(url, data=payload, timeout=20)
            return res.status_code == 200

    except Exception as e:
        print(f"⚠️ [Instagram Audit Telegram] Ralat menghantar audit: {e}")
        return False