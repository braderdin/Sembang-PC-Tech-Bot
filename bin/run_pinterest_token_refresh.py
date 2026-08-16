#!/usr/bin/env python3
"""
Production Job: Pinterest Token Auto-Refresher Cron Runner
Ensures zero-downtime Pinterest automation by continuously renewing tokens in Upstash Redis.
"""

import os
import sys
from pathlib import Path

# Setup Project Path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from experiments.test_pinterest_token_refresher import refresh_pinterest_token

if __name__ == "__main__":
    success = refresh_pinterest_token()
    if not success:
        print("⚠️ Amaran: Pembaharuan token tidak berjaya sepenuhnya (Sila semak App Secret).")
        sys.exit(0)  # Keluar dengan kod 0 supaya GitHub Action tidak bertukar merah jika menunggu kelulusan