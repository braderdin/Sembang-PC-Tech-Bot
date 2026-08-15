Sembang-PC-Tech-Bot/
├── bin/
│   └── run_telegram_bot.py          # Runner utama
└── telegram_catalog/
    ├── __init__.py
    ├── config.py                     # Bacaan env selamat
    ├── keyboards.py                  # Butang-butang GUI interaktif
    ├── bot.py                        # Setup bot & routing handler
    └── handlers/
        ├── __init__.py
        ├── start.py                  # Mesej alu-aluan & Main Menu
        └── catalog.py                # Navigasi kategori & katalog Supabase