#!/usr/bin/env python3
"""
Diagnostic & Permission Verification Script for Meta Instagram API
Sembang PC & Tech Ecosystem (Optimized for Page Access Token)
"""

import os
import sys
import requests
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# 1. Muat naik pembolehubah persekitaran (.env.local diutamakan)
root_dir = Path(__file__).resolve().parent.parent.parent
env_local_path = root_dir / ".env.local"
env_path = root_dir / ".env"

if env_local_path.exists():
    load_dotenv(dotenv_path=env_local_path)
    print(f"📄 Memuatkan konfigurasi dari: {env_local_path.name}")
elif env_path.exists():
    load_dotenv(dotenv_path=env_path)
    print(f"📄 Memuatkan konfigurasi dari: {env_path.name}")
else:
    load_dotenv()
    print("⚠️ Fail .env/.env.local tidak dijumpai, membaca persekitaran sistem.")

# 2. Ambil Kunci Instagram
IG_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID", "").strip()
IG_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "").strip()
IG_APP_ID = os.getenv("INSTAGRAM_APP_ID", "").strip()

GRAPH_API_VERSION = "v26.0"
GRAPH_BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


def print_separator(title=""):
    print("\n" + "=" * 60)
    if title:
        print(f"  {title}")
        print("=" * 60)


def test_keys_presence():
    print_separator("🔍 UJIAN 1: SEMAKAN KUNCI DALAM ENV")
    keys = {
        "INSTAGRAM_ACCOUNT_ID": IG_ACCOUNT_ID,
        "INSTAGRAM_ACCESS_TOKEN": IG_ACCESS_TOKEN,
    }
    
    all_present = True
    for key_name, key_val in keys.items():
        if key_val:
            masked = key_val[:4] + "..." + key_val[-4:] if len(key_val) > 8 else "***"
            print(f"  ✅ {key_name:<25}: DIJUMPAI ({masked})")
        else:
            print(f"  ❌ {key_name:<25}: KOSONG / TIADA!")
            all_present = False
            
    return all_present


def test_token_debug_and_permissions():
    print_separator("🔐 UJIAN 2: STATUS TOKEN & PERMISSIONS")
    
    debug_url = f"{GRAPH_BASE_URL}/debug_token"
    params = {
        "input_token": IG_ACCESS_TOKEN,
        "access_token": IG_ACCESS_TOKEN
    }
    
    try:
        response = requests.get(debug_url, params=params, timeout=15)
        res_json = response.json()
        
        if response.status_code != 200 or "error" in res_json:
            # Fallback jika debug_token memerlukan app token
            url = f"{GRAPH_BASE_URL}/me/permissions"
            perm_res = requests.get(url, params={"access_token": IG_ACCESS_TOKEN}, timeout=15).json()
            if "data" in perm_res:
                print("  ✅ Token Aktif & Sah (Membaca kebenaran dari Page Permissions)")
                for p in perm_res["data"]:
                    if p.get("status") == "granted":
                        print(f"     - {p.get('permission')}")
                return True
            print(f"  ❌ Ralat Semakan Token: {res_json.get('error', {}).get('message', res_json)}")
            return False
            
        data = res_json.get("data", {})
        is_valid = data.get("is_valid", False)
        token_type = data.get("type", "Unknown")
        expires_at = data.get("expires_at", 0)
        scopes = data.get("scopes", [])
        
        print(f"  • Token Valid     : {'✅ SAH (True)' if is_valid else '❌ TIDAK SAH'}")
        print(f"  • Token Type      : {token_type} {'(Page Token - Sesuai!)' if token_type == 'PAGE' else ''}")
        
        if expires_at == 0:
            print(f"  • Status Hayat    : ✅ NEVER EXPIRES (Token Kekal)")
        else:
            exp_date = datetime.fromtimestamp(expires_at).strftime('%Y-%m-%d %H:%M:%S')
            print(f"  • Status Hayat    : ⚠️ Akan Luput Pada {exp_date}")

        print(f"\n  📋 Senarai Permissions Aktif ({len(scopes)} scopes):")
        for scope in scopes:
            print(f"     - {scope}")
            
        return is_valid
        
    except requests.exceptions.RequestException as e:
        print(f"  ❌ Gagal berhubung ke Meta Graph API: {str(e)}")
        return False


def test_instagram_account_profile():
    print_separator("👤 UJIAN 3: MAKLUMAT AKAUN INSTAGRAM")
    
    url = f"{GRAPH_BASE_URL}/{IG_ACCOUNT_ID}"
    params = {
        "fields": "id,username,name,biography,followers_count,follows_count,media_count",
        "access_token": IG_ACCESS_TOKEN
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        res_json = response.json()
        
        if response.status_code != 200 or "error" in res_json:
            err = res_json.get("error", {})
            print(f"  ❌ Gagal membaca profil ({response.status_code}):")
            print(f"     Kod Ralat : {err.get('code')}")
            print(f"     Mesej     : {err.get('message')}")
            print(f"     Subcode   : {err.get('error_subcode', 'N/A')}")
            return False
            
        print(f"  ✅ Akaun Berjaya Ditemui:")
        print(f"  • Username       : @{res_json.get('username', 'N/A')}")
        print(f"  • Nama Paparan   : {res_json.get('name', 'N/A')}")
        print(f"  • Account ID     : {res_json.get('id', 'N/A')}")
        print(f"  • Jumlah Media   : {res_json.get('media_count', 0)} hantaran")
        print(f"  • Pengikut       : {res_json.get('followers_count', 0)} followers")
        print(f"  • Bio            :\n    {res_json.get('biography', '').strip()}")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"  ❌ Ralat Permintaan: {str(e)}")
        return False


def main():
    print("\n🚀 MEMULAKAN UJIAN DIAGNOSTIK KUNCI META INSTAGRAM")
    
    if not test_keys_presence():
        sys.exit(1)
        
    t2 = test_token_debug_and_permissions()
    t3 = test_instagram_account_profile()
    
    print_separator("🏁 KEPUTUSAN KESELURUHAN")
    if t2 and t3:
        print("  🎉 TAHNIAH! Kunci Instagram 100% SAH & BERSEDIA UNTUK AUTO-POST!")
    else:
        print("  ⚠️ Sila pastikan anda memilih Page Access Token di Graph Explorer.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()