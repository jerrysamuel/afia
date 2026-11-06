"""Add merchant auth, storefront customization and fulfillment fields."""
from alembic import op
import sqlalchemy as sa

revision = "0008_store_commerce_fields"
down_revision = "0007_customer_auth"
branch_labels = None
depends_on = None

def upgrade() -> None:
    for name, typ in (("email", sa.String(320)), ("username", sa.String(64)), ("password_hash", sa.String(256)), ("wallet_address", sa.String(42))):
        op.add_column("merchants", sa.Column(name, typ, nullable=True))
    for name, typ, default in (("category", sa.String(64), "other"), ("template_id", sa.String(100), "default"), ("theme_config", sa.JSON(), "{}"), ("sections_config", sa.JSON(), "{}"), ("settings_config", sa.JSON(), "{}")):
        op.add_column("stores", sa.Column(name, typ, nullable=False, server_default=default))
    op.add_column("products", sa.Column("product_type", sa.String(16), nullable=False, server_default="physical"))
    op.add_column("products", sa.Column("digital_url", sa.String(2000), nullable=True))
    op.add_column("orders", sa.Column("buyer_email", sa.String(320), nullable=True))
    op.add_column("orders", sa.Column("shipping_address", sa.JSON(), nullable=True))
    for column in ("email", "username", "wallet_address"):
        op.create_index(f"ix_merchants_{column}", "merchants", [column], unique=True)

def downgrade() -> None:
    for column in ("wallet_address", "username", "email"):
        op.drop_index(f"ix_merchants_{column}", table_name="merchants")
    for table, column in (("orders", "shipping_address"), ("orders", "buyer_email"), ("products", "digital_url"), ("products", "product_type"), ("stores", "settings_config"), ("stores", "sections_config"), ("stores", "theme_config"), ("stores", "template_id"), ("stores", "category"), ("merchants", "wallet_address"), ("merchants", "password_hash"), ("merchants", "username"), ("merchants", "email")):
        op.drop_column(table, column)
