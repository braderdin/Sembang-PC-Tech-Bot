#!/usr/bin/env python3
"""
Instagram Dedicated Vector Memory Manager (Upstash Vector REST API)
Sembang PC & Tech Ecosystem (100% Environment Driven)
"""

import os
import requests
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


class InstagramVectorManager:
    """Pengurus memori vektor hantaran Instagram melalui Upstash Vector REST API."""

    def __init__(self):
        self.vector_url = os.getenv("UPSTASH_VECTOR_REST_URL", "").strip().rstrip("/")
        self.vector_token = os.getenv("UPSTASH_VECTOR_REST_TOKEN", "").strip()

    def store_post_vector(self, text: str, product_id: str, title: str = "") -> bool:
        """Menyimpan data teks ke Upstash Vector DB secara dinamik."""
        if not self.vector_url or not self.vector_token:
            return False

        headers = {
            "Authorization": f"Bearer {self.vector_token}",
            "Content-Type": "application/json",
        }
        endpoint = f"{self.vector_url}/upsert"
        payload = {
            "id": f"ig_{product_id}",
            "data": f"{title} {text}".strip(),
            "metadata": {"title": title, "platform": "instagram"},
        }
        try:
            res = requests.post(endpoint, headers=headers, json=payload, timeout=10)
            return res.status_code == 200
        except Exception as e:
            print(f"⚠️ [Instagram Vector Warning] {e}")
            return False


# Singleton instance
instagram_vector = InstagramVectorManager()