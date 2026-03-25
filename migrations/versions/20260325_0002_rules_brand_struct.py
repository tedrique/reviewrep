"""Add auto rules, brand structured fields, missing_fact."""

from alembic import op
import sqlalchemy as sa

revision = "20260325_0002"
down_revision = "20260325_0001"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("businesses") as b:
        b.add_column(sa.Column("brand_hours", sa.Text(), server_default=""))
        b.add_column(sa.Column("brand_services", sa.Text(), server_default=""))
        b.add_column(sa.Column("brand_geo", sa.Text(), server_default=""))
        b.add_column(sa.Column("brand_usp", sa.Text(), server_default=""))
        b.add_column(sa.Column("allowed_phrases", sa.Text(), server_default=""))
        b.add_column(sa.Column("auto_rule_1_2", sa.Text(), server_default="draft"))
        b.add_column(sa.Column("auto_rule_3", sa.Text(), server_default="draft"))
        b.add_column(sa.Column("auto_rule_4_5", sa.Text(), server_default="approve"))
        b.add_column(sa.Column("quiet_hours", sa.Text(), server_default=""))
        b.add_column(sa.Column("sla_hours_neg", sa.Integer(), server_default="24"))
    with op.batch_alter_table("responses") as r:
        r.add_column(sa.Column("missing_fact", sa.Integer(), server_default="0"))


def downgrade():
    with op.batch_alter_table("responses") as r:
        r.drop_column("missing_fact")
    with op.batch_alter_table("businesses") as b:
        b.drop_column("sla_hours_neg")
        b.drop_column("quiet_hours")
        b.drop_column("auto_rule_4_5")
        b.drop_column("auto_rule_3")
        b.drop_column("auto_rule_1_2")
        b.drop_column("allowed_phrases")
        b.drop_column("brand_usp")
        b.drop_column("brand_geo")
        b.drop_column("brand_services")
        b.drop_column("brand_hours")
