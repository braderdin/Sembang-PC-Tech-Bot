import os
from pathlib import Path
from dotenv import load_dotenv

# Cari fail .env.local di root project
ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_LOCAL_PATH = ROOT_DIR / ".env.local"

if ENV_LOCAL_PATH.exists():
    load_dotenv(dotenv_path=ENV_LOCAL_PATH)
else:
    load_dotenv()

# Telegram Credentials
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_CATALOG_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_ADMIN_USER_ID = os.getenv("TELEGRAM_ADMIN_USER_ID", "")
TELEGRAM_BOT_USERNAME = os.getenv("TELEGRAM_CATALOG_BOT_USERNAME", "")

# Supabase Credentials
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY", "")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("⚠️ TELEGRAM_CATALOG_BOT_TOKEN tidak dijumpai dalam .env.local!")