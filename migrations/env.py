from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

from app.core.config import settings
from app.models import Customer, InventoryItem, InventoryMovement, Merchant, Product, Store  # noqa: F401
from app.models.orders import Order, OrderItem  # noqa: F401
from app.models.payments import Payment, PaymentAttempt  # noqa: F401
from app.models.embeddings import ProductEmbedding  # noqa: F401

config = context.config
database_url = settings.database_url
if not database_url:
    raise RuntimeError("DATABASE_URL must be configured before running Alembic")
config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
