import requests

def send_to_facebook_page(page_id, page_token, caption, image_url, affiliate_link=""):
    """
    Menghantar gambar + caption ke Facebook Page Feed, dan meletakkan link affiliate di ruangan komen.
    """
    if not page_id or not page_token:
        return False, "Kunci FACEBOOK_PAGE_ID atau FB_PAGE_ACCESS_TOKEN tidak dijumpai."

    graph_base_url = "https://graph.facebook.com/v19.0"

    # Muat turun gambar ke memori
    img_bytes = None
    if image_url:
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            res = requests.get(image_url, headers=headers, timeout=15)
            if res.status_code == 200 and len(res.content) > 100:
                img_bytes = res.content
        except Exception as e:
            print(f"⚠️ [FB WARN] Gagal muat turun gambar binary: {e}")

    photo_url = f"{graph_base_url}/{page_id}/photos"
    
    try:
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
                "url": image_url,
                "caption": caption,
                "published": "true",
                "access_token": page_token
            }
            res_photo = requests.post(photo_url, data=photo_payload, timeout=25)

        photo_json = res_photo.json()

        if res_photo.status_code != 200 or ("id" not in photo_json and "post_id" not in photo_json):
            err = photo_json.get("error", {})
            return False, f"Gagal muat naik gambar FB: {err.get('message', res_photo.text)}"

        target_post_id = photo_json.get("post_id") or photo_json.get("id")

        # Masukkan pautan affiliate ke ruangan komen
        clean_link = str(affiliate_link or "").strip()
        if clean_link:
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