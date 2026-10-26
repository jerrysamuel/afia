"""Add provider-agnostic payments and payment attempts."""
from alembic import op
import sqlalchemy as sa

revision = "0004_payment_foundation"
down_revision = "0003_inventory_reservations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=12), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_payment_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id"),
    )
    op.create_index("ix_payments_order_id", "payments", ["order_id"], unique=False)
    op.create_index("ix_payments_status", "payments", ["status"], unique=False)
    op.create_table(
        "payment_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("payment_id", sa.Integer(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("provider_reference", sa.String(length=255), nullable=True),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("failure_message", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payment_id", "attempt_number", name="uq_payment_attempt_number"),
    )
    op.create_index("ix_payment_attempts_payment_id", "payment_attempts", ["payment_id"], unique=False)
    op.create_index("ix_payment_attempts_status", "payment_attempts", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_payment_attempts_status", table_name="payment_attempts")
    op.drop_index("ix_payment_attempts_payment_id", table_name="payment_attempts")
    op.drop_table("payment_attempts")
    op.drop_index("ix_payments_status", table_name="payments")
    op.drop_index("ix_payments_order_id", table_name="payments")
    op.drop_table("payments")
