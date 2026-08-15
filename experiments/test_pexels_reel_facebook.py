#!/usr/bin/env python3
"""
🧪 EKSPERIMEN: Pexels 9:16 Video Reel Generator & Facebook Reels Publisher
Lokasi: experiments/test_pexels_reel_facebook.py
Ciri-ciri:
1. 1 Permintaan API Pexels untuk 3 video vertikal (9:16) bertema serupa.
2. Cantum 3 klip video (durasi 20–30 saat) + Audio latar tempatan.
3. Muat naik ke Facebook Reels (Meta Graph API) dengan laporan diagnostik ralat penuh.
"""

import os
import sys
import time
import random
import tempfile
import requests
from pathlib import Path
from dotenv import load_dotenv

# MoviePy v1.x & v2.x Compatibility Layer
try:
    from moviepy import VideoFileClip, AudioFileClip, concatenate_videoclips
except ImportError:
    from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips

# Masukkan Project Root ke sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Baca .env.local secara dinamik
env_local = PROJECT_ROOT / ".env.local"
if env_local.exists():
    load_dotenv(dotenv_path=env_local)
else:
    load_dotenv()

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "").strip()
FACEBOOK_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID", "").strip() or os.getenv("META_PAGE_ID", "").strip()
FACEBOOK_PAGE_TOKEN = (
    os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN", "").strip()
    or os.getenv("FB_PAGE_ACCESS_TOKEN", "").strip()
    or os.getenv("META_PAGE_ACCESS_TOKEN", "").strip()
)
MUSIC_FOLDER = PROJECT_ROOT / "assets" / "music"


def fetch_pexels_vertical_videos(query: str, count: int = 3):
    """
    Menghantar 1 permintaan API ke Pexels untuk mendapatkan video berkualiti tinggi 9:16 (Portrait).
    """
    print(f"\n📡 [PEXELS API] Menghantar 1 request carian video: '{query}' (Orientation: Portrait)...")
    
    if not PEXELS_API_KEY:
        print("❌ [PEXELS ERROR] Kunci 'PEXELS_API_KEY' tidak dijumpai dalam .env.local!")
        return []

    url = "https://api.pexels.com/videos/search"
    headers = {"Authorization": PEXELS_API_KEY}
    params = {
        "query": query,
        "orientation": "portrait",
        "per_page": count + 3,  # Ambil lebihan sedikit sebagai sandaran
        "size": "medium"
    }

    try:
        res = requests.get(url, headers=headers, params=params, timeout=20)
        print(f"  ℹ️ Status Pexels API: HTTP {res.status_code}")
        
        if res.status_code != 200:
            print(f"  ❌ [PEXELS ERROR RESPONSE] {res.text}")
            return []

        data = res.json()
        videos = data.get("videos", [])
        print(f"  ✅ Ditemui {len(videos)} calon video dari Pexels.")

        selected_download_links = []
        for vid in videos:
            files = vid.get("video_files", [])
            # Cari fail video MP4 vertikal (height > width)
            best_file = None
            for f in files:
                if f.get("file_type") == "video/mp4":
                    w = f.get("width") or 0
                    h = f.get("height") or 0
                    if h >= w:  # 9:16 Portrait
                        best_file = f
                        break
            
            # Jika tiada tag portrait ketat, ambil kualiti HD pertama
            if not best_file and files:
                best_file = files[0]

            if best_file and "link" in best_file:
                selected_download_links.append({
                    "id": vid.get("id"),
                    "duration": vid.get("duration", 0),
                    "url": best_file["link"],
                    "width": best_file.get("width"),
                    "height": best_file.get("height")
                })

            if len(selected_download_links) >= count:
                break

        return selected_download_links

    except Exception as e:
        print(f"❌ [PEXELS EXCEPTION] Ralat membuat panggilan API: {e}")
        return []


def download_video_file(url: str, filename_prefix: str = "clip") -> str:
    """Memuat turun video binary dari URL ke fail sementara tempatan."""
    try:
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, stream=True, timeout=30)
        if res.status_code == 200:
            temp_file = tempfile.NamedTemporaryFile(suffix=".mp4", prefix=f"{filename_prefix}_", delete=False)
            for chunk in res.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    temp_file.write(chunk)
            temp_file.close()
            return temp_file.name
    except Exception as e:
        print(f"  ⚠️ Gagal muat turun video dari {url[:40]}...: {e}")
    return ""


def get_local_background_music(target_duration: int = 24):
    """Mengambil audio rawak daripada assets/music/."""
    if not MUSIC_FOLDER.exists():
        MUSIC_FOLDER.mkdir(parents=True, exist_ok=True)
        return None

    audio_files = [f for f in os.listdir(MUSIC_FOLDER) if f.lower().endswith((".mp3", ".wav", ".m4a", ".mp4"))]
    if not audio_files:
        print("  ⚠️ Tiada fail audio di assets/music/. Video akan dijana tanpa lagu.")
        return None

    selected = random.choice(audio_files)
    song_path = str(MUSIC_FOLDER / selected)
    print(f"  🎵 [AUDIO] Memilih muzik latar: '{selected}'")

    try:
        audio = AudioFileClip(song_path)
        start = random.randint(0, max(0, int(audio.duration) - target_duration - 2)) if audio.duration > target_duration + 5 else 0
        end = start + target_duration
        
        if hasattr(audio, "subclipped"):
            return audio.subclipped(start, end)
        return audio.subclip(start, end)
    except Exception as e:
        print(f"  ⚠️ Ralat memproses audio: {e}")
        return None


def create_stitched_reel_video(video_items: list, clip_duration: int = 8) -> str:
    """
    Mencantum 3 klip video menjadi 1 video Reel penuh (20–25 saat)
    berserta resolusi vertikal standard 1080x1920 dan muzik latar.
    """
    print(f"\n🎬 [MOVIEPY] Memulakan proses cantuman {len(video_items)} klip video...")
    downloaded_paths = []
    loaded_clips = []

    try:
        for idx, item in enumerate(video_items, 1):
            print(f"  📥 Muat turun klip {idx}/{len(video_items)} (ID: {item['id']})...")
            p = download_video_file(item["url"], filename_prefix=f"pexels_{idx}")
            if p and os.path.exists(p):
                downloaded_paths.append(p)
                clip = VideoFileClip(p)
                
                # Potong klip mengikut durasi sasaran
                actual_dur = min(clip.duration, clip_duration)
                if hasattr(clip, "subclipped"):
                    clip = clip.subclipped(0, actual_dur)
                else:
                    clip = clip.subclip(0, actual_dur)

                # Buang audio asal Pexels agar tidak bertindih
                if hasattr(clip, "without_audio"):
                    clip = clip.without_audio()
                else:
                    clip = clip.set_audio(None)

                # Skalakan saiz ke 1080x1920 jika perlu
                if hasattr(clip, "resized"):
                    clip = clip.resized((1080, 1920))
                elif hasattr(clip, "resize"):
                    clip = clip.resize((1080, 1920))

                loaded_clips.append(clip)

        if not loaded_clips:
            print("❌ Tiada klip video yang berjaya dimuatkan.")
            return ""

        # Cantumkan klip-klip video
        final_video = concatenate_videoclips(loaded_clips, method="compose")
        total_duration = int(final_video.duration)
        print(f"  ⏱️ Jumlah durasi Reel: {total_duration} saat.")

        # Pasang muzik latar
        bg_audio = get_local_background_music(target_duration=total_duration)
        if bg_audio:
            if hasattr(final_video, "with_audio"):
                final_video = final_video.with_audio(bg_audio)
            else:
                final_video = final_video.set_audio(bg_audio)

        # Simpan fail output video
        output_temp = tempfile.NamedTemporaryFile(suffix=".mp4", prefix="final_reel_", delete=False)
        output_path = output_temp.name
        output_temp.close()

        print(f"  ⚙️ Menjana fail video MP4 (H.264 / AAC)...")
        final_video.write_videofile(
            output_path,
            fps=24,
            codec="libx264",
            audio_codec="aac",
            preset="ultrafast",
            threads=4,
            logger=None
        )

        # Tutup sumber memori
        final_video.close()
        for c in loaded_clips:
            c.close()
        if bg_audio:
            bg_audio.close()

        return output_path

    finally:
        # Bersihkan fail klip sementara
        for dp in downloaded_paths:
            if os.path.exists(dp):
                try:
                    os.remove(dp)
                except Exception:
                    pass


def upload_to_facebook_reels(video_path: str, caption: str):
    """
    Memuat naik video MP4 ke Facebook Reels menggunakan Meta Video Reels Publishing API
    dan menangkap semua laporan respons ralat secara terperinci.
    """
    print("\n" + "=" * 65)
    print("🚀 [META GRAPH API] Memulakan Proses Muat Naik Facebook Reel...")
    print("=" * 65)

    if not FACEBOOK_PAGE_ID or not FACEBOOK_PAGE_TOKEN:
        print("❌ [ERROR] FACEBOOK_PAGE_ID atau FACEBOOK_PAGE_ACCESS_TOKEN tidak dijumpai!")
        return

    graph_url = "https://graph.facebook.com/v26.0"
    file_size = os.path.getsize(video_path)
    print(f"📁 Saiz video sedia dimuat naik: {file_size:,} bytes ({file_size / (1024*1024):.2f} MB)")

    # -------------------------------------------------------------------------
    # LANGKAH 1: Inisialisasi Sesi (upload_phase = start)
    # -------------------------------------------------------------------------
    print("\n🔹 [LANGKAH 1] Permintaan Sesi Mula (upload_phase = start)...")
    start_url = f"{graph_url}/{FACEBOOK_PAGE_ID}/video_reels"
    start_payload = {
        "upload_phase": "start",
        "access_token": FACEBOOK_PAGE_TOKEN
    }

    res_start = requests.post(start_url, data=start_payload, timeout=25)
    print(f"  Status Kod: HTTP {res_start.status_code}")
    print(f"  Respons Mentah: {res_start.text}")

    start_json = res_start.json()
    if res_start.status_code != 200 or "video_id" not in start_json:
        print("\n❌ [DIAGNOSTIK RALAT LANGKAH 1]:")
        print(f"  Mesej Ralat Meta: {start_json.get('error', {}).get('message')}")
        print(f"  Kod Ralat: {start_json.get('error', {}).get('code')} (Subcode: {start_json.get('error', {}).get('error_subcode')})")
        return

    video_id = start_json["video_id"]
    upload_url = start_json["upload_url"]
    print(f"  ✅ Sesi Berjaya Dimulakan! Video ID: {video_id}")

    # -------------------------------------------------------------------------
    # LANGKAH 2: Muat Naik Fail Binary Video (rupload server)
    # -------------------------------------------------------------------------
    print("\n🔹 [LANGKAH 2] Memuat naik Binary Video ke Meta Rupload Server...")
    with open(video_path, "rb") as vf:
        video_data = vf.read()

    upload_headers = {
        "Authorization": f"OAuth {FACEBOOK_PAGE_TOKEN}",
        "offset": "0",
        "file_size": str(file_size),
        "Content-Type": "application/octet-stream"
    }

    res_upload = requests.post(upload_url, headers=upload_headers, data=video_data, timeout=90)
    print(f"  Status Kod: HTTP {res_upload.status_code}")
    print(f"  Respons Mentah: {res_upload.text}")

    if res_upload.status_code != 200:
        print(f"\n❌ [DIAGNOSTIK RALAT LANGKAH 2] Gagal memuat naik fail video ke server Meta.")
        return

    print("  ✅ Muat naik binary video selesai!")

    # -------------------------------------------------------------------------
    # LANGKAH 3: Penerbitan Facebook Reel (upload_phase = finish)
    # -------------------------------------------------------------------------
    print("\n🔹 [LANGKAH 3] Menerbitkan Reel (upload_phase = finish)...")
    finish_payload = {
        "upload_phase": "finish",
        "video_id": video_id,
        "video_state": "PUBLISHED",
        "description": caption,
        "access_token": FACEBOOK_PAGE_TOKEN
    }

    res_finish = requests.post(start_url, data=finish_payload, timeout=25)
    print(f"  Status Kod: HTTP {res_finish.status_code}")
    print(f"  Respons Mentah: {res_finish.text}")

    finish_json = res_finish.json()
    if res_finish.status_code == 200 and finish_json.get("success", False):
        print("\n" + "=" * 65)
        print(f"🎉 [BERJAYA] Facebook Reel berjaya diterbitkan! (Video ID: {video_id})")
        print("=" * 65 + "\n")
    else:
        print("\n❌ [DIAGNOSTIK RALAT LANGKAH 3]:")
        print(f"  Mesej Ralat Meta: {finish_json.get('error', {}).get('message')}")


def main():
    print("=" * 70)
    print("🧪 [START] UJIAN PEXELS VIDEO REELS ENGINE (9:16 VERTICAL)")
    print("=" * 70)

    # 1. Pilihan Kata Kunci Carian Video Tech
    query_theme = "mechanical keyboard typing"
    
    # 2. Tarik 3 Video Vertikal daripada Pexels (1 API Request)
    video_list = fetch_pexels_vertical_videos(query=query_theme, count=3)
    if not video_list:
        print("⚠️ Tiada video ditemui daripada Pexels. Ujian dibatalkan.")
        return

    # 3. Cantum Video (Total 21–24 Saat)
    final_video_path = create_stitched_reel_video(video_list, clip_duration=8)
    if not final_video_path or not os.path.exists(final_video_path):
        print("❌ Gagal menjana fail video akhir.")
        return

    # 4. Kapsyen Santai Brader Din
    sample_caption = (
        "Bila setup meja kemas dan bunyi keyboard sedap di telinga, fokus buat kerja jadi makin tenang. "
        "Korang jenis suka keyboard switch bunyi clicky kuat atau yang senyap dan lembut?\n\n"
        "#SembangPCTech #MechanicalKeyboard #DeskSetup #TechMalaysia #ReelsMalaysia"
    )

    try:
        # 5. Muat Naik & Uji Ralat di Facebook Reels
        upload_to_facebook_reels(final_video_path, sample_caption)
    finally:
        # Bersihkan fail video output selepas ujian
        if os.path.exists(final_video_path):
            os.remove(final_video_path)


if __name__ == "__main__":
    main()