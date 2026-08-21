#!/usr/bin/env python3
"""
Ujian Ping Paling Asas (Minimal Ping Test)
Lokasi Fail: experiments/test_openrouter_Ai_persona_gemma.py
"""

import os
import requests
from pathlib import Path
from dotenv import load_dotenv

# Baca fail .env.local
env_local = Path(__file__).resolve().parent.parent / ".env.local"
load_dotenv(dotenv_path=env_local if env_local.exists() else None)

BASE_URL = (os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1").rstrip("/")
API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()

# Model untuk diuji
MODELS = [
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "dots-studio/dots-3-note-preview:free"  # Model kawalan (control model)
]

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json; charset=utf-8"
}

print(f"📡 Base URL : {BASE_URL}")
print(f"🔑 API Key  : {'Dikesan (' + API_KEY[:8] + '...)' if API_KEY else 'TIADA'}\n")

for model in MODELS:
    print(f"Menguji ping ke -> {model}")
    
    # Payload paling minimum (hanya tanya khabar)
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": "Hai, apa khabar?"}
        ],
        "max_tokens": 50
    }
    
    try:
        res = requests.post(f"{BASE_URL}/chat/completions", json=payload, headers=headers, timeout=15)
        
        if res.status_code == 200:
            jawapan = res.json()["choices"][0]["message"]["content"].strip()
            print(f"  ✅ [STATUS 200 OK] Respon: {jawapan}\n")
        else:
            print(f"  ❌ [RALAT HTTP {res.status_code}] Mesej Pelayan: {res.text}\n")
            
    except Exception as e:
        print(f"  ⚠️ [EXCEPTION]: {e}\n")