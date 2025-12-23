"""Add image perceptual hashes"""

from alembic import op
import sqlalchemy as sa

revision = "7f1b6d9a2d10"
down_revision = "2e3d0a7f9c12"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("images", sa.Column("signature_phash", sa.String(length=16), nullable=True))
    op.add_column("images", sa.Column("signature_dhash", sa.String(length=16), nullable=True))


def downgrade():
    op.drop_column("images", "signature_dhash")
    op.drop_column("images", "signature_phash")
