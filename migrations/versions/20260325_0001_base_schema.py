"""Base schema with business extensions, notifications, team."""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260325_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.Text, nullable=False, unique=True),
        sa.Column("name", sa.Text, nullable=False, server_default=""),
        sa.Column("google_id", sa.Text, unique=True),
        sa.Column("google_access_token", sa.Text, server_default=""),
        sa.Column("google_refresh_token", sa.Text, server_default=""),
        sa.Column("stripe_customer_id", sa.Text, server_default=""),
        sa.Column("subscription_status", sa.Text, server_default="trial"),
        sa.Column("subscription_plan", sa.Text, server_default=""),
        sa.Column("trial_ends_at", sa.Text, server_default=""),
        sa.Column("email_verified", sa.Integer, server_default="0"),
        sa.Column("email_token", sa.Text, server_default=""),
        sa.Column("created_at", sa.Text, server_default="(datetime('now'))"),
        sa.Column("updated_at", sa.Text, server_default="(datetime('now'))"),
    )

    op.create_table(
        "businesses",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("type", sa.Text, nullable=False, server_default="restaurant"),
        sa.Column("location", sa.Text, nullable=False, server_default=""),
        sa.Column("google_location_id", sa.Text, server_default=""),
        sa.Column("tone", sa.Text, server_default="friendly and professional"),
        sa.Column("owner_name", sa.Text, server_default=""),
        sa.Column("auto_approve_high", sa.Integer, server_default="0"),
        sa.Column("banned_phrases", sa.Text, server_default=""),
        sa.Column("signoff_library", sa.Text, server_default=""),
        sa.Column("brand_facts", sa.Text, server_default=""),
        sa.Column("created_at", sa.Text, server_default="(datetime('now'))"),
    )

    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("business_id", sa.Integer, sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("google_review_id", sa.Text, server_default=""),
        sa.Column("author", sa.Text, nullable=False, server_default="Customer"),
        sa.Column("rating", sa.Integer, nullable=False, server_default="5"),
        sa.Column("text", sa.Text, nullable=False, server_default=""),
        sa.Column("review_time", sa.Text, server_default=""),
        sa.Column("created_at", sa.Text, server_default="(datetime('now'))"),
    )
    op.create_index("idx_reviews_business_id", "reviews", ["business_id"])

    op.create_table(
        "responses",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("review_id", sa.Integer, sa.ForeignKey("reviews.id"), nullable=False),
        sa.Column("ai_response", sa.Text, nullable=False, server_default=""),
        sa.Column("edited_response", sa.Text, server_default=""),
        sa.Column("status", sa.Text, server_default="pending"),
        sa.Column("published_at", sa.Text, server_default=""),
        sa.Column("created_at", sa.Text, server_default="(datetime('now'))"),
    )
    op.create_index("idx_responses_review_id", "responses", ["review_id"])

    op.create_table(
        "notification_prefs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("account_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("channel", sa.Text, nullable=False),
        sa.Column("target", sa.Text, nullable=False),
        sa.Column("events", sa.Text, nullable=False, server_default="new_review,draft_ready"),
        sa.Column("created_at", sa.Text, server_default="(datetime('now'))"),
        sa.Column("updated_at", sa.Text, server_default="(datetime('now'))"),
    )

    op.create_table(
        "team_memberships",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("account_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("member_user_id", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column("email", sa.Text, nullable=False),
        sa.Column("role", sa.Text, nullable=False, server_default="staff"),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        sa.Column("created_at", sa.Text, server_default="(datetime('now'))"),
        sa.Column("updated_at", sa.Text, server_default="(datetime('now'))"),
    )
    op.create_index("idx_team_account", "team_memberships", ["account_id"])

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("account_id", sa.Integer, nullable=False),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("target_type", sa.Text, server_default=""),
        sa.Column("target_id", sa.Integer),
        sa.Column("meta", sa.Text, server_default=""),
        sa.Column("created_at", sa.Text, server_default="(datetime('now'))"),
    )
    op.create_index("idx_audit_account", "audit_log", ["account_id"])

    op.create_table(
        "dead_letters",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("task", sa.Text, nullable=False),
        sa.Column("payload", sa.Text, nullable=False),
        sa.Column("error", sa.Text, nullable=False),
        sa.Column("created_at", sa.Text, server_default="(datetime('now'))"),
    )


def downgrade():
    op.drop_index("idx_team_account", table_name="team_memberships")
    op.drop_table("team_memberships")
    op.drop_index("idx_audit_account", table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_table("dead_letters")
    op.drop_table("notification_prefs")
    op.drop_index("idx_responses_review_id", table_name="responses")
    op.drop_table("responses")
    op.drop_index("idx_reviews_business_id", table_name="reviews")
    op.drop_table("reviews")
    op.drop_table("businesses")
    op.drop_table("users")
