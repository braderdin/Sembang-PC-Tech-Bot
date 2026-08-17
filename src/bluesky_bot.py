#!/usr/bin/env python3
"""
Dedicated Bluesky AT-Protocol Bot Engine
Sembang PC & Tech Ecosystem (100% Dynamic Keys & Native XRPC REST)
Features:
- AT Protocol Session Management & JWT Authentication
- Byte-accurate Rich Text Facet Generator (Clickable URLs & Hashtags)
- Multi-Media Blob Uploader (Images & Video MP4 via REST PDS)
- External Affiliate Link Card Embed (Shopee / Lazada Card)
- Multi-Image Carousel Post (1 to 4 Images)
- Vertical Video Reel Post (Feed & Video Tab)
- Thread Auto-Reply / First-Comment Engine for Affiliate Links
"""

import os
import re
import time
import mimetypes
import requests
from typing import Dict, Any, Tuple, Optional, List, Union
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

# Set Project Root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
env_local = PROJECT_ROOT / ".env.local"
if env_local.exists():
    load_dotenv(dotenv_path=env_local)
else:
    load_dotenv()

BSKY_BASE_URL = "https://bsky.social/xrpc"


class BlueskyBot:
    """Enjin automasi penerbitan kandungan ke Bluesky AT-Protocol."""

    def __init__(self):
        self.handle = os.getenv("BLUESKY_HANDLE", "").strip()
        self.app_password = os.getenv("BLUESKY_APP_PASSWORD", "").strip()
        self.access_jwt: Optional[str] = None
        self.did: Optional[str] = None
        self.session_expiry: float = 0.0

    def is_configured(self) -> bool:
        """Menyemak sama ada kunci Bluesky telah ditetapkan."""
        return bool(self.handle and self.app_password)

    # -------------------------------------------------------------------------
    # 1. PENGESAHAN SESI & LOG MASUK (AT-PROTOCOL AUTH)
    # -------------------------------------------------------------------------
    def authenticate(self, force_refresh: bool = False) -> bool:
        """Membina sesi log masuk dan mendapatkan Access JWT serta DID."""
        if not self.is_configured():
            print("❌ [BLUESKY BOT] Kunci BLUESKY_HANDLE atau BLUESKY_APP_PASSWORD tidak diisi dalam .env.local.")
            return False

        # Guna sesi sedia ada jika masih sah
        if not force_refresh and self.access_jwt and self.did and time.time() < self.session_expiry:
            return True

        url = f"{BSKY_BASE_URL}/com.atproto.server.createSession"
        payload = {
            "identifier": self.handle,
            "password": self.app_password
        }

        try:
            res = requests.post(url, json=payload, timeout=20)
            if res.status_code == 200:
                data = res.json()
                self.access_jwt = data.get("accessJwt")
                self.did = data.get("did")
                # Anggarkan jangka hayat sesi selama 90 minit (Token sah sehingga 2 jam)
                self.session_expiry = time.time() + 5400
                print(f"🦋 [BLUESKY AUTH] Berjaya log masuk sebagai @{self.handle} (DID: {self.did[:15]}...)")
                return True
            else:
                print(f"❌ [BLUESKY AUTH ERROR] HTTP {res.status_code}: {res.text}")
                return False
        except Exception as e:
            print(f"❌ [BLUESKY AUTH EXCEPTION] {e}")
            return False

    # -------------------------------------------------------------------------
    # 2. PEMBINA FACETS (PAUTAN & HASHTAG AKTIF DENGAN KIRAAN BAIT UTF-8)
    # -------------------------------------------------------------------------
    def generate_facets(self, text: str) -> List[Dict[str, Any]]:
        """
        Menjana byte facets mengikut standard AT Protocol.
        Bluesky memerlukan indeks permulaan & pengakhiran dalam ukuran bait UTF-8 (bukan panjang string).
        """
        if not text:
            return []

        facets = []

        # A. Pengesanan Pautan URL Web (http / https)
        url_pattern = re.compile(r'https?://[^\s]+')
        for match in url_pattern.finditer(text):
            url_str = match.group(0)
            start_byte = len(text[:match.start()].encode("utf-8"))
            end_byte = len(text[:match.end()].encode("utf-8"))
            facets.append({
                "index": {"byteStart": start_byte, "byteEnd": end_byte},
                "features": [{"$type": "app.bsky.richtext.facet#link", "uri": url_str}]
            })

        # B. Pengesanan Hashtags (#tag)
        hashtag_pattern = re.compile(r'#([a-zA-Z0-9_]+)')
        for match in hashtag_pattern.finditer(text):
            tag_name = match.group(1)
            start_byte = len(text[:match.start()].encode("utf-8"))
            end_byte = len(text[:match.end()].encode("utf-8"))
            facets.append({
                "index": {"byteStart": start_byte, "byteEnd": end_byte},
                "features": [{"$type": "app.bsky.richtext.facet#tag", "tag": tag_name}]
            })

        return facets

    # -------------------------------------------------------------------------
    # 3. MUAT NAIK MEDIA BLOB (GAMBAR & VIDEO)
    # -------------------------------------------------------------------------
    def upload_blob(self, data_bytes: bytes, mime_type: str) -> Optional[Dict[str, Any]]:
        """Memuat naik fail binari ke storan PDS Bluesky."""
        if not self.authenticate():
            return None

        url = f"{BSKY_BASE_URL}/com.atproto.repo.uploadBlob"
        headers = {
            "Authorization": f"Bearer {self.access_jwt}",
            "Content-Type": mime_type
        }

        try:
            res = requests.post(url, headers=headers, data=data_bytes, timeout=90)
            if res.status_code == 200:
                return res.json().get("blob")
            else:
                print(f"⚠️ [BLUESKY BLOB ERROR] Gagal muat naik blob (HTTP {res.status_code}): {res.text}")
                return None
        except Exception as e:
            print(f"⚠️ [BLUESKY BLOB EXCEPTION] {e}")
            return None

    def upload_image_from_url(self, image_url: str) -> Optional[Dict[str, Any]]:
        """Memuat turun gambar daripada URL dan memuat naik sebagai blob."""
        if not image_url:
            return None
        try:
            res = requests.get(image_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
            if res.status_code == 200:
                content_type = res.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
                if not content_type.startswith("image/"):
                    content_type = "image/jpeg"
                return self.upload_blob(res.content, content_type)
        except Exception as e:
            print(f"⚠️ [BLUESKY IMAGE URL WARN] Ralat muat turun imej '{image_url[:40]}...': {e}")
        return None

    def upload_local_file(self, file_path: Union[str, Path]) -> Optional[Dict[str, Any]]:
        """Membaca fail tempatan (gambar/video) dan memuat naik sebagai blob."""
        path = Path(file_path)
        if not path.exists():
            print(f"❌ [BLUESKY ERROR] Fail tempatan tidak dijumpai: {file_path}")
            return None

        mime_type, _ = mimetypes.guess_type(str(path))
        if not mime_type:
            mime_type = "video/mp4" if path.suffix.lower() == ".mp4" else "image/jpeg"

        try:
            with open(path, "rb") as f:
                data = f.read()
            return self.upload_blob(data, mime_type)
        except Exception as e:
            print(f"⚠️ [BLUESKY FILE READ ERROR] {e}")
            return None

    # -------------------------------------------------------------------------
    # 4. PENERBITAN POST REKOD (CREATE RECORD)
    # -------------------------------------------------------------------------
    def _create_record(
        self,
        text: str,
        embed: Optional[Dict[str, Any]] = None,
        reply_context: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """Menerbitkan rekod pos atau komen balasan ke suapan Bluesky."""
        if not self.authenticate():
            return False, {"error": "Gagal autentikasi sesi Bluesky."}

        now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        facets = self.generate_facets(text)

        record: Dict[str, Any] = {
            "$type": "app.bsky.feed.post",
            "text": text,
            "createdAt": now_iso
        }

        if facets:
            record["facets"] = facets
        if embed:
            record["embed"] = embed
        if reply_context:
            record["reply"] = reply_context

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
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=25)
            if res.status_code == 200:
                data = res.json()
                uri = data.get("uri", "")
                cid = data.get("cid", "")
                rkey = uri.split("/")[-1] if "/" in uri else ""
                permalink = f"https://bsky.app/profile/{self.handle}/post/{rkey}"
                return True, {
                    "uri": uri,
                    "cid": cid,
                    "rkey": rkey,
                    "permalink": permalink
                }
            else:
                err_msg = res.text
                print(f"❌ [BLUESKY CREATE RECORD ERROR] HTTP {res.status_code}: {err_msg}")
                return False, {"error": err_msg}
        except Exception as e:
            print(f"❌ [BLUESKY CREATE RECORD EXCEPTION] {e}")
            return False, {"error": str(e)}

    # -------------------------------------------------------------------------
    # 5. FUNGSI PENERBITAN KHUSUS (PRODUK, LIFESTYLE & VIDEO)
    # -------------------------------------------------------------------------
    def post_text(self, text: str) -> Tuple[bool, Dict[str, Any]]:
        """Menerbitkan pos teks biasa berserta pautan/hashtag aktif."""
        return self._create_record(text=text)

    def post_link_card(
        self,
        text: str,
        link_url: str,
        title: str,
        description: str,
        thumb_image_url: Optional[str] = None,
        thumb_file_path: Optional[Union[str, Path]] = None,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Menerbitkan pos dengan Kad Pautan Luar Boleh Klik (External Affiliate Embed Card).
        Sesuai untuk pautan Shopee / Lazada / Katalog.
        """
        thumb_blob = None
        if thumb_file_path:
            thumb_blob = self.upload_local_file(thumb_file_path)
        elif thumb_image_url:
            thumb_blob = self.upload_image_from_url(thumb_image_url)

        external_data: Dict[str, Any] = {
            "uri": link_url,
            "title": title[:200],
            "description": description[:300],
        }
        if thumb_blob:
            external_data["thumb"] = thumb_blob

        embed_payload = {
            "$type": "app.bsky.embed.external",
            "external": external_data
        }

        return self._create_record(text=text, embed=embed_payload)

    def post_images(
        self,
        text: str,
        image_sources: List[Union[str, Path]],
        alt_text: str = "Sembang PC & Tech Workspace Visual"
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Menerbitkan pos gambar atau album imej (Maksimum 4 imej mengikut had Bluesky).
        image_sources boleh terdiri daripada senarai URL atau laluan fail tempatan.
        """
        if not image_sources:
            return self.post_text(text)

        images_payload = []
        for src in image_sources[:4]:
            blob = None
            if isinstance(src, Path) or (isinstance(src, str) and os.path.exists(src)):
                blob = self.upload_local_file(src)
            elif isinstance(src, str) and src.startswith("http"):
                blob = self.upload_image_from_url(src)

            if blob:
                images_payload.append({
                    "alt": alt_text[:300],
                    "image": blob
                })

        if not images_payload:
            print("⚠️ [BLUESKY WARN] Tiada blob imej berjaya dimuat naik. Menghantar sebagai pos teks.")
            return self.post_text(text)

        embed_payload = {
            "$type": "app.bsky.embed.images",
            "images": images_payload
        }

        return self._create_record(text=text, embed=embed_payload)

    def post_video(
        self,
        text: str,
        video_path: Union[str, Path],
        alt_text: str = "Sembang PC & Tech Vertical Video Reel"
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Menerbitkan video MP4 ke Bluesky (Muncul di Feed & Tab Video).
        """
        blob = self.upload_local_file(video_path)
        if not blob:
            return False, {"error": "Gagal memuat naik fail video ke Bluesky PDS."}

        embed_payload = {
            "$type": "app.bsky.embed.video",
            "video": blob,
            "alt": alt_text[:300]
        }

        return self._create_record(text=text, embed=embed_payload)

    # -------------------------------------------------------------------------
    # 6. ENJIN BALASAN KOMEN PERTAMA (AUTO-REPLY / FIRST COMMENT)
    # -------------------------------------------------------------------------
    def reply_to_post(
        self,
        parent_uri: str,
        parent_cid: str,
        root_uri: Optional[str] = None,
        root_cid: Optional[str] = None,
        reply_text: str = "",
        embed: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Menghantar balasan komen ke bawah pos induk (Thread Reply).
        Digunakan untuk menyelitkan pautan affiliate di ruang komen pertama.
        """
        r_uri = root_uri or parent_uri
        r_cid = root_cid or parent_cid

        reply_context = {
            "root": {"uri": r_uri, "cid": r_cid},
            "parent": {"uri": parent_uri, "cid": parent_cid}
        }

        return self._create_record(text=reply_text, embed=embed, reply_context=reply_context)

    def post_with_affiliate_reply(
        self,
        main_text: str,
        affiliate_reply_text: str,
        image_sources: Optional[List[Union[str, Path]]] = None,
        video_path: Optional[Union[str, Path]] = None,
        alt_text: str = "Sembang PC & Tech Visual"
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Alur kerja penuh:
        1. Pos media utama (Gambar Unsplash atau Video Pexels).
        2. Komen secara automatik pautan affiliate pada balasan pertama di bawah pos tersebut.
        """
        # A. Pos Utama
        if video_path:
            ok, res_main = self.post_video(text=main_text, video_path=video_path, alt_text=alt_text)
        elif image_sources:
            ok, res_main = self.post_images(text=main_text, image_sources=image_sources, alt_text=alt_text)
        else:
            ok, res_main = self.post_text(text=main_text)

        if not ok:
            return False, res_main

        parent_uri = res_main.get("uri")
        parent_cid = res_main.get("cid")
        permalink = res_main.get("permalink")

        # B. Balasan Komen Pertama (Auto-Reply Affiliate)
        reply_permalink = ""
        if affiliate_reply_text and parent_uri and parent_cid:
            time.sleep(1.5)  # Beri masa sekejap untuk PDS menyelaraskan rekod
            ok_reply, res_reply = self.reply_to_post(
                parent_uri=parent_uri,
                parent_cid=parent_cid,
                reply_text=affiliate_reply_text
            )
            if ok_reply:
                reply_permalink = res_reply.get("permalink", "")
                print(f"  💬 [BLUESKY AUTO-REPLY] Pautan affiliate berjaya dibalas di komen pertama! ({reply_permalink})")

        return True, {
            "uri": parent_uri,
            "cid": parent_cid,
            "permalink": permalink,
            "reply_permalink": reply_permalink,
            "main_post": res_main
        }


# Singleton instance
bluesky_bot = BlueskyBot()