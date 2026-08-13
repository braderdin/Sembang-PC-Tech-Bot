import os
import time
import random
import tempfile
import requests

# Menyokong MoviePy v2.x dan v1.x secara automatik
try:
    from moviepy import ImageClip, AudioFileClip, concatenate_videoclips
except ImportError:
    from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips

# Laluan folder audio tempatan di dalam projek
MUSIC_FOLDER_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "music")

def get_random_local_audio(duration=9):
    """
    Mengimbas folder assets/music dan memilih satu fail audio/video secara rawak.
    """
    if not os.path.exists(MUSIC_FOLDER_PATH):
        os.makedirs(MUSIC_FOLDER_PATH, exist_ok=True)
        return None, None

    audio_files = [
        f for f in os.listdir(MUSIC_FOLDER_PATH) 
        if f.lower().endswith(('.mp3', '.wav', '.m4a', '.mp4'))
    ]

    if not audio_files:
        return None, None

    selected_song = random.choice(audio_files)
    song_path = os.path.join(MUSIC_FOLDER_PATH, selected_song)

    try:
        audio_clip = AudioFileClip(song_path)
        start_time = random.randint(0, max(0, int(audio_clip.duration) - duration - 2)) if audio_clip.duration > duration + 5 else 0
        end_time = start_time + duration

        if hasattr(audio_clip, "subclipped"):
            audio_clip = audio_clip.subclipped(start_time, end_time)
        else:
            audio_clip = audio_clip.subclip(start_time, end_time)

        return audio_clip, song_path
    except Exception as e:
        print(f"⚠️ [LIFESTYLE REEL AUDIO ERROR] Gagal memuatkan fail audio '{selected_song}': {e}")
        return None, None

def convert_multiple_images_to_reel_video(image_urls, total_duration=9):
    """
    Muat turun 3 gambar Unsplash dan tukarkan menjadi video slideshow MP4 berdurasi 9 saat
    berserta lagu latar tempatan dari assets/music.
    """
    if not image_urls:
        return None

    temp_image_paths = []
    video_clips = []
    
    # Hitung durasi setiap gambar (contoh: 9 saat / 3 gambar = 3 saat per gambar)
    clip_duration = total_duration / len(image_urls)

    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        
        # 1. Muat turun setiap gambar ke fail sementara
        for url in image_urls:
            res = requests.get(url, headers=headers, timeout=15)
            if res.status_code == 200 and len(res.content) > 500:
                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp_img:
                    temp_img.write(res.content)
                    temp_image_paths.append(temp_img.name)

        if not temp_image_paths:
            print("❌ [LIFESTYLE REEL DEBUG] Gagal muat turun gambar Unsplash.")
            return None

        # 2. Bina ImageClip bagi setiap gambar
        for img_path in temp_image_paths:
            clip = ImageClip(img_path)
            if hasattr(clip, "with_duration"):
                clip = clip.with_duration(clip_duration)
            else:
                clip = clip.set_duration(clip_duration)
            video_clips.append(clip)

        # 3. Gabungkan klip-klip gambar menjadi 1 video
        final_video = concatenate_videoclips(video_clips, method="compose")

        # 4. Masukkan lagu dari assets/music secara dinamik
        audio_clip, song_path = get_random_local_audio(duration=total_duration)
        if audio_clip:
            if hasattr(final_video, "with_audio"):
                final_video = final_video.with_audio(audio_clip)
            else:
                final_video = final_video.set_audio(audio_clip)

        # 5. Render ke fail MP4 sementara
        temp_video_path = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
        final_video.write_videofile(
            temp_video_path,
            fps=24,
            codec="libx264",
            audio_codec="aac",
            logger=None
        )

        # Bersihkan memori dan fail sementara gambar
        final_video.close()
        for c in video_clips:
            c.close()
        if audio_clip:
            audio_clip.close()

        for path in temp_image_paths:
            if os.path.exists(path):
                os.remove(path)

        return temp_video_path

    except Exception as e:
        print(f"❌ [LIFESTYLE REEL DEBUG] Ralat bina video slideshow MP4: {e}")
        for path in temp_image_paths:
            if os.path.exists(path):
                os.remove(path)
        return None

def send_lifestyle_to_facebook_reel(page_id, page_token, caption, image_urls):
    """
    Memuat naik video slideshow lifestyle ke Facebook Reels via Meta Graph API.
    """
    if not page_id or not page_token:
        return False, "Kunci FACEBOOK_PAGE_ID atau FB_PAGE_ACCESS_TOKEN tidak dijumpai."

    graph_base_url = "https://graph.facebook.com/v19.0"

    print("  🎬 [LIFESTYLE REEL] Memulakan penukaran gambar Unsplash ke video slideshow MP4...")
    video_file_path = convert_multiple_images_to_reel_video(image_urls, total_duration=9)
    if not video_file_path or not os.path.exists(video_file_path):
        return False, "Gagal memproses gambar Unsplash menjadi video Reel MP4."

    file_size = os.path.getsize(video_file_path)
    print(f"  🎬 [LIFESTYLE REEL] Saiz video slideshow MP4: {file_size} bytes")

    try:
        # 1. Langkah A Meta API: Mula Sesi Upload Reel
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

        # 2. Langkah B Meta API: Upload Binary Video MP4
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

        # 3. Langkah C Meta API: Terbitkan Reel
        print("  🎬 [REEL STEP C] Menerbitkan Lifestyle Reel ke Facebook Page...")
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

        print(f"  ✅ [REEL STEP C SUCCESS] Facebook Lifestyle Reel berjaya diterbitkan! (Video ID: {video_id})")
        return True, {"video_id": video_id}

    except Exception as e:
        if os.path.exists(video_file_path):
            os.remove(video_file_path)
        print(f"❌ [REEL EXCEPTION] Ralat tidak dijangka: {str(e)}")
        return False, f"Ralat Rangkaian Facebook Reels API: {str(e)}"