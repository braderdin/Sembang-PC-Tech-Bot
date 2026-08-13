import os
import sys
from dotenv import load_dotenv

# Dapatkan laluan folder tepat
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "../main"))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../../.."))

if MAIN_DIR not in sys.path:
    sys.path.insert(0, MAIN_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

env_local_path = os.path.join(PROJECT_ROOT, ".env.local")
if os.path.exists(env_local_path):
    load_dotenv(dotenv_path=env_local_path)
else:
    load_dotenv()

from threads_client import (
    check_threads_profile_and_permissions,
    refresh_threads_access_token,
    create_and_publish_threads_image_post
)

def run_threads_image_test():
    print("\n" + "=" * 70)
    print("🖼️ [UJIAN PERCUBAN 2] PEMPOSAN GAMBAR + TEKS + LINK KE THREADS API")
    print("=" * 70)

    app_id = os.getenv("THREADS_APP_ID", "").strip()
    app_secret = os.getenv("THREADS_APP_SECRET", "").strip()
    user_id = os.getenv("THREADS_USER_ID", "").strip()
    access_token = os.getenv("THREADS_ACCESS_TOKEN", "").strip()

    if not all([app_id, app_secret, user_id, access_token]):
        print("\n❌ [STOP] Kunci Threads di .env.local tidak lengkap.")
        return

    # 1. Semakan Profil & Keizinan
    print("\n📡 [UJIAN 1] Semakan Profil Threads...")
    ok_prof, prof_res = check_threads_profile_and_permissions(user_id, access_token)
    if not ok_prof or not isinstance(prof_res, dict):
        print(f"  ❌ SEMAKAN PROFIL GAGAL: {prof_res}")
        return
    print(f"  ✅ PERMISSION OK! Username: @{prof_res.get('username')}")

    # 2. Hantar Pos Gambar + Teks + Pautan Affiliate
    print("\n📸 [UJIAN 2] Menghantar Hantaran GAMBAR + TEKS + PAUTAN ke Threads...")
    
    test_image_url = "https://images.unsplash.com/photo-1587829741301-dc798b83add3?q=80&w=1000&auto=format&fit=crop"
    test_caption = (
        "Minimalist setup macam ni memang buat fokus kerja makin padu. "
        "Keyboard mekanikal tanpa wayar ni pilihan terbaik untuk ruang kerja kemas. 💻⚡\n\n"
        "🔗 Dapatkan promo Shopee/Lazada di sini: https://shopee.com.my"
    )

    ok_post, post_res = create_and_publish_threads_image_post(
        user_id=user_id,
        access_token=access_token,
        text_content=test_caption,
        image_url=test_image_url
    )

    if ok_post and isinstance(post_res, dict):
        print(f"\n🎉 [BERJAYA] Hantaran GAMBAR Threads berjaya diterbitkan! (Post ID: {post_res.get('thread_post_id')})")
        print("📲 Sila semak profil Threads @braderdin360 di telefon/browser anda sekarang!")
    else:
        print(f"\n❌ [GAGAL POS GAMBAR THREADS]: {post_res}")

if __name__ == "__main__":
    run_threads_image_test()