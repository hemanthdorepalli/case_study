"""Create the PostgreSQL database (if missing) and all tables.

Run directly with `python -m app.init_db`; the API also calls create_tables() on startup.
"""
import logging

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url

from app import models  # noqa: F401  (registers the models on Base.metadata)
from app.database import Base, engine

logger = logging.getLogger(__name__)


def ensure_database_exists(url: str | URL) -> None:
    url = make_url(url)
    # CREATE DATABASE cannot run inside a transaction, so use the maintenance DB in autocommit mode.
    admin_engine = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            exists = conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": url.database}
            )
            if not exists:
                quoted = conn.dialect.identifier_preparer.quote(url.database)
                conn.execute(text(f"CREATE DATABASE {quoted}"))
                logger.info("Created database %s", url.database)
    finally:
        admin_engine.dispose()


def create_tables() -> None:
    ensure_database_exists(engine.url)
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    create_tables()
    print(f"Database '{engine.url.database}' and tables are ready.")
