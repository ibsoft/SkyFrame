"""Add feed seen tracking"""

from alembic import op
import sqlalchemy as sa

revision = "9b2c1f2e5f4a"
down_revision = "d5a6e7b32a1c"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "feed_seen",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("image_id", sa.Integer(), nullable=False),
        sa.Column("seen_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["image_id"], ["images.id"]),
        sa.UniqueConstraint("user_id", "image_id", name="uq_feed_seen_user_image"),
    )
    op.create_index("ix_feed_seen_user_seen_at", "feed_seen", ["user_id", "seen_at"])


def downgrade():
    op.drop_index("ix_feed_seen_user_seen_at", table_name="feed_seen")
    op.drop_table("feed_seen")
