"""
Vercel Python serverless entry point for AquaSense API.

Vercel runs this as an ASGI function — it imports `app` and handles
requests directly without uvicorn. The FastAPI app is reused as-is.

Notes:
- ONNX model inference is skipped (no filesystem in serverless).
  The app falls back automatically to Gemini Vision API.
- Set DATABASE_URL and GEMINI_API_KEY in Vercel project settings
  (Settings → Environment Variables).
"""

import sys
from pathlib import Path

# Make the repo root importable (Vercel runs from /var/task/)
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

# Import the FastAPI application — all routes, middleware, and lifespan included.
from apps.api.app.main import app  # noqa: F401  (Vercel picks up `app`)
