import sqlite3

def setup_database():
    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    # Create users table with full fields
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            display_name TEXT,
            birthday TEXT,
            location TEXT,
            country TEXT,
            favorite_animal TEXT,
            dog_free_reason TEXT,
            profile_pic TEXT,
            bio TEXT,
            gender TEXT,
            sexuality TEXT,
            show_sexuality INTEGER DEFAULT 0,
            show_gender INTEGER DEFAULT 1,
            interests TEXT,
            main_tag TEXT,
            tags TEXT,
            latitude REAL,
            longitude REAL,
            email_verified INTEGER DEFAULT 0,
            last_login DATETIME,
            is_admin INTEGER DEFAULT 0,

            -- Optional future-proofing:
            profile_completed INTEGER DEFAULT 0,
            signup_method TEXT DEFAULT 'email'
        )
    """)

    # Add gallery image columns if they don't exist
    new_columns = [
        "gallery_image_1 TEXT",
        "gallery_image_2 TEXT",
        "gallery_image_3 TEXT",
        "gallery_image_4 TEXT",
        "gallery_image_5 TEXT"
    ]

    for col in new_columns:
        try:
            c.execute(f"ALTER TABLE users ADD COLUMN {col}")
        except sqlite3.OperationalError:
            print(f"Column already exists for error adding: {col}")

    # Reports table
    c.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reported_user TEXT NOT NULL,
            reporter TEXT NOT NULL,
            reason TEXT,
            comments TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Blocks table
    c.execute("""
        CREATE TABLE IF NOT EXISTS blocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            blocker TEXT NOT NULL,
            blocked TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Likes table
    c.execute("""
        CREATE TABLE IF NOT EXISTS likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            liker TEXT NOT NULL,
            liked TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Messages table
    c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL,
            recipient TEXT NOT NULL,
            content TEXT,
            image_url TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_read INTEGER DEFAULT 0,
            is_deleted_by_sender INTEGER DEFAULT 0,
            is_deleted_by_recipient INTEGER DEFAULT 0
        )
    """)

    # Session logs for analytics
    c.execute("""
        CREATE TABLE IF NOT EXISTS session_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            login_time DATETIME,
            logout_time DATETIME,
            duration_seconds INTEGER
        )
    """)

    conn.commit()
    conn.close()
