import sqlite3

# Connect to or create the database
conn = sqlite3.connect("users.db")
c = conn.cursor()

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
        is_admin INTEGER DEFAULT 0
    )
""")

# Add new columns to store up to 5 gallery image paths
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
        # Column might already exist if re-run
        print(f"Column already exists for error adding: {col}")

# Create a table to store reports
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

c.execute("""
    CREATE TABLE IF NOT EXISTS blocks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        blocker TEXT NOT NULL,
        blocked TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
""")


# Table to store likes
c.execute("""
    CREATE TABLE IF NOT EXISTS likes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        liker TEXT NOT NULL,
        liked TEXT NOT NULL
    )
""")

# Table for messages
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

# Create session_logs table to track login/logout activity
c.execute("""
    CREATE TABLE IF NOT EXISTS session_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        login_time DATETIME,
        logout_time DATETIME,
        duration_seconds INTEGER
    )
""")

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
