from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from telegram_catalog.keyboards import get_main_menu_keyboard

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mengendalikan arahan /start"""
    user = update.effective_user
    greeting_name = user.first_name if user else "Kawan"

    text = (
        f"👋 **Hai, {greeting_name}! Selamat Datang ke Lubuk Barang Murah Padu.**\n\n"
        f"Pilih mana-mana butang di bawah untuk mula meneroka tawaran terbaik kami:"
    )

    if update.message:
        await update.message.reply_text(
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_menu_keyboard()
        )
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_menu_keyboard()
        )