"""Add user active flag and motd tables"""

from alembic import op
import sqlalchemy as sa

revision = "4c1c1d32b3b4"
down_revision = "9b2c1f2e5f4a"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.alter_column("users", "active", server_default=None)

    op.create_table(
        "motd",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=140), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("published", sa.Boolean(), nullable=False),
        sa.Column("starts_at", sa.DateTime(), nullable=True),
        sa.Column("ends_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_motd_published", "motd", ["published"])
    op.create_index("ix_motd_window", "motd", ["starts_at", "ends_at"])

    op.create_table(
        "motd_seen",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("motd_id", sa.Integer(), nullable=False),
        sa.Column("seen_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["motd_id"], ["motd.id"]),
        sa.UniqueConstraint("user_id", "motd_id", name="uq_motd_seen_user"),
    )
    op.create_index("ix_motd_seen_user", "motd_seen", ["user_id", "seen_at"])


def downgrade():
    op.drop_index("ix_motd_seen_user", table_name="motd_seen")
    op.drop_table("motd_seen")
    op.drop_index("ix_motd_window", table_name="motd")
    op.drop_index("ix_motd_published", table_name="motd")
    op.drop_table("motd")
    op.drop_column("users", "active")
