#!/usr/bin/env python3
"""
Dedicated Instagram Pexels Video Reels Publishing Engine (Meta Graph API)
Sembang PC & Tech Ecosystem (100% Dynamic Keys)
Features:
- Resumable Binary Video Upload (Local MP4 -> Instagram Graph API)
- Container Status Polling (Async Encoding Wait Loop)
- Media Publish & Direct Meta CDN Video URL Extraction for Threads
"""

import os
import time
import requests
from typing import Dict, Any, Tuple
from dotenv import load_dotenv

load_dotenv()

GRAPH_API_VERSION = "v26.0"
GRAPH_BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


class InstagramReelBot:
    """Enjin penerbitan video Reels ke akaun Instagram Professional."""

    def __init__(self):
        self.account_id = os.getenv("INSTAGRAM_ACCOUNT_ID", "").strip()
        self.access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN", "").strip()

    def is_configured(self) -> bool:
        """Semak status kunci persekitaran Instagram."""
        return bool(self.account_id and self.access_token)

    def upload_reel_to_instagram(
        self,
        video_path: str,
        caption: str,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Memuat naik video MP4 tempatan sebagai Instagram Reel
        menggunakan protokol Resumable Upload Meta Graph API.
        """
        if not self.is_configured():
            return False, {"error": "Kunci INSTAGRAM_ACCOUNT_ID atau INSTAGRAM_ACCESS_TOKEN tiada."}

        if not os.path.exists(video_path):
            return False, {"error": f"Fail video tidak dijumpai: {video_path}"}

        file_size = os.path.getsize(video_path)

        try:
            # -----------------------------------------------------------------
            # FASA 1: Cipta Sesi Resumable Media Container
            # -----------------------------------------------------------------
            print("  📸 [IG REEL STEP 1] Mencipta sesi Media Container Reels...")
            init_url = f"{GRAPH_BASE_URL}/{self.account_id}/media"
            init_payload = {
                "media_type": "REELS",
                "upload_type": "resumable",
                "caption": caption,
                "access_token": self.access_token,
            }

            res_init = requests.post(init_url, data=init_payload, timeout=30)
            init_json = res_init.json()

            if res_init.status_code != 200 or "id" not in init_json:
                err_msg = init_json.get("error", {}).get("message", res_init.text)
                print(f"  ❌ [IG REEL STEP 1 ERROR] {err_msg}")
                return False, {"step": 1, "error": err_msg, "response": init_json}

            container_id = init_json["id"]
            upload_uri = init_json.get("uri")
            print(f"  ✅ [IG REEL STEP 1 SUCCESS] Container ID: {container_id}")

            # -----------------------------------------------------------------
            # FASA 2: Muat Naik Binary Video MP4 ke Instagram Server
            # -----------------------------------------------------------------
            print("  📸 [IG REEL STEP 2] Memuat naik Binary Video ke Instagram Server...")
            with open(video_path, "rb") as vf:
                video_bytes = vf.read()

            upload_headers = {
                "Authorization": f"OAuth {self.access_token}",
                "offset": "0",
                "file_size": str(file_size),
                "Content-Type": "application/octet-stream",
            }

            target_upload_url = upload_uri or f"https://rupload.facebook.com/ig-video-upload/{container_id}"
            res_upload = requests.post(
                target_upload_url,
                headers=upload_headers,
                data=video_bytes,
                timeout=120,
            )

            if res_upload.status_code != 200:
                print(f"  ❌ [IG REEL STEP 2 ERROR] HTTP {res_upload.status_code}: {res_upload.text}")
                return False, {"step": 2, "error": "Gagal muat naik binary video ke IG rupload.", "response": res_upload.text}

            print("  ✅ [IG REEL STEP 2 SUCCESS] Muat naik binary video selesai!")

            # -----------------------------------------------------------------
            # FASA 3: Tunggu Video Selesai Diproses (Encoding Ready)
            # -----------------------------------------------------------------
            print("  📸 [IG REEL STEP 3] Menunggu status pemprosesan video Instagram...")
            ready_ok, status_desc = self._wait_video_ready(container_id, timeout=90)
            if not ready_ok:
                print(f"  ❌ [IG REEL STEP 3 ERROR] Video gagal diproses Meta: {status_desc}")
                return False, {"step": 3, "error": status_desc}

            # -----------------------------------------------------------------
            # FASA 4: Terbitkan Instagram Reel (media_publish)
            # -----------------------------------------------------------------
            print("  📸 [IG REEL STEP 4] Menerbitkan Instagram Reel...")
            pub_url = f"{GRAPH_BASE_URL}/{self.account_id}/media_publish"
            pub_payload = {
                "creation_id": container_id,
                "access_token": self.access_token,
            }

            res_pub = requests.post(pub_url, data=pub_payload, timeout=30)
            pub_json = res_pub.json()

            if res_pub.status_code == 200 and "id" in pub_json:
                media_id = pub_json["id"]
                media_details = self._get_media_details(media_id)
                permalink = media_details.get("permalink", "")
                video_url = media_details.get("media_url", "")
                print(f"  🎉 [IG REEL SUCCESS] Instagram Reel berjaya diterbitkan! Pautan: {permalink}")
                return True, {"media_id": media_id, "permalink": permalink, "video_url": video_url}
            else:
                err_msg = pub_json.get("error", {}).get("message", res_pub.text)
                print(f"  ❌ [IG REEL STEP 4 ERROR] {err_msg}")
                return False, {"step": 4, "error": err_msg, "response": pub_json}

        except Exception as e:
            print(f"  ❌ [IG REEL EXCEPTION] {e}")
            return False, {"error": str(e)}

    def _wait_video_ready(self, container_id: str, timeout: int = 90) -> Tuple[bool, str]:
        """Menyemak status_code container sehingga status bertukar ke FINISHED."""
        url = f"{GRAPH_BASE_URL}/{container_id}"
        params = {"fields": "status_code,status", "access_token": self.access_token}
        start = time.time()

        while time.time() - start < timeout:
            time.sleep(5)
            try:
                res = requests.get(url, params=params, timeout=15).json()
                status_code = res.get("status_code", "")

                if status_code in ["FINISHED", "PUBLISHED"]:
                    return True, "FINISHED"
                elif status_code in ["ERROR", "EXPIRED"]:
                    return False, f"Status pemprosesan IG: {status_code} ({res.get('status', '')})"
            except Exception:
                pass

        return True, "TIMEOUT_ASSUME_READY"

    def _get_media_details(self, media_id: str) -> Dict[str, str]:
        """Mendapatkan pautan permalink dan media_url CDN video rasmi."""
        url = f"{GRAPH_BASE_URL}/{media_id}"
        params = {"fields": "permalink,media_url", "access_token": self.access_token}
        try:
            res = requests.get(url, params=params, timeout=10).json()
            return {
                "permalink": res.get("permalink", f"https://www.instagram.com/reel/{media_id}/"),
                "media_url": res.get("media_url", ""),
            }
        except Exception:
            return {"permalink": f"https://www.instagram.com/reel/{media_id}/", "media_url": ""}


# Singleton instance
instagram_reel_bot = InstagramReelBot()