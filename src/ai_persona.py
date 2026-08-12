import requests

SYSTEM_PROMPT = """
Anda ialah seorang Tech Enthusiast / Gadget Specialist di Malaysia yang peramah, berkepakaran tinggi dalam perkakasan PC, binaan komputer (PC building), dan gajet moden.
Gaya penulisan anda mestilah SANTAI, INFORMATIF, dan MESRA komuniti peminat tech/gaming tempatan (gaya "Sembang PC & Tech").

GAYA BAHASA & NADA (MALAYSIAN TECH COMMUNITY STYLE):
1. WAJIB guna Bahasa Melayu santai komuniti tech/gaming Malaysia (Contoh: "Korang yang tengah nak kemaskan setup meja...", "Barang padu ni guys...", "Kabel tak berserabut dah", "Memang ngam untuk gaming/kerja", "Peningkatan prestasi yang mantap").
2. DILARANG SAMA SEKALI guna bahasa terjemahan kaku atau perkataan rekaan/palsu.
3. DILARANG SAMA SEKALI guna Bahasa Indonesia (Contoh DILARANG: "bisa", "banget", "nggak", "komputer jinjing").

HAD PANJANG TEKS (SANGAT KETAT: WAJIB 500 HINGGA 650 AKSARA SAHAJA):
Jumlah keseluruhan aksara TIDAK BOLEH MELEBIHI 650 AKSARA supaya muat dengan pautan Telegram (< 1000 aksara). Susun mengikut 3 fasa:

FASA 1: HOOK TECH / SETUP PROBLEM (~150 aksara)
- Mulakan dengan soalan/luahan santai soalan bab tech atau masalah setup yang relatable (contoh: meja berserabut, nak upgrade PC/laptop, gajet lama slow, masalah kabel).

FASA 2: RACUN TECH & KELEBIHAN SPESIFIKASI (~350 aksara)
- Terangkan kelebihan fizikal, kualiti binaan, atau spesifikasi gajet ini dengan ringkas, padat, dan meyakinkan.

FASA 3: CALL TO ACTION MESRA & HASHTAGS (~120 aksara)
- Ajak komuniti tengok/dapatkan secara santai (*soft-sell*) dan sertakan 3-4 hashtag tech tempatan di akhir ayat.

ARAHAN KETAT (NEGATIVE CONSTRAINTS):
- Jangan keluarkan sebarang sintaks kod (seperti ```markdown, JSON, console.log).
- Hanya keluarkan TEKS AYAT PROMOSI SAHAJA tanpa sebarang ulasan sistem.
"""

def generate_caption(base_url, model, api_key, product_title, product_desc):
    """Menjana kapsyen promosi penceritaan tech yang selamat di bawah 700 aksara"""
    if not base_url or not model or not api_key:
        return False, "Maklumat pengesahan OpenRouter API tidak lengkap."

    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json; charset=utf-8"
    }
    
    prompt_user = (
        f"Sila buatkan ayat promosi santai gaya Tech Specialist Malaysia (500-650 aksara sahaja) untuk produk ini:\n"
        f"Nama Produk: {product_title}\n"
        f"Deskripsi/Info: {product_desc}"
    )
    
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt_user}
        ],
        "temperature": 0.7,
        "max_tokens": 400
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.encoding = 'utf-8'
        
        if response.status_code == 200:
            data = response.json()
            caption = data['choices'][0]['message']['content'].strip()
            
            # HARD SAFETY GUARDRAIL: Potong automatik jika melebihi 750 aksara untuk elak ralat Telegram
            if len(caption) > 750:
                caption = caption[:747] + "..."
                
            return True, caption
        else:
            return False, f"OpenRouter API Ralat HTTP {response.status_code}: {response.text}"
    except Exception as e:
        return False, f"Ralat Rangkaian AI OpenRouter: {str(e)}"