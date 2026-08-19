#!/usr/bin/env python3
"""
Shopee Feed Auto-Poster: Step 3 (Bluesky Module)
Workflow Runner:
1. Read 'temp/shopee_payload.json'.
2. Authenticate with Bluesky AT-Protocol (createSession).
3. Download product image and upload blob to Bluesky PDS.
4. Parse UTF-8 byte facets for clickable affiliate links and hashtags.
5. Create post record (app.bsky.feed.post) with image embed.
6. Output 'POST ID :' and post URL for GitHub Actions tracking.
7. Update 'post_results.bluesky' inside 'temp/shopee_payload.json'.
"""

import os
import sys
import json
import time
import re
import requests
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

# 1. Konfigurasi Laluan Projek & Environment
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

env_local = PROJECT_ROOT / ".env.local"
if env_local.exists():
    load_dotenv(dotenv_path=env_local)
else:
    load_dotenv()

PAYLOAD_FILE = PROJECT_ROOT / "temp" / "shopee_payload.json"
BSKY_SERVICE_URL = "https://bsky.social"


def get_bluesky_credentials():
    """Membaca kelayakan Bluesky daripada persekitaran (env)."""
    handle = os.getenv("BLUESKY_HANDLE", "").strip()
    app_password = os.getenv("BLUESKY_APP_PASSWORD", "").strip()
    return handle, app_password


def create_bluesky_session(handle: str, app_password: str):
    """Mencipta sesi pengesahan AT-Protocol dan mendapatkan accessJwt serta DID."""
    url = f"{BSKY_SERVICE_URL}/xrpc/com.atproto.server.createSession"
    payload = {
        "identifier": handle,
        "password": app_password
    }
    try:
        res = requests.post(url, json=payload, timeout=20)
        if res.status_code == 200:
            return True, res.json()
        return False, f"HTTP {res.status_code}: {res.text}"
    except Exception as e:
        return False, f"Ralat sambungan login Bluesky: {str(e)}"


def upload_image_blob(access_jwt: str, image_url: str):
    """
    Memuat turun imej produk dan memuat naik sebagai Blob ke Bluesky.
    Memulangkan objek rujukan blob (blob ref).
    """
    # 1. Muat turun gambar binary
    img_bytes = None
    content_type = "image/jpeg"
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        res_dl = requests.get(image_url, headers=headers, timeout=15)
        if res_dl.status_code == 200 and len(res_dl.content) > 100:
            img_bytes = res_dl.content
            c_type = res_dl.headers.get("Content-Type", "")
            if "png" in c_type.lower():
                content_type = "image/png"
            elif "webp" in c_type.lower():
                content_type = "image/webp"
    except Exception as e:
        return False, f"Gagal muat turun gambar produk: {str(e)}"

    if not img_bytes:
        return False, "Data binary gambar kosong atau tidak sah."

    # Had saiz imej Bluesky = 1MB (1,000,000 bytes)
    if len(img_bytes) > 990000:
        print(f"⚠️ [BLUESKY WARN] Saiz imej ({len(img_bytes)} bytes) besar, memproses muat naik...")

    # 2. Muat naik Blob ke AT-Protocol
    upload_url = f"{BSKY_SERVICE_URL}/xrpc/com.atproto.repo.uploadBlob"
    headers = {
        "Authorization": f"Bearer {access_jwt}",
        "Content-Type": content_type
    }

    try:
        res_up = requests.post(upload_url, data=img_bytes, headers=headers, timeout=30)
        if res_up.status_code == 200:
            blob_data = res_up.json().get("blob")
            return True, blob_data
        return False, f"Gagal muat naik blob (HTTP {res_up.status_code}): {res_up.text}"
    except Exception as e:
        return False, f"Ralat rangkaian upload blob: {str(e)}"


def parse_bluesky_facets(text: str):
    """
    Mengekstrak pautan URL dan tanda pagar (#hashtag)
    serta mengira kedudukan indeks bait UTF-8 untuk pautan boleh klik di Bluesky.
    """
    facets = []
    text_bytes = text.encode("utf-8")

    # 1. Ekstrak URLs (Pautan Web / Shopee)
    url_pattern = re.compile(rb'https?://[^\s<>"]+|www\.[^\s<>"]+')
    for match in url_pattern.finditer(text_bytes):
        url_bytes = match.group(0)
        raw_url = url_bytes.decode("utf-8")
        full_url = raw_url if raw_url.startswith("http") else f"https://{raw_url}"
        facets.append({
            "index": {
                "byteStart": match.start(),
                "byteEnd": match.end()
            },
            "features": [{
                "$type": "app.bsky.richtext.facet#link",
                "uri": full_url
            }]
        })

    # 2. Ekstrak Hashtags (#tag)
    tag_pattern = re.compile(rb'#([a-zA-Z0-9_\u00C0-\u024F]+)')
    for match in tag_pattern.finditer(text_bytes):
        tag_text = match.group(1).decode("utf-8")
        facets.append({
            "index": {
                "byteStart": match.start(),
                "byteEnd": match.end()
            },
            "features": [{
                "$type": "app.bsky.richtext.facet#tag",
                "tag": tag_text
            }]
        })

    return facets


def post_to_bluesky_feed(handle: str, app_password: str, caption: str, image_url: str, product_name: str):
    """
    Menerbitkan hantaran bergambar ke Bluesky Feed lengkap dengan facets.
    """
    # 1. Login Sesi
    ok_session, session_data = create_bluesky_session(handle, app_password)
    if not ok_session:
        return False, f"Gagal log masuk ke Bluesky: {session_data}"

    access_jwt = session_data.get("accessJwt")
    user_did = session_data.get("did")

    # 2. Muat naik imej jika ada
    blob_ref = None
    if image_url and image_url.startswith("http"):
        print("🦋 [BLUESKY STEP A] Memuat naik imej ke Bluesky Blob Storage...")
        ok_blob, blob_result = upload_image_blob(access_jwt, image_url)
        if ok_blob:
            blob_ref = blob_result
            print("✅ [BLUESKY STEP A SUCCESS] Imej berjaya dimuat naik.")
        else:
            print(f"⚠️ [BLUESKY STEP A WARN] {blob_result}. Meneruskan hantaran tanpa imej...")

    # 3. Bina Facets & Struktur Rekod Pos
    facets = parse_bluesky_facets(caption)
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    record_payload = {
        "$type": "app.bsky.feed.post",
        "text": caption,
        "createdAt": created_at,
    }

    if facets:
        record_payload["facets"] = facets

    # Pasang lampiran imej ke dalam rekod
    if blob_ref:
        record_payload["embed"] = {
            "$type": "app.bsky.embed.images",
            "images": [
                {
                    "alt": f"Tawaran Shopee: {product_name[:60]}",
                    "image": blob_ref
                }
            ]
        }

    # 4. Cipta Rekod Hantaran (createRecord)
    print(f"🦋 [BLUESKY STEP B] Menerbitkan hantaran ke feed (Saiz: {len(caption)}/300 aksara)...")
    post_url = f"{BSKY_SERVICE_URL}/xrpc/com.atproto.repo.createRecord"
    headers = {
        "Authorization": f"Bearer {access_jwt}",
        "Content-Type": "application/json"
    }
    request_body = {
        "repo": user_did,
        "collection": "app.bsky.feed.post",
        "record": record_payload
    }

    try:
        res = requests.post(post_url, json=request_body, headers=headers, timeout=25)
        if res.status_code == 200:
            res_data = res.json()
            uri = res_data.get("uri", "")  # at://did:plc:.../app.bsky.feed.post/<rkey>
            rkey = uri.split("/")[-1] if "/" in uri else uri
            clean_handle = handle.replace("@", "")
            web_post_url = f"https://bsky.app/profile/{clean_handle}/post/{rkey}"

            return True, {
                "uri": uri,
                "rkey": rkey,
                "post_url": web_post_url
            }
        else:
            return False, f"HTTP {res.status_code} | {res.text}"
    except Exception as e:
        return False, f"Ralat rangkaian Bluesky createRecord: {str(e)}"


def run_bluesky_posting():
    print("\n" + "=" * 70)
    print("🦋 [START] MEMULAKAN HANTARAN SHOPEE KE BLUESKY FEED")
    print("=" * 70)

    # 1. Semak kewujudan fail payload
    if not PAYLOAD_FILE.exists():
        print(f"❌ [ABORT] Fail payload '{PAYLOAD_FILE}' tidak dijumpai. Sila jalankan penyediaan dahulu.")
        sys.exit(1)

    try:
        with open(PAYLOAD_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception as e:
        print(f"❌ [ABORT] Gagal membaca fail payload: {e}")
        sys.exit(1)

    handle, app_password = get_bluesky_credentials()
    if not handle or not app_password:
        print("⚠️ [BLUESKY SKIP] Kunci BLUESKY_HANDLE atau BLUESKY_APP_PASSWORD tiada dalam env. Langkau.")
        payload.setdefault("post_results", {})["bluesky"] = {
            "status": "failed",
            "error": "Konfigurasi handle/password Bluesky tidak lengkap."
        }
        with open(PAYLOAD_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return

    # 2. Dapatkan data hantaran dari payload
    caption = payload.get("ai_captions", {}).get("bluesky", "")
    image_url = payload.get("picture_url", "")
    product_name = payload.get("product_name", "Produk Shopee")

    print(f"📦 Produk : {product_name}")
    print(f"🖼️ Gambar : {image_url}")

    # 3. Lakukan hantaran ke Bluesky Feed
    ok, result = post_to_bluesky_feed(
        handle=handle,
        app_password=app_password,
        caption=caption,
        image_url=image_url,
        product_name=product_name
    )

    # 4. Kemas kini status hasil hantaran
    if ok:
        post_uri = result.get("uri")
        post_url = result.get("post_url")
        rkey = result.get("rkey")

        print(f"\n🎉 [BLUESKY SUCCESS] Hantaran berjaya dipos ke Bluesky Feed!")
        print(f"📌 POST ID : {rkey}")
        print(f"🔗 URL     : {post_url}")

        payload.setdefault("post_results", {})["bluesky"] = {
            "status": "success",
            "uri": post_uri,
            "post_id": rkey,
            "post_url": post_url
        }
    else:
        err_msg = str(result)
        print(f"\n❌ [BLUESKY FAILED] {err_msg}")
        payload.setdefault("post_results", {})["bluesky"] = {
            "status": "failed",
            "error": err_msg
        }

    # 5. Simpan kemas kini ke fail payload sementara
    with open(PAYLOAD_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"💾 [SAVED] Status Bluesky dikemas kini dalam payload.")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    run_bluesky_posting()