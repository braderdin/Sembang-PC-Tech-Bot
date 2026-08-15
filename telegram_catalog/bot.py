from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
from telegram_catalog.config import TELEGRAM_BOT_TOKEN
from telegram_catalog.handlers.start import start_handler
from telegram_catalog.handlers.catalog import menu_callback_handler

def build_catalog_bot():
    """Membina dan mendaftarkan handler bot"""
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Daftarkan arahan asas
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("menu", start_handler))

    # Daftarkan semua interaksi butang inline (GUI)
    app.add_handler(CallbackQueryHandler(menu_callback_handler))

    return app