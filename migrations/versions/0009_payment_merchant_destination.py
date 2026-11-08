"""Snapshot the merchant wallet on each payment."""

from alembic import op
import sqlalchemy as sa


revision = "0009_payment_merchant_destination"
down_revision = "0008_store_commerce_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("pay_to", sa.String(length=42), nullable=True))
    op.create_index("ix_payments_pay_to", "payments", ["pay_to"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_payments_pay_to", table_name="payments")
    op.drop_column("payments", "pay_to")
