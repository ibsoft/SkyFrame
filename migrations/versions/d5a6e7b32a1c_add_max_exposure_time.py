"""Add max exposure time metadata to images"""

from alembic import op
import sqlalchemy as sa

revision = "d5a6e7b32a1c"
down_revision = "79a3407b3852"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("images", sa.Column("max_exposure_time", sa.Float(), nullable=True))


def downgrade():
    op.drop_column("images", "max_exposure_time")
