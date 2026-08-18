#!/usr/bin/env python3
"""
Dedicated Facebook Pexels Video Reels Engine
Sembang PC & Tech Ecosystem
Features:
- 1-API Call Pexels Batch Fetch (70 Videos) & Redis 30-Day Duplicate Filtering
- Comprehensive Facial & Sensitive Filter (Rejects all human faces, gamers, streamers, selfies)
- High-Performance MoviePy 9:16 Stitching (1080x1920, H.264/AAC, 21-24 Saat)
- Smart Audio Metadata & ID3 Ingestion (Extracts Clean Title, Artist, Genre & Vibe)
- Meta Graph API Video Reels Publisher with Comprehensive Diagnostics
"""

import os
import re
import random
import tempfile
import requests
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path

# Mutagen ID3 Metadata Reader
try:
    from mutagen import File as MutagenFile
    from mutagen.easyid3 import EasyID3
except ImportError:
    MutagenFile = None
    EasyID3 = None

# MoviePy v1.x & v2.x Compatibility Layer
try:
    from moviepy import VideoFileClip, AudioFileClip, concatenate_videoclips
except ImportError:
    from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips

from src.pexels_redis_db import is_pexels_video_posted

GRAPH_BASE_URL = "https://graph.facebook.com/v26.0"

# Senarai kata kunci dilarang ketat (Muka manusia, gamer, model, selfie, haiwan sensitif)
FORBIDDEN_VIDEO_KEYWORDS = [
    # Manusia & Watak
    "man", "men", "woman", "women", "girl", "girls", "boy", "boys", "person", "people",
    "lady", "guy", "guys", "female", "male", "human", "adult", "child", "kid", "teen", "teenager",
    # Muka, Potret & Ekspresi
    "face", "faces", "portrait", "selfie", "vlog", "model", "posing", "smile", "smiling",
    "looking", "eyes", "head", "headshot", "profile", "closeup-of-face",
    # Gamer, Streamer & Pekerja Berwajah
    "gamer", "gamers", "player", "players", "streamer", "streamers", "influencer", "creator",
    "actor", "worker", "programmer-face",
    # Haiwan Sensitif
    "dog", "dogs", "puppy", "puppies", "canine",
    "pig", "pigs", "pork", "swine", "boar"
]


def is_video_safe_and_faceless(video_data: Dict[str, Any]) -> bool:
    """Menyemak URL slug dan teks video Pexels bagi menolak sebarang klip berwajah manusia."""
    video_url = str(video_data.get("url", "")).lower()
    
    for bad_word in FORBIDDEN_VIDEO_KEYWORDS:
        # Padanan sempadan perkataan (mengesan '-gamer-', '_man_', '/woman/')
        pattern = rf'(?:^|[\-_/]){re.escape(bad_word)}(?:$|[\-_/])'
        if re.search(pattern, video_url):
            return False

    return True


def fetch_and_filter_pexels_videos(
    api_key: str,
    redis_url: str,
    redis_token: str,
    query: str,
    needed_count: int = 3,
    batch_size: int = 70,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Menghantar 1 permintaan API ke Pexels (per_page=70) dan menapis kandungan selamat serta segar."""
    print(f"\n📡 [PEXELS API] Menghantar 1 request (per_page={batch_size}) carian video: '{query}'...")

    if not api_key:
        print("❌ [PEXELS ERROR] Kunci API Pexels tidak disediakan.")
        return [], []

    url = "https://api.pexels.com/videos/search"
    headers = {"Authorization": api_key}
    params = {
        "query": query,
        "orientation": "portrait",
        "per_page": batch_size,
        "size": "medium",
    }

    try:
        res = requests.get(url, headers=headers, params=params, timeout=25)
        if res.status_code != 200:
            print(f"❌ [PEXELS ERROR] HTTP {res.status_code}: {res.text}")
            return [], []

        data = res.json()
        videos = data.get("videos", [])
        print(f"  ✅ Diterima {len(videos)} calon video dari Pexels API.")

        selected_videos = []
        skipped_ids = []

        for vid in videos:
            vid_id = str(vid.get("id"))
            duration = vid.get("duration", 0)
            files = vid.get("video_files", [])

            # 1. Tapisan Muka Orang & Haiwan Sensitif
            if not is_video_safe_and_faceless(vid):
                vid_slug = vid.get("url", "").split("/")[-2] if "/" in vid.get("url", "") else vid_id
                print(f"  🚫 [FACE/SENSITIVE SKIP] ID {vid_id} ditolak (Dikesan manusia/muka: '{vid_slug}').")
                continue

            # 2. Semak Penjara 30 Hari Redis
            if is_pexels_video_posted(redis_url, redis_token, vid_id):
                print(f"  ⏭️ [REDIS VIDEO SKIP] ID {vid_id} pernah digunakan < 30 hari lepas.")
                skipped_ids.append(vid_id)
                continue

            # 3. Cari fail MP4 vertikal (height >= width)
            best_file = None
            for f in files:
                if f.get("file_type") == "video/mp4":
                    w = f.get("width") or 0
                    h = f.get("height") or 0
                    if h >= w and h >= 720:
                        best_file = f
                        break

            if not best_file and files:
                for f in files:
                    if f.get("file_type") == "video/mp4":
                        best_file = f
                        break

            if best_file and "link" in best_file:
                selected_videos.append({
                    "id": vid_id,
                    "duration": duration,
                    "url": best_file["link"],
                    "width": best_file.get("width"),
                    "height": best_file.get("height"),
                })

            if len(selected_videos) >= needed_count:
                break

        print(f"  🎯 Berjaya memilih {len(selected_videos)} video 9:16 bebas muka yang disahkan 100% segar.")
        return selected_videos, skipped_ids

    except Exception as e:
        print(f"❌ [PEXELS EXCEPTION] Ralat membuat panggilan API: {e}")
        return [], []


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


def detect_audio_vibe(title: str, genre: str, artist: str) -> str:
    """Mengenal pasti emosi/vibe muzik secara automatik untuk disalurkan ke AI Persona."""
    text = f"{title} {genre} {artist}".lower()
    
    if any(k in text for k in ["acoustic", "guitar", "evening", "peace", "calm", "relax", "serene", "nature"]):
        return "Akustik Santai, Damai & Menenangkan Fikiran"
    elif any(k in text for k in ["lofi", "lo-fi", "chill", "coffee", "night", "study", "cozy", "rain"]):
        return "Lo-Fi Chill, Santai & Terapi Ruang Kerja"
    elif any(k in text for k in ["cyberpunk", "synthwave", "retrowave", "neon", "future", "matrix", "dark"]):
        return "Synthwave Futuristik & Battlestation Ambient"
    elif any(k in text for k in ["piano", "classical", "melodic", "soft", "ambient", "dream"]):
        return "Melodi Piano Lembut & Fokus Reflektif"
    elif any(k in text for k in ["rock", "electronic", "upbeat", "energetic", "beat", "drum"]):
        return "Rentak Bertenaga & Mood Produktiviti Tinggi"
    
    return "Muzik Latar Estetik & Santai"


def extract_smart_audio_metadata(song_path: str, filename: str) -> Dict[str, str]:
    """Mengekstrak metadata audio dengan menapis ID berangka Meta dan membersihkan nama fail."""
    base_name = os.path.splitext(filename)[0]
    
    clean_title_from_file = re.sub(r'[_\-]+', ' ', base_name).strip()
    clean_title_from_file = re.sub(r'\b(30s|loop|instrumental|reels sound|before after)\b', '', clean_title_from_file, flags=re.I)
    clean_title_from_file = re.sub(r'\s+', ' ', clean_title_from_file).strip().title()

    title = ""
    artist = ""
    genre = ""

    if MutagenFile:
        try:
            audio_tag = MutagenFile(song_path)
            if audio_tag and hasattr(audio_tag, "get"):
                raw_nam = str(audio_tag.get("\xa9nam", [""])[0] if isinstance(audio_tag.get("\xa9nam"), list) else audio_tag.get("\xa9nam", ""))
                if raw_nam and not raw_nam.strip().isdigit():
                    title = raw_nam.strip()

                raw_art = str(audio_tag.get("\xa9ART", [""])[0] if isinstance(audio_tag.get("\xa9ART"), list) else audio_tag.get("\xa9ART", ""))
                if raw_art and not raw_art.strip().isdigit():
                    artist = raw_art.strip()
        except Exception:
            pass

    if not title or title.isdigit():
        title = clean_title_from_file or "Original Audio"

    if not artist:
        artist = "Artis Komposer Pilihan"

    vibe = detect_audio_vibe(title, genre, artist)

    return {
        "title": title,
        "artist": artist,
        "genre": genre or "Acoustic / Chill Ambient",
        "vibe": vibe,
        "filename": filename
    }


def get_local_music_clip(music_dir: Path, target_duration: int = 24) -> Tuple[Optional[Any], Dict[str, str]]:
    """Mengambil audio rawak daripada folder assets/music/ dan memulangkan klip audio serta metadata lengkap."""
    default_meta = {
        "title": "Original Audio",
        "artist": "Sembang PC & Tech",
        "genre": "Aesthetic Ambient",
        "vibe": "Santai & Tenang",
        "filename": "Original Audio"
    }

    if not music_dir.exists():
        music_dir.mkdir(parents=True, exist_ok=True)
        return None, default_meta

    audio_files = [f for f in os.listdir(music_dir) if f.lower().endswith((".mp3", ".wav", ".m4a", ".mp4"))]
    if not audio_files:
        print("  ⚠️ Tiada fail audio di assets/music/. Video dijana tanpa lagu latar.")
        return None, default_meta

    selected_file = random.choice(audio_files)
    song_path = str(music_dir / selected_file)
    meta = extract_smart_audio_metadata(song_path, selected_file)
    
    print(f"  🎵 [AUDIO METADATA] Trek: '{meta['title']}' | Artis: '{meta['artist']}' | Genre: '{meta['genre']}' | Vibe: '{meta['vibe']}'")

    try:
        audio = AudioFileClip(song_path)
        start = random.randint(0, max(0, int(audio.duration) - target_duration - 2)) if audio.duration > target_duration + 5 else 0
        end = start + target_duration

        if hasattr(audio, "subclipped"):
            cut_audio = audio.subclipped(start, end)
        else:
            cut_audio = audio.subclip(start, end)

        return cut_audio, meta
    except Exception as e:
        print(f"  ⚠️ Ralat memproses audio latar: {e}")
        return None, default_meta


def render_stitched_reel_video(
    video_items: List[Dict[str, Any]],
    music_dir: Path,
    single_clip_duration: int = 8,
) -> Tuple[Optional[str], Dict[str, str], int]:
    """
    Mencantumkan 3 klip video menjadi 1 video Reel vertikal (1080x1920, 21–24 saat)
    berserta trek audio AAC berkualiti tinggi.
    """
    print(f"\n🎬 [MOVIEPY] Memulakan proses cantuman {len(video_items)} klip video...")
    downloaded_paths = []
    loaded_clips = []
    selected_music_info = {
        "title": "Original Audio",
        "artist": "Sembang PC & Tech",
        "genre": "Aesthetic Ambient",
        "vibe": "Santai & Tenang",
        "filename": "Original Audio"
    }
    total_duration = 24

    try:
        for idx, item in enumerate(video_items, 1):
            print(f"  📥 [Klip {idx}/{len(video_items)}] Muat turun video ID {item['id']}...")
            p = download_video_clip(item["url"], filename_prefix=f"pexels_reel_{idx}")
            if p and os.path.exists(p):
                downloaded_paths.append(p)
                clip = VideoFileClip(p)

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

                # Standardkan resolusi 1080x1920 (9:16)
                if hasattr(clip, "resized"):
                    clip = clip.resized((1080, 1920))
                elif hasattr(clip, "resize"):
                    clip = clip.resize((1080, 1920))

                loaded_clips.append(clip)

        if not loaded_clips:
            print("❌ Tiada klip video yang berjaya dimuatkan.")
            return None, selected_music_info, 0

        # Cantumkan klip-klip
        final_video = concatenate_videoclips(loaded_clips, method="compose")
        total_duration = int(final_video.duration)
        print(f"  ⏱️ Jumlah durasi Reel: {total_duration} saat.")

        # Pasangkan muzik latar
        bg_audio, selected_music_info = get_local_music_clip(music_dir, target_duration=total_duration)
        if bg_audio:
            if hasattr(final_video, "with_audio"):
                final_video = final_video.with_audio(bg_audio)
            else:
                final_video = final_video.set_audio(bg_audio)

        # Simpan fail video sementara
        output_temp = tempfile.NamedTemporaryFile(suffix=".mp4", prefix="fb_pexels_reel_", delete=False)
        output_path = output_temp.name
        output_temp.close()

        print("  ⚙️ Menjana fail video MP4 (H.264 / AAC)...")
        final_video.write_videofile(
            output_path,
            fps=24,
            codec="libx264",
            audio_codec="aac",
            preset="fast",
            threads=4,
            logger=None,
        )

        final_video.close()
        for c in loaded_clips:
            c.close()
        if bg_audio:
            bg_audio.close()

        return output_path, selected_music_info, total_duration

    finally:
        for dp in downloaded_paths:
            if os.path.exists(dp):
                try:
                    os.remove(dp)
                except Exception:
                    pass


def upload_reel_to_facebook(
    page_id: str,
    page_token: str,
    video_path: str,
    caption: str,
) -> Tuple[bool, Dict[str, Any]]:
    """Memuat naik video MP4 ke Facebook Reels via Meta Video Reels Publishing API."""
    if not page_id or not page_token:
        return False, {"error": "Kunci FACEBOOK_PAGE_ID atau FACEBOOK_PAGE_ACCESS_TOKEN tiada."}

    file_size = os.path.getsize(video_path)
    start_url = f"{GRAPH_BASE_URL}/{page_id}/video_reels"

    try:
        # Fasa 1: Mula Sesi
        print("  🎬 [REEL STEP 1] Memulakan sesi muat naik Facebook Reel...")
        res_start = requests.post(
            start_url,
            data={"upload_phase": "start", "access_token": page_token},
            timeout=25,
        )
        start_json = res_start.json()
        if res_start.status_code != 200 or "video_id" not in start_json:
            err_msg = start_json.get("error", {}).get("message", res_start.text)
            print(f"  ❌ [REEL STEP 1 ERROR] {err_msg}")
            return False, {"step": 1, "error": err_msg, "response": start_json}

        video_id = start_json["video_id"]
        upload_url = start_json["upload_url"]
        print(f"  ✅ [REEL STEP 1 SUCCESS] Video ID: {video_id}")

        # Fasa 2: Upload Binary Video
        print("  🎬 [REEL STEP 2] Memuat naik Binary Video ke Meta Rupload Server...")
        with open(video_path, "rb") as vf:
            video_data = vf.read()

        upload_headers = {
            "Authorization": f"OAuth {page_token}",
            "offset": "0",
            "file_size": str(file_size),
            "Content-Type": "application/octet-stream",
        }
        res_upload = requests.post(upload_url, headers=upload_headers, data=video_data, timeout=90)
        if res_upload.status_code != 200:
            print(f"  ❌ [REEL STEP 2 ERROR] Status HTTP {res_upload.status_code}: {res_upload.text}")
            return False, {"step": 2, "error": "Gagal muat naik binary video ke Meta.", "response": res_upload.text}

        print("  ✅ [REEL STEP 2 SUCCESS] Muat naik binary video selesai!")

        # Fasa 3: Terbitkan Reel
        print("  🎬 [REEL STEP 3] Menerbitkan Facebook Reel...")
        finish_payload = {
            "upload_phase": "finish",
            "video_id": video_id,
            "video_state": "PUBLISHED",
            "description": caption,
            "access_token": page_token,
        }
        res_finish = requests.post(start_url, data=finish_payload, timeout=25)
        finish_json = res_finish.json()

        if res_finish.status_code == 200 and finish_json.get("success", False):
            print(f"  🎉 [REEL SUCCESS] Facebook Reel berjaya diterbitkan! (Video ID: {video_id})")
            return True, {"video_id": video_id}
        else:
            err_msg = finish_json.get("error", {}).get("message", res_finish.text)
            print(f"  ❌ [REEL STEP 3 ERROR] {err_msg}")
            return False, {"step": 3, "error": err_msg, "response": finish_json}

    except Exception as e:
        print(f"  ❌ [REEL EXCEPTION] Ralat tidak dijangka: {e}")
        return False, {"error": str(e)}