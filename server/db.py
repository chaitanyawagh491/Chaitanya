import sqlite3
import os
import bcrypt
from pathlib import Path

DB_PATH = Path(__file__).parent / "auth.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(10)).decode("utf-8")

def init_db():
    os.makedirs(Path(DB_PATH).parent, exist_ok=True)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user',
        hwid TEXT DEFAULT NULL,
        is_banned INTEGER DEFAULT 0,
        credits INTEGER DEFAULT 15,
        credits_unlimited INTEGER DEFAULT 0,
        lifetime_requests INTEGER DEFAULT 0,
        last_request_at TEXT DEFAULT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        last_login TEXT
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS login_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        ip_address TEXT,
        hwid TEXT,
        status TEXT,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        actor TEXT NOT NULL,
        action TEXT NOT NULL,
        target TEXT,
        ip_address TEXT,
        details TEXT,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS system_config (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS invite_keys (
        key TEXT PRIMARY KEY,
        is_used INTEGER DEFAULT 0,
        used_by TEXT DEFAULT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()
    cursor.execute("SELECT * FROM users WHERE username = ?", ("admin",))
    if not cursor.fetchone():
        admin_pass = os.environ.get("ADMIN_PASSWORD", "admin123")
        hashed = hash_password(admin_pass)
        cursor.execute(
            "INSERT INTO users (username, password_hash, role, credits, credits_unlimited) VALUES (?, ?, ?, ?, ?)",
            ("admin", hashed, "admin", 15, 1)
        )
        print("[DB] Seeded administrator account: admin")
    configs = {
        "latest_version": "3.0.0",
        "changelog": "Portal Client v3.0.0",
        "download_url": "",
        "announcements": "Welcome to local development server."
    }
    for key, value in configs.items():
        cursor.execute("SELECT * FROM system_config WHERE key = ?", (key,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO system_config (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()
    print("[DB] Database initialization complete.")

if __name__ == "__main__":
    init_db()
