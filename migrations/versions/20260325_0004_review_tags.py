"""Add review_tags table for auto-tagging complaints."""

from alembic import op
import sqlalchemy as sa

revision = "20260325_0004"
down_revision = "20260325_0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "review_tags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("review_id", sa.Integer(), sa.ForeignKey("reviews.id"), nullable=False),
        sa.Column("tag", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_index("idx_review_tags_review", "review_tags", ["review_id"])
    op.create_index("idx_review_tags_tag", "review_tags", ["tag"])


def downgrade():
    op.drop_index("idx_review_tags_tag", table_name="review_tags")
    op.drop_index("idx_review_tags_review", table_name="review_tags")
    op.drop_table("review_tags")
