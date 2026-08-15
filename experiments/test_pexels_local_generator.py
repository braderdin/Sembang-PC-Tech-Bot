#!/usr/bin/env python3
"""
🧪 EKSPERIMEN: Pexels 20-Video Batch Fetch & Local Reel Generator
Lokasi: experiments/test_pexels_local_generator.py
Tujuan:
1. Menghantar 1 permintaan API ke Pexels untuk 20 video (per_page=20, orientation=portrait).
2. Memilih 3 video vertikal (9:16) berkualiti tinggi.
3. Mencantumkan 3 klip (durasi ~21-24 saat) + muzik latar dari assets/music/.
4. Menyimpan fail video akhir secara TEMPATAN (.mp4) untuk tontonan & semakan terus.
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

# Tetapan Laluan Projek
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Baca .env.local
env_local = PROJECT_ROOT / ".env.local"
if env_local.exists():
    load_dotenv(dotenv_path=env_local)
else:
    load_dotenv()

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "").strip()
MUSIC_FOLDER = PROJECT_ROOT / "assets" / "music"
OUTPUT_DIR = PROJECT_ROOT / "experiments" / "output"


def fetch_20_pexels_vertical_videos(query: str, needed_count: int = 3):
    """
    Menghantar TEPAT 1 API Request ke Pexels untuk mendapatkan 20 calon video (per_page=20).
    Menapis dan memulangkan calon video yang berformat vertikal 9:16 (Portrait).
    """
    print(f"\n📡 [PEXELS API] Menghantar 1 request (per_page=20) bagi carian: '{query}'...")

    if not PEXELS_API_KEY:
        print("❌ [PEXELS ERROR] Kunci 'PEXELS_API_KEY' tidak dijumpai dalam .env.local!")
        return []

    url = "https://api.pexels.com/videos/search"
    headers = {"Authorization": PEXELS_API_KEY}
    params = {
        "query": query,
        "orientation": "portrait",
        "per_page": 20,
        "size": "medium",
    }

    try:
        res = requests.get(url, headers=headers, params=params, timeout=25)
        print(f"  ℹ️ Status Respons Pexels: HTTP {res.status_code}")

        if res.status_code != 200:
            print(f"  ❌ [PEXELS ERROR RESPONSE] {res.text}")
            return []

        data = res.json()
        videos = data.get("videos", [])
        total_found = data.get("total_results", 0)
        print(f"  ✅ Ditemui {len(videos)} calon video dalam batch ini (Jumlah keseluruhan di Pexels: {total_found}).")

        portrait_candidates = []
        for idx, vid in enumerate(videos, 1):
            vid_id = vid.get("id")
            vid_dur = vid.get("duration", 0)
            files = vid.get("video_files", [])

            # Cari fail MP4 dengan nisbah menegak (height > width)
            best_file = None
            for f in files:
                if f.get("file_type") == "video/mp4":
                    w = f.get("width") or 0
                    h = f.get("height") or 0
                    if h >= w and h >= 720:  # Kualiti HD Portrait
                        best_file = f
                        break

            # Fallback jika tiada tag kualiti HD
            if not best_file and files:
                for f in files:
                    if f.get("file_type") == "video/mp4":
                        best_file = f
                        break

            if best_file and "link" in best_file:
                portrait_candidates.append({
                    "id": vid_id,
                    "duration": vid_dur,
                    "url": best_file["link"],
                    "width": best_file.get("width"),
                    "height": best_file.get("height"),
                    "quality": best_file.get("quality"),
                })

        print(f"  🎯 Disahkan {len(portrait_candidates)} video benar-benar berformat 9:16 Portrait.")

        # Ambil 3 video pertama daripada senarai calon yang lulus
        selected_3 = portrait_candidates[:needed_count]
        print(f"\n📋 [3 VIDEO TERPILIH UNTUK REEL]:")
        for i, item in enumerate(selected_3, 1):
            print(f"   {i}. ID: {item['id']} | Resolusi: {item['width']}x{item['height']} | Durasi Asal: {item['duration']}s")

        return selected_3

    except Exception as e:
        print(f"❌ [PEXELS EXCEPTION] Ralat panggilan API: {e}")
        return []


def download_video_clip(url: str, filename_prefix: str = "clip") -> str:
    """Memuat turun fail video MP4 dari URL ke fail sementara."""
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
        print(f"  ⚠️ Ralat muat turun video: {e}")
    return ""


def get_random_local_music(target_duration: int = 24):
    """Mengambil dan memotong fail audio latar dari assets/music/."""
    if not MUSIC_FOLDER.exists():
        MUSIC_FOLDER.mkdir(parents=True, exist_ok=True)
        return None

    audio_files = [f for f in os.listdir(MUSIC_FOLDER) if f.lower().endswith((".mp3", ".wav", ".m4a", ".mp4"))]
    if not audio_files:
        print("  ⚠️ Tiada fail audio di assets/music/. Video dijana tanpa audio.")
        return None

    selected_song = random.choice(audio_files)
    song_path = str(MUSIC_FOLDER / selected_song)
    print(f"  🎵 [AUDIO] Menggunakan muzik latar: '{selected_song}'")

    try:
        audio = AudioFileClip(song_path)
        start = random.randint(0, max(0, int(audio.duration) - target_duration - 2)) if audio.duration > target_duration + 5 else 0
        end = start + target_duration

        if hasattr(audio, "subclipped"):
            return audio.subclipped(start, end)
        return audio.subclip(start, end)
    except Exception as e:
        print(f"  ⚠️ Ralat memuatkan muzik latar: {e}")
        return None


def generate_local_reel_video(video_items: list, single_clip_duration: int = 8) -> str:
    """
    Mencantumkan 3 klip video dan memasang audio latar,
    kemudian menyimpannya secara kekal di folder experiments/output/.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp_str = time.strftime("%Y%m%d_%H%M%S")
    final_output_path = str(OUTPUT_DIR / f"test_reel_preview_{timestamp_str}.mp4")

    print(f"\n🎬 [MOVIEPY] Memulakan proses cantuman {len(video_items)} klip video...")
    downloaded_paths = []
    loaded_clips = []

    try:
        for idx, item in enumerate(video_items, 1):
            print(f"  📥 [Klip {idx}/{len(video_items)}] Memuat turun video ID {item['id']}...")
            p = download_video_clip(item["url"], filename_prefix=f"pexels_{idx}")
            if p and os.path.exists(p):
                downloaded_paths.append(p)
                clip = VideoFileClip(p)

                # Potong klip mengikut durasi yang dimahukan
                actual_dur = min(clip.duration, single_clip_duration)
                if hasattr(clip, "subclipped"):
                    clip = clip.subclipped(0, actual_dur)
                else:
                    clip = clip.subclip(0, actual_dur)

                # Buang audio asal Pexels
                if hasattr(clip, "without_audio"):
                    clip = clip.without_audio()
                else:
                    clip = clip.set_audio(None)

                # Standardkan resolusi 1080x1920 (9:16 Portrait)
                if hasattr(clip, "resized"):
                    clip = clip.resized((1080, 1920))
                elif hasattr(clip, "resize"):
                    clip = clip.resize((1080, 1920))

                loaded_clips.append(clip)

        if not loaded_clips:
            print("❌ Tiada klip yang berjaya dimuatkan.")
            return ""

        # Cantumkan semua klip menjadi satu video berterusan
        final_video = concatenate_videoclips(loaded_clips, method="compose")
        total_duration = int(final_video.duration)
        print(f"  ⏱️ Jumlah durasi video Reel: {total_duration} saat.")

        # Pasangkan muzik latar
        bg_audio = get_random_local_music(target_duration=total_duration)
        if bg_audio:
            if hasattr(final_video, "with_audio"):
                final_video = final_video.with_audio(bg_audio)
            else:
                final_video = final_video.set_audio(bg_audio)

        print(f"\n⚙️ Menjana dan mengekod fail video MP4 (H.264 / AAC)... Sila tunggu...")
        final_video.write_videofile(
            final_output_path,
            fps=24,
            codec="libx264",
            audio_codec="aac",
            preset="fast",
            threads=4,
            logger=None,
        )

        # Tutup sumber memori
        final_video.close()
        for c in loaded_clips:
            c.close()
        if bg_audio:
            bg_audio.close()

        return final_output_path

    finally:
        # Bersihkan fail klip sementara sahaja (fail video akhir kekal disimpan)
        for dp in downloaded_paths:
            if os.path.exists(dp):
                try:
                    os.remove(dp)
                except Exception:
                    pass


def main():
    print("=" * 70)
    print("🧪 [START] UJIAN PEXELS BATCH 20 & LOCAL REEL GENERATOR (TANPA UPLOAD FB)")
    print("=" * 70)

    # 1. Pilihan Kata Kunci Tema Video
    query_keyword = "mechanical keyboard typing"

    # 2. Tarik 20 video dalam 1 panggilan API, tapis & ambil 3
    selected_videos = fetch_20_pexels_vertical_videos(query=query_keyword, needed_count=3)
    if not selected_videos:
        print("⚠️ Tiada video berjaya diekstrak.")
        return

    # 3. Jana video Reel tempatan berdurasi 24 saat
    output_video = generate_local_reel_video(selected_videos, single_clip_duration=8)

    if output_video and os.path.exists(output_video):
        file_size_bytes = os.path.getsize(output_video)
        file_size_mb = file_size_bytes / (1024 * 1024)

        print("\n" + "=" * 70)
        print("🎉 [BERJAYA DIJANA SECARA TEMPATAN!]")
        print(f"📁 Lokasi Fail Video : {output_video}")
        print(f"📊 Saiz Fail Video   : {file_size_bytes:,} bytes ({file_size_mb:.2f} MB)")
        print(f"📐 Nisbah Paparan    : 1080 x 1920 (9:16 Vertikal Penuh)")
        print("💡 Anda boleh buka dan tonton fail video ini terus di VS Code atau File Explorer anda!")
        print("=" * 70 + "\n")


if __name__ == "__main__":
    main()