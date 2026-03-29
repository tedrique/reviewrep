"""Database layer — PostgreSQL (prod) with SQLite fallback (dev)."""
import os
import sqlite3
from datetime import datetime, timedelta
from contextlib import contextmanager

DATABASE_URL = os.getenv("DATABASE_URL", "")
USE_PG = DATABASE_URL.startswith("postgresql")

if USE_PG:
    import psycopg2
    import psycopg2.extras

# ---------- connection wrapper ----------

class _PgRow(dict):
    """Dict that also supports index access like sqlite3.Row."""
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class _PgCursorResult:
    """Wraps PG cursor fetchone/fetchall to return dicts like sqlite3.Row."""
    def __init__(self, cursor):
        self._cur = cursor
        self._desc = cursor.description
    def fetchone(self):
        row = self._cur.fetchone()
        if row is None:
            return None
        cols = [d[0] for d in self._desc]
        return _PgRow(zip(cols, row))
    def fetchall(self):
        rows = self._cur.fetchall()
        cols = [d[0] for d in self._desc]
        return [_PgRow(zip(cols, r)) for r in rows]
    @property
    def lastrowid(self):
        return getattr(self._cur, 'lastrowid', None)


class DbConn:
    """Wrapper that makes PG connections behave like SQLite for main.py compatibility.
    Converts ? placeholders to %s for PG, returns dict-like rows."""
    def __init__(self, raw_conn):
        self._conn = raw_conn

    def execute(self, sql, params=None):
        if USE_PG:
            sql = sql.replace("?", "%s")
            # Convert SQLite date functions to PG equivalents
            sql = sql.replace("datetime('now')", "NOW()")
            sql = sql.replace("date('now')", "CURRENT_DATE")
            sql = sql.replace("date('now','-7 day')", "(CURRENT_DATE - INTERVAL '7 days')")
            sql = sql.replace("date('now','-30 day')", "(CURRENT_DATE - INTERVAL '30 days')")
            sql = sql.replace("date('now','-60 day')", "(CURRENT_DATE - INTERVAL '60 days')")
            sql = sql.replace("date('now', 'start of month')", "date_trunc('month', CURRENT_DATE)")
            sql = sql.replace("strftime('%s',", "EXTRACT(EPOCH FROM CAST(")
            # Close the CAST with ::timestamp) after the column ref
            import re
            sql = re.sub(r"EXTRACT\(EPOCH FROM CAST\(\s*(\w+\.\w+)\)", r"EXTRACT(EPOCH FROM CAST(\1 AS TIMESTAMP))", sql)
            sql = sql.replace("strftime('%Y-%m-%d',", "TO_CHAR(")
            if "TO_CHAR(" in sql and "as d" in sql.lower():
                sql = sql.replace(") as d", "::timestamp, 'YYYY-MM-DD') as d")
            # PG doesn't have rowid
            sql = sql.replace("ORDER BY rowid", "ORDER BY id")
            cur = self._conn.cursor()
            cur.execute(sql, params or ())
            if cur.description:
                return _PgCursorResult(cur)
            return cur
        else:
            return self._conn.execute(sql, params or ())

    def executescript(self, sql):
        if USE_PG:
            cur = self._conn.cursor()
            cur.execute(sql)
            cur.close()
        else:
            self._conn.executescript(sql)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


def _raw_pg_conn():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn

def _raw_sqlite_conn():
    from app.config import DB_PATH
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

@contextmanager
def db_connection():
    raw = _raw_pg_conn() if USE_PG else _raw_sqlite_conn()
    conn = DbConn(raw)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def _cur(conn):
    """Return a cursor — RealDictCursor for PG, normal for SQLite."""
    if USE_PG:
        return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return conn

def _ph(name: str = ""):
    """Placeholder: %s for PG, ? for SQLite."""
    return "%s" if USE_PG else "?"

def _now():
    return "NOW()" if USE_PG else "datetime('now')"

def _execute(conn, sql, params=None):
    """Execute via DbConn wrapper — auto-converts ? to %s for PG."""
    return conn.execute(sql, params)

def _fetchone(conn, sql, params=None):
    result = conn.execute(sql, params or ())
    if result is None:
        return None
    row = result.fetchone()
    return dict(row) if row else None

def _fetchall(conn, sql, params=None):
    result = conn.execute(sql, params or ())
    rows = result.fetchall()
    return [dict(r) for r in rows]

def _insert_returning(conn, sql, params=None):
    """Insert and return id. PG uses RETURNING, SQLite uses lastrowid."""
    if USE_PG:
        result = conn.execute(sql + " RETURNING id", params or ())
        row = result.fetchone()
        return row["id"] if isinstance(row, dict) else row[0]
    else:
        result = conn.execute(sql, params or ())
        return result.lastrowid

# ---------- init ----------

_PG_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
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
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS businesses (
    id SERIAL PRIMARY KEY,
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
    brand_hours TEXT DEFAULT '',
    brand_services TEXT DEFAULT '',
    brand_geo TEXT DEFAULT '',
    brand_usp TEXT DEFAULT '',
    allowed_phrases TEXT DEFAULT '',
    auto_rule_1_2 TEXT DEFAULT 'draft',
    auto_rule_3 TEXT DEFAULT 'draft',
    auto_rule_4_5 TEXT DEFAULT 'approve',
    quiet_hours TEXT DEFAULT '',
    sla_hours_neg INTEGER DEFAULT 24,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS reviews (
    id SERIAL PRIMARY KEY,
    business_id INTEGER NOT NULL REFERENCES businesses(id),
    google_review_id TEXT DEFAULT '',
    author TEXT NOT NULL DEFAULT 'Customer',
    rating INTEGER NOT NULL DEFAULT 5,
    text TEXT NOT NULL DEFAULT '',
    review_time TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS responses (
    id SERIAL PRIMARY KEY,
    review_id INTEGER NOT NULL REFERENCES reviews(id),
    ai_response TEXT NOT NULL DEFAULT '',
    edited_response TEXT DEFAULT '',
    status TEXT DEFAULT 'pending',
    published_at TEXT DEFAULT '',
    missing_fact INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS notification_prefs (
    id SERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES users(id),
    channel TEXT NOT NULL,
    target TEXT NOT NULL,
    events TEXT NOT NULL DEFAULT 'new_review,draft_ready',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS team_memberships (
    id SERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES users(id),
    member_user_id INTEGER REFERENCES users(id),
    email TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'staff',
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    target_type TEXT DEFAULT '',
    target_id INTEGER,
    meta TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_account ON audit_log(account_id);

CREATE TABLE IF NOT EXISTS dead_letters (
    id SERIAL PRIMARY KEY,
    task TEXT NOT NULL,
    payload TEXT NOT NULL,
    error TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS review_comments (
    id SERIAL PRIMARY KEY,
    review_id INTEGER NOT NULL REFERENCES reviews(id),
    user_id INTEGER,
    text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS review_tags (
    id SERIAL PRIMARY KEY,
    review_id INTEGER NOT NULL REFERENCES reviews(id),
    tag TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
"""

_SQLITE_SCHEMA = """
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
    brand_hours TEXT DEFAULT '',
    brand_services TEXT DEFAULT '',
    brand_geo TEXT DEFAULT '',
    brand_usp TEXT DEFAULT '',
    allowed_phrases TEXT DEFAULT '',
    auto_rule_1_2 TEXT DEFAULT 'draft',
    auto_rule_3 TEXT DEFAULT 'draft',
    auto_rule_4_5 TEXT DEFAULT 'approve',
    quiet_hours TEXT DEFAULT '',
    sla_hours_neg INTEGER DEFAULT 24,
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
    missing_fact INTEGER DEFAULT 0,
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

CREATE TABLE IF NOT EXISTS review_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id INTEGER NOT NULL REFERENCES reviews(id),
    user_id INTEGER,
    text TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS review_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id INTEGER NOT NULL REFERENCES reviews(id),
    tag TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);
"""


def init_db():
    with db_connection() as conn:
        schema = _PG_SCHEMA if USE_PG else _SQLITE_SCHEMA
        conn.executescript(schema)


# ---------- users ----------

def create_user(email: str, name: str, google_id: str, access_token: str = "", refresh_token: str = "") -> int:
    trial_end = (datetime.utcnow() + timedelta(days=7)).isoformat()
    p = "%s" if USE_PG else "?"
    with db_connection() as conn:
        existing = _fetchone(conn, f"SELECT id FROM users WHERE email = {p}", (email,))
        if not existing and google_id:
            existing = _fetchone(conn, f"SELECT id FROM users WHERE google_id = {p}", (google_id,))
        if existing:
            _execute(conn, f"UPDATE users SET google_access_token = {p}, google_refresh_token = {p}, updated_at = NOW() WHERE id = {p}" if USE_PG else f"UPDATE users SET google_access_token = ?, google_refresh_token = ?, updated_at = datetime('now') WHERE id = ?",
                     (access_token, refresh_token or "", existing["id"]))
            return existing["id"]
        return _insert_returning(conn,
            f"INSERT INTO users (email, name, google_id, google_access_token, google_refresh_token, trial_ends_at) VALUES ({p}, {p}, {p}, {p}, {p}, {p})",
            (email, name, google_id, access_token, refresh_token or "", trial_end))


def get_user(user_id: int) -> dict | None:
    p = "%s" if USE_PG else "?"
    with db_connection() as conn:
        return _fetchone(conn, f"SELECT * FROM users WHERE id = {p}", (user_id,))


# ---------- businesses ----------

def create_business(user_id: int, name: str, business_type: str, location: str,
                    tone: str = "friendly and professional",
                    auto_approve_high: int = 0, banned_phrases: str = "",
                    signoff_library: str = "", brand_facts: str = "") -> int:
    p = "%s" if USE_PG else "?"
    with db_connection() as conn:
        return _insert_returning(conn,
            f"INSERT INTO businesses (user_id, name, type, location, tone, auto_approve_high, banned_phrases, signoff_library, brand_facts) VALUES ({p},{p},{p},{p},{p},{p},{p},{p},{p})",
            (user_id, name, business_type, location, tone, auto_approve_high, banned_phrases, signoff_library, brand_facts))


def get_businesses(user_id: int) -> list[dict]:
    p = "%s" if USE_PG else "?"
    with db_connection() as conn:
        return _fetchall(conn, f"SELECT * FROM businesses WHERE user_id = {p}", (user_id,))


# ---------- reviews ----------

def add_review(business_id: int, author: str, rating: int, text: str, google_review_id: str = "", review_time: str = "") -> int:
    p = "%s" if USE_PG else "?"
    with db_connection() as conn:
        return _insert_returning(conn,
            f"INSERT INTO reviews (business_id, author, rating, text, google_review_id, review_time) VALUES ({p},{p},{p},{p},{p},{p})",
            (business_id, author, rating, text, google_review_id, review_time))


def get_reviews(business_id: int, limit: int = 50, offset: int = 0,
                status: str | None = None, rating_filter: str | None = None, search: str | None = None) -> list[dict]:
    p = "%s" if USE_PG else "?"
    sql = f"""
        SELECT r.*, resp.ai_response, resp.edited_response, resp.status as response_status, resp.id as response_id
        FROM reviews r
        LEFT JOIN responses resp ON resp.review_id = r.id
        WHERE r.business_id = {p}
    """
    params: list = [business_id]
    if status == "needs_action":
        sql += " AND ((resp.status IS NULL) OR (resp.status != 'approved'))"
    elif status == "pending":
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
        sql += f" AND (r.text LIKE {p} OR r.author LIKE {p})"
        params += [f"%{search}%", f"%{search}%"]
    sql += f" ORDER BY r.created_at DESC LIMIT {p} OFFSET {p}"
    params += [limit, offset]
    with db_connection() as conn:
        return _fetchall(conn, sql, tuple(params))


def count_reviews(business_id: int) -> int:
    p = "%s" if USE_PG else "?"
    with db_connection() as conn:
        row = _fetchone(conn, f"SELECT COUNT(*) as c FROM reviews WHERE business_id = {p}", (business_id,))
        return row["c"] if row else 0


# ---------- responses ----------

def save_response(review_id: int, ai_response: str) -> int:
    p = "%s" if USE_PG else "?"
    now = "NOW()" if USE_PG else "datetime('now')"
    with db_connection() as conn:
        existing = _fetchone(conn, f"SELECT id FROM responses WHERE review_id = {p}", (review_id,))
        if existing:
            _execute(conn, f"UPDATE responses SET ai_response = {p}, status = 'pending', created_at = {now} WHERE id = {p}",
                     (ai_response, existing["id"]))
            return existing["id"]
        return _insert_returning(conn,
            f"INSERT INTO responses (review_id, ai_response, status) VALUES ({p}, {p}, 'pending')",
            (review_id, ai_response))


def save_response_with_flags(review_id: int, ai_response: str, missing_fact: int = 0) -> int:
    p = "%s" if USE_PG else "?"
    now = "NOW()" if USE_PG else "datetime('now')"
    with db_connection() as conn:
        existing = _fetchone(conn, f"SELECT id FROM responses WHERE review_id = {p}", (review_id,))
        if existing:
            _execute(conn, f"UPDATE responses SET ai_response = {p}, status = 'pending', missing_fact={p}, created_at = {now} WHERE id = {p}",
                     (ai_response, missing_fact, existing["id"]))
            return existing["id"]
        return _insert_returning(conn,
            f"INSERT INTO responses (review_id, ai_response, status, missing_fact) VALUES ({p}, {p}, 'pending', {p})",
            (review_id, ai_response, missing_fact))


def count_responses_this_month(user_id: int) -> int:
    p = "%s" if USE_PG else "?"
    month_filter = "date_trunc('month', CURRENT_DATE)" if USE_PG else "date('now', 'start of month')"
    with db_connection() as conn:
        row = _fetchone(conn, f"""
            SELECT COUNT(*) as c FROM responses resp
            JOIN reviews r ON resp.review_id = r.id
            JOIN businesses b ON r.business_id = b.id
            WHERE b.user_id = {p} AND resp.created_at >= {month_filter}
        """, (user_id,))
        return row["c"] if row else 0


def approve_response(response_id: int, edited_text: str = "") -> None:
    p = "%s" if USE_PG else "?"
    now = "NOW()" if USE_PG else "datetime('now')"
    with db_connection() as conn:
        _execute(conn, f"UPDATE responses SET status = 'approved', edited_response = {p}, published_at = {now} WHERE id = {p}",
                 (edited_text, response_id))


# ---------- audit ----------

def add_audit(account_id: int, user_id: int, action: str, target_type: str = "", target_id: int | None = None, meta: str = ""):
    p = "%s" if USE_PG else "?"
    now = "NOW()" if USE_PG else "datetime('now')"
    with db_connection() as conn:
        _execute(conn, f"INSERT INTO audit_log (account_id, user_id, action, target_type, target_id, meta, created_at) VALUES ({p},{p},{p},{p},{p},{p},{now})",
                 (account_id, user_id, action, target_type, target_id, meta))


def log_dead_letter(task: str, payload: str, error: str):
    p = "%s" if USE_PG else "?"
    now = "NOW()" if USE_PG else "datetime('now')"
    with db_connection() as conn:
        _execute(conn, f"INSERT INTO dead_letters (task, payload, error, created_at) VALUES ({p},{p},{p},{now})",
                 (task, payload, error[:1000]))


def get_dead_letters(limit: int = 50) -> list[dict]:
    p = "%s" if USE_PG else "?"
    with db_connection() as conn:
        return _fetchall(conn, f"SELECT * FROM dead_letters ORDER BY created_at DESC LIMIT {p}", (limit,))


# ---------- notifications ----------

def get_notification_prefs(account_id: int) -> list[dict]:
    p = "%s" if USE_PG else "?"
    with db_connection() as conn:
        return _fetchall(conn, f"SELECT * FROM notification_prefs WHERE account_id = {p}", (account_id,))


def save_notification_pref(account_id: int, channel: str, target: str, events: str = "new_review,draft_ready") -> int:
    p = "%s" if USE_PG else "?"
    now = "NOW()" if USE_PG else "datetime('now')"
    with db_connection() as conn:
        existing = _fetchone(conn, f"SELECT id FROM notification_prefs WHERE account_id = {p} AND channel = {p}", (account_id, channel))
        if existing:
            _execute(conn, f"UPDATE notification_prefs SET target = {p}, events = {p}, updated_at = {now} WHERE id = {p}",
                     (target, events, existing["id"]))
            return existing["id"]
        return _insert_returning(conn,
            f"INSERT INTO notification_prefs (account_id, channel, target, events) VALUES ({p},{p},{p},{p})",
            (account_id, channel, target, events))


# ---------- team ----------

def get_team_members(account_id: int) -> list[dict]:
    p = "%s" if USE_PG else "?"
    with db_connection() as conn:
        return _fetchall(conn, f"""
            SELECT tm.*, u.name as user_name, u.email as user_email
            FROM team_memberships tm
            LEFT JOIN users u ON tm.member_user_id = u.id
            WHERE tm.account_id = {p}
            ORDER BY tm.created_at
        """, (account_id,))


def create_team_invite(account_id: int, email: str, role: str = "staff") -> int:
    p = "%s" if USE_PG else "?"
    with db_connection() as conn:
        return _insert_returning(conn,
            f"INSERT INTO team_memberships (account_id, email, role, status) VALUES ({p},{p},{p},'pending')",
            (account_id, email, role))


def attach_member_user(email: str, user_id: int) -> dict | None:
    p = "%s" if USE_PG else "?"
    now = "NOW()" if USE_PG else "datetime('now')"
    with db_connection() as conn:
        invite = _fetchone(conn, f"SELECT * FROM team_memberships WHERE email = {p} AND status = 'pending'", (email,))
        if invite:
            _execute(conn, f"UPDATE team_memberships SET member_user_id = {p}, status = 'active', updated_at = {now} WHERE id = {p}",
                     (user_id, invite["id"]))
            return invite
        return None


def remove_team_member(membership_id: int):
    p = "%s" if USE_PG else "?"
    with db_connection() as conn:
        _execute(conn, f"DELETE FROM team_memberships WHERE id = {p}", (membership_id,))


# ---------- comments ----------

def add_comment(review_id: int, user_id: int | None, text: str) -> int:
    p = "%s" if USE_PG else "?"
    now = "NOW()" if USE_PG else "datetime('now')"
    with db_connection() as conn:
        return _insert_returning(conn,
            f"INSERT INTO review_comments (review_id, user_id, text, created_at) VALUES ({p},{p},{p},{now})",
            (review_id, user_id, text))


def get_comments_by_review_ids(review_ids: list[int]) -> dict[int, list[dict]]:
    if not review_ids:
        return {}
    p = "%s" if USE_PG else "?"
    placeholders = ",".join(p for _ in review_ids)
    with db_connection() as conn:
        rows = _fetchall(conn, f"""
            SELECT rc.*, u.name as user_name, u.email as user_email
            FROM review_comments rc
            LEFT JOIN users u ON rc.user_id = u.id
            WHERE rc.review_id IN ({placeholders})
            ORDER BY rc.created_at ASC
        """, tuple(review_ids))
        grouped: dict[int, list[dict]] = {}
        for r in rows:
            grouped.setdefault(r["review_id"], []).append(r)
        return grouped


# ---------- tags ----------

def save_tags(review_id: int, tags: list[str]):
    if tags is None:
        tags = []
    p = "%s" if USE_PG else "?"
    now = "NOW()" if USE_PG else "datetime('now')"
    with db_connection() as conn:
        _execute(conn, f"DELETE FROM review_tags WHERE review_id = {p}", (review_id,))
        for t in tags:
            _execute(conn, f"INSERT INTO review_tags (review_id, tag, created_at) VALUES ({p},{p},{now})", (review_id, t))


def get_tags_by_review_ids(review_ids: list[int]) -> dict[int, list[str]]:
    if not review_ids:
        return {}
    p = "%s" if USE_PG else "?"
    placeholders = ",".join(p for _ in review_ids)
    with db_connection() as conn:
        rows = _fetchall(conn, f"SELECT review_id, tag FROM review_tags WHERE review_id IN ({placeholders})", tuple(review_ids))
        grouped: dict[int, list[str]] = {}
        for r in rows:
            grouped.setdefault(r["review_id"], []).append(r["tag"])
        return grouped


def get_top_tags(business_id: int, limit: int = 10) -> list[dict]:
    p = "%s" if USE_PG else "?"
    with db_connection() as conn:
        return _fetchall(conn, f"""
            SELECT rt.tag, COUNT(*) as cnt
            FROM review_tags rt
            JOIN reviews r ON rt.review_id = r.id
            WHERE r.business_id = {p}
            GROUP BY rt.tag
            ORDER BY cnt DESC
            LIMIT {p}
        """, (business_id, limit))
