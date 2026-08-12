import os
import json
from datetime import datetime

# Mengira laluan akar projek (PROJECT_ROOT) secara dinamik supaya folder 'data' sentiasa ditemui dari dalam 'src'
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_POOL_FILE = os.path.join(PROJECT_ROOT, "data", "affiliate_link_pool.json")

def ensure_data_directory(file_path=DEFAULT_POOL_FILE):
    """Memastikan folder simpanan data wujud secara automatik[cite: 7]."""
    dir_name = os.path.dirname(file_path)
    if dir_name and not os.path.exists(dir_name):
        os.makedirs(dir_name, exist_ok=True)

def load_link_pool(file_path=DEFAULT_POOL_FILE):
    """Membaca senarai pautan affiliate yang disimpan daripada fail JSON[cite: 7]."""
    ensure_data_directory(file_path)
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception as e:
        print(f"⚠️ [LINK POOL WARN] Gagal membaca fail pool: {e}")
        return []

def save_link_pool(link_items, file_path=DEFAULT_POOL_FILE):
    """Menyimpan keseluruhan senarai pautan affiliate ke dalam fail JSON[cite: 7]."""
    ensure_data_directory(file_path)
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(link_items, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"❌ [LINK POOL ERROR] Gagal menyimpan fail pool: {e}")
        return False

def add_links_to_pool(new_items, file_path=DEFAULT_POOL_FILE):
    """
    Menambah pautan produk affiliate baharu ke dalam simpanan pool[cite: 7].
    Secara automatik menapis produk berulang (deduplication) berasaskan product_id[cite: 7].
    Memulangkan: (added_count, total_pool_count)[cite: 7]
    """
    current_pool = load_link_pool(file_path)
    existing_ids = {str(item.get("product_id") or item.get("id")) for item in current_pool}
    
    added_count = 0
    for item in new_items:
        item_id = str(item.get("product_id") or item.get("id") or "").strip()
        if item_id and item_id not in existing_ids:
            existing_ids.add(item_id)
            item_entry = {
                "product_id": item_id,
                "title": item.get("title", ""),
                "category": item.get("category", ""),
                "keyword": item.get("keyword", ""),
                "original_url": item.get("original_url", ""),
                "affiliate_link": item.get("affiliate_link", ""),
                "image_url": item.get("image_url", ""),
                "b2_image_url": item.get("b2_image_url", ""),
                "commission_rate": item.get("commission_rate", ">=2.5%"),  # Dilaraskan minima kepada >=2.5%
                "created_at": item.get("created_at") or datetime.now().isoformat()
            }
            current_pool.append(item_entry)
            added_count += 1

    if added_count > 0:
        save_link_pool(current_pool, file_path)
        
    return added_count, len(current_pool)

def get_stored_links(limit=None, file_path=DEFAULT_POOL_FILE):
    """Mengambil pautan yang tersimpan untuk digunakan oleh aplikasi utama[cite: 7]."""
    pool = load_link_pool(file_path)
    return pool[:limit] if limit else pool

def remove_link_from_pool(product_id, file_path=DEFAULT_POOL_FILE):
    """Memadam pautan daripada simpanan pool selepas ia berjaya digunakan/dijual[cite: 7]."""
    current_pool = load_link_pool(file_path)
    target_id = str(product_id).strip()
    updated_pool = [item for item in current_pool if str(item.get("product_id") or item.get("id")).strip() != target_id]
    
    if len(updated_pool) < len(current_pool):
        save_link_pool(updated_pool, file_path)
        return True
    return False