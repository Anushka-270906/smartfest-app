import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.database import init_db
from app.routers import (
    auth,
    events,
    registrations,
    checkin,
    venues,
    recommendations,
    notifications,
    feedback,
    analytics,
    users,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite database and seed initial data
    init_db()
    yield

app = FastAPI(
    title="SmartFest — AI/ML-Based College Fest Coordination Platform",
    description="Full-stack implementation according to CS3021 Software Engineering SRS & UML Specifications.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(auth.router)
app.include_router(events.router)
app.include_router(registrations.router)
app.include_router(checkin.router)
app.include_router(venues.router)
app.include_router(recommendations.router)
app.include_router(notifications.router)
app.include_router(feedback.router)
app.include_router(analytics.router)
app.include_router(users.router)

# Static Files
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
def read_root():
    """Serve the single-page application entry point."""
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "SmartFest API is running. Visit /docs for OpenAPI Swagger documentation."}

@app.get("/api/health")
def health_check():
    return {"status": "healthy", "platform": "SmartFest AI/ML Platform", "version": "1.0.0"}
