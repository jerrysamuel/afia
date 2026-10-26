"""Add customers and historical orders."""
from alembic import op
import sqlalchemy as sa

revision = "0002_customers_orders"
down_revision = "0001_catalog_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_customers_email", "customers", ["email"], unique=False)
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_number", sa.String(length=32), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("store_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("payment_status", sa.String(length=32), nullable=False),
        sa.Column("total_amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=12), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_number"),
    )
    op.create_index("ix_orders_order_number", "orders", ["order_number"], unique=False)
    op.create_index("ix_orders_customer_id", "orders", ["customer_id"], unique=False)
    op.create_index("ix_orders_store_id", "orders", ["store_id"], unique=False)
    op.create_index("ix_orders_status", "orders", ["status"], unique=False)
    op.create_index("ix_orders_payment_status", "orders", ["payment_status"], unique=False)
    op.create_table(
        "order_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("product_name", sa.String(length=200), nullable=False),
        sa.Column("unit_amount_minor", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("line_total_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=12), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id", "product_id", name="uq_order_items_order_product"),
    )
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"], unique=False)
    op.create_index("ix_order_items_product_id", "order_items", ["product_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_order_items_product_id", table_name="order_items")
    op.drop_index("ix_order_items_order_id", table_name="order_items")
    op.drop_table("order_items")
    for index in ("ix_orders_payment_status", "ix_orders_status", "ix_orders_store_id", "ix_orders_customer_id", "ix_orders_order_number"):
        op.drop_index(index, table_name="orders")
    op.drop_table("orders")
    op.drop_index("ix_customers_email", table_name="customers")
    op.drop_table("customers")
