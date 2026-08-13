import os
import sys

# Memastikan laluan akar projek dimasukkan ke dalam sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv

# Muat turun tetapan daripada .env.local
env_local_path = os.path.join(PROJECT_ROOT, ".env.local")
if os.path.exists(env_local_path):
    load_dotenv(dotenv_path=env_local_path)
else:
    load_dotenv()

# Import fungsi modul
from src.supabase_db import fetch_unused_links, get_supabase_config
from lazada_image_fetcher.src.lazada_api import fetch_product_images_from_lazada

def run_test():
    print("\n==================================================")
    print("🧪 [TEST START] UJIAN TARIK GAMBAR BERBILANG VIA LAZADA API")
    print("==================================================")

    # 1. Tarik 1 Produk dari Supabase DB
    print("\n📦 [STEP 1] Membaca 1 produk calon dari Supabase Cloud...")
    ok, records, err = fetch_unused_links(limit=1)

    if not ok or not records:
        print("⚠️ Tiada produk status_used=false. Membaca produk dari pangkalan data...")
        supabase_url, api_key, _ = get_supabase_config()
        if supabase_url and api_key:
            import requests
            endpoint = f"{supabase_url}/rest/v1/affiliate_links?select=*&limit=1"
            headers = {"apikey": api_key, "Authorization": f"Bearer {api_key}"}
            res = requests.get(endpoint, headers=headers, timeout=10)
            if res.status_code == 200:
                records = res.json()

    if not records:
        print("❌ [TEST ABORT] Tiada rekod produk ditemui di dalam Supabase.")
        return

    product = records[0]
    p_id = str(product.get("product_id") or product.get("id") or "").strip()
    title = str(product.get("title") or "").strip()
    single_img_url = str(product.get("image_url") or "").strip()

    print(f"✅ Produk Diperolehi Dari Supabase:")
    print(f"   - Product ID   : {p_id}")
    print(f"   - Tajuk        : {title}")
    print(f"   - Gambar asal  : {single_img_url}\n")

    # 2. Panggil API Rasmi Lazada untuk dapatkan 3-5 gambar
    print("🛍️ [STEP 2] Memanggil API Rasmi Lazada...")
    api_ok, image_urls, msg = fetch_product_images_from_lazada(p_id)

    print("\n==================================================")
    print("📊 [TEST RESULT REPORT]")
    print("==================================================")
    if api_ok:
        print(f"🎉 STATUS: BERJAYA! {msg}")
        print(f"📸 SENARAI {len(image_urls)} GAMBAR DIPEROLEHI:")
        for idx, url in enumerate(image_urls, 1):
            print(f"   {idx}. {url}")
    else:
        print(f"❌ STATUS: GAGAL!")
        print(f"⚠️ MESEJ RALAT: {msg}")
    print("==================================================\n")

if __name__ == "__main__":
    run_test()