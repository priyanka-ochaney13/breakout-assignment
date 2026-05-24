import os
from fastapi import APIRouter
from app.database import check_db_connection
from app.schemas import HealthResponse

router = APIRouter(tags=["Health"], prefix="/health")

@router.get(
    "",
    response_model=HealthResponse,
    summary="api health check",
    description="returns api status and database connection status",
)
def health_check():
    db_ok = check_db_connection()
    return HealthResponse(
        status="ok" if db_ok else "error",
        database="ok" if db_ok else "error",
        environment=os.getenv("APP_ENV", "development")
    )