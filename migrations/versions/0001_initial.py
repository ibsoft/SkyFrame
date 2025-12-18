"""Initial SkyFrame schema"""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("username", sa.String(length=80), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("avatar_type", sa.String(length=64), nullable=False, server_default="gravatar"),
        sa.Column("avatar_path", sa.String(length=255)),
        sa.Column("bio", sa.Text),
    )

    op.create_table(
        "images",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("file_path", sa.String(length=255), nullable=False),
        sa.Column("thumb_path", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("object_name", sa.String(length=128), nullable=False),
        sa.Column("observer_name", sa.String(length=128), nullable=False),
        sa.Column("observed_at", sa.DateTime, nullable=False),
        sa.Column("location", sa.String(length=128)),
        sa.Column("filter", sa.String(length=64)),
        sa.Column("telescope", sa.String(length=128)),
        sa.Column("camera", sa.String(length=128)),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_images_category", "images", ["category"])
    op.create_index("ix_images_object", "images", ["object_name"])
    op.create_index("ix_images_observer", "images", ["observer_name"])
    op.create_index("ix_images_observed_at", "images", ["observed_at"])
    op.create_index("ix_images_created_at", "images", ["created_at"])

    op.create_table(
        "likes",
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("image_id", sa.Integer, sa.ForeignKey("images.id"), primary_key=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "favorites",
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("image_id", sa.Integer, sa.ForeignKey("images.id"), primary_key=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "follows",
        sa.Column("follower_id", sa.Integer, sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("followed_id", sa.Integer, sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "comments",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("image_id", sa.Integer, sa.ForeignKey("images.id"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("comments")
    op.drop_table("follows")
    op.drop_table("favorites")
    op.drop_table("likes")
    op.drop_index("ix_images_created_at", table_name="images")
    op.drop_index("ix_images_observed_at", table_name="images")
    op.drop_index("ix_images_observer", table_name="images")
    op.drop_index("ix_images_object", table_name="images")
    op.drop_index("ix_images_category", table_name="images")
    op.drop_table("images")
    op.drop_table("users")
