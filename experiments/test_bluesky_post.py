#!/usr/bin/env python3
"""
Bluesky AT-Protocol Dedicated Multi-Media & Affiliate Tester
Sembang PC & Tech Ecosystem (100% Dynamic Keys & Native XRPC REST)
Features:
- AT Protocol Session Creation (JWT Auth)
- Byte-accurate Rich Text Facets (Clickable URLs & Hashtags)
- Test 1: Affiliate External Link Card Embed (Shopee / Lazada Card)
- Test 2: Image Post with Blob Upload
- Test 3: Video Reel Post to Feed & Video Tab
"""

import os
import sys
import json
import time
import requests
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

# Setup Project Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load .env.local
env_local = PROJECT_ROOT / ".env.local"
if env_local.exists():
    load_dotenv(dotenv_path=env_local)
else:
    load_dotenv()

BLUESKY_HANDLE = os.getenv("BLUESKY_HANDLE", "").strip()
BLUESKY_APP_PASSWORD = os.getenv("BLUESKY_APP_PASSWORD", "").strip()
BSKY_BASE_URL = "https://bsky.social/xrpc"


class BlueskyClient:
    """Klien AT-Protocol REST untuk Bluesky."""

    def __init__(self, handle: str, app_password: str):
        self.handle = handle
        self.app_password = app_password
        self.access_jwt = None
        self.did = None

    def authenticate(self) -> bool:
        """Mencipta sesi dan mendapatkan accessJwt serta DID."""
        if not self.handle or not self.app_password:
            print("❌ [BLUESKY ERROR] BLUESKY_HANDLE atau BLUESKY_APP_PASSWORD tidak diisi dalam .env.local.")
            return False

        url = f"{BSKY_BASE_URL}/com.atproto.server.createSession"
        payload = {
            "identifier": self.handle,
            "password": self.app_password
        }

        try:
            res = requests.post(url, json=payload, timeout=15)
            if res.status_code == 200:
                data = res.json()
                self.access_jwt = data.get("accessJwt")
                self.did = data.get("did")
                print(f"✅ [AUTH SUCCESS] Log masuk berjaya! (DID: {self.did})")
                return True
            else:
                print(f"❌ [AUTH ERROR] HTTP {res.status_code}: {res.text}")
                return False
        except Exception as e:
            print(f"❌ [AUTH EXCEPTION] {e}")
            return False

    def upload_blob(self, file_bytes: bytes, mime_type: str) -> dict:
        """Memuat naik fail binari (gambar/video) ke Bluesky PDS."""
        url = f"{BSKY_BASE_URL}/com.atproto.repo.uploadBlob"
        headers = {
            "Authorization": f"Bearer {self.access_jwt}",
            "Content-Type": mime_type
        }
        res = requests.post(url, headers=headers, data=file_bytes, timeout=60)
        if res.status_code == 200:
            return res.json().get("blob")
        else:
            print(f"⚠️ [BLOB ERROR] Gagal muat naik blob: {res.text}")
            return None

    def _generate_facets(self, text: str):
        """Menjana facet bait untuk pautan web dan hashtag supaya boleh diklik."""
        facets = []
        utf8_bytes = text.encode("utf-8")

        import re
        # 1. Pautan URL
        url_regex = re.compile(r'https?://[^\s]+')
        for match in url_regex.finditer(text):
            url_str = match.group(0)
            start_byte = len(text[:match.start()].encode("utf-8"))
            end_byte = len(text[:match.end()].encode("utf-8"))
            facets.append({
                "index": {"byteStart": start_byte, "byteEnd": end_byte},
                "features": [{"$type": "app.bsky.richtext.facet#link", "uri": url_str}]
            })

        # 2. Hashtags
        tag_regex = re.compile(r'#([a-zA-Z0-9_]+)')
        for match in tag_regex.finditer(text):
            tag_name = match.group(1)
            start_byte = len(text[:match.start()].encode("utf-8"))
            end_byte = len(text[:match.end()].encode("utf-8"))
            facets.append({
                "index": {"byteStart": start_byte, "byteEnd": end_byte},
                "features": [{"$type": "app.bsky.richtext.facet#tag", "tag": tag_name}]
            })

        return facets

    def create_post(self, text: str, embed: dict = None) -> tuple:
        """Menerbitkan hantaran (Post) ke Feed Bluesky."""
        now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        facets = self._generate_facets(text)

        record = {
            "$type": "app.bsky.feed.post",
            "text": text,
            "createdAt": now_iso
        }
        if facets:
            record["facets"] = facets
        if embed:
            record["embed"] = embed

        payload = {
            "repo": self.did,
            "collection": "app.bsky.feed.post",
            "record": record
        }
        headers = {
            "Authorization": f"Bearer {self.access_jwt}",
            "Content-Type": "application/json"
        }

        url = f"{BSKY_BASE_URL}/com.atproto.repo.createRecord"
        res = requests.post(url, headers=headers, json=payload, timeout=20)
        if res.status_code == 200:
            data = res.json()
            rkey = data.get("uri", "").split("/")[-1]
            permalink = f"https://bsky.app/profile/{self.handle}/post/{rkey}"
            return True, permalink
        else:
            return False, res.text


def run_bluesky_diagnostics():
    print("\n" + "=" * 70)
    print("🦋 [START] PENGUJIAN API BLUESKY (AT-PROTOCOL)")
    print("=" * 70)

    client = BlueskyClient(BLUESKY_HANDLE, BLUESKY_APP_PASSWORD)
    if not client.authenticate():
        return

    # -------------------------------------------------------------------------
    # UJIAN 1: Post Affiliate Link Card (Kad Pautan Boleh Klik)
    # -------------------------------------------------------------------------
    print("\n📌 [TEST 1] Menguji Hantaran Kad Produk Affiliate (Clickable Link Card)...")
    
    # Contoh gambar thumbnail untuk kad pautan
    thumb_url = "https://images.pexels.com/photos/1779487/pexels-photo-1779487.jpeg?auto=compress&cs=tinysrgb&w=800"
    thumb_blob = None
    try:
        t_res = requests.get(thumb_url, timeout=15)
        if t_res.status_code == 200:
            thumb_blob = client.upload_blob(t_res.content, "image/jpeg")
    except Exception:
        pass

    affiliate_card_embed = {
        "$type": "app.bsky.embed.external",
        "external": {
            "uri": "https://t.me/lubuk_barang_murah_padu_bot",
            "title": "Lubuk Racun Gajet & PC Setup Malaysia 🖥️🔥",
            "description": "Himpunan tawaran aksesori meja kerja, keyboard dan perkakasan komputer padu terkini.",
            "thumb": thumb_blob
        }
    }

    caption_card = (
        "Salam warga Bluesky! 👋 Hari ni kita uji kad pautan affiliate rasmi Sembang PC & Tech.\n\n"
        "Bagi peminat setup minimalis dan perkakasan PC, boleh jenguk tawaran padu di link bawah ini! 👇✨\n\n"
        "#SembangPCTech #TechMalaysia #PCSetup #MalaysiaTech"
    )

    ok, link_or_err = client.create_post(caption_card, embed=affiliate_card_embed)
    if ok:
        print(f"  🎉 [TEST 1 BERJAYA] Kad Affiliate diterbitkan! Pautan: {link_or_err}")
    else:
        print(f"  ❌ [TEST 1 GAGAL] {link_or_err}")

    # -------------------------------------------------------------------------
    # UJIAN 2: Post Gambar Bergambar (Image Post)
    # -------------------------------------------------------------------------
    print("\n📸 [TEST 2] Menguji Hantaran Gambar...")
    img_url = "https://images.pexels.com/photos/7915225/pexels-photo-7915225.jpeg?auto=compress&cs=tinysrgb&w=1200"
    try:
        img_res = requests.get(img_url, timeout=15)
        if img_res.status_code == 200:
            img_blob = client.upload_blob(img_res.content, "image/jpeg")
            if img_blob:
                image_embed = {
                    "$type": "app.bsky.embed.images",
                    "images": [{
                        "alt": "Minimalist Dark PC Workspace Setup",
                        "image": img_blob
                    }]
                }
                caption_img = "Ruang kerja tenang untuk fokus waktu malam. Korang suka tema lampu ambient gelap macam ni? ☕🖥️✨ #SembangPCTech #PCSetup"
                ok_img, link_img = client.create_post(caption_img, embed=image_embed)
                if ok_img:
                    print(f"  🎉 [TEST 2 BERJAYA] Gambar diterbitkan! Pautan: {link_img}")
                else:
                    print(f"  ❌ [TEST 2 GAGAL] {link_img}")
    except Exception as e:
        print(f"  ⚠️ [TEST 2 ERROR] {e}")

    print("\n" + "=" * 70)
    print("🏁 Pengujian Bluesky Selesai!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    run_bluesky_diagnostics()