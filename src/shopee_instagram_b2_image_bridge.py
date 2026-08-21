#!/usr/bin/env python3
"""
Shopee Instagram Backblaze B2 Image Bridge Engine
Lokasi Fail: src/shopee_instagram_b2_image_bridge.py

Fungsi Utama:
1. Memuat turun fail gambar binary Shopee secara terus melalui rangkaian pelari (Runner/WSL).
2. Memuat naik fail imej sementara ke Backblaze B2 Private Storage via REST API v2.
3. Menjana Signed Download Authorization Token (sah selama 300-600 saat) supaya Meta Graph API
   boleh memuat turun imej tanpa halangan WAF/Geo-block CDN Shopee.
4. Menyediakan fungsi pembersihan automatik (b2_delete_file_version) untuk memadam imej
   sejurus selepas kontena Instagram selesai diproses bagi mengekalkan penggunaan storan 0 MB.
"""

import os
import time
import hashlib
import urllib.parse
import requests
from typing import Dict, Any, Tuple, Optional
from dotenv import load_dotenv

# Muat turun pembolehubah persekitaran
load_dotenv()


class ShopeeInstagramB2Bridge:
    """Enjin Jambatan Imej Backblaze B2 untuk Hantaran Instagram Feed."""

    def __init__(self):
        self.b2_key_id = (
            os.getenv("B2_ACC1_KEY_ID", "").strip()
            or os.getenv("B2_KEY_ID", "").strip()
        )
        self.b2_app_key = (
            os.getenv("B2_ACC1_APPLICATION_KEY", "").strip()
            or os.getenv("B2_APPLICATION_KEY", "").strip()
        )
        self.b2_bucket_id = (
            os.getenv("B2_ACC1_BUCKET_ID", "").strip()
            or os.getenv("B2_BUCKET_ID", "").strip()
        )
        self.b2_bucket_name = (
            os.getenv("B2_ACC1_BUCKET_NAME", "").strip()
            or os.getenv("B2_BUCKET_NAME", "").strip()
        )

    def is_configured(self) -> bool:
        """Menyemak kelengkapan kunci Backblaze B2 dalam persekitaran."""
        return bool(
            self.b2_key_id
            and self.b2_app_key
            and self.b2_bucket_id
            and self.b2_bucket_name
        )

    # -------------------------------------------------------------------------
    # 1. PENGESAHAN & OPERASI REST API BACKBLAZE B2
    # -------------------------------------------------------------------------
    def _b2_authorize(self) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Mendapatkan Authorization Token, API URL, dan Download URL daripada Backblaze B2."""
        auth_url = "https://api.backblazeb2.com/b2api/v2/b2_authorize_account"
        try:
            res = requests.get(auth_url, auth=(self.b2_key_id, self.b2_app_key), timeout=15)
            if res.status_code == 200:
                data = res.json()
                return data.get("authorizationToken"), data.get("apiUrl"), data.get("downloadUrl")
            print(f"  ❌ [B2 AUTH ERROR] HTTP {res.status_code}: {res.text}")
        except Exception as e:
            print(f"  ❌ [B2 AUTH EXCEPTION] {e}")
        return None, None, None

    def _b2_get_upload_url(self, api_url: str, auth_token: str) -> Tuple[Optional[str], Optional[str]]:
        """Mendapatkan URL muat naik khusus untuk bucket B2."""
        url = f"{api_url}/b2api/v2/b2_get_upload_url"
        headers = {"Authorization": auth_token}
        payload = {"bucketId": self.b2_bucket_id}
        try:
            res = requests.post(url, json=payload, headers=headers, timeout=15)
            if res.status_code == 200:
                data = res.json()
                return data.get("uploadUrl"), data.get("authorizationToken")
            print(f"  ❌ [B2 UPLOAD URL ERROR] HTTP {res.status_code}: {res.text}")
        except Exception as e:
            print(f"  ❌ [B2 UPLOAD URL EXCEPTION] {e}")
        return None, None

    def _b2_get_download_authorization(
        self, api_url: str, auth_token: str, file_name: str, valid_duration: int = 600
    ) -> Optional[str]:
        """Menjana Signed Download Authorization Token untuk capaian perayap Meta."""
        url = f"{api_url}/b2api/v2/b2_get_download_authorization"
        headers = {"Authorization": auth_token}
        payload = {
            "bucketId": self.b2_bucket_id,
            "fileNamePrefix": file_name,
            "validDurationInSeconds": valid_duration,
        }
        try:
            res = requests.post(url, json=payload, headers=headers, timeout=15)
            if res.status_code == 200:
                return res.json().get("authorizationToken")
            print(f"  ⚠️ [B2 DOWNLOAD AUTH WARN] HTTP {res.status_code}: {res.text}")
        except Exception as e:
            print(f"  ⚠️ [B2 DOWNLOAD AUTH EXCEPTION] {e}")
        return None

    # -------------------------------------------------------------------------
    # 2. MUAT TURUN & MUAT NAIK IMEJ KE B2
    # -------------------------------------------------------------------------
    def download_image_bytes(self, image_url: str) -> Tuple[Optional[bytes], str]:
        """Memuat turun fail binary imej daripada URL CDN Shopee."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        }
        try:
            res = requests.get(image_url, headers=headers, timeout=20)
            if res.status_code == 200 and len(res.content) > 500:
                content_type = res.headers.get("Content-Type", "").lower()
                mime = "image/jpeg"
                if "png" in content_type:
                    mime = "image/png"
                elif "webp" in content_type:
                    mime = "image/webp"
                return res.content, mime
            return None, f"HTTP {res.status_code} (Saiz: {len(res.content)} bytes)"
        except Exception as e:
            return None, str(e)

    def upload_shopee_image_to_b2(
        self, image_url: str, product_id: str = ""
    ) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """
        Aliran Penuh Jambatan Imej:
        1. Muat turun gambar daripada Shopee CDN.
        2. Muat naik ke Backblaze B2 Bucket.
        3. Jana Signed Public URL untuk Instagram Container API.
        """
        if not self.is_configured():
            return False, None, "Kunci konfigurasi Backblaze B2 tidak lengkap dalam persekitaran."

        # A. Muat turun fail imej
        print("  🌉 [B2 BRIDGE STEP 1] Memuat turun binary imej daripada Shopee CDN...")
        img_bytes, mime_type = self.download_image_bytes(image_url)
        if not img_bytes:
            return False, None, f"Gagal memuat turun imej daripada Shopee: {mime_type}"

        # B. Dapatkan pengesahan B2
        print("  🌉 [B2 BRIDGE STEP 2] Mengesahkan akaun Backblaze B2...")
        auth_token, api_url, download_url = self._b2_authorize()
        if not auth_token or not api_url or not download_url:
            return False, None, "Gagal mendapatkan sesi pengesahan Backblaze B2."

        upload_url, upload_auth_token = self._b2_get_upload_url(api_url, auth_token)
        if not upload_url or not upload_auth_token:
            return False, None, "Gagal mendapatkan uploadUrl daripada Backblaze B2."

        # C. Muat naik imej binary ke B2
        clean_id = "".join(c for c in str(product_id) if c.isalnum()) or "item"
        file_name = f"shopee_ig_{clean_id}_{int(time.time())}.jpg"
        encoded_file_name = urllib.parse.quote(file_name)
        sha1_hash = hashlib.sha1(img_bytes).hexdigest()

        headers = {
            "Authorization": upload_auth_token,
            "X-Bz-File-Name": encoded_file_name,
            "Content-Type": "image/jpeg",
            "Content-Length": str(len(img_bytes)),
            "X-Bz-Content-Sha1": sha1_hash,
        }

        print(f"  🌉 [B2 BRIDGE STEP 3] Memuat naik imej ({len(img_bytes)} bytes) ke bucket B2...")
        try:
            res_up = requests.post(upload_url, headers=headers, data=img_bytes, timeout=30)
            if res_up.status_code != 200:
                return False, None, f"B2 Upload Error (HTTP {res_up.status_code}): {res_up.text}"

            file_id = res_up.json().get("fileId")

            # D. Jana Signed Download URL (Sah 600 saat / 10 minit)
            download_token = self._b2_get_download_authorization(
                api_url, auth_token, file_name, valid_duration=600
            )

            base_file_url = f"{download_url}/file/{self.b2_bucket_name}/{encoded_file_name}"
            signed_url = f"{base_file_url}?Authorization={download_token}" if download_token else base_file_url

            print(f"  ✅ [B2 BRIDGE SUCCESS] Signed Imej URL dijana: {base_file_url}")

            bridge_payload = {
                "signed_url": signed_url,
                "file_id": file_id,
                "file_name": file_name,
                "api_url": api_url,
                "auth_token": auth_token,
            }
            return True, bridge_payload, "Berjaya menjana Signed URL Backblaze B2."

        except Exception as e:
            return False, None, f"Ralat rangkaian muat naik B2: {str(e)}"

    # -------------------------------------------------------------------------
    # 3. PEMBERSIHAN FAIL SEMENTARA
    # -------------------------------------------------------------------------
    def delete_image_from_b2(
        self, api_url: str, auth_token: str, file_id: str, file_name: str
    ) -> bool:
        """Memadam fail imej sementara dari B2 bucket untuk menjimatkan storan."""
        if not file_id or not file_name or not api_url or not auth_token:
            return False
        url = f"{api_url}/b2api/v2/b2_delete_file_version"
        headers = {"Authorization": auth_token}
        payload = {"fileId": file_id, "fileName": file_name}
        try:
            res = requests.post(url, json=payload, headers=headers, timeout=10)
            if res.status_code == 200:
                print(f"  🧹 [B2 CLEANUP] Fail sementara '{file_name}' berjaya dipadam daripada B2.")
                return True
            print(f"  ⚠️ [B2 CLEANUP WARN] Gagal memadam fail B2 (HTTP {res.status_code}): {res.text}")
        except Exception as e:
            print(f"  ⚠️ [B2 CLEANUP EXCEPTION] {e}")
        return False

    def cleanup_bridge(self, bridge_data: Optional[Dict[str, Any]]) -> bool:
        """Pembungkus pembersihan mudah menggunakan objek data bridge."""
        if not bridge_data or not isinstance(bridge_data, dict):
            return False
        return self.delete_image_from_b2(
            api_url=bridge_data.get("api_url", ""),
            auth_token=bridge_data.get("auth_token", ""),
            file_id=bridge_data.get("file_id", ""),
            file_name=bridge_data.get("file_name", ""),
        )


# Singleton instance
shopee_b2_bridge = ShopeeInstagramB2Bridge()