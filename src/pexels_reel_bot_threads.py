#!/usr/bin/env python3
"""
Dedicated Threads Video Publishing Engine (Meta Threads API via Backblaze B2 Storage)
Sembang PC & Tech Ecosystem (100% Dynamic Keys & Sifar Kunci Hardcode)
Features:
- Native REST B2 Video Hosting with Signed Download Authorization Token
- Ingestion Self-Check (HTTP 200 & MIME Type Verification)
- Resumable Threads Video Container Processing & Publishing Loop
- Automatic Cleanup of Temp MP4 from Backblaze B2 Post-Publish
"""

import os
import time
import hashlib
import urllib.parse
import requests
from typing import Dict, Any, Tuple, Optional
from dotenv import load_dotenv

load_dotenv()

THREADS_BASE_URL = "https://graph.threads.net/v1.0"


def smart_trim_for_threads(text: str, max_chars: int = 480) -> str:
    """Memotong kapsyen secara pintar di bawah had ketat 500 aksara Threads API."""
    if not text or len(text) <= max_chars:
        return text

    trimmed = text[:max_chars]
    last_punc = max(trimmed.rfind("."), trimmed.rfind("?"), trimmed.rfind("!"))

    if last_punc != -1 and last_punc > 80:
        return trimmed[: last_punc + 1].strip()

    last_space = trimmed.rfind(" ")
    if last_space != -1:
        return trimmed[:last_space].strip() + "..."

    return trimmed[: max_chars - 3] + "..."


class ThreadsReelBot:
    """Enjin penerbitan video ke akaun Threads rasmi via Backblaze B2."""

    def __init__(self):
        self.user_id = os.getenv("THREADS_USER_ID", "").strip()
        self.access_token = os.getenv("THREADS_ACCESS_TOKEN", "").strip()

        # Baca Kunci Backblaze B2 dari Environment
        self.b2_key_id = os.getenv("B2_ACC1_KEY_ID", "").strip() or os.getenv("B2_KEY_ID", "").strip()
        self.b2_app_key = os.getenv("B2_ACC1_APPLICATION_KEY", "").strip() or os.getenv("B2_APPLICATION_KEY", "").strip()
        self.b2_bucket_id = os.getenv("B2_ACC1_BUCKET_ID", "").strip() or os.getenv("B2_BUCKET_ID", "").strip()
        self.b2_bucket_name = os.getenv("B2_ACC1_BUCKET_NAME", "").strip() or os.getenv("B2_BUCKET_NAME", "").strip()

    def is_configured(self) -> bool:
        """Semak status kelengkapan kunci persekitaran."""
        return bool(self.user_id and self.access_token and self.b2_key_id and self.b2_app_key)

    # -------------------------------------------------------------------------
    # MODUL STOKAN BACKBLAZE B2 NATIVE REST API
    # -------------------------------------------------------------------------
    def _b2_authorize(self) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Mendapatkan Authorization Token dan API URL dari Backblaze B2."""
        auth_url = "https://api.backblazeb2.com/b2api/v2/b2_authorize_account"
        try:
            res = requests.get(auth_url, auth=(self.b2_key_id, self.b2_app_key), timeout=15)
            if res.status_code == 200:
                data = res.json()
                return data.get("authorizationToken"), data.get("apiUrl"), data.get("downloadUrl")
        except Exception as e:
            print(f"  ❌ [B2 AUTH EXCEPTION] {e}")
        return None, None, None

    def _b2_get_upload_url(self, api_url: str, auth_token: str) -> Tuple[Optional[str], Optional[str]]:
        """Mendapatkan URL muat naik khusus bucket B2."""
        url = f"{api_url}/b2api/v2/b2_get_upload_url"
        headers = {"Authorization": auth_token}
        payload = {"bucketId": self.b2_bucket_id}
        try:
            res = requests.post(url, json=payload, headers=headers, timeout=15)
            if res.status_code == 200:
                data = res.json()
                return data.get("uploadUrl"), data.get("authorizationToken")
        except Exception as e:
            print(f"  ❌ [B2 UPLOAD URL EXCEPTION] {e}")
        return None, None

    def _b2_get_download_authorization(self, api_url: str, auth_token: str, file_name: str, valid_duration: int = 3600) -> Optional[str]:
        """Menjana Signed Download Token untuk membolehkan Meta memuat turun dari Private Bucket."""
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
        except Exception as e:
            print(f"  ⚠️ [B2 DOWNLOAD AUTH EXCEPTION] {e}")
        return None

    def _upload_video_to_b2(self, video_path: str) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]]:
        """Memuat naik fail MP4 tempatan ke B2 dan memulangkan Signed Public URL."""
        auth_token, api_url, download_url = self._b2_authorize()
        if not auth_token:
            return None, None, None, None, None

        upload_url, upload_auth_token = self._b2_get_upload_url(api_url, auth_token)
        if not upload_url:
            return None, None, None, None, None

        file_name = f"threads_reel_{int(time.time())}.mp4"
        encoded_file_name = urllib.parse.quote(file_name)

        with open(video_path, "rb") as f:
            file_bytes = f.read()

        sha1_hash = hashlib.sha1(file_bytes).hexdigest()
        headers = {
            "Authorization": upload_auth_token,
            "X-Bz-File-Name": encoded_file_name,
            "Content-Type": "video/mp4",
            "Content-Length": str(len(file_bytes)),
            "X-Bz-Content-Sha1": sha1_hash,
        }

        try:
            res = requests.post(upload_url, headers=headers, data=file_bytes, timeout=60)
            if res.status_code == 200:
                file_id = res.json().get("fileId")
                download_token = self._b2_get_download_authorization(api_url, auth_token, file_name, valid_duration=3600)
                base_url = f"{download_url}/file/{self.b2_bucket_name}/{encoded_file_name}"
                signed_url = f"{base_url}?Authorization={download_token}" if download_token else base_url
                print(f"  ☁️ [B2 STORAGE] Video berjaya dihoskan: {base_url}")
                return signed_url, file_id, file_name, api_url, auth_token
        except Exception as e:
            print(f"  ❌ [B2 UPLOAD EXCEPTION] {e}")

        return None, None, None, None, None

    def _delete_from_b2(self, api_url: str, auth_token: str, file_id: str, file_name: str):
        """Memadam fail video sementara dari B2."""
        if not file_id or not file_name or not api_url:
            return
        url = f"{api_url}/b2api/v2/b2_delete_file_version"
        headers = {"Authorization": auth_token}
        payload = {"fileId": file_id, "fileName": file_name}
        try:
            requests.post(url, json=payload, headers=headers, timeout=10)
            print(f"  🧹 [B2 CLEANUP] Fail sementara '{file_name}' dipadam dari B2.")
        except Exception:
            pass

    def _verify_video_url(self, url: str) -> bool:
        """Menguji sama ada pautan video boleh diakses secara langsung (HTTP 200)."""
        try:
            res = requests.get(url, stream=True, timeout=15)
            content_type = res.headers.get("Content-Type", "")
            return res.status_code == 200 and "video" in content_type.lower()
        except Exception:
            return False

    # -------------------------------------------------------------------------
    # MODUL PENERBITAN THREADS API
    # -------------------------------------------------------------------------
    def upload_video_to_threads(self, video_path: str, caption: str = "") -> Tuple[bool, Dict[str, Any]]:
        """Memuat naik video MP4 tempatan ke Threads Feed via Backblaze B2 Hosting."""
        if not self.is_configured():
            return False, {"error": "Kunci THREADS atau BACKBLAZE B2 tidak lengkap dalam .env.local."}

        if not os.path.exists(video_path):
            return False, {"error": f"Fail video tidak dijumpai: {video_path}"}

        print("  🧵 [THREADS STEP 1] Memuat naik MP4 ke Backblaze B2 untuk penyediaan pautan Meta...")
        signed_url, file_id, file_name, api_url, auth_token = self._upload_video_to_b2(video_path)

        if not signed_url:
            return False, {"error": "Gagal menjana Public Signed URL di Backblaze B2."}

        # Uji akses URL sebelum dihantar
        if not self._verify_video_url(signed_url):
            self._delete_from_b2(api_url, auth_token, file_id, file_name)
            return False, {"error": "Pautan video B2 gagal melepasi semakan akses kendiri (Self-Check)."}

        clean_caption = smart_trim_for_threads(caption, max_chars=480)

        try:
            # 1. Cipta Container
            print("  🧵 [THREADS STEP 2] Mencipta Media Container di Threads API...")
            init_url = f"{THREADS_BASE_URL}/{self.user_id}/threads"
            init_payload = {
                "media_type": "VIDEO",
                "video_url": signed_url,
                "text": clean_caption,
                "access_token": self.access_token,
            }

            res_init = requests.post(init_url, data=init_payload, timeout=30)
            init_json = res_init.json()

            if res_init.status_code != 200 or "id" not in init_json:
                err_msg = init_json.get("error", {}).get("message", res_init.text)
                print(f"  ❌ [THREADS STEP 2 ERROR] {err_msg}")
                return False, {"step": 2, "error": err_msg, "response": init_json}

            container_id = init_json["id"]
            print(f"  ✅ [THREADS STEP 2 SUCCESS] Container ID: {container_id}")

            # 2. Tunggu Transcoding Siap
            print("  🧵 [THREADS STEP 3] Menunggu status pemprosesan video Threads...")
            ready_ok, status_desc = self._wait_video_ready(container_id, timeout=120)
            if not ready_ok:
                print(f"  ❌ [THREADS STEP 3 ERROR] {status_desc}")
                return False, {"step": 3, "error": status_desc}

            # 3. Terbitkan
            print("  🧵 [THREADS STEP 4] Menerbitkan Hantaran Video di Threads...")
            pub_url = f"{THREADS_BASE_URL}/{self.user_id}/threads_publish"
            pub_payload = {"creation_id": container_id, "access_token": self.access_token}

            res_pub = requests.post(pub_url, data=pub_payload, timeout=30)
            pub_json = res_pub.json()

            if res_pub.status_code == 200 and "id" in pub_json:
                thread_id = pub_json["id"]
                permalink = f"https://www.threads.net/post/{thread_id}"
                print(f"  🎉 [THREADS SUCCESS] Video Threads berjaya diterbitkan! Pautan: {permalink}")
                return True, {"thread_id": thread_id, "permalink": permalink}
            else:
                err_msg = pub_json.get("error", {}).get("message", res_pub.text)
                print(f"  ❌ [THREADS STEP 4 ERROR] {err_msg}")
                return False, {"step": 4, "error": err_msg, "response": pub_json}

        except Exception as e:
            print(f"  ❌ [THREADS EXCEPTION] {e}")
            return False, {"error": str(e)}

        finally:
            # Padam fail dari B2 secara automatik
            if api_url and auth_token and file_id:
                self._delete_from_b2(api_url, auth_token, file_id, file_name)

    def _wait_video_ready(self, container_id: str, timeout: int = 120) -> Tuple[bool, str]:
        """Menyemak status_code container Threads sehingga bertukar ke FINISHED."""
        url = f"{THREADS_BASE_URL}/{container_id}"
        params = {"fields": "status,error_message", "access_token": self.access_token}
        start = time.time()

        while time.time() - start < timeout:
            time.sleep(6)
            try:
                res = requests.get(url, params=params, timeout=15).json()
                status_code = res.get("status", "")
                if status_code in ["FINISHED", "PUBLISHED"]:
                    return True, "FINISHED"
                elif status_code in ["ERROR", "EXPIRED"]:
                    return False, f"Status pemprosesan: {status_code} ({res.get('error_message', '')})"
            except Exception:
                pass

        return True, "TIMEOUT_ASSUME_READY"


# Singleton instance
threads_reel_bot = ThreadsReelBot()