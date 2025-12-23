"""Add notification read tracking"""

from alembic import op
import sqlalchemy as sa

revision = "6b2c8d3f4a61"
down_revision = "0c4a9d3e7b21"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "notification_reads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=16), nullable=False),
        sa.Column("image_id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=False),
        sa.Column("event_created_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["image_id"], ["images.id"]),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.UniqueConstraint(
            "user_id",
            "event_type",
            "image_id",
            "actor_id",
            "event_created_at",
            name="uq_notification_read_event",
        ),
    )
    op.create_index("ix_notification_reads_user_type", "notification_reads", ["user_id", "event_type"])


def downgrade():
    op.drop_index("ix_notification_reads_user_type", table_name="notification_reads")
    op.drop_table("notification_reads")
