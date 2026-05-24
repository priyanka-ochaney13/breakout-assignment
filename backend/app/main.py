from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.routes import enquiry, health
from app.logger import get_logger
from app.database import Base, engine

logger = get_logger("app.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    #create tables on startup
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialised", extra={"event": "startup"})
    yield
    logger.info("Application shutting down", extra={"event": "shutdown"})

app = FastAPI(
    title="Closira Enquiry API",
    description="API for receiving and processing customer enquiries asynchronously.",
    version="1.0.0",
    lifespan=lifespan,
)

#exception handler for unhandled exceptions
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        "Unhandled exception",
        extra={"path": request.url.path, "error": str(exc)},
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again later."},
    )

#routers
app.include_router(enquiry.router)
app.include_router(health.router)

@app.get("/")
def root():
    return {"message": "Closira API is running. Visit /docs for the full API reference."}