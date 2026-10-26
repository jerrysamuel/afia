"""Add inventory reservations and movement history."""
from alembic import op
import sqlalchemy as sa

revision = "0003_inventory_reservations"
down_revision = "0002_customers_orders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("inventory_items", sa.Column("reserved_quantity", sa.Integer(), nullable=False, server_default="0"))
    op.create_table(
        "inventory_movements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("movement_type", sa.String(length=32), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_inventory_movements_product_id", "inventory_movements", ["product_id"], unique=False)
    op.create_index("ix_inventory_movements_order_id", "inventory_movements", ["order_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_inventory_movements_order_id", table_name="inventory_movements")
    op.drop_index("ix_inventory_movements_product_id", table_name="inventory_movements")
    op.drop_table("inventory_movements")
    op.drop_column("inventory_items", "reserved_quantity")
