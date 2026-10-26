from collections.abc import Generator
from functools import lru_cache

from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine

from app.core.config import settings


def _create_engine() -> Engine:
    connect_args = {}
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(settings.database_url, echo=settings.app_env == "development", connect_args=connect_args)


@lru_cache
def get_engine() -> Engine:
    return _create_engine()


def get_session() -> Generator[Session, None, None]:
    with Session(get_engine()) as session:
        yield session
