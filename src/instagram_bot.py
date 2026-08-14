#!/usr/bin/env python3
"""
Instagram Publishing Bot Engine (Meta Graph API)
Sembang PC & Tech Ecosystem (100% Dynamic Keys)
"""

import os
import time
import requests
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

from src.instagram_redis import instagram_redis
from src.instagram_vector import instagram_vector

load_dotenv()

GRAPH_API_VERSION = "v26.0"
GRAPH_BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


class InstagramBot:
    """Enjin penerbitan kandungan ke akaun Instagram Professional."""

    def __init__(self):
        self.account_id = os.getenv("INSTAGRAM_ACCOUNT_ID", "").strip()
        self.access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN", "").strip()

    def is_configured(self) -> bool:
        """Semak status kunci persekitaran."""
        return bool(self.account_id and self.access_token)

    def post_photo(
        self,
        image_url: str,
        caption: str,
        product_id: Optional[str] = None,
        post_type: str = "affiliate",
    ) -> Dict[str, Any]:
        """Menghantar 1 gambar ke Instagram Feed."""
        if not self.is_configured():
            return {"success": False, "error": "Kunci Instagram tiada dalam persekitaran."}

        container_url = f"{GRAPH_BASE_URL}/{self.account_id}/media"
        payload = {
            "image_url": image_url,
            "caption": caption,
            "access_token": self.access_token,
        }

        try:
            res_c = requests.post(container_url, data=payload, timeout=30).json()
            if "id" not in res_c:
                return {"success": False, "error": res_c.get("error", {}).get("message", str(res_c))}

            creation_id = res_c["id"]
            self._wait_ready(creation_id)

            pub_res = self._publish(creation_id)
            if not pub_res.get("success"):
                return pub_res

            media_id = pub_res["media_id"]
            permalink = self._get_permalink(media_id)

            if product_id:
                instagram_redis.mark_product_as_posted(product_id, {"media_id": media_id, "permalink": permalink})
                instagram_vector.store_post_vector(caption, product_id, post_type)
            instagram_redis.increment_daily_post_count()

            return {"success": True, "media_id": media_id, "permalink": permalink}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def post_carousel(self, image_urls: List[str], caption: str, product_id: Optional[str] = None) -> Dict[str, Any]:
        """Menghantar album Carousel ke Instagram."""
        if not self.is_configured():
            return {"success": False, "error": "Kunci Instagram tiada."}
        if len(image_urls) < 2:
            return self.post_photo(image_urls[0], caption, product_id)

        try:
            item_ids = []
            for img in image_urls[:10]:
                u = f"{GRAPH_BASE_URL}/{self.account_id}/media"
                p = {"image_url": img, "is_carousel_item": True, "access_token": self.access_token}
                res = requests.post(u, data=p, timeout=20).json()
                if "id" in res:
                    item_ids.append(res["id"])
                time.sleep(1)

            if len(item_ids) < 2:
                return {"success": False, "error": "Gagal mencipta item kontena carousel."}

            parent_url = f"{GRAPH_BASE_URL}/{self.account_id}/media"
            parent_p = {
                "media_type": "CAROUSEL",
                "children": ",".join(item_ids),
                "caption": caption,
                "access_token": self.access_token,
            }
            res_parent = requests.post(parent_url, data=parent_p, timeout=30).json()
            if "id" not in res_parent:
                return {"success": False, "error": res_parent.get("error", {}).get("message", str(res_parent))}

            carousel_id = res_parent["id"]
            self._wait_ready(carousel_id)

            pub_res = self._publish(carousel_id)
            if not pub_res.get("success"):
                return pub_res

            media_id = pub_res["media_id"]
            permalink = self._get_permalink(media_id)
            return {"success": True, "media_id": media_id, "permalink": permalink}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _wait_ready(self, creation_id: str, timeout: int = 25):
        url = f"{GRAPH_BASE_URL}/{creation_id}"
        params = {"fields": "status_code", "access_token": self.access_token}
        start = time.time()
        while time.time() - start < timeout:
            time.sleep(3)
            try:
                res = requests.get(url, params=params, timeout=10).json()
                if res.get("status_code") in ["FINISHED", "PUBLISHED"]:
                    return True
            except Exception:
                pass
        return True

    def _publish(self, creation_id: str) -> Dict[str, Any]:
        url = f"{GRAPH_BASE_URL}/{self.account_id}/media_publish"
        payload = {"creation_id": creation_id, "access_token": self.access_token}
        res = requests.post(url, data=payload, timeout=30).json()
        if "id" in res:
            return {"success": True, "media_id": res["id"]}
        return {"success": False, "error": res.get("error", {}).get("message", str(res))}

    def _get_permalink(self, media_id: str) -> str:
        url = f"{GRAPH_BASE_URL}/{media_id}"
        params = {"fields": "permalink", "access_token": self.access_token}
        try:
            res = requests.get(url, params=params, timeout=10).json()
            return res.get("permalink", f"https://www.instagram.com/p/{media_id}/")
        except Exception:
            return f"https://www.instagram.com/p/{media_id}/"


# Singleton instance
instagram_bot = InstagramBot()