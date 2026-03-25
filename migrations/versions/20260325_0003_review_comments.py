"""Add review_comments table."""

from alembic import op
import sqlalchemy as sa

revision = "20260325_0003"
down_revision = "20260325_0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "review_comments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("review_id", sa.Integer(), sa.ForeignKey("reviews.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_index("idx_comments_review", "review_comments", ["review_id"])


def downgrade():
    op.drop_index("idx_comments_review", table_name="review_comments")
    op.drop_table("review_comments")
