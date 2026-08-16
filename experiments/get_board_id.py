import re
import requests

# Pautan Board Awam anda di Pinterest
BOARD_URL = "https://www.pinterest.com/lubukbarangmurahpadu/racun-gajet-pc-setup-malaysia/"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
}

print(f"🔍 Menyemak Board: {BOARD_URL}...")
response = requests.get(BOARD_URL, headers=headers)

if response.status_code == 200:
    html = response.text
    # Cari ID berangka Board di dalam data JSON halaman
    matches = re.findall(r'"board_id":"(\d+)"', html) or re.findall(r'"board":\{"id":"(\d+)"', html) or re.findall(r'"id":"(\d{15,20})"', html)
    
    if matches:
        board_id = matches[0]
        print("\n" + "=" * 60)
        print("🎉 BERJAYA MENEMUI PINTEREST BOARD ID!")
        print("=" * 60)
        print(f"📌 Nama Board : Racun Gajet & PC Setup Malaysia")
        print(f"🔑 Board ID   : {board_id}")
        print("=" * 60)
        print(f"\nSimpan nilai ini di .env.local:\nPINTEREST_BOARD_ID=\"{board_id}\"")
    else:
        print("⚠️ Tidak dapat mengekstrak ID secara automatik. Sila gunakan Cara 2 (Manual Browser).")
else:
    print(f"❌ Gagal memuat turun halaman: HTTP {response.status_code}")