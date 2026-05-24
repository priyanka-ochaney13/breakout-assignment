import os 
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.logger import get_logger
_logger = get_logger("app.database")

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./breakout-assignment.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}  if DATABASE_URL.startswith("sqlite") else {},
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    #yields a DB session and ensures it's closed after the request
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
    
def check_db_connection():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception as e:
        _logger.error("Database health check failed", extra={"error": str(e)})
        return False