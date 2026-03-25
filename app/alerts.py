from datetime import datetime, timedelta
from app.database import db_connection, add_audit
from app.notifications import send_notifications


def sla_scan_and_alert():
    """Find 1-2★ reviews without approved response older than SLA and alert."""
    now = datetime.utcnow()
    with db_connection() as conn:
        rows = conn.execute("""
            SELECT r.id as review_id, r.author, r.rating, r.text, r.created_at, b.name as business_name,
                   b.user_id as account_id, b.sla_hours_neg
            FROM reviews r
            JOIN businesses b ON r.business_id = b.id
            LEFT JOIN responses resp ON resp.review_id = r.id
            WHERE r.rating <= 2
              AND (resp.status IS NULL OR resp.status != 'approved')
              AND r.created_at <= datetime('now', '-' || COALESCE(NULLIF(b.sla_hours_neg, ''), 24) || ' hour')
        """).fetchall()
    for row in rows:
        try:
            send_notifications(row["account_id"], "sla_alert", {
                "business_name": row["business_name"],
                "rating": row["rating"],
                "author": row["author"],
                "review_id": row["review_id"],
            })
            add_audit(row["account_id"], row["account_id"], "sla.alert", "review", row["review_id"], f"rating={row['rating']}")
        except Exception:
            continue
