"""Add customer shopping carts."""
from alembic import op
import sqlalchemy as sa

revision = "0005_carts"
down_revision = "0004_payment_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "carts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("store_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("customer_id", "store_id", name="uq_carts_customer_store"),
    )
    op.create_index("ix_carts_customer_id", "carts", ["customer_id"], unique=False)
    op.create_index("ix_carts_store_id", "carts", ["store_id"], unique=False)
    op.create_table(
        "cart_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cart_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["cart_id"], ["carts.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cart_id", "product_id", name="uq_cart_items_cart_product"),
    )
    op.create_index("ix_cart_items_cart_id", "cart_items", ["cart_id"], unique=False)
    op.create_index("ix_cart_items_product_id", "cart_items", ["product_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_cart_items_product_id", table_name="cart_items")
    op.drop_index("ix_cart_items_cart_id", table_name="cart_items")
    op.drop_table("cart_items")
    op.drop_index("ix_carts_store_id", table_name="carts")
    op.drop_index("ix_carts_customer_id", table_name="carts")
    op.drop_table("carts")
