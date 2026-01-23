"""
Database configuration and session management for SQLAlchemy.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get DATABASE_URL from environment, with fallback
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://minimarket:minimarket@localhost:5432/minimarket"
)

# Create engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Verify connections before using
    echo=False,  # Set to True for SQL query logging
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """
    Dependency function that yields a database session.
    Use this in FastAPI route dependencies.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
