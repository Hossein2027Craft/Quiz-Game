import sqlite3
from pathlib import Path
# مسیر دیتابیس
DB_PATH = Path(__file__).resolve().parent / "quiz_game.db"
# ساخت جدول بازیکنان
def initialize_db():
    connection = sqlite3.connect(DB_PATH)
    try:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_code TEXT NOT NULL,
                player_name TEXT NOT NULL,
                player_role TEXT NOT NULL,
                joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(room_code, player_name)
            )
        """)
        connection.commit()
    finally:
        connection.close()
# ذخیره نام بازیکن
def save_player(room_code, player_name, player_role="player"):
    connection = sqlite3.connect(DB_PATH)
    try:
        connection.execute("""
            INSERT INTO players (
                room_code,
                player_name,
                player_role
            )
            VALUES (?, ?, ?)
        """, (room_code, player_name, player_role))
        connection.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        connection.close()
# دریافت بازیکنان یک اتاق
def get_players(room_code):
    connection = sqlite3.connect(DB_PATH)
    try:
        cursor = connection.execute("""
            SELECT player_name
            FROM players
            WHERE room_code = ?
            ORDER BY id
        """, (room_code,))
        return [row[0] for row in cursor.fetchall()]
    finally:
        connection.close()
# ساخت دیتابیس در شروع برنامه
initialize_db()