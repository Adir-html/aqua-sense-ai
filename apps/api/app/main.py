"""
AquaSense API - FastAPI application for water irrigation analysis.

Run with: uvicorn apps.api.app.main:app --reload
"""

import asyncio
import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from dotenv import load_dotenv

# Add workspace root to Python path to enable absolute imports.
# In Docker: /app/app/main.py  → workspace root = /app  (parents[1])
# In local dev: <repo>/apps/api/app/main.py → workspace root = <repo> (parents[3])
_here = Path(__file__).resolve()
_candidates = [_here.parents[1]]
if len(_here.parents) > 3:
    _candidates.append(_here.parents[3])
for _candidate in _candidates:
    if (_candidate / "src").is_dir() or (_candidate / "models").is_dir():
        workspace_root = _candidate
        break
else:
    workspace_root = _here.parents[1]  # sensible fallback

if str(workspace_root) not in sys.path:
    sys.path.insert(0, str(workspace_root))

# Load environment variables from .env file at workspace root
env_file = workspace_root / ".env"
if env_file.exists():
    load_dotenv(env_file)
else:
    load_dotenv()  # Try to find .env in parent directories

# Import routers — try local dev path first (IDE-friendly), fall back to Docker path
try:
    from apps.api.app.routers import health
    from apps.api.app.routers import auth as auth_router
except ImportError:
    from app.routers import health  # type: ignore[import]  # Docker path
    from app.routers import auth as auth_router  # type: ignore[import]

try:
    from src.api.inference_router import router as inference_router
except ImportError:
    sys.path.insert(0, str(workspace_root))
    from src.api.inference_router import router as inference_router  # type: ignore[import]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────────────
    logger = logging.getLogger("uvicorn")
    logger.info("Starting AquaSense API...")

    if not os.environ.get("DATABASE_URL"):
        logger.error(
            "DATABASE_URL is not set — the database is unavailable. "
            "Set DATABASE_URL in your .env file. "
            "Analyses will not be saved and history will be empty."
        )
    try:
        try:
            from app.database import init_db
        except ImportError:
            from apps.api.app.database import init_db
        init_db()
    except Exception as e:
        logger.warning(f"DB init failed (continuing without DB): {e}")

    try:
        from src.ai.inference_client import get_inference_client
        client = get_inference_client()
        if client.is_ready():
            logger.info("ONNX model loaded and ready (fallback tier)")
        else:
            logger.info("ONNX model not available — will use AI vision API or heuristic")
    except Exception as e:
        logger.warning(f"ONNX model init skipped: {e}")

    yield  # application runs here

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("Shutting down AquaSense API...")
    try:
        try:
            from app.database import close_pool
        except ImportError:
            from apps.api.app.database import close_pool
        close_pool()
        logger.info("DB connection pool closed")
    except Exception as e:
        logger.debug(f"Pool close skipped: {e}")


# Create FastAPI application
app = FastAPI(
    title="aqua-sense-api",
    description="AI-powered water irrigation analysis API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware - allow web UI to call API from browser
_cors_env = os.environ.get("CORS_ORIGINS", "")
_cors_origins = (
    [o.strip() for o in _cors_env.split(",") if o.strip()]
    if _cors_env
    else [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:8000",
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://127.0.0.1:3000",
    ]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """
    Require x-api-key header when API_KEY environment variable is set.
    If API_KEY is not set, this middleware is bypassed (useful for development).
    """

    def __init__(self, app):
        super().__init__(app)
        self.required_key = os.environ.get("API_KEY")

    async def dispatch(self, request: Request, call_next):
        if not self.required_key:
            return await call_next(request)

        # Skip auth for health checks
        if request.url.path in ("/health", "/health/ping"):
            return await call_next(request)

        key = request.headers.get("x-api-key")
        if not key:
            auth = request.headers.get("authorization", "")
            if auth.lower().startswith("bearer "):
                key = auth.split(None, 1)[1].strip()

        if key != self.required_key:
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)

        return await call_next(request)


class SimpleRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple in-memory rate limiter enabled when RATE_LIMIT_PER_MIN is set.
    Uses asyncio.Lock to prevent race conditions.
    Note: per-process only — not suitable for multi-worker deployments.
    """

    def __init__(self, app):
        super().__init__(app)
        try:
            self.limit = int(os.environ.get("RATE_LIMIT_PER_MIN", "0"))
        except Exception:
            self.limit = 0
        self.window = 60
        self.clients: dict = {}  # ip -> (count, window_start)
        self._lock = asyncio.Lock()

    async def dispatch(self, request: Request, call_next):
        if not self.limit or self.limit <= 0:
            return await call_next(request)

        client = request.client.host if request.client else "unknown"
        now = int(time.monotonic())  # monotonic: immune to system clock jumps

        async with self._lock:
            count, start = self.clients.get(client, (0, now))
            if now - start >= self.window:
                count, start = 0, now
            count += 1
            self.clients[client] = (count, start)
            remaining = max(0, self.limit - count)
            over_limit = count > self.limit
            # Purge expired entries periodically to prevent unbounded memory growth
            if len(self.clients) > 500:
                cutoff = now - self.window
                self.clients = {ip: v for ip, v in self.clients.items() if v[1] >= cutoff}

        if over_limit:
            resp = JSONResponse({"detail": "Too Many Requests"}, status_code=429)
            resp.headers["X-RateLimit-Limit"]     = str(self.limit)
            resp.headers["X-RateLimit-Remaining"] = "0"
            resp.headers["X-RateLimit-Reset"]     = str(start + self.window)
            return resp

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"]     = str(self.limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"]     = str(start + self.window)
        return response


# Add middleware
app.add_middleware(APIKeyAuthMiddleware)
app.add_middleware(SimpleRateLimitMiddleware)

# Include routers
app.include_router(health.router, prefix="", tags=["health"])
app.include_router(inference_router, prefix="/api", tags=["inference"])
app.include_router(auth_router.router, tags=["auth"])


@app.get("/")
async def root():
    """Root endpoint - API status check."""
    return {
        "service": "aqua-sense-api",
        "status": "running",
        "version": "1.0.0"
    }
