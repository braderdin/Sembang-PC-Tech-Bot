from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Menu Utama Pantas (Interactive GUI)"""
    keyboard = [
        [
            InlineKeyboardButton("🔥 Tawaran Hangat", callback_data="menu:hot_deals"),
            InlineKeyboardButton("📂 Kategori Produk", callback_data="menu:categories")
        ],
        [
            InlineKeyboardButton("🎲 Cadangan Rawak", callback_data="menu:random"),
            InlineKeyboardButton("🔍 Cara Guna / Info", callback_data="menu:help")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_categories_keyboard() -> InlineKeyboardMarkup:
    """Pilihan Kategori Produk"""
    keyboard = [
        [
            InlineKeyboardButton("💻 Laptop & PC", callback_data="cat:laptop_pc"),
            InlineKeyboardButton("📱 Telefon & Tablet", callback_data="cat:mobile")
        ],
        [
            InlineKeyboardButton("🎧 Aksesori & Audio", callback_data="cat:accessories"),
            InlineKeyboardButton("🎮 Gaming & Gear", callback_data="cat:gaming")
        ],
        [
            InlineKeyboardButton("⚡ Semua Produk Terkini", callback_data="cat:all")
        ],
        [
            InlineKeyboardButton("🔙 Kembali ke Menu Utama", callback_data="menu:main")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_back_button() -> InlineKeyboardMarkup:
    """Butang Kembali ke Menu Utama"""
    keyboard = [
        [InlineKeyboardButton("🔙 Kembali ke Menu", callback_data="menu:main")]
    ]
    return InlineKeyboardMarkup(keyboard)