from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from telegram_catalog.keyboards import get_categories_keyboard, get_back_button, get_main_menu_keyboard

async def menu_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mengendalikan klik butang menu"""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "menu:main":
        user = update.effective_user
        greeting_name = user.first_name if user else "Kawan"
        text = (
            f"👋 **Hai, {greeting_name}! Selamat Datang ke Lubuk Barang Murah Padu.**\n\n"
            f"Pilih fungsi yang anda inginkan di bawah:"
        )
        await query.edit_message_text(
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_menu_keyboard()
        )

    elif data == "menu:categories":
        text = "📂 **Pilih Kategori Produk:**\n\nSila pilih segmen barang yang ingin anda lihat:"
        await query.edit_message_text(
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_categories_keyboard()
        )

    elif data == "menu:hot_deals":
        text = (
            "🔥 **Tawaran Hangat Terpilih!**\n\n"
            "Senarai tawaran promosi terbaik sedang dimuatkan terus daripada pangkalan data Supabase..."
        )
        await query.edit_message_text(
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_back_button()
        )

    elif data == "menu:random":
        text = "🎲 **Pilihan Rawak Menarik:**\n\nMencari barangan berkualiti untuk anda..."
        await query.edit_message_text(
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_back_button()
        )

    elif data == "menu:help":
        text = (
            "ℹ️ **Panduan Lubuk Barang Murah**\n\n"
            "• Anda tidak perlu menaip apa-apa arahan.\n"
            "• Gunakan butang sentuhan interaktif untuk memilih barang.\n"
            "• Semua pautan belian disahkan terus daripada rakan niaga rasmi."
        )
        await query.edit_message_text(
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_back_button()
        )

    elif data.startswith("cat:"):
        cat_key = data.split(":")[1]
        text = f"📦 **Memaparkan barangan bagi kategori:** `{cat_key}`\n\nSedang menyambung ke pangkalan data..."
        await query.edit_message_text(
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_categories_keyboard()
        )