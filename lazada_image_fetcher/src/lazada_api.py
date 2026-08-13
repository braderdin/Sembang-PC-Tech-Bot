import os
import time
import hmac
import hashlib
import requests
import json

def generate_lazada_signature(api_path, params, app_secret):
    """
    Menjana tandatangan rasmi HMAC-SHA256 Lazada Open API.
    """
    sorted_keys = sorted(params.keys())
    
    sign_string = api_path
    for k in sorted_keys:
        if k != "sign" and params[k] is not None:
            sign_string += f"{k}{params[k]}"
            
    signature = hmac.new(
        app_secret.encode("utf-8"),
        sign_string.encode("utf-8"),
        hashlib.sha256
    ).hexdigest().upper()
    
    return signature

def fetch_product_images_from_lazada(product_id):
    """
    Memanggil API Rasmi Lazada Affiliate Feed (/marketing/product/feed)
    untuk mendapatkan senarai gambar produk ('pictures').
    """
    app_key = os.getenv("LAZADA_APP_KEY", "").strip() or os.getenv("LAZADA_LITEAPP_KEY", "").strip()
    app_secret = os.getenv("LAZADA_APP_SECRET", "").strip() or os.getenv("LAZADA_LITEAPP_SECRET", "").strip()
    user_token = os.getenv("LAZADA_USER_TOKEN", "").strip()

    print("\n--------------------------------------------------")
    print("🔑 [LAZADA CONFIG CHECK]")
    print(f"   APP_KEY     : {app_key[:6]}***" if app_key else "   APP_KEY     : ❌ Tidak dijumpai")
    print(f"   APP_SECRET  : {app_secret[:6]}***" if app_secret else "   APP_SECRET  : ❌ Tidak dijumpai")
    print(f"   USER_TOKEN  : {user_token[:6]}***" if user_token else "   USER_TOKEN  : ❌ Tidak dijumpai")
    print("--------------------------------------------------")

    if not app_key or not app_secret or not user_token:
        return False, [], "Kunci LAZADA_APP_KEY, LAZADA_APP_SECRET, atau LAZADA_USER_TOKEN tidak lengkap dalam .env.local."

    base_url = "https://api.lazada.com.my/rest"
    api_path = "/marketing/product/feed"

    print(f"\n📡 [LAZADA REQUEST] Memanggil Marketing Product Feed API bagi Product ID: {product_id}...")

    timestamp = str(int(time.time() * 1000))
    
    params = {
        "app_key": app_key,
        "timestamp": timestamp,
        "sign_method": "sha256",
        "userToken": user_token,
        "offerType": "1",
        "page": "1",
        "limit": "10",
        "productIds": f"[{product_id}]"
    }

    params["sign"] = generate_lazada_signature(api_path, params, app_secret)

    try:
        res = requests.get(f"{base_url}{api_path}", params=params, timeout=20)
        print(f"📥 [LAZADA HTTP STATUS] HTTP {res.status_code}")
        
        try:
            res_json = res.json()
        except Exception:
            return False, [], f"Respons bukan format JSON: {res.text}"

        print("\n🔍 [LAZADA RAW RESPONSE DATA]:")
        print(json.dumps(res_json, indent=2, ensure_ascii=False))

        if res_json.get("code") != "0":
            err_code = res_json.get("code", "UNKNOWN")
            err_msg = res_json.get("message", "Tiada mesej ralat spesifik")
            return False, [], f"Lazada API Error [{err_code}]: {err_msg}"

        # Pembacaan tepat: Ekstrak 'data' di dalam 'result'
        result_obj = res_json.get("result", {})
        products = []
        if isinstance(result_obj, dict):
            products = result_obj.get("data", [])
        elif isinstance(result_obj, list):
            products = result_obj
        else:
            products = res_json.get("data", [])

        image_list = []
        if isinstance(products, list) and len(products) > 0:
            target_product = products[0]
            raw_pictures = target_product.get("pictures") or target_product.get("images") or []
            
            if isinstance(raw_pictures, list):
                image_list = [img for img in raw_pictures if isinstance(img, str) and img.startswith("http")]
            elif isinstance(raw_pictures, str) and raw_pictures.startswith("http"):
                image_list = [raw_pictures]

        if image_list:
            return True, image_list, f"Berjaya menarik {len(image_list)} gambar dari Lazada Affiliate API."
        else:
            return False, [], "API memberi respons berjaya tetapi tiada senarai gambar dijumpai dalam medan 'pictures'."

    except Exception as e:
        return False, [], f"Ralat Rangkaian semasa memanggil Lazada API: {str(e)}"