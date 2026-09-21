"""
database.py — SQLAlchemy engine using Cloud SQL Python Connector (or local SQLite).
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

_connector = None

def _getconn():
    # Moved import inside so it is only evaluated if we actually connect to Cloud SQL
    from google.cloud.sql.connector import Connector
    global _connector
    if _connector is None:
        _connector = Connector()
    return _connector.connect(
        os.environ["CLOUD_SQL_INSTANCE"],   # "project:region:instance"
        "pg8000",
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASS"],
        db=os.environ["DB_NAME"],
    )

# If CLOUD_SQL_INSTANCE is present, use the production Postgres connection.
# Otherwise, fall back to a local SQLite database for local testing.
if "CLOUD_SQL_INSTANCE" in os.environ:
    engine = create_engine(
        "postgresql+pg8000://",
        creator=_getconn,
        pool_pre_ping=True,
        pool_recycle=1800,
    )
else:
    print("[Database] CLOUD_SQL_INSTANCE not found. Using local SQLite database (exam.db).")
    engine = create_engine(
        "sqlite:///./exam.db",
        connect_args={"check_same_thread": False} # Required for FastAPI + SQLite
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()