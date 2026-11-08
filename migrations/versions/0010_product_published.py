"""Add product publication state."""
from alembic import op
import sqlalchemy as sa

revision = "0010_product_published"
down_revision = "0009_merchant_payto"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("products", sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_index("ix_products_published", "products", ["published"], unique=False)

def downgrade() -> None:
    op.drop_index("ix_products_published", table_name="products")
    op.drop_column("products", "published")
