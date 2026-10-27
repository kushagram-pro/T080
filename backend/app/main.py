import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.limiter import limiter
from app.routers import admin, approvals, auth, collaborations, departments, notifications, profiles, reports, search, suggestions

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")

app = FastAPI(title="Faculty Collaboration Network Portal", version="0.1.0")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_credentials=True,  # needed for the refresh-token cookie
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router)
app.include_router(approvals.router)
app.include_router(departments.router)
app.include_router(profiles.router)
app.include_router(search.router)
app.include_router(suggestions.router)
app.include_router(collaborations.router)
app.include_router(notifications.router)
app.include_router(admin.router)
app.include_router(reports.router)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
