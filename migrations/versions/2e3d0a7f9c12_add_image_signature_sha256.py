"""Add image SHA-256 signature"""

from alembic import op
import sqlalchemy as sa

revision = "2e3d0a7f9c12"
down_revision = "4c1c1d32b3b4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("images", sa.Column("signature_sha256", sa.String(length=64), nullable=True))


def downgrade():
    op.drop_column("images", "signature_sha256")
