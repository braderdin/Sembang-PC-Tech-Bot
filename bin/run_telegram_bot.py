#!/usr/bin/env python3
import sys
from pathlib import Path

# Masukkan root path ke sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from telegram_catalog.bot import build_catalog_bot

def main():
    print("==================================================")
    print("🤖 [START] Menjalankan Telegram Catalog Bot...")
    print("==================================================")
    
    app = build_catalog_bot()
    
    print("✅ Bot berjaya diaktifkan! Sedia menerima mesej & interaksi GUI.")
    print("Tekan CTRL+C untuk berhenti.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()