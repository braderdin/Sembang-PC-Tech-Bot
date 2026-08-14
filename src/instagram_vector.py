#!/usr/bin/env python3
"""
Instagram Dedicated Vector Memory & Similarity Manager
Sembang PC & Tech Ecosystem
"""

import os
import json
import math
from datetime import datetime
from typing import List, Dict, Any, Optional
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Konfigurasi Google Gemini Embeddings
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

EMBEDDING_MODEL = "models/text-embedding-004"
DEFAULT_SIMILARITY_THRESHOLD = 0.85  # Had kesamaan 85% dianggap serupa


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Mengira nilai kesamaan kosinus (Cosine Similarity) antara 2 vektor."""
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm_a = math.sqrt(sum(a * a for a in vec1))
    norm_b = math.sqrt(sum(b * b for b in vec2))
    
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
        
    return dot_product / (norm_a * norm_b)


class InstagramVectorManager:
    """Pengurus memori vektor semantik khas hantaran Instagram."""

    def __init__(self, memory_file: str = "data/instagram_vectors.json"):
        self.memory_file = memory_file
        self.vectors_cache: List[Dict[str, Any]] = []
        self._load_memory()

    def _load_memory(self):
        """Memuat naik arkib vektor Instagram dari storan setempat."""
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    self.vectors_cache = json.load(f)
            except Exception as e:
                print(f"⚠️ [Instagram Vector] Ralat membaca fail memori: {e}")
                self.vectors_cache = []
        else:
            # Pastikan folder wujud
            os.makedirs(os.path.dirname(self.memory_file), exist_ok=True)
            self.vectors_cache = []

    def _save_memory(self):
        """Menyimpan data vektor terkini ke dalam fail JSON."""
        try:
            os.makedirs(os.path.dirname(self.memory_file), exist_ok=True)
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(self.vectors_cache[-150:], f, ensure_ascii=False, indent=2)  # Simpan 150 rekod terbaru
        except Exception as e:
            print(f"⚠️ [Instagram Vector] Ralat menyimpan fail memori: {e}")

    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Menjana array vektor menggunakan model Gemini Embedding."""
        if not GEMINI_API_KEY:
            return None
        try:
            clean_text = text.replace("\n", " ").strip()
            response = genai.embed_content(
                model=EMBEDDING_MODEL,
                content=clean_text,
                task_type="retrieval_document"
            )
            return response.get("embedding", None)
        except Exception as e:
            print(f"⚠️ [Instagram Vector] Ralat penjanaan embedding: {e}")
            return None

    def is_caption_too_similar(
        self, new_caption: str, threshold: float = DEFAULT_SIMILARITY_THRESHOLD
    ) -> bool:
        """
        Menyemak sama ada kapsyen baharu terlalu serupa dengan koleksi kapsyen IG sebelum ini.
        Mengembalikan True jika serupa (perlu jana baru), False jika segar/unik.
        """
        new_vec = self.generate_embedding(new_caption)
        if not new_vec or not self.vectors_cache:
            return False  # Jika tiada asas semakan, benarkan terus

        for item in self.vectors_cache:
            past_vec = item.get("embedding")
            if not past_vec:
                continue
            sim_score = cosine_similarity(new_vec, past_vec)
            if sim_score >= threshold:
                print(f"⚠️ [Instagram Vector] Kapsyen terlalu serupa ({sim_score:.2%}) dengan hantaran: '{item.get('title', '')}'")
                return True

        return False

    def store_post_vector(
        self, text: str, title: str = "", post_type: str = "affiliate", media_id: str = ""
    ) -> bool:
        """
        Menyimpan vektor kapsyen yang telah berjaya dipos ke dalam arkib memori IG.
        """
        vector = self.generate_embedding(text)
        if not vector:
            return False

        record = {
            "title": title,
            "type": post_type,
            "media_id": media_id,
            "timestamp": datetime.now().isoformat(),
            "embedding": vector,
            "preview": text[:100] + "..."
        }

        self.vectors_cache.append(record)
        self._save_memory()
        return True


# Singleton instance untuk kemudahan import
instagram_vector = InstagramVectorManager()