#!/usr/bin/env python3
"""
Reddit Tech Storyteller Engine - Experiment 1: Dual-Engine Fetcher (JSON + RSS Fallback)
Lokasi Fail: experiments/exp_reddit_fetch.py

Ciri-ciri Utama:
1. Dual-Engine Ingestion: Mencuba JSON API terlebih dahulu; jika berlaku HTTP 403,
   sistem beralih automatik ke RSS/Atom Feed XML tanpa henti.
2. Full Browser Fingerprinting: Header lengkap bagi mengelakkan sekatan bot Reddit.
3. XML/HTML Parser Bersepadu: Mengekstrak teks, imej asal (i.redd.it/imgur), dan pautan.
4. Auto-Filter & Sorting: Menyusun kandungan terbaik mengikut skor dan kesesuaian tema MYT.
"""

import os
import re
import sys
import json
import html
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple

# =============================================================================
# 1. TEMPORAL CONTEXT & WEEKLY SUBREDDIT ROTATION MATRIX
# =============================================================================
MYT_TIMEZONE = timezone(timedelta(hours=8))

SUBREDDIT_THEME_MATRIX = {
    "Monday": {
        "theme_name": "Monday Productivity & Battlestation",
        "morning": ["battlestations", "macsetups", "workstations"],
        "night": ["talesfromtechsupport", "sysadmin", "techsupportmacgyver"]
    },
    "Tuesday": {
        "theme_name": "AI, Frontier Tech & Tech Support Drama",
        "morning": ["LocalLLaMA", "artificial", "singularity", "OpenAI"],
        "night": ["talesfromtechsupport", "techsupportmacgyver", "sysadmin"]
    },
    "Wednesday": {
        "theme_name": "Linux, Open Source & MacGyver Inovasi",
        "morning": ["linux", "selfhosted", "homelab", "linuxmasterrace"],
        "night": ["techsupportmacgyver", "talesfromtechsupport", "sysadmin"]
    },
    "Thursday": {
        "theme_name": "Software Engineering & PC Build Journey",
        "morning": ["programming", "webdev", "ProgrammerHumor", "technology"],
        "night": ["buildapc", "pcmasterrace", "pcgaming"]
    },
    "Friday": {
        "theme_name": "Gadgets, Future Hardware & Mechanical Keyboards",
        "morning": ["gadgets", "technology", "hardware", "virtualreality"],
        "night": ["MechanicalKeyboards", "CustomKeyboards", "olkb"]
    },
    "Saturday": {
        "theme_name": "Weekend Gaming Rig & Tech Horror Stories",
        "morning": ["pcmasterrace", "MouseReview", "Monitors", "buildapcmonitors"],
        "night": ["techsupportgore", "hardwaregore", "vintagecomputing"]
    },
    "Sunday": {
        "theme_name": "Modding Showcase & Epic Fails",
        "morning": ["MechanicalKeyboards", "battlestations", "watercooling"],
        "night": ["vintagecomputing", "techsupportgore", "pcmasterrace"]
    }
}

NAMA_HARI_MALAY = {
    "Monday": "Isnin",
    "Tuesday": "Selasa",
    "Wednesday": "Rabu",
    "Thursday": "Khamis",
    "Friday": "Jumaat",
    "Saturday": "Sabtu",
    "Sunday": "Ahad"
}

NAMA_BULAN_MALAY = {
    1: "Januari", 2: "Februari", 3: "Mac", 4: "April",
    5: "Mei", 6: "Jun", 7: "Julai", 8: "Ogos",
    9: "September", 10: "Oktober", 11: "November", 12: "Disember"
}


def get_current_myt_context() -> Dict[str, Any]:
    """Mengira masa zon waktu Malaysia (MYT / UTC+8) dan membina konteks temporal."""
    now_myt = datetime.now(MYT_TIMEZONE)
    day_english = now_myt.strftime("%A")
    day_malay = NAMA_HARI_MALAY.get(day_english, day_english)
    month_malay = NAMA_BULAN_MALAY.get(now_myt.month, now_myt.strftime("%B"))

    hour = now_myt.hour
    is_morning_slot = 4 <= hour < 16

    slot_key = "morning" if is_morning_slot else "night"
    slot_label = "Pagi (08:15 AM)" if is_morning_slot else "Malam (08:15 PM)"
    slot_mood = (
        "Produktif, segar, membina setup, tech terkini dan berita hangat"
        if is_morning_slot
        else "Santai, lepak kedai kopi, drama kerenah tech support, cerita nostalgia & modding"
    )

    day_config = SUBREDDIT_THEME_MATRIX.get(day_english, SUBREDDIT_THEME_MATRIX["Friday"])
    target_subreddits = day_config.get(slot_key, ["MechanicalKeyboards", "gadgets", "pcmasterrace"])

    return {
        "timestamp_iso": now_myt.isoformat(),
        "time_display": now_myt.strftime("%I:%M %p"),
        "date_display": f"{now_myt.day} {month_malay} {now_myt.year}",
        "day_name_en": day_english,
        "day_name_my": day_malay,
        "slot_key": slot_key,
        "slot_label": slot_label,
        "slot_mood": slot_mood,
        "theme_name": day_config.get("theme_name", "Tech Exploration"),
        "target_subreddits": target_subreddits
    }


# =============================================================================
# 2. PEMBERSIHAN & NORMALISASI TEKS REDDIT
# =============================================================================
def clean_reddit_text(raw_text: str, max_chars: int = 2500) -> str:
    """Membersihkan kod Markdown, pautan URL, tag HTML, dan nota kaki Reddit."""
    if not raw_text:
        return ""

    text = html.unescape(raw_text)

    # Buang tag HTML jika datang dari RSS content
    text = re.sub(r'<[^>]+>', ' ', text)

    if text.strip() in ["[removed]", "[deleted]"]:
        return ""

    # Buang tag spoiler, pautan markdown & URL terus
    text = re.sub(r'>!([\s\S]*?)!<', r'\1', text)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'(?i)\n+\s*(?:edit|update|tldr|tl;dr|ps)[\s\S]*$', '', text)
    text = re.sub(r'[*_~`#]', '', text)

    lines = [line.strip() for line in text.splitlines()]
    clean_lines = [l for l in lines if l]
    cleaned = "\n\n".join(clean_lines).strip()

    if len(cleaned) > max_chars:
        trimmed = cleaned[:max_chars]
        last_punct = max(trimmed.rfind('.'), trimmed.rfind('!'), trimmed.rfind('?'), trimmed.rfind('\n'))
        if last_punct > 300:
            cleaned = trimmed[:last_punct + 1].strip()
        else:
            cleaned = trimmed.rsplit(' ', 1)[0].strip() + "..."

    return cleaned


# =============================================================================
# 3. ENJIN 1: PENGAMBILAN DATA JSON (DENGAN EMULASI PENYEMAK IMBAS LENGKAP)
# =============================================================================
def fetch_via_json(subreddit: str, listing: str = "hot", limit: int = 20) -> Tuple[bool, List[Dict[str, Any]], str]:
    clean_sub = subreddit.replace("r/", "").strip()
    endpoint = f"https://www.reddit.com/r/{clean_sub}/{listing}.json?limit={limit}&raw_json=1"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1"
    }

    try:
        res = requests.get(endpoint, headers=headers, timeout=10)
        if res.status_code != 200:
            return False, [], f"JSON HTTP {res.status_code}"

        data = res.json()
        children = data.get("data", {}).get("children", [])
        if not children:
            return False, [], "JSON tiada senarai pos"

        candidates = []
        for item in children:
            p = item.get("data", {})
            title = p.get("title", "").strip()
            selftext = p.get("selftext", "").strip()
            over_18 = p.get("over_18", False)
            is_pinned = p.get("stickied", False)
            score = p.get("score", 0)
            comments = p.get("num_comments", 0)
            author = p.get("author", "")
            post_id = p.get("id", "")
            url = p.get("url", "")

            if over_18 or is_pinned or not title or author in ["[deleted]", "AutoModerator"]:
                continue

            # Pengekstrakan Imej
            image_url = None
            if url and any(url.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp"]):
                image_url = url
            elif "preview" in p and "images" in p["preview"] and len(p["preview"]["images"]) > 0:
                image_url = p["preview"]["images"][0].get("source", {}).get("url")

            clean_body = clean_reddit_text(selftext)

            candidates.append({
                "post_id": post_id,
                "subreddit": clean_sub,
                "title": title,
                "cleaned_text": clean_body,
                "image_url": image_url,
                "has_direct_image": image_url is not None,
                "score": score,
                "num_comments": comments,
                "author": author,
                "permalink": f"https://www.reddit.com{p.get('permalink', '')}",
                "source_engine": "JSON_API"
            })

        return True, candidates, f"JSON: Berjaya menarik {len(candidates)} pos"
    except Exception as e:
        return False, [], f"JSON Error: {str(e)}"


# =============================================================================
# 4. ENJIN 2: PENGAMBILAN DATA RSS / ATOM XML (KEBAL SEKATAN 403)
# =============================================================================
def fetch_via_rss(subreddit: str, listing: str = "hot") -> Tuple[bool, List[Dict[str, Any]], str]:
    clean_sub = subreddit.replace("r/", "").strip()
    endpoint = f"https://www.reddit.com/r/{clean_sub}/{listing}.rss"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
        "Accept": "application/atom+xml,application/xml,text/xml;q=0.9,*/*;q=0.8"
    }

    try:
        res = requests.get(endpoint, headers=headers, timeout=12)
        if res.status_code != 200:
            return False, [], f"RSS HTTP {res.status_code}"

        root = ET.fromstring(res.content)
        # Namespace Atom XML Reddit
        ns = {'atom': 'http://www.w3.org/2005/Atom'}

        entries = root.findall('atom:entry', ns)
        if not entries:
            return False, [], "RSS tiada entri ditemui"

        candidates = []
        for index, entry in enumerate(entries):
            title_elem = entry.find('atom:title', ns)
            link_elem = entry.find('atom:link', ns)
            content_elem = entry.find('atom:content', ns)
            author_elem = entry.find('atom:author/atom:name', ns)
            id_elem = entry.find('atom:id', ns)

            title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""
            permalink = link_elem.attrib.get('href', '') if link_elem is not None else ""
            raw_html = content_elem.text if content_elem is not None and content_elem.text else ""
            author = author_elem.text.replace("/u/", "") if author_elem is not None and author_elem.text else "Anonymous"
            post_id = id_elem.text.split("_")[-1] if id_elem is not None and id_elem.text else f"rss_{index}"

            if not title or author in ["[deleted]", "AutoModerator"]:
                continue

            # 1. Ekstrak Pautan Gambar Langsung daripada HTML Content
            image_url = None
            img_match = re.search(r'href="([^"]+\.(?:jpg|jpeg|png|webp))"', raw_html, re.I)
            if not img_match:
                img_match = re.search(r'src="([^"]+\.(?:jpg|jpeg|png|webp))"', raw_html, re.I)
            if img_match:
                image_url = html.unescape(img_match.group(1))

            # 2. Ekstrak & Bersihkan Teks Pos
            clean_body = clean_reddit_text(raw_html)

            # Anggaran skor berdasarkan ranking kedudukan RSS
            estimated_score = max(500 - (index * 20), 50)

            candidates.append({
                "post_id": post_id,
                "subreddit": clean_sub,
                "title": title,
                "cleaned_text": clean_body,
                "image_url": image_url,
                "has_direct_image": image_url is not None,
                "score": estimated_score,
                "num_comments": 25,
                "author": author,
                "permalink": permalink,
                "source_engine": "RSS_XML_FEED"
            })

        return True, candidates, f"RSS Feed: Berjaya mengekstrak {len(candidates)} pos"
    except Exception as e:
        return False, [], f"RSS Error: {str(e)}"


# =============================================================================
# 5. INTEGRASI GABUNGAN & PEMILIHAN CALON UTAMA
# =============================================================================
def fetch_subreddit_hybrid(subreddit: str) -> Tuple[bool, List[Dict[str, Any]], str]:
    """Mencuba JSON terlebih dahulu; jika disekat (403), beralih ke RSS XML."""
    print(f"  ↳ Mencuba Enjin JSON API...")
    ok_json, data_json, msg_json = fetch_via_json(subreddit, listing="hot")
    if ok_json and data_json:
        return True, data_json, msg_json

    print(f"  ⚠️ {msg_json} -> Mengaktifkan Enjin Sandaran (RSS/Atom Feed)...")
    ok_rss, data_rss, msg_rss = fetch_via_rss(subreddit, listing="hot")
    if ok_rss and data_rss:
        return True, data_rss, msg_rss

    return False, [], f"Kedua-dua enjin gagal ({msg_json} | {msg_rss})"


def select_best_reddit_story() -> Tuple[bool, Optional[Dict[str, Any]], Dict[str, Any], str]:
    context = get_current_myt_context()
    target_subs = context["target_subreddits"]

    print("\n" + "=" * 75)
    print(f"🕒 [TEMPORAL MYT] {context['day_name_my']} ({context['date_display']}) | {context['time_display']}")
    print(f"📌 [SLOT & MOOD] {context['slot_label']} -> {context['theme_name']}")
    print(f"🎯 [TARGET SUBS] {', '.join([f'r/{s}' for s in target_subs])}")
    print("=" * 75)

    for sub in target_subs:
        print(f"\n🔍 [IMBAS] r/{sub} ...")
        ok, candidates, msg = fetch_subreddit_hybrid(sub)

        if ok and candidates:
            # Susun calon: Beri keutamaan kepada pos yang mempunyai imej atau teks panjang
            candidates.sort(key=lambda x: (x["has_direct_image"], len(x["cleaned_text"])), reverse=True)
            best_post = candidates[0]
            print(f"  ✅ Calon Terbaik Ditemui melalui [{best_post['source_engine']}] di r/{sub}!")
            return True, best_post, context, f"Berjaya dari r/{sub}"

    return False, None, context, "Semua subreddit dalam senarai gagal diambil."


# =============================================================================
# 6. RUNNER
# =============================================================================
if __name__ == "__main__":
    print("\n🚀 [EXPERIMENT 1] MEMULAKAN UJIAN DUAL-ENGINE REDDIT FETCHER...")
    
    success, selected_story, myt_ctx, status_message = select_best_reddit_story()

    if success and selected_story:
        print("\n" + "🔥" * 38)
        print("🏆 HASIL KEPUTUSAN POS REDDIT TERPILIH:")
        print("🔥" * 38)
        print(f"📌 Subreddit      : r/{selected_story['subreddit']}")
        print(f"🆔 Post ID        : {selected_story['post_id']}")
        print(f"⚙️ Enjin Sumber   : {selected_story['source_engine']}")
        print(f"👤 Pengarang      : u/{selected_story['author']}")
        print(f"👍 Anggaran Skor  : ~{selected_story['score']} upvotes")
        print(f"🔗 Pautan Reddit  : {selected_story['permalink']}")
        print(f"🖼️ Imej Langsung  : {selected_story['image_url'] if selected_story['image_url'] else '[TIADA - Sedia untuk Unsplash Fallback]'}")
        
        print(f"\n📖 TAJUK ASAL:")
        print(f"   \"{selected_story['title']}\"")
        
        print(f"\n📝 INTIPATI KANDUNGAN ({len(selected_story['cleaned_text'])} aksara):")
        print("-" * 75)
        if selected_story['cleaned_text']:
            preview = selected_story['cleaned_text'][:450] + ("..." if len(selected_story['cleaned_text']) > 450 else "")
            print(preview)
        else:
            print("[Kandungan berasaskan Imej & Tajuk Utama Showcase]")
        print("-" * 75)
        print("\n✨ Ujian 1 Selesai dengan Jayanya! Bersedia untuk Ujian 2.\n")
    else:
        print(f"\n❌ [RALAT UJIAN 1] {status_message}\n")