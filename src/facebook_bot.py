import json
import time
import requests

def send_to_facebook_page(page_id, page_token, caption, image_url=None, affiliate_link="", image_urls=None):
    """
    Menghantar gambar (tunggal atau multi-gambar album) + caption ke Facebook Page Feed,
    dan meletakkan link affiliate di ruangan komen jika disediakan.
    Dilengkapi Auto-Retry 3 Saat untuk mengelakkan ralat 'reduce amount of data'.
    """
    if not page_id or not page_token:
        return False, "Kunci FACEBOOK_PAGE_ID atau FB_PAGE_ACCESS_TOKEN tidak dijumpai."

    graph_base_url = "https://graph.facebook.com/v19.0"

    all_urls = []
    if image_urls and isinstance(image_urls, list):
        all_urls = [u for u in image_urls if u]
    elif isinstance(image_url, list):
        all_urls = [u for u in image_url if u]
    elif image_url:
        all_urls = [image_url]

    if not all_urls:
        return False, "Tiada URL gambar yang sah disediakan."

    try:
        # =====================================================================
        # KES A: MULTI-GAMBAR (> 1 GAMBAR) -> MULTI-PHOTO ALBUM POST
        # =====================================================================
        if len(all_urls) > 1:
            media_ids = []
            photo_upload_url = f"{graph_base_url}/{page_id}/photos"

            for idx, u in enumerate(all_urls):
                img_bytes = None
                try:
                    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                    res_dl = requests.get(u, headers=headers, timeout=15)
                    if res_dl.status_code == 200 and len(res_dl.content) > 100:
                        img_bytes = res_dl.content
                except Exception as e:
                    print(f"⚠️ [FB MULTI-PHOTO WARN] Gagal muat turun gambar {idx+1}: {e}")

                if img_bytes:
                    files = {"source": (f"photo_{idx+1}.jpg", img_bytes, "image/jpeg")}
                    payload = {
                        "published": "false",
                        "access_token": page_token
                    }
                    res_up = requests.post(photo_upload_url, data=payload, files=files, timeout=30)
                else:
                    payload = {
                        "url": u,
                        "published": "false",
                        "access_token": page_token
                    }
                    res_up = requests.post(photo_upload_url, data=payload, timeout=25)

                if res_up.status_code == 200:
                    data_up = res_up.json()
                    p_id = data_up.get("id")
                    if p_id:
                        media_ids.append(p_id)
                else:
                    print(f"⚠️ [FB PHOTO UPLOAD WARN] Gagal upload photo {idx+1}: {res_up.text}")

            if not media_ids:
                return False, "Gagal memuat naik gambar-gambar untuk album Facebook."

            feed_url = f"{graph_base_url}/{page_id}/feed"
            attached_media_list = [{"media_fbid": str(mid)} for mid in media_ids]
            feed_payload = {
                "message": caption,
                "attached_media": json.dumps(attached_media_list),
                "access_token": page_token
            }
            res_feed = requests.post(feed_url, data=feed_payload, timeout=30)
            feed_json = res_feed.json()

            if res_feed.status_code != 200 or "id" not in feed_json:
                err = feed_json.get("error", {})
                return False, f"Gagal menerbitkan multi-photo album FB: {err.get('message', res_feed.text)}"

            target_post_id = feed_json.get("id")

        # =====================================================================
        # KES B: 1 GAMBAR TUNGGAL (DENGAN AUTO-RETRY KESESAKAN FB)
        # =====================================================================
        else:
            single_url = all_urls[0]
            img_bytes = None
            try:
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                res = requests.get(single_url, headers=headers, timeout=15)
                if res.status_code == 200 and len(res.content) > 100:
                    img_bytes = res.content
            except Exception as e:
                print(f"⚠️ [FB WARN] Gagal muat turun gambar binary: {e}")

            photo_url = f"{graph_base_url}/{page_id}/photos"
            target_post_id = None
            last_err_msg = ""

            for attempt in range(2):
                if img_bytes:
                    files = {"source": ("product.jpg", img_bytes, "image/jpeg")}
                    photo_payload = {
                        "caption": caption,
                        "published": "true",
                        "access_token": page_token
                    }
                    res_photo = requests.post(photo_url, data=photo_payload, files=files, timeout=30)
                else:
                    photo_payload = {
                        "url": single_url,
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
                    last_err_msg = err.get('message', res_photo.text)
                    if attempt == 0:
                        print(f"⚠️ [FB FEED RETRY] Percubaan 1 gagal ({last_err_msg[:60]}...). Menunggu 3 saat...")
                        time.sleep(3)
                        # Percubaan kedua guna kaedah URL terus untuk jimat bandwidth
                        img_bytes = None
                    else:
                        return False, f"Gagal muat naik gambar FB: {last_err_msg}"

        # Masukkan pautan affiliate ke ruangan komen jika disediakan
        clean_link = str(affiliate_link or "").strip()
        if clean_link and target_post_id:
            comment_url = f"{graph_base_url}/{target_post_id}/comments"
            comment_text = f"🛒 Dapatkan di Lazada sekarang👇\n{clean_link}"
            comment_payload = {
                "message": comment_text,
                "access_token": page_token
            }
            res_comment = requests.post(comment_url, data=comment_payload, timeout=20)
            comment_json = res_comment.json()

            if res_comment.status_code == 200 and "id" in comment_json:
                return True, {"post_id": target_post_id, "comment_id": comment_json.get("id")}
            else:
                return False, f"Gambar dipos, tetapi gagal komen: {res_comment.text}"
        else:
            return True, {"post_id": target_post_id, "comment_id": None}

    except Exception as e:
        return False, f"Ralat Rangkaian Facebook API: {str(e)}"