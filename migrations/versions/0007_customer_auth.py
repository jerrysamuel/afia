"""Add shopper account credentials and wallet linking."""
from alembic import op
import sqlalchemy as sa

revision = "0007_customer_auth"
down_revision = "0006_product_embeddings"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("customers", sa.Column("username", sa.String(length=64), nullable=True))
    op.add_column("customers", sa.Column("password_hash", sa.String(length=256), nullable=True))
    op.add_column("customers", sa.Column("wallet_address", sa.String(length=42), nullable=True))
    op.create_index("ix_customers_username", "customers", ["username"], unique=True)
    op.create_index("ix_customers_wallet_address", "customers", ["wallet_address"], unique=True)

def downgrade() -> None:
    op.drop_index("ix_customers_wallet_address", table_name="customers")
    op.drop_index("ix_customers_username", table_name="customers")
    op.drop_column("customers", "wallet_address")
    op.drop_column("customers", "password_hash")
    op.drop_column("customers", "username")
