#!/usr/bin/env python3
"""
Lazada Feed Auto-Poster: Step 3 (Facebook Module)
Workflow Runner:
1. Read 'temp/lazada_payload.json'.
2. Post product image + Facebook AI caption to Facebook Page Feed.
3. Automatically post the official Lazada affiliate link into the 1st comment.
4. Output 'POST ID :' for GitHub Actions tracking and debugging.
5. Update 'post_results.facebook' inside 'temp/lazada_payload.json'.
"""

import os
import sys
import json
import time
import requests
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

PAYLOAD_FILE = PROJECT_ROOT / "temp" / "lazada_payload.json"
GRAPH_BASE_URL = "https://graph.facebook.com/v19.0"


def get_facebook_credentials():
    """Membaca kelayakan Facebook Page secara dinamik daripada persekitaran."""
    page_id = (
        os.getenv("FACEBOOK_PAGE_ID", "").strip()
        or os.getenv("META_PAGE_ID", "").strip()
    )
    page_token = (
        os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN", "").strip()
        or os.getenv("FB_PAGE_ACCESS_TOKEN", "").strip()
        or os.getenv("META_PAGE_ACCESS_TOKEN", "").strip()
    )
    return page_id, page_token


def post_to_facebook_page(page_id: str, page_token: str, caption: str, image_url: str, affiliate_link: str):
    """
    Memuat naik gambar dan teks ke Facebook Page Feed,
    diikuti dengan menghantar pautan Lazada ke ruangan komen pertama.
    """
    if not page_id or not page_token:
        return False, "Kunci FACEBOOK_PAGE_ID atau FB_PAGE_ACCESS_TOKEN tidak dijumpai."

    if not image_url:
        return False, "Tiada URL gambar yang sah disediakan."

    # 1. Muat turun fail binary imej
    img_bytes = None
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        res_dl = requests.get(image_url, headers=headers, timeout=15)
        if res_dl.status_code == 200 and len(res_dl.content) > 100:
            img_bytes = res_dl.content
    except Exception as e:
        print(f"⚠️ [FB WARN] Gagal muat turun gambar binary: {e}")

    photo_url = f"{GRAPH_BASE_URL}/{page_id}/photos"
    target_post_id = None
    last_err_msg = ""

    # 2. Muat naik gambar ke Facebook Feed (Percubaan Auto-Retry jika pelayan sibuk)
    for attempt in range(2):
        try:
            if img_bytes:
                files = {"source": ("lazada_product.jpg", img_bytes, "image/jpeg")}
                photo_payload = {
                    "caption": caption,
                    "published": "true",
                    "access_token": page_token
                }
                res_photo = requests.post(photo_url, data=photo_payload, files=files, timeout=30)
            else:
                photo_payload = {
                    "url": image_url,
                    "caption": caption,
                    "published": "true",
                    "access_token": page_token
                }
                res_photo = requests.post(photo_url, data=photo_payload, timeout=25)

            try:
                photo_json = res_photo.json()
            except Exception:
                photo_json = {}

            if res_photo.status_code == 200 and ("id" in photo_json or "post_id" in photo_json):
                target_post_id = photo_json.get("post_id") or photo_json.get("id")
                break
            else:
                err = photo_json.get("error", {})
                last_err_msg = err.get("message", res_photo.text)
                if attempt == 0:
                    print(f"⚠️ [FB FEED RETRY] Percubaan 1 gagal ({last_err_msg[:60]}...). Menunggu 3 saat...")
                    time.sleep(3)
                    img_bytes = None  # Gunakan kaedah URL terus untuk percubaan kedua
                else:
                    return False, f"Gagal muat naik gambar FB: {last_err_msg}"

        except Exception as e:
            last_err_msg = str(e)
            if attempt == 0:
                time.sleep(3)
            else:
                return False, f"Ralat sambungan Facebook API: {last_err_msg}"

    if not target_post_id:
        return False, f"Tiada Post ID diterima dari Facebook: {last_err_msg}"

    # 3. Masukkan Pautan Affiliate Lazada ke Ruangan Komen Pertama
    clean_link = str(affiliate_link or "").strip()
    comment_id = None
    if clean_link and target_post_id:
        try:
            comment_url = f"{GRAPH_BASE_URL}/{target_post_id}/comments"
            comment_text = f"🛒 Dapatkan di Lazada sekarang👇\n{clean_link}"
            comment_payload = {
                "message": comment_text,
                "access_token": page_token
            }
            res_comment = requests.post(comment_url, data=comment_payload, timeout=20)
            comment_json = res_comment.json()

            if res_comment.status_code == 200 and "id" in comment_json:
                comment_id = comment_json.get("id")
            else:
                print(f"⚠️ [FB COMMENT WARN] Gambar dipos tetapi gagal meletakkan komen: {res_comment.text}")
        except Exception as e:
            print(f"⚠️ [FB COMMENT EXCEPTION] Gagal hantar komen: {e}")

    fb_post_url = f"https://www.facebook.com/{target_post_id}"
    return True, {
        "post_id": target_post_id,
        "comment_id": comment_id,
        "post_url": fb_post_url
    }


def run_facebook_posting():
    print("\n" + "=" * 70)
    print("📘 [START] MEMULAKAN HANTARAN LAZADA KE FACEBOOK PAGE FEED")
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

    page_id, page_token = get_facebook_credentials()
    if not page_id or not page_token:
        print("⚠️ [FB SKIP] Kunci FACEBOOK_PAGE_ID atau FACEBOOK_PAGE_ACCESS_TOKEN tiada dalam env. Langkau.")
        payload.setdefault("post_results", {})["facebook"] = {
            "status": "failed",
            "error": "Konfigurasi token/Page ID Facebook tidak lengkap."
        }
        with open(PAYLOAD_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return

    # 2. Dapatkan data hantaran dari payload
    caption = payload.get("ai_captions", {}).get("facebook", "")
    image_url = payload.get("picture_url") or payload.get("image_url", "")
    affiliate_link = payload.get("affiliate_link", "")
    product_name = payload.get("product_name") or payload.get("title", "Produk Lazada")

    print(f"📦 Produk : {product_name}")
    print(f"🖼️ Gambar : {image_url}")

    # 3. Lakukan hantaran ke Facebook Feed
    ok, result = post_to_facebook_page(
        page_id=page_id,
        page_token=page_token,
        caption=caption,
        image_url=image_url,
        affiliate_link=affiliate_link
    )

    # 4. Kemas kini status hasil hantaran
    if ok:
        post_id = result.get("post_id")
        post_url = result.get("post_url")
        comment_id = result.get("comment_id")

        print(f"\n🎉 [FACEBOOK SUCCESS] Hantaran berjaya dipos ke Facebook Page!")
        print(f"📌 POST ID : {post_id}")
        print(f"🔗 URL     : {post_url}")
        if comment_id:
            print(f"💬 Komen ID: {comment_id}")

        payload.setdefault("post_results", {})["facebook"] = {
            "status": "success",
            "post_id": post_id,
            "comment_id": comment_id,
            "post_url": post_url
        }
    else:
        err_msg = str(result)
        print(f"\n❌ [FACEBOOK FAILED] {err_msg}")
        payload.setdefault("post_results", {})["facebook"] = {
            "status": "failed",
            "error": err_msg
        }

    # 5. Simpan kemas kini ke fail payload sementara
    with open(PAYLOAD_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"💾 [SAVED] Status Facebook dikemas kini dalam payload.")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    run_facebook_posting()