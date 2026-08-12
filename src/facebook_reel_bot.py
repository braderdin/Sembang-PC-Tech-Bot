import os
import time
import tempfile
import requests

# Menyokong MoviePy v2.x dan v1.x secara automatik
try:
    from moviepy import ImageClip
except ImportError:
    from moviepy.editor import ImageClip

def convert_image_to_reel_video(image_url, duration=6):
    """
    Muat turun gambar dan tukarkan menjadi fail video MP4 berdurasi 6 saat untuk Reels.
    """
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        res = requests.get(image_url, headers=headers, timeout=15)
        if res.status_code != 200 or len(res.content) < 100:
            print(f"❌ [REEL DEBUG] Gagal muat turun gambar: HTTP {res.status_code}")
            return None

        # Simpan gambar sementara
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp_img:
            temp_img.write(res.content)
            temp_img_path = temp_img.name

        # Bina video MP4 dari gambar
        temp_video_path = temp_img_path.replace(".jpg", ".mp4")
        clip = ImageClip(temp_img_path)
        
        # Penyesuaian sintaks durasi mengikut versi MoviePy
        if hasattr(clip, "with_duration"):
            clip = clip.with_duration(duration)
        else:
            clip = clip.set_duration(duration)

        clip.write_videofile(temp_video_path, fps=24, codec="libx264", audio=False, logger=None)
        clip.close()

        # Padam fail gambar sementara
        if os.path.exists(temp_img_path):
            os.remove(temp_img_path)

        return temp_video_path
    except Exception as e:
        print(f"❌ [REEL DEBUG] Ralat semasa proses penukaran gambar ke MP4: {e}")
        return None

def send_to_facebook_reel(page_id, page_token, caption, image_url, affiliate_link=""):
    """
    Memuat naik gambar produk sebagai Facebook Reel (via Meta Video Reels Publishing API).
    """
    if not page_id or not page_token:
        return False, "Kunci FACEBOOK_PAGE_ID atau FB_PAGE_ACCESS_TOKEN tidak dijumpai."

    graph_base_url = "https://graph.facebook.com/v19.0"

    print("  🎬 [REEL PROCESS] Memulakan penukaran gambar ke video MP4...")
    video_file_path = convert_image_to_reel_video(image_url, duration=6)
    if not video_file_path or not os.path.exists(video_file_path):
        return False, "Gagal memproses gambar produk menjadi video Reel MP4."

    file_size = os.path.getsize(video_file_path)
    print(f"  🎬 [REEL PROCESS] Saiz video MP4 dihasilkan: {file_size} bytes")

    try:
        # 1. Langkah A Meta API: Mula Sesi Upload Reel (upload_phase = start)
        print("  🎬 [REEL STEP A] Menghantar permintaan mula sesi (start phase)...")
        start_url = f"{graph_base_url}/{page_id}/video_reels"
        start_payload = {
            "upload_phase": "start",
            "access_token": page_token
        }
        res_start = requests.post(start_url, data=start_payload, timeout=20)
        start_json = res_start.json()

        if res_start.status_code != 200 or "video_id" not in start_json:
            error_details = f"HTTP {res_start.status_code} | Response: {res_start.text}"
            print(f"  ❌ [REEL STEP A ERROR] {error_details}")
            return False, f"Langkah A (Start) Gagal: {error_details}"

        video_id = start_json["video_id"]
        upload_url = start_json["upload_url"]
        print(f"  ✅ [REEL STEP A SUCCESS] Video ID: {video_id}")

        # 2. Langkah B Meta API: Upload Binary Video MP4 ke Server Meta dengan Pengepala offset yang Tepat
        print("  🎬 [REEL STEP B] Memuat naik data binary video ke Meta rupload server...")
        with open(video_file_path, "rb") as video_file:
            video_data = video_file.read()

        upload_headers = {
            "Authorization": f"OAuth {page_token}",
            "offset": "0",
            "file_size": str(file_size),
            "Content-Type": "application/octet-stream"
        }
        res_upload = requests.post(upload_url, headers=upload_headers, data=video_data, timeout=60)

        # Padam fail video sementara dari disk tempatan
        if os.path.exists(video_file_path):
            os.remove(video_file_path)

        if res_upload.status_code != 200:
            error_details = f"HTTP {res_upload.status_code} | Response: {res_upload.text}"
            print(f"  ❌ [REEL STEP B ERROR] {error_details}")
            return False, f"Langkah B (Binary Upload) Gagal: {error_details}"

        print("  ✅ [REEL STEP B SUCCESS] Muat naik binary video selesai!")

        # 3. Langkah C Meta API: Terbitkan Reel (upload_phase = finish)
        print("  🎬 [REEL STEP C] Menerbitkan Reel ke Facebook Page...")
        finish_payload = {
            "upload_phase": "finish",
            "video_id": video_id,
            "video_state": "PUBLISHED",
            "description": caption,
            "access_token": page_token
        }
        res_finish = requests.post(start_url, data=finish_payload, timeout=20)
        finish_json = res_finish.json()

        if res_finish.status_code != 200 or not finish_json.get("success", False):
            error_details = f"HTTP {res_finish.status_code} | Response: {res_finish.text}"
            print(f"  ❌ [REEL STEP C ERROR] {error_details}")
            return False, f"Langkah C (Finish/Publish) Gagal: {error_details}"

        print(f"  ✅ [REEL STEP C SUCCESS] Facebook Reel berjaya diterbitkan! (Video ID: {video_id})")

        # 4. Masukkan Pautan Affiliate ke Komen Facebook Reel
        clean_link = str(affiliate_link or "").strip()
        if clean_link:
            print("  🎬 [REEL STEP D] Menambah komen pautan affiliate...")
            time.sleep(3)  # Tunggu 3 saat untuk memastikan video sedia menerima komen
            comment_url = f"{graph_base_url}/{video_id}/comments"
            comment_text = f"🛒 Dapatkan produk dalam Reel ini di Lazada sekarang👇\n{clean_link}"
            comment_payload = {
                "message": comment_text,
                "access_token": page_token
            }
            res_comment = requests.post(comment_url, data=comment_payload, timeout=20)
            comment_json = res_comment.json()

            if res_comment.status_code == 200 and "id" in comment_json:
                print("  ✅ [REEL STEP D SUCCESS] Komen pautan affiliate berjaya ditambah!")
                return True, {"video_id": video_id, "comment_id": comment_json.get("id")}
            else:
                print(f"  ⚠️ [REEL STEP D WARN] Reel terbit tetapi gagal komen: {res_comment.text}")
                return True, {"video_id": video_id, "comment_error": res_comment.text}
        else:
            return True, {"video_id": video_id, "comment_id": None}

    except Exception as e:
        if os.path.exists(video_file_path):
            os.remove(video_file_path)
        print(f"❌ [REEL EXCEPTION] Ralat tidak dijangka: {str(e)}")
        return False, f"Ralat Rangkaian Facebook Reels API: {str(e)}"