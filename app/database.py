"""SQLite database models and connection."""
import sqlite3
from datetime import datetime
from contextlib import contextmanager
from app.config import DB_PATH


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def db_connection():
    conn = get_db()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with db_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL DEFAULT '',
                google_id TEXT UNIQUE,
                google_access_token TEXT DEFAULT '',
                google_refresh_token TEXT DEFAULT '',
                stripe_customer_id TEXT DEFAULT '',
                subscription_status TEXT DEFAULT 'trial',
                subscription_plan TEXT DEFAULT '',
                trial_ends_at TEXT DEFAULT '',
                email_verified INTEGER DEFAULT 0,
                email_token TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS businesses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                name TEXT NOT NULL,
                type TEXT NOT NULL DEFAULT 'restaurant',
                location TEXT NOT NULL DEFAULT '',
                google_location_id TEXT DEFAULT '',
                tone TEXT DEFAULT 'friendly and professional',
                owner_name TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_id INTEGER NOT NULL REFERENCES businesses(id),
                google_review_id TEXT DEFAULT '',
                author TEXT NOT NULL DEFAULT 'Customer',
                rating INTEGER NOT NULL DEFAULT 5,
                text TEXT NOT NULL DEFAULT '',
                review_time TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                review_id INTEGER NOT NULL REFERENCES reviews(id),
                ai_response TEXT NOT NULL DEFAULT '',
                edited_response TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                published_at TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now'))
            );
        """)


# --- Helper queries ---

def create_user(email: str, name: str, google_id: str, access_token: str = "", refresh_token: str = "") -> int:
    trial_end = datetime.utcnow().isoformat()
    with db_connection() as conn:
        # Check by email first (covers demo re-login)
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if not existing:
            existing = conn.execute("SELECT id FROM users WHERE google_id = ?", (google_id,)).fetchone()
        if existing:
            conn.execute(
                "UPDATE users SET google_access_token = ?, google_refresh_token = ?, updated_at = datetime('now') WHERE id = ?",
                (access_token, refresh_token or "", existing["id"])
            )
            return existing["id"]
        cursor = conn.execute(
            "INSERT INTO users (email, name, google_id, google_access_token, google_refresh_token, trial_ends_at) VALUES (?, ?, ?, ?, ?, ?)",
            (email, name, google_id, access_token, refresh_token or "", trial_end)
        )
        return cursor.lastrowid


def get_user(user_id: int) -> dict | None:
    with db_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def create_business(user_id: int, name: str, business_type: str, location: str, tone: str = "friendly and professional") -> int:
    with db_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO businesses (user_id, name, type, location, tone) VALUES (?, ?, ?, ?, ?)",
            (user_id, name, business_type, location, tone)
        )
        return cursor.lastrowid


def get_businesses(user_id: int) -> list[dict]:
    with db_connection() as conn:
        rows = conn.execute("SELECT * FROM businesses WHERE user_id = ?", (user_id,)).fetchall()
        return [dict(r) for r in rows]


def add_review(business_id: int, author: str, rating: int, text: str, google_review_id: str = "", review_time: str = "") -> int:
    with db_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO reviews (business_id, author, rating, text, google_review_id, review_time) VALUES (?, ?, ?, ?, ?, ?)",
            (business_id, author, rating, text, google_review_id, review_time)
        )
        return cursor.lastrowid


def get_reviews(business_id: int) -> list[dict]:
    with db_connection() as conn:
        rows = conn.execute("""
            SELECT r.*, resp.ai_response, resp.edited_response, resp.status as response_status, resp.id as response_id
            FROM reviews r
            LEFT JOIN responses resp ON resp.review_id = r.id
            WHERE r.business_id = ?
            ORDER BY r.created_at DESC
        """, (business_id,)).fetchall()
        return [dict(r) for r in rows]


def save_response(review_id: int, ai_response: str) -> int:
    with db_connection() as conn:
        existing = conn.execute("SELECT id FROM responses WHERE review_id = ?", (review_id,)).fetchone()
        if existing:
            conn.execute("UPDATE responses SET ai_response = ?, status = 'pending', created_at = datetime('now') WHERE id = ?",
                         (ai_response, existing["id"]))
            return existing["id"]
        cursor = conn.execute("INSERT INTO responses (review_id, ai_response, status) VALUES (?, ?, 'pending')",
                              (review_id, ai_response))
        return cursor.lastrowid


def approve_response(response_id: int, edited_text: str = "") -> None:
    with db_connection() as conn:
        conn.execute(
            "UPDATE responses SET status = 'approved', edited_response = ?, published_at = datetime('now') WHERE id = ?",
            (edited_text, response_id)
        )


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
