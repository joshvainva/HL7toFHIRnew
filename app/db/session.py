import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:password@localhost:5432/innova_fhir")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def ensure_schema():
    """Self-fixing schema: ensure new columns exist when the app starts."""
    from sqlalchemy import text
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE conversion_log ADD COLUMN IF NOT EXISTS field_mappings JSONB"))
    except Exception:
        # Tables might not exist yet (metadata.create_all handles that usually) or DB might be read-only
        pass

ensure_schema()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
