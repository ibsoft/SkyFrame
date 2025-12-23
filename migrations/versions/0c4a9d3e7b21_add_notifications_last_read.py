"""Add notifications last read timestamp"""

from alembic import op
import sqlalchemy as sa

revision = "0c4a9d3e7b21"
down_revision = "7f1b6d9a2d10"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("notifications_last_read_at", sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column("users", "notifications_last_read_at")
