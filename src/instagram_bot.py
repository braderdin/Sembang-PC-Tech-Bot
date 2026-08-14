#!/usr/bin/env python3
"""
Instagram Publishing Bot Engine (Meta Graph API)
Sembang PC & Tech Ecosystem
"""

import os
import sys
import time
import requests
from typing import Dict, Any, Optional, List
from pathlib import Path
from dotenv import load_dotenv

# Muat naik storan Redis & Vector khas Instagram
from src.instagram_redis import instagram_redis
from src.instagram_vector import instagram_vector

load_dotenv()

GRAPH_API_VERSION = "v26.0"
GRAPH_BASE_URL = f"[https://graph.facebook.com/](https://graph.facebook.com/){GRAPH_API_VERSION}"


class InstagramBot:
    """Enjin rasmi untuk menyiarkan kandungan ke akaun Instagram Professional."""

    def __init__(
        self,
        account_id: Optional[str] = None,
        access_token: Optional[str] = None,
    ):
        self.account_id = (account_id or os.getenv("INSTAGRAM_ACCOUNT_ID", "")).strip()
        self.access_token = (access_token or os.getenv("INSTAGRAM_ACCESS_TOKEN", "")).strip()

    def is_configured(self) -> bool:
        """Semak sama ada kunci akaun Instagram telah disediakan."""
        return bool(self.account_id and self.access_token)

    # -------------------------------------------------------------------------
    # 1. HANTARAN GAMBAR FEED TUNGGAL (SINGLE PHOTO POST)
    # -------------------------------------------------------------------------

    def post_photo(
        self,
        image_url: str,
        caption: str,
        product_id: Optional[str] = None,
        post_type: str = "affiliate",
    ) -> Dict[str, Any]:
        """
        Menghantar 1 gambar feed bersama kapsyen ke Instagram.
        """
        if not self.is_configured():
            return {"success": False, "error": "Instagram credentials not configured."}

        print(f"📸 [Instagram Bot] Menghantar hantaran gambar ke @braderdin360...")

        # 1. Cipta Container Gambar
        container_url = f"{GRAPH_BASE_URL}/{self.account_id}/media"
        payload = {
            "image_url": image_url,
            "caption": caption,
            "access_token": self.access_token,
        }

        try:
            res_cont = requests.post(container_url, data=payload, timeout=30).json()
            if "id" not in res_cont:
                err_msg = res_cont.get("error", {}).get("message", str(res_cont))
                print(f"❌ [Instagram Bot] Ralat Container Gambar: {err_msg}")
                return {"success": False, "error": err_msg}

            creation_id = res_cont["id"]

            # 2. Tunggu Pemprosesan Siap (Polling status)
            if not self._wait_for_media_ready(creation_id, timeout_sec=20):
                return {"success": False, "error": "Media container processing timeout."}

            # 3. Terbitkan Hantaran
            publish_res = self._publish_container(creation_id)
            if not publish_res.get("success"):
                return publish_res

            media_id = publish_res["media_id"]
            permalink = self._get_permalink(media_id)

            # 4. Rekod ke Redis & Vector DB
            self._save_success_records(
                media_id=media_id,
                permalink=permalink,
                caption=caption,
                product_id=product_id,
                post_type=post_type,
            )

            print(f"🎉 [Instagram Bot] Hantaran Berjaya! Pautan: {permalink}")
            return {
                "success": True,
                "media_id": media_id,
                "permalink": permalink,
            }

        except Exception as e:
            print(f"❌ [Instagram Bot] Ralat Permintaan: {str(e)}")
            return {"success": False, "error": str(e)}

    # -------------------------------------------------------------------------
    # 2. HANTARAN VIDEO REELS (INSTAGRAM REELS)
    # -------------------------------------------------------------------------

    def post_reel(
        self,
        video_url: str,
        caption: str,
        product_id: Optional[str] = None,
        post_type: str = "reel",
    ) -> Dict[str, Any]:
        """
        Menghantar video ke Instagram Reels secara automatik.
        """
        if not self.is_configured():
            return {"success": False, "error": "Instagram credentials not configured."}

        print(f"🎬 [Instagram Bot] Memuat naik video ke Instagram Reels...")

        # 1. Cipta Container Reels
        container_url = f"{GRAPH_BASE_URL}/{self.account_id}/media"
        payload = {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "share_to_feed": True,  # Turut dipaparkan di grid feed utama
            "access_token": self.access_token,
        }

        try:
            res_cont = requests.post(container_url, data=payload, timeout=45).json()
            if "id" not in res_cont:
                err_msg = res_cont.get("error", {}).get("message", str(res_cont))
                print(f"❌ [Instagram Bot] Ralat Container Reel: {err_msg}")
                return {"success": False, "error": err_msg}

            creation_id = res_cont["id"]

            # 2. Tunggu Pemprosesan Video Siap (Reels perlukan masa lebih sedikit ~60s)
            if not self._wait_for_media_ready(creation_id, timeout_sec=90):
                return {"success": False, "error": "Reel encoding/processing timeout."}

            # 3. Terbitkan Reels
            publish_res = self._publish_container(creation_id)
            if not publish_res.get("success"):
                return publish_res

            media_id = publish_res["media_id"]
            permalink = self._get_permalink(media_id)

            # 4. Rekod Kejayaan
            self._save_success_records(
                media_id=media_id,
                permalink=permalink,
                caption=caption,
                product_id=product_id,
                post_type=post_type,
            )

            print(f"🎉 [Instagram Bot] Reels Berjaya Diterbitkan! Pautan: {permalink}")
            return {
                "success": True,
                "media_id": media_id,
                "permalink": permalink,
            }

        except Exception as e:
            print(f"❌ [Instagram Bot] Ralat Muat Naik Reel: {str(e)}")
            return {"success": False, "error": str(e)}

    # -------------------------------------------------------------------------
    # 3. HANTARAN ALBUM CAROUSEL (MULTI-IMAGE POST)
    # -------------------------------------------------------------------------

    def post_carousel(
        self,
        image_urls: List[str],
        caption: str,
        product_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Menghantar album Carousel (2 hingga 10 gambar) ke Instagram.
        """
        if not self.is_configured():
            return {"success": False, "error": "Instagram credentials not configured."}
        if len(image_urls) < 2:
            return self.post_photo(image_urls[0], caption, product_id)

        print(f"🖼️ [Instagram Bot] Mencipta album Carousel ({len(image_urls)} gambar)...")

        try:
            # 1. Cipta item container bagi setiap gambar
            item_ids = []
            for img_url in image_urls[:10]:
                item_url = f"{GRAPH_BASE_URL}/{self.account_id}/media"
                payload = {
                    "image_url": img_url,
                    "is_carousel_item": True,
                    "access_token": self.access_token,
                }
                res = requests.post(item_url, data=payload, timeout=20).json()
                if "id" in res:
                    item_ids.append(res["id"])
                time.sleep(1)

            if len(item_ids) < 2:
                return {"success": False, "error": "Gagal mencipta item kontena carousel."}

            # 2. Cipta Parent Carousel Container
            parent_url = f"{GRAPH_BASE_URL}/{self.account_id}/media"
            parent_payload = {
                "media_type": "CAROUSEL",
                "children": ",".join(item_ids),
                "caption": caption,
                "access_token": self.access_token,
            }
            res_parent = requests.post(parent_url, data=parent_payload, timeout=30).json()
            if "id" not in res_parent:
                return {"success": False, "error": res_parent.get("error", {}).get("message", str(res_parent))}

            carousel_id = res_parent["id"]
            self._wait_for_media_ready(carousel_id, timeout_sec=20)

            # 3. Terbitkan Carousel
            publish_res = self._publish_container(carousel_id)
            if not publish_res.get("success"):
                return publish_res

            media_id = publish_res["media_id"]
            permalink = self._get_permalink(media_id)

            self._save_success_records(media_id, permalink, caption, product_id, post_type="carousel")
            return {"success": True, "media_id": media_id, "permalink": permalink}

        except Exception as e:
            return {"success": False, "error": str(e)}

    # -------------------------------------------------------------------------
    # FUNGSI-FUNGSI BANTUAN DALAMAN (INTERNAL HELPERS)
    # -------------------------------------------------------------------------

    def _wait_for_media_ready(self, creation_id: str, timeout_sec: int = 30) -> bool:
        """Menyemak status pemprosesan media pelayan Meta sehingga FINISHED."""
        status_url = f"{GRAPH_BASE_URL}/{creation_id}"
        params = {"fields": "status_code", "access_token": self.access_token}
        start_time = time.time()

        while time.time() - start_time < timeout_sec:
            time.sleep(3)
            try:
                res = requests.get(status_url, params=params, timeout=10).json()
                status = res.get("status_code", "FINISHED")
                if status == "FINISHED":
                    return True
                elif status == "ERROR":
                    print(f"❌ [Instagram Bot] Status Media Meta ERROR: {res}")
                    return False
            except Exception:
                pass
        return True

    def _publish_container(self, creation_id: str) -> Dict[str, Any]:
        """Menerbitkan kontena media yang telah sedia."""
        publish_url = f"{GRAPH_BASE_URL}/{self.account_id}/media_publish"
        payload = {"creation_id": creation_id, "access_token": self.access_token}

        res = requests.post(publish_url, data=payload, timeout=30).json()
        if "id" in res:
            return {"success": True, "media_id": res["id"]}
        err_msg = res.get("error", {}).get("message", str(res))
        return {"success": False, "error": err_msg}

    def _get_permalink(self, media_id: str) -> str:
        """Mengambil pautan URL hantaran rasmi dari Instagram."""
        url = f"{GRAPH_BASE_URL}/{media_id}"
        params = {"fields": "permalink", "access_token": self.access_token}
        try:
            res = requests.get(url, params=params, timeout=10).json()
            return res.get("permalink", f"[https://www.instagram.com/p/](https://www.instagram.com/p/){media_id}/")
        except Exception:
            return f"[https://www.instagram.com/p/](https://www.instagram.com/p/){media_id}/"

    def _save_success_records(
        self,
        media_id: str,
        permalink: str,
        caption: str,
        product_id: Optional[str] = None,
        post_type: str = "affiliate",
    ):
        """Menyimpan rekod kejayaan ke Redis dan pangkalan data Vector."""
        try:
            # 1. Tandakan di Redis
            if product_id:
                instagram_redis.mark_product_as_posted(
                    product_id=product_id,
                    metadata={"media_id": media_id, "permalink": permalink},
                )
            instagram_redis.increment_daily_post_count()
            instagram_redis.log_published_post(
                post_type=post_type,
                item_id=product_id or "lifestyle",
                media_id=media_id,
                permalink=permalink,
            )

            # 2. Simpan Embedding di Vector DB
            instagram_vector.store_post_vector(
                text=caption,
                title=f"IG Post {media_id}",
                post_type=post_type,
                media_id=media_id,
            )
        except Exception as e:
            print(f"⚠️ [Instagram Bot] Amaran simpan rekod sejarah: {e}")


# Singleton instance bot
instagram_bot = InstagramBot()