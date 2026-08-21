#!/usr/bin/env python3
"""
Shopee Feed Auto-Poster: Step 3 (Instagram Module via Backblaze B2 Bridge)
Lokasi Fail: bin/run_shopee_post_instagram.py

Aliran Kerja (Workflow Runner):
1. Membaca fail 'temp/shopee_payload.json'.
2. Memuat naik fail imej Shopee ke Backblaze B2 Private Bucket dan menjana Signed Public URL
   melalui enjin 'src/shopee_instagram_b2_image_bridge.py' bagi melepasi sekatan WAF/Geo-block CDN Shopee.
3. Mencipta Instagram Single-Photo Media Container via Meta Graph API menggunakan Signed URL B2.
4. Menunggu pemprosesan container menjadi FINISHED.
5. Menerbitkan container ke suapan profil Instagram Professional.
6. Enjin Pemulihan Kendiri (Self-Healing): Mengesan pos jika Meta memulangkan ralat transient.
7. Memadam fail imej daripada Backblaze B2 di dalam blok 'finally' untuk mengekalkan storan 0 MB.
8. Mengemas kini status hantaran ke 'post_results.instagram' dalam 'temp/shopee_payload.json'.
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

# 2. Import Modul Jambatan B2 dari src/
from src.shopee_instagram_b2_image_bridge import shopee_b2_bridge

PAYLOAD_FILE = PROJECT_ROOT / "temp" / "shopee_payload.json"
GRAPH_BASE_URL = "https://graph.facebook.com/v19.0"


def get_instagram_credentials():
    """Membaca kelayakan Instagram Business/Professional daripada persekitaran."""
    account_id = os.getenv("INSTAGRAM_ACCOUNT_ID", "").strip()
    access_token = (
        os.getenv("INSTAGRAM_ACCESS_TOKEN", "").strip()
        or os.getenv("META_PAGE_ACCESS_TOKEN", "").strip()
        or os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN", "").strip()
    )
    return account_id, access_token


def wait_for_container_ready(creation_id: str, access_token: str, timeout: int = 30) -> str:
    """
    Menunggu sehingga Meta selesai memproses dan mengoptimumkan imej
    di pelayan CDN sebelum membenarkan penerbitan container.
    Memulangkan status akhir: 'FINISHED', 'PUBLISHED', atau 'ERROR'.
    """
    url = f"{GRAPH_BASE_URL}/{creation_id}"
    params = {"fields": "status_code", "access_token": access_token}
    start_time = time.time()

    while time.time() - start_time < timeout:
        time.sleep(3)
        try:
            res = requests.get(url, params=params, timeout=10)
            if res.status_code == 200:
                status = res.json().get("status_code", "").upper()
                if status in ["FINISHED", "PUBLISHED"]:
                    return status
                elif status in ["ERROR", "EXPIRED"]:
                    print(f"⚠️ [IG CONTAINER ERROR] Status Container: {status}")
                    return status
        except Exception:
            pass

    return "FINISHED"


def get_instagram_permalink(media_id: str, access_token: str) -> str:
    """Mendapatkan pautan terus (permalink) hantaran Instagram rasmi."""
    url = f"{GRAPH_BASE_URL}/{media_id}"
    params = {"fields": "permalink", "access_token": access_token}
    try:
        res = requests.get(url, params=params, timeout=10)
        if res.status_code == 200:
            return res.json().get("permalink", f"https://www.instagram.com/p/{media_id}/")
    except Exception:
        pass
    return f"https://www.instagram.com/p/{media_id}/"


def check_recent_published_post(account_id: str, access_token: str, match_caption: str):
    """
    Enjin Pengesanan Kendiri (Self-Healing Recovery):
    Menyemak 3 media terkini di akaun Instagram untuk memastikan sama ada
    hantaran telah berjaya diterbitkan sekiranya Meta API mengembalikan ralat transient.
    """
    url = f"{GRAPH_BASE_URL}/{account_id}/media"
    params = {
        "fields": "id,caption,permalink,timestamp",
        "limit": 3,
        "access_token": access_token
    }
    try:
        res = requests.get(url, params=params, timeout=15)
        if res.status_code == 200:
            data = res.json().get("data", [])
            clean_needle = match_caption.strip()[:40].lower() if match_caption else ""

            for item in data:
                item_caption = str(item.get("caption", "")).strip().lower()
                if clean_needle and clean_needle in item_caption:
                    media_id = item.get("id")
                    permalink = item.get("permalink") or f"https://www.instagram.com/p/{media_id}/"
                    return True, media_id, permalink
    except Exception as e:
        print(f"⚠️ [IG RECOVERY WARN] Ralat semasa semakan pemulihan: {e}")

    return False, None, None


def post_to_instagram_feed(account_id: str, access_token: str, caption: str, image_url: str, product_id: str = ""):
    """
    Menerbitkan gambar ke Instagram Feed menggunakan aliran Backblaze B2 Bridge -> Meta Container -> Publish
    lengkap dengan pembersihan automatik fail storan B2 di dalam blok finally.
    """
    if not account_id or not access_token:
        return False, "Kunci INSTAGRAM_ACCOUNT_ID atau INSTAGRAM_ACCESS_TOKEN tidak dijumpai."

    if not image_url or not image_url.startswith("http"):
        return False, "URL gambar tidak sah atau tidak boleh diakses."

    target_image_url = image_url
    bridge_data = None

    # =========================================================================
    # LANGKAH 0: AKTIFKAN BACKBLAZE B2 IMAGE BRIDGE
    # =========================================================================
    if shopee_b2_bridge.is_configured():
        print("🌉 [IG B2 BRIDGE] Mengaktifkan Jambatan Backblaze B2 untuk memintas sekatan CDN Shopee...")
        ok_bridge, b2_payload, b2_msg = shopee_b2_bridge.upload_shopee_image_to_b2(
            image_url=image_url, product_id=product_id
        )
        if ok_bridge and b2_payload:
            bridge_data = b2_payload
            target_image_url = b2_payload.get("signed_url") or image_url
            print(f"✅ [IG B2 BRIDGE SUCCESS] Meta akan merayap imej melalui Signed B2 Storage.")
        else:
            print(f"⚠️ [IG B2 BRIDGE WARN] {b2_msg}. Mencuba URL asal sebagai sandaran...")
    else:
        print("⚠️ [IG B2 BRIDGE SKIP] Kunci Backblaze B2 tidak lengkap. Menggunakan URL CDN terus.")

    try:
        # =====================================================================
        # LANGKAH 1: Cipta Media Container di Instagram API (Auto-Retry 2x)
        # =====================================================================
        print(f"📸 [IG STEP A] Membina Media Container Instagram (Panjang Teks: {len(caption)} aksara)...")
        container_url = f"{GRAPH_BASE_URL}/{account_id}/media"
        container_payload = {
            "image_url": target_image_url,
            "caption": caption,
            "access_token": access_token
        }

        creation_id = None
        last_err_a = ""

        for attempt in range(2):
            res_container = requests.post(container_url, data=container_payload, timeout=30)
            try:
                container_json = res_container.json()
            except Exception:
                container_json = {}

            if res_container.status_code == 200 and "id" in container_json:
                creation_id = container_json["id"]
                print(f"✅ [IG STEP A SUCCESS] Container ID: {creation_id}")
                break
            else:
                err = container_json.get("error", {})
                last_err_a = err.get("message", res_container.text)
                if attempt == 0:
                    print(f"⚠️ [IG STEP A RETRY] Percubaan 1 gagal ({last_err_a[:60]}...). Menunggu 3 saat...")
                    time.sleep(3)
                else:
                    return False, f"Langkah A Gagal: {last_err_a}"

        # Tunggu sehingga fail imej siap diproses di CDN Meta
        status = wait_for_container_ready(creation_id, access_token, timeout=25)
        if status == "ERROR":
            return False, "Meta gagal memproses fail imej (Status Container: ERROR)."

        # Beri jeda 3 saat bagi mengelakkan ralat burst limit Meta
        time.sleep(3)

        # =====================================================================
        # LANGKAH 2: Terbitkan Media Container ke Instagram Feed
        # =====================================================================
        print("📸 [IG STEP B] Menerbitkan hantaran ke akaun Instagram...")
        publish_url = f"{GRAPH_BASE_URL}/{account_id}/media_publish"
        publish_payload = {
            "creation_id": creation_id,
            "access_token": access_token
        }

        res_publish = requests.post(publish_url, data=publish_payload, timeout=30)
        publish_json = res_publish.json()

        if res_publish.status_code == 200 and "id" in publish_json:
            media_id = publish_json["id"]
            permalink = get_instagram_permalink(media_id, access_token)
            return True, {
                "media_id": media_id,
                "permalink": permalink,
                "post_url": permalink
            }

        # Jika Langkah B memberi ralat transient, lakukan Self-Healing Verification
        err = publish_json.get("error", {})
        err_msg = err.get("message", res_publish.text)
        print(f"⚠️ [IG PUBLISH NOTICE] Respon Meta: {err_msg}. Menyemak status penerbitan sebenar di profil...")

        time.sleep(3)
        is_found, rec_id, rec_permalink = check_recent_published_post(account_id, access_token, caption)
        if is_found:
            print(f"🎉 [IG AUTO-RECOVERY SUCCESS] Hantaran disahkan wujud dan berjaya diterbitkan di Instagram!")
            return True, {
                "media_id": rec_id,
                "permalink": rec_permalink,
                "post_url": rec_permalink
            }

        return False, f"Langkah B Gagal: {err_msg}"

    except Exception as e:
        return False, f"Ralat Rangkaian Instagram API: {str(e)}"

    finally:
        # =====================================================================
        # PEMBERSIHAN AUTOMATIK FAIL STORAN BACKBLAZE B2
        # =====================================================================
        if bridge_data:
            shopee_b2_bridge.cleanup_bridge(bridge_data)


def run_instagram_posting():
    print("\n" + "=" * 70)
    print("📸 [START] MEMULAKAN HANTARAN SHOPEE KE INSTAGRAM FEED")
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

    account_id, access_token = get_instagram_credentials()
    if not account_id or not access_token:
        print("⚠️ [IG SKIP] Kunci INSTAGRAM_ACCOUNT_ID atau INSTAGRAM_ACCESS_TOKEN tiada dalam env. Langkau.")
        payload.setdefault("post_results", {})["instagram"] = {
            "status": "failed",
            "error": "Konfigurasi token/Account ID Instagram tidak lengkap."
        }
        with open(PAYLOAD_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return

    # 2. Dapatkan data hantaran dari payload
    caption = payload.get("ai_captions", {}).get("instagram", "")
    image_url = (
        payload.get("picture_url")
        or payload.get("shopee_picture_url")
        or payload.get("image_url", "")
    )
    product_name = (
        payload.get("product_name")
        or payload.get("shopee_product_name")
        or payload.get("title", "Produk Shopee")
    )
    product_id = str(
        payload.get("product_id")
        or payload.get("shopee_product_id")
        or ""
    ).strip()

    print(f"📦 Produk : {product_name} (ID: {product_id})")
    print(f"🖼️ Gambar : {image_url}")

    # 3. Lakukan hantaran ke Instagram Feed melalui B2 Bridge
    ok, result = post_to_instagram_feed(
        account_id=account_id,
        access_token=access_token,
        caption=caption,
        image_url=image_url,
        product_id=product_id
    )

    # 4. Kemas kini status hasil hantaran
    if ok:
        media_id = result.get("media_id")
        permalink = result.get("permalink")

        print(f"\n🎉 [INSTAGRAM SUCCESS] Hantaran berjaya dipos ke Instagram Feed!")
        print(f"📌 POST ID : {media_id}")
        print(f"🔗 URL     : {permalink}")

        payload.setdefault("post_results", {})["instagram"] = {
            "status": "success",
            "post_id": media_id,
            "permalink": permalink,
            "post_url": permalink
        }
    else:
        err_msg = str(result)
        print(f"\n❌ [INSTAGRAM FAILED] {err_msg}")
        payload.setdefault("post_results", {})["instagram"] = {
            "status": "failed",
            "error": err_msg
        }

    # 5. Simpan kemas kini ke fail payload sementara
    with open(PAYLOAD_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"💾 [SAVED] Status Instagram dikemas kini dalam payload.")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    run_instagram_posting()