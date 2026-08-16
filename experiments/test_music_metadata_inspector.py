#!/usr/bin/env python3
"""
Deep Audio Metadata Inspector & Diagnostic Tool
Sembang PC & Tech Ecosystem
Features:
- Deeply inspects ID3v1, ID3v2, EasyID3, MP4, and WAV metadata tags
- Dissects all raw frames (TPE1, TPE2, TIT2, TCON, albumartist, etc.)
- Tests robust multi-layer extraction to ensure Artist & Title are 100% captured
"""

import os
import re
import sys
from pathlib import Path

# Setup Project Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Mutagen Ingestion
try:
    import mutagen
    from mutagen import File as MutagenFile
    from mutagen.easyid3 import EasyID3
    from mutagen.id3 import ID3
except ImportError:
    print("❌ Sila pasang mutagen dahulu: pip install mutagen")
    sys.exit(1)


def deep_extract_audio_tags(file_path: Path):
    """Mengekstrak maklumat audio menggunakan pelbagai lapisan decoder mutagen."""
    filename = file_path.name
    results = {
        "filename": filename,
        "raw_title": None,
        "raw_artist": None,
        "raw_genre": None,
        "all_tags_found": {},
        "detection_method": "Unknown"
    }

    # 1. Kaedah A: EasyID3 (Paling standard untuk MP3)
    try:
        easy_audio = EasyID3(str(file_path))
        for k, v in easy_audio.items():
            results["all_tags_found"][f"EasyID3:{k}"] = v

        if "title" in easy_audio and easy_audio["title"]:
            results["raw_title"] = easy_audio["title"][0]
        if "artist" in easy_audio and easy_audio["artist"]:
            results["raw_artist"] = easy_audio["artist"][0]
        elif "albumartist" in easy_audio and easy_audio["albumartist"]:
            results["raw_artist"] = easy_audio["albumartist"][0]
        elif "composer" in easy_audio and easy_audio["composer"]:
            results["raw_artist"] = easy_audio["composer"][0]
        if "genre" in easy_audio and easy_audio["genre"]:
            results["raw_genre"] = easy_audio["genre"][0]

        if results["raw_title"] or results["raw_artist"]:
            results["detection_method"] = "EasyID3"
    except Exception:
        pass

    # 2. Kaedah B: Raw ID3 Frame Decoder (Jika EasyID3 terlepas membaca frame khas)
    if not results["raw_artist"] or not results["raw_title"]:
        try:
            id3_audio = ID3(str(file_path))
            for frame_key, frame_val in id3_audio.items():
                results["all_tags_found"][f"RawID3:{frame_key}"] = str(frame_val)

            # TIT2 = Title, TPE1 = Lead Artist, TPE2 = Band/Album Artist, TCOM = Composer
            if not results["raw_title"] and "TIT2" in id3_audio:
                results["raw_title"] = str(id3_audio["TIT2"])
            if not results["raw_artist"]:
                if "TPE1" in id3_audio:
                    results["raw_artist"] = str(id3_audio["TPE1"])
                elif "TPE2" in id3_audio:
                    results["raw_artist"] = str(id3_audio["TPE2"])
                elif "TCOM" in id3_audio:
                    results["raw_artist"] = str(id3_audio["TCOM"])
            if not results["raw_genre"] and "TCON" in id3_audio:
                results["raw_genre"] = str(id3_audio["TCON"])

            if results["raw_artist"] or results["raw_title"]:
                results["detection_method"] = "Raw ID3 Frames"
        except Exception:
            pass

    # 3. Kaedah C: Generic Mutagen File (Menyokong MP4, M4A, FLAC, OGG, RIFF/WAV)
    if not results["raw_artist"] or not results["raw_title"]:
        try:
            mf = MutagenFile(str(file_path))
            if mf and mf.tags:
                for k, v in mf.tags.items():
                    results["all_tags_found"][f"Generic:{k}"] = str(v)

                # Format MP4 / M4A
                if hasattr(mf.tags, "get"):
                    if not results["raw_title"]:
                        results["raw_title"] = str(mf.tags.get("\xa9nam", [""])[0] if isinstance(mf.tags.get("\xa9nam"), list) else mf.tags.get("\xa9nam", ""))
                    if not results["raw_artist"]:
                        results["raw_artist"] = str(mf.tags.get("\xa9ART", [""])[0] if isinstance(mf.tags.get("\xa9ART"), list) else mf.tags.get("\xa9ART", ""))
                    if not results["raw_genre"]:
                        results["raw_genre"] = str(mf.tags.get("\xa9gen", [""])[0] if isinstance(mf.tags.get("\xa9gen"), list) else mf.tags.get("\xa9gen", ""))

                if results["raw_artist"] or results["raw_title"]:
                    results["detection_method"] = "Generic Mutagen Tags"
        except Exception:
            pass

    # 4. Kaedah D: Fallback Struktur Nama Fail
    base_name = file_path.stem
    if " - " in base_name:
        parts = base_name.split(" - ", 1)
        fallback_artist = parts[0].strip().title()
        fallback_title = parts[1].strip().title()
    else:
        fallback_artist = ""
        fallback_title = re.sub(r'[_\-]+', ' ', base_name).strip().title()

    final_title = (results["raw_title"] or fallback_title or "Original Audio").strip()
    final_artist = (results["raw_artist"] or fallback_artist or "Artis Komposer Pilihan").strip()
    final_genre = (results["raw_genre"] or "Acoustic / Chill Ambient").strip()

    return {
        "filename": filename,
        "final_title": final_title,
        "final_artist": final_artist,
        "final_genre": final_genre,
        "detection_method": results["detection_method"],
        "all_tags_found": results["all_tags_found"]
    }


def run_music_inspection():
    music_dir = PROJECT_ROOT / "assets" / "music"
    print("\n" + "=" * 75)
    print("🎧 [START] PENGIMBAS METADATA AUDIO MENYELURUH (ASSETS/MUSIC)")
    print("=" * 75)

    if not music_dir.exists():
        print(f"❌ Folder tidak dijumpai: {music_dir}")
        return

    audio_files = sorted([f for f in music_dir.iterdir() if f.suffix.lower() in [".mp3", ".wav", ".m4a", ".mp4", ".flac", ".ogg"]])
    total_files = len(audio_files)

    if total_files == 0:
        print(f"⚠️ Tiada fail audio dijumpai di {music_dir}")
        return

    print(f"📂 Dijumpai {total_files} fail audio. Memulakan imbasan tag...\n")

    detected_artists = 0
    fallback_artists = 0

    for idx, audio_path in enumerate(audio_files, 1):
        info = deep_extract_audio_tags(audio_path)
        is_identified = info["final_artist"] not in ["Artis Komposer Pilihan", ""]

        if is_identified:
            detected_artists += 1
            status_icon = "✅"
        else:
            fallback_artists += 1
            status_icon = "⚠️"

        print(f"{idx}. {status_icon} Fail: {info['filename']}")
        print(f"   🎵 Tajuk  : {info['final_title']}")
        print(f"   🎤 Artis  : {info['final_artist']}")
        print(f"   🎸 Genre  : {info['final_genre']}")
        print(f"   🔍 Kaedah : {info['detection_method']}")
        
        # Paparkan tag mentah jika ada
        if info["all_tags_found"]:
            tags_str = ", ".join([f"{k}={v}" for k, v in list(info["all_tags_found"].items())[:4]])
            print(f"   📦 Tags   : {tags_str}")
        else:
            print(f"   📦 Tags   : [TIADA TAG ID3 DALAM FAIL]")
        print("-" * 75)

    print("\n" + "=" * 75)
    print("📊 RINGKASAN IMBASAN METADATA:")
    print("=" * 75)
    print(f"📁 Jumlah Fail Audio    : {total_files}")
    print(f"✅ Artis Berjaya Dikesan: {detected_artists} fail")
    print(f"⚠️ Menggunakan Fallback : {fallback_artists} fail")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    run_music_inspection()