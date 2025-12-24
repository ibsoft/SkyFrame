"""Add cascade delete for image foreign keys."""

from alembic import op

revision = "b1c2d3e4f5a6"
down_revision = "6b2c8d3f4a61"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("notification_reads_image_id_fkey", "notification_reads", type_="foreignkey")
    op.create_foreign_key(
        "notification_reads_image_id_fkey",
        "notification_reads",
        "images",
        ["image_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint("feed_seen_image_id_fkey", "feed_seen", type_="foreignkey")
    op.create_foreign_key(
        "feed_seen_image_id_fkey",
        "feed_seen",
        "images",
        ["image_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade():
    op.drop_constraint("notification_reads_image_id_fkey", "notification_reads", type_="foreignkey")
    op.create_foreign_key(
        "notification_reads_image_id_fkey",
        "notification_reads",
        "images",
        ["image_id"],
        ["id"],
    )
    op.drop_constraint("feed_seen_image_id_fkey", "feed_seen", type_="foreignkey")
    op.create_foreign_key(
        "feed_seen_image_id_fkey",
        "feed_seen",
        "images",
        ["image_id"],
        ["id"],
    )
