#!/usr/bin/env python3
"""
Pinterest API v5 Auto-Token Refresher Engine (Test / Experiment)
Sembang PC & Tech Ecosystem
Features:
1. Reads initial tokens from .env.local / Environment.
2. Checks token validity & expiry timestamp stored in Upstash Redis.
3. Performs OAuth 2.0 refresh_token exchange via Pinterest v5 API.
4. Persists new access_token, refresh_token, and TTL into Upstash Redis.
5. Resilient error-handling for pending APP_SECRET approvals.
"""

import os
import sys
import time
import base64
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

# Set Project Root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load .env.local
env_local = PROJECT_ROOT / ".env.local"
if env_local.exists():
    load_dotenv(dotenv_path=env_local)
else:
    load_dotenv()

# Upstash Redis Configuration
REDIS_URL = os.getenv("UPSTASH_REDIS_REST_URL", "").strip().rstrip("/")
REDIS_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN", "").strip()

# Pinterest Configuration
PINTEREST_APP_ID = os.getenv("PINTEREST_APP_ID", "").strip()
PINTEREST_APP_SECRET = os.getenv("PINTEREST_APP_SECRET", "").strip()
PINTEREST_ACCESS_TOKEN = os.getenv("PINTEREST_ACCESS_TOKEN", "").strip()
PINTEREST_REFRESH_TOKEN = os.getenv("PINTEREST_REFRESH_TOKEN", "").strip()

REDIS_KEY_AUTH = "pinterest:auth_data"
REDIS_KEY_ACCESS = "pinterest:access_token"


def redis_command(command, *args):
    """Menghantar arahan REST ke Upstash Redis tanpa bergantung pada pustaka luaran."""
    if not REDIS_URL or not REDIS_TOKEN:
        return None
    url = f"{REDIS_URL}/{command}/" + "/".join(str(a) for a in args)
    headers = {"Authorization": f"Bearer {REDIS_TOKEN}"}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            return res.json().get("result")
    except Exception as e:
        print(f"⚠️ [REDIS ERROR] {e}")
    return None


def redis_set_json(key, data, ex_seconds=None):
    """Menyimpan data JSON ke Redis dengan tempoh luput (TTL)."""
    if not REDIS_URL or not REDIS_TOKEN:
        return False
    payload = json.dumps(data)
    url = f"{REDIS_URL}/set/{key}"
    headers = {
        "Authorization": f"Bearer {REDIS_TOKEN}",
        "Content-Type": "application/json"
    }
    try:
        if ex_seconds:
            res = requests.post(f"{url}?ex={ex_seconds}", headers=headers, data=payload, timeout=10)
        else:
            res = requests.post(url, headers=headers, data=payload, timeout=10)
        return res.status_code == 200
    except Exception as e:
        print(f"⚠️ [REDIS SET ERROR] {e}")
        return False


def get_current_stored_auth():
    """Mengambil rekod token terkini dari Redis atau fallback ke .env."""
    raw_data = redis_command("get", REDIS_KEY_AUTH)
    if raw_data:
        try:
            return json.loads(raw_data)
        except Exception:
            pass
    return {
        "access_token": PINTEREST_ACCESS_TOKEN,
        "refresh_token": PINTEREST_REFRESH_TOKEN,
        "expires_at": 0,
        "updated_at": 0
    }


def refresh_pinterest_token():
    print("\n" + "=" * 70)
    print("🔄 [START] ENJIN AUTO-REFRESH TOKEN PINTEREST API v5 (UPSTASH REDIS)")
    print("=" * 70)

    # 1. Semak Ketersediaan Kunci Asas
    if not REDIS_URL or not REDIS_TOKEN:
        print("❌ [RALAT] UPSTASH_REDIS_REST_URL / TOKEN tidak ditemui di persekitaran.")
        return False

    auth_data = get_current_stored_auth()
    refresh_token = auth_data.get("refresh_token") or PINTEREST_REFRESH_TOKEN
    current_access_token = auth_data.get("access_token") or PINTEREST_ACCESS_TOKEN

    print(f"📌 Pinterest App ID  : {PINTEREST_APP_ID or '[BELUM DIISI]'}")
    print(f"🔑 Status App Secret : {'Sedia (Ada Nilai)' if PINTEREST_APP_SECRET else 'Menunggu Kelulusan (Pending)'}")
    print(f"📦 Storan Memori     : Upstash Redis ({REDIS_URL[:30]}...)")

    # 2. Jika App Secret belum ada, simpan token sedia ada ke Redis untuk kegunaan awal
    if not PINTEREST_APP_SECRET or not refresh_token:
        print("\nℹ️ [STATUS SEMASA] Kunci 'PINTEREST_APP_SECRET' atau 'refresh_token' belum lengkap.")
        if current_access_token:
            print("💾 Menyimpan 'PINTEREST_ACCESS_TOKEN' sedia ada ke Redis...")
            redis_set_json(REDIS_KEY_AUTH, {
                "access_token": current_access_token,
                "refresh_token": refresh_token or "",
                "expires_at": int(time.time()) + 86400,
                "updated_at": int(time.time()),
                "status": "initial_seeded"
            })
            redis_command("set", REDIS_KEY_ACCESS, current_access_token)
            print("✅ Token sedia ada berjaya disimpan ke Upstash Redis.")
        return True

    # 3. Lakukan Pertukaran OAuth 2.0 Refresh Token jika kunci lengkap
    print("\n🚀 Memulakan panggilan OAuth 2.0 ke Pinterest API...")
    auth_header = base64.b64encode(f"{PINTEREST_APP_ID}:{PINTEREST_APP_SECRET}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    body = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }

    try:
        res = requests.post("https://api.pinterest.com/v5/oauth/token", headers=headers, data=body, timeout=15)
        if res.status_code == 200:
            data = res.json()
            new_access_token = data.get("access_token")
            new_refresh_token = data.get("refresh_token", refresh_token)
            expires_in = data.get("expires_in", 86400)  # Biasanya 24 jam (86400 saat)

            now = int(time.time())
            expires_at = now + expires_in

            new_auth_payload = {
                "access_token": new_access_token,
                "refresh_token": new_refresh_token,
                "expires_at": expires_at,
                "updated_at": now,
                "token_type": data.get("token_type", "bearer"),
                "scope": data.get("scope", "")
            }

            # Simpan ke Redis (Kunci data penuh & Kunci akses terus)
            redis_set_json(REDIS_KEY_AUTH, new_auth_payload)
            redis_command("set", REDIS_KEY_ACCESS, new_access_token)

            print("🎉 [BERJAYA] Token Pinterest berjaya diperbaharui & disimpan ke Redis!")
            print(f"  🔑 New Access Token : {new_access_token[:15]}...{new_access_token[-10:]}")
            print(f"  ⏳ Luput Pada       : {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(expires_at))}")
            return True
        else:
            print(f"❌ [API ERROR] HTTP {res.status_code}: {res.text}")
            return False
    except Exception as e:
        print(f"❌ [REQUEST ERROR] {e}")
        return False


if __name__ == "__main__":
    refresh_pinterest_token()