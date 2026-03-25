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
                auto_approve_high INTEGER DEFAULT 0,
                banned_phrases TEXT DEFAULT '',
                signoff_library TEXT DEFAULT '',
                brand_facts TEXT DEFAULT '',
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

            CREATE TABLE IF NOT EXISTS notification_prefs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL REFERENCES users(id),
                channel TEXT NOT NULL,
                target TEXT NOT NULL,
                events TEXT NOT NULL DEFAULT 'new_review,draft_ready',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS team_memberships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL REFERENCES users(id),
                member_user_id INTEGER REFERENCES users(id),
                email TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'staff',
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                target_type TEXT DEFAULT '',
                target_id INTEGER,
                meta TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_audit_account ON audit_log(account_id);

            CREATE TABLE IF NOT EXISTS dead_letters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task TEXT NOT NULL,
                payload TEXT NOT NULL,
                error TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            );
        """)

        # Backfill new columns for existing databases
        for sql in [
            "ALTER TABLE businesses ADD COLUMN auto_approve_high INTEGER DEFAULT 0",
            "ALTER TABLE businesses ADD COLUMN banned_phrases TEXT DEFAULT ''",
            "ALTER TABLE businesses ADD COLUMN signoff_library TEXT DEFAULT ''",
            "ALTER TABLE businesses ADD COLUMN brand_facts TEXT DEFAULT ''",
        ]:
            try:
                conn.execute(sql)
            except Exception:
                pass


# --- Helper queries ---

def create_user(email: str, name: str, google_id: str, access_token: str = "", refresh_token: str = "") -> int:
    from datetime import timedelta
    trial_end = (datetime.utcnow() + timedelta(days=7)).isoformat()
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


def create_business(
    user_id: int,
    name: str,
    business_type: str,
    location: str,
    tone: str = "friendly and professional",
    auto_approve_high: int = 0,
    banned_phrases: str = "",
    signoff_library: str = "",
    brand_facts: str = "",
) -> int:
    with db_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO businesses (user_id, name, type, location, tone, auto_approve_high, banned_phrases, signoff_library, brand_facts)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, name, business_type, location, tone, auto_approve_high, banned_phrases, signoff_library, brand_facts)
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


def get_reviews(
    business_id: int,
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
    rating_filter: str | None = None,
    search: str | None = None,
) -> list[dict]:
    sql = """
        SELECT r.*, resp.ai_response, resp.edited_response, resp.status as response_status, resp.id as response_id
        FROM reviews r
        LEFT JOIN responses resp ON resp.review_id = r.id
        WHERE r.business_id = :biz
    """
    params = {"biz": business_id, "limit": limit, "offset": offset}
    if status == "pending":
        sql += " AND (resp.status IS NULL OR resp.status != 'approved')"
    elif status == "approved":
        sql += " AND resp.status = 'approved'"
    if rating_filter == "neg":
        sql += " AND r.rating <= 2"
    elif rating_filter == "mid":
        sql += " AND r.rating = 3"
    elif rating_filter == "pos":
        sql += " AND r.rating >= 4"
    if search:
        sql += " AND (r.text LIKE :q OR r.author LIKE :q)"
        params["q"] = f"%{search}%"
    sql += " ORDER BY r.created_at DESC LIMIT :limit OFFSET :offset"
    with db_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
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


def count_reviews(business_id: int) -> int:
    with db_connection() as conn:
        row = conn.execute("SELECT COUNT(*) as c FROM reviews WHERE business_id = ?", (business_id,)).fetchone()
        return row["c"] if row else 0


# --- Audit log ---

def add_audit(account_id: int, user_id: int, action: str, target_type: str = "", target_id: int | None = None, meta: str = ""):
    with db_connection() as conn:
        conn.execute(
            "INSERT INTO audit_log (account_id, user_id, action, target_type, target_id, meta, created_at) VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
            (account_id, user_id, action, target_type, target_id, meta)
        )


def log_dead_letter(task: str, payload: str, error: str):
    with db_connection() as conn:
        conn.execute(
            "INSERT INTO dead_letters (task, payload, error, created_at) VALUES (?, ?, ?, datetime('now'))",
            (task, payload, error[:1000])
        )


def get_dead_letters(limit: int = 50) -> list[dict]:
    with db_connection() as conn:
        rows = conn.execute("SELECT * FROM dead_letters ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]


def approve_response(response_id: int, edited_text: str = "") -> None:
    with db_connection() as conn:
        conn.execute(
            "UPDATE responses SET status = 'approved', edited_response = ?, published_at = datetime('now') WHERE id = ?",
            (edited_text, response_id)
        )


# --- Notifications ---

def get_notification_prefs(account_id: int) -> list[dict]:
    with db_connection() as conn:
        rows = conn.execute("SELECT * FROM notification_prefs WHERE account_id = ?", (account_id,)).fetchall()
        return [dict(r) for r in rows]


def save_notification_pref(account_id: int, channel: str, target: str, events: str) -> None:
    with db_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM notification_prefs WHERE account_id = ? AND channel = ?",
            (account_id, channel)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE notification_prefs SET target = ?, events = ?, updated_at = datetime('now') WHERE id = ?",
                (target, events, existing["id"])
            )
        else:
            conn.execute(
                "INSERT INTO notification_prefs (account_id, channel, target, events) VALUES (?, ?, ?, ?)",
                (account_id, channel, target, events)
            )


# --- Team ---

def create_team_invite(account_id: int, email: str, role: str) -> int:
    with db_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM team_memberships WHERE account_id = ? AND email = ?",
            (account_id, email)
        ).fetchone()
        if existing:
            conn.execute("UPDATE team_memberships SET role = ?, status = 'pending', updated_at = datetime('now') WHERE id = ?",
                         (role, existing["id"]))
            return existing["id"]
        cur = conn.execute(
            "INSERT INTO team_memberships (account_id, email, role, status) VALUES (?, ?, ?, 'pending')",
            (account_id, email, role)
        )
        return cur.lastrowid


def get_team_members(account_id: int) -> list[dict]:
    with db_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM team_memberships WHERE account_id = ? ORDER BY created_at DESC",
            (account_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def attach_member_user(email: str, user_id: int) -> dict | None:
    """Link a logged-in user to a pending invite."""
    with db_connection() as conn:
        invite = conn.execute(
            "SELECT * FROM team_memberships WHERE email = ? AND status = 'pending' ORDER BY created_at DESC LIMIT 1",
            (email,)
        ).fetchone()
        if not invite:
            return None
        conn.execute(
            "UPDATE team_memberships SET member_user_id = ?, status = 'active', updated_at = datetime('now') WHERE id = ?",
            (user_id, invite["id"])
        )
        return dict(invite)


def remove_team_member(account_id: int, member_id: int) -> None:
    with db_connection() as conn:
        conn.execute("DELETE FROM team_memberships WHERE account_id = ? AND id = ?", (account_id, member_id))


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
