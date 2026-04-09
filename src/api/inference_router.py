"""
Inference and analysis API endpoints.
"""

import asyncio
import csv
import io
import os
import logging
import tempfile
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

try:
    from src.api import runner as inference_runner
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from src.api import runner as inference_runner

logger = logging.getLogger("inference_router")
router = APIRouter()


def _auth_enabled() -> bool:
    """Return True when Google OAuth is configured (production mode)."""
    return bool(os.environ.get("GOOGLE_CLIENT_ID", "").strip())


def _get_user_id(request) -> Optional[int]:
    """Extract the current user's DB id from the session cookie, or None."""
    try:
        try:
            from apps.api.app.routers.auth import get_current_user
        except ImportError:
            from app.routers.auth import get_current_user  # type: ignore[import]
        user = get_current_user(request)
        uid = user.get("id") if user else None
        logger.debug(f"_get_user_id: uid={uid} cookies={list(request.cookies.keys())}")
        return uid
    except Exception as e:
        logger.warning(f"_get_user_id failed: {e}")
        return None


def _send_alert(filename: str, field_zone: Optional[str], result: dict) -> None:
    """Fire-and-forget webhook alert for critical detections.

    Set ALERT_WEBHOOK_URL in .env to enable. Compatible with ntfy.sh:
      ALERT_WEBHOOK_URL=https://ntfy.sh/your-topic
    """
    webhook_url = os.environ.get("ALERT_WEBHOOK_URL", "").strip()
    if not webhook_url:
        return
    import threading, requests as _req
    zone_part = f" [{field_zone}]" if field_zone else ""
    issue     = result.get("issue_type") or "unknown issue"
    pct       = int(float(result.get("affected_area_pct") or 0))
    body      = (
        f"🔴 CRITICAL: {issue.replace('_',' ').title()}{zone_part}\n"
        f"File: {filename} | Area affected: {pct}%\n"
        f"{result.get('recommendation') or ''}"
    ).strip()

    def _post():
        try:
            _req.post(webhook_url, data=body.encode(), timeout=5,
                      headers={"Title": "AquaSense Alert", "Priority": "high", "Tags": "rotating_light"})
        except Exception as e:
            logger.warning(f"Alert webhook failed: {e}")

    threading.Thread(target=_post, daemon=True).start()


def _get_db():
    try:
        from apps.api.app.database import (
            save_analysis, get_analyses, get_stats, get_image,
            is_available, get_trend, delete_analysis, get_zones, get_analysis,
        )
    except ImportError:
        from app.database import (  # type: ignore[import]  # Docker path
            save_analysis, get_analyses, get_stats, get_image,
            is_available, get_trend, delete_analysis, get_zones, get_analysis,
        )
    return save_analysis, get_analyses, get_stats, get_image, is_available, get_trend, delete_analysis, get_zones, get_analysis


# ── Schemas ───────────────────────────────────────────────────────────────────

class AnalysisResponse(BaseModel):
    id: Optional[int] = None
    filename: str
    field_zone: Optional[str] = None
    # Core result
    result: str                          # "faulty" | "normal"
    status: str = "unknown"             # "critical" | "warning" | "healthy"
    confidence: float
    issue_detected: bool
    # Issue detail
    issue_type: Optional[str] = None     # primary issue key
    issue_category: Optional[str] = None # "water_quality" | "irrigation_system" | etc.
    all_issues: List[str] = []
    severity: Optional[str] = None
    urgency: Optional[str] = None
    # Agricultural fields
    affected_area_pct: float = 0.0
    water_waste_risk: Optional[str] = None
    crop_impact: Optional[str] = None
    # Human readable
    message: Optional[str] = None
    recommendation: Optional[str] = None
    # Meta
    model_type: str = "classification"
    faulty_probability: Optional[float] = None
    normal_probability: Optional[float] = None
    dataset_saved: bool = False
    created_at: Optional[str] = None


class HealthResponse(BaseModel):
    model_ready: bool
    active_engine: str
    db_connected: bool
    model_path: Optional[str] = None
    message: str


class StatsResponse(BaseModel):
    total: int = 0
    critical: int = 0
    warning: int = 0
    healthy: int = 0
    urgent: int = 0
    avg_affected_pct: float = 0.0
    high_waste: int = 0
    field_zones: int = 0
    last_analysis: Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_image(
    request: Request,
    file: UploadFile = File(...),
    field_zone: Optional[str] = Form(None),
):
    """Analyze an irrigation image. Optionally tag with field_zone (e.g. 'North Field')."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be an image")
    if field_zone is not None and len(field_zone.strip()) > 80:
        raise HTTPException(status_code=422, detail="field_zone must be 80 characters or fewer")

    try:
        image_data = await file.read()
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to read file")

    MAX_BYTES = 10 * 1024 * 1024  # 10 MB
    if len(image_data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="Image too large — maximum size is 10 MB")

    # Validate file by magic bytes (not just MIME type, which can be spoofed)
    _MAGIC = [
        (b"\xff\xd8\xff", "image/jpeg"),          # JPEG
        (b"\x89PNG\r\n\x1a\n", "image/png"),      # PNG
        (b"GIF87a", "image/gif"),                  # GIF87
        (b"GIF89a", "image/gif"),                  # GIF89
        (b"RIFF", None),                           # WebP (RIFF....WEBP)
    ]
    detected = None
    for magic, mime in _MAGIC:
        if image_data[:len(magic)] == magic:
            if magic == b"RIFF" and image_data[8:12] != b"WEBP":
                continue
            detected = mime or "image/webp"
            break
    if detected is None:
        raise HTTPException(status_code=400, detail="File does not appear to be a valid image")

    suffix = Path(file.filename).suffix or ".jpg"
    tmp_path: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(image_data)
            tmp_path = tmp.name
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to write temp file")

    try:
        result = await asyncio.to_thread(inference_runner.run, tmp_path)

        label  = result.get("result", "unknown")
        status = result.get("status", "unknown")

        save_fn = _get_db()[0]  # index 0 = save_analysis
        db_id = save_fn(
            filename           = file.filename,
            result             = label,
            confidence         = float(result.get("confidence", 0.0)),
            issue_detected     = bool(result.get("issue_detected", False)),
            issue_type         = result.get("issue_type"),
            severity           = result.get("severity"),
            message            = result.get("message"),
            recommendation     = result.get("recommendation"),
            model_type         = result.get("model_type"),
            faulty_probability = result.get("faulty_probability"),
            normal_probability = result.get("normal_probability"),
            dataset_path       = None,
            dataset_saved      = False,
            image_data         = image_data,
            field_zone         = field_zone,
            status             = status,
            issue_category     = result.get("issue_category"),
            all_issues         = result.get("all_issues", []),
            urgency            = result.get("urgency"),
            affected_area_pct  = float(result.get("affected_area_pct", 0.0)),
            water_waste_risk   = result.get("water_waste_risk"),
            crop_impact        = result.get("crop_impact"),
            user_id            = _get_user_id(request),
        )

        response = AnalysisResponse(
            id                 = db_id,
            filename           = file.filename,
            field_zone         = field_zone,
            result             = label,
            status             = status,
            confidence         = float(result.get("confidence", 0.0)),
            issue_detected     = bool(result.get("issue_detected", False)),
            issue_type         = result.get("issue_type"),
            issue_category     = result.get("issue_category"),
            all_issues         = result.get("all_issues", []),
            severity           = result.get("severity"),
            urgency            = result.get("urgency"),
            affected_area_pct  = float(result.get("affected_area_pct", 0.0)),
            water_waste_risk   = result.get("water_waste_risk"),
            crop_impact        = result.get("crop_impact"),
            message            = result.get("message"),
            recommendation     = result.get("recommendation"),
            model_type         = result.get("model_type", "classification"),
            faulty_probability = result.get("faulty_probability"),
            normal_probability = result.get("normal_probability"),
            dataset_saved      = False,
            created_at         = datetime.now(timezone.utc).isoformat(),
        )

        if status == "critical":
            _send_alert(file.filename, field_zone, result)

        return response

    except Exception as e:
        try:
            from src.ai.openrouter_vision import QuotaExceededError
            if isinstance(e, QuotaExceededError):
                raise HTTPException(status_code=429, detail="AI API quota exceeded — please try again in a few moments")
        except ImportError:
            pass
        logger.exception(f"Analysis failed: {e}")
        raise HTTPException(status_code=500, detail="Analysis failed")
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception as e:
                logger.warning(f"Failed to clean up temp file {tmp_path}: {e}")


@router.get("/analyses/export")
async def export_analyses_csv(
    request:    Request,
    field_zone: Optional[str] = None,
    date_from:  Optional[str] = Query(None, description="ISO date e.g. 2024-01-01"),
    date_to:    Optional[str] = Query(None, description="ISO date e.g. 2024-12-31"),
):
    """Download full history as a CSV file."""
    from datetime import date as _date
    def _validate_date(val: Optional[str], name: str) -> None:
        if val is None:
            return
        try:
            _date.fromisoformat(val)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid {name}: expected YYYY-MM-DD format")

    _validate_date(date_from, "date_from")
    _validate_date(date_to,   "date_to")

    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must not be after date_to")

    user_id = _get_user_id(request)
    if _auth_enabled() and user_id is None:
        from fastapi.responses import StreamingResponse as _SR
        return _SR(iter([""]), media_type="text/csv",
                   headers={"Content-Disposition": 'attachment; filename="empty.csv"'})

    _, get_fn, _, _, _, _, _, _, _ = _get_db()
    rows = get_fn(limit=10000, field_zone=field_zone, date_from=date_from, date_to=date_to,
                  user_id=user_id)

    out = io.StringIO()
    fields = ["id","created_at","filename","field_zone","status","issue_type","issue_category",
              "confidence","affected_area_pct","water_waste_risk","urgency","severity",
              "crop_impact","recommendation","model_type"]
    writer = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        row = dict(r)
        if row.get("created_at"):
            row["created_at"] = row["created_at"].isoformat()
        row["confidence"] = round(float(row.get("confidence") or 0) * 100, 1)
        writer.writerow(row)

    out.seek(0)
    from datetime import timezone
    filename = f"aquasense_export_{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        iter([out.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/analyses", response_model=List[AnalysisResponse])
async def list_analyses(
    request:    Request,
    limit:      int            = 20,
    offset:     int            = 0,
    field_zone: Optional[str]  = None,
    issue_type: Optional[str]  = None,
    date_from:  Optional[str]  = Query(None, description="ISO date e.g. 2024-01-01"),
    date_to:    Optional[str]  = Query(None, description="ISO date e.g. 2024-12-31"),
):
    from datetime import date as _date
    for val, name in [(date_from, "date_from"), (date_to, "date_to")]:
        if val is not None:
            try:
                _date.fromisoformat(val)
            except ValueError:
                raise HTTPException(status_code=422, detail=f"Invalid {name}: expected YYYY-MM-DD format")
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must not be after date_to")

    user_id = _get_user_id(request)
    if _auth_enabled() and user_id is None:
        return []

    _, get_fn, _, _, _, _, _, _, _ = _get_db()
    rows = get_fn(
        limit=min(limit, 200), offset=max(offset, 0),
        field_zone=field_zone, issue_type=issue_type,
        date_from=date_from, date_to=date_to,
        user_id=user_id,
    )
    return [
        AnalysisResponse(
            id                 = r["id"],
            filename           = r["filename"],
            field_zone         = r.get("field_zone"),
            result             = r["result"],
            status             = r.get("status", "unknown"),
            confidence         = r["confidence"],
            issue_detected     = r["issue_detected"],
            issue_type         = r.get("issue_type"),
            issue_category     = r.get("issue_category"),
            all_issues         = r.get("all_issues") or [],
            severity           = r.get("severity"),
            urgency            = r.get("urgency"),
            affected_area_pct  = r.get("affected_area_pct") or 0.0,
            water_waste_risk   = r.get("water_waste_risk"),
            crop_impact        = r.get("crop_impact"),
            message            = r.get("message"),
            recommendation     = r.get("recommendation"),
            model_type         = r.get("model_type") or "classification",
            faulty_probability = r.get("faulty_probability"),
            normal_probability = r.get("normal_probability"),
            dataset_saved      = r.get("dataset_saved", False),
            created_at         = r["created_at"].isoformat() if r.get("created_at") else None,
        )
        for r in rows
    ]


@router.get("/analyses/{analysis_id}", response_model=AnalysisResponse)
async def get_analysis_by_id(analysis_id: int):
    """Fetch a single analysis record by id."""
    _, _, _, _, _, _, _, _, get_one_fn = _get_db()
    r = get_one_fn(analysis_id)
    if not r:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return AnalysisResponse(
        id                 = r["id"],
        filename           = r["filename"],
        field_zone         = r.get("field_zone"),
        result             = r["result"],
        status             = r.get("status", "unknown"),
        confidence         = r["confidence"],
        issue_detected     = r["issue_detected"],
        issue_type         = r.get("issue_type"),
        issue_category     = r.get("issue_category"),
        all_issues         = r.get("all_issues") or [],
        severity           = r.get("severity"),
        urgency            = r.get("urgency"),
        affected_area_pct  = r.get("affected_area_pct") or 0.0,
        water_waste_risk   = r.get("water_waste_risk"),
        crop_impact        = r.get("crop_impact"),
        message            = r.get("message"),
        recommendation     = r.get("recommendation"),
        model_type         = r.get("model_type") or "classification",
        faulty_probability = r.get("faulty_probability"),
        normal_probability = r.get("normal_probability"),
        dataset_saved      = r.get("dataset_saved", False),
        created_at         = r["created_at"].isoformat() if r.get("created_at") else None,
    )


@router.get("/trend")
async def get_trend(days: int = 14):
    """Daily critical/warning/healthy counts for the last N days."""
    _, _, _, _, _, trend_fn, _, _, _ = _get_db()
    rows = trend_fn(days=min(days, 90))
    return [
        {
            "day":      str(r["day"]),
            "critical": r.get("critical", 0),
            "warning":  r.get("warning",  0),
            "healthy":  r.get("healthy",  0),
            "total":    r.get("total",    0),
        }
        for r in rows
    ]


@router.get("/zones")
async def list_zones(request: Request):
    """Return each unique field zone with its aggregated stats."""
    user_id = _get_user_id(request)
    if _auth_enabled() and user_id is None:
        return []
    _, _, _, _, _, _, _, zones_fn, _ = _get_db()
    rows = zones_fn(user_id=user_id)
    return [
        {
            "field_zone":    r["field_zone"],
            "total":         r.get("total", 0),
            "critical":      r.get("critical", 0),
            "warning":       r.get("warning", 0),
            "healthy":       r.get("healthy", 0),
            "latest_status": r.get("latest_status", "unknown"),
            "last_scan":     r["last_scan"].isoformat() if r.get("last_scan") else None,
        }
        for r in rows
    ]


@router.get("/stats", response_model=StatsResponse)
async def get_stats(request: Request, field_zone: Optional[str] = None):
    user_id = _get_user_id(request)
    if _auth_enabled() and user_id is None:
        return StatsResponse()
    _, _, stats_fn, _, _, _, _, _, _ = _get_db()
    s = stats_fn(field_zone=field_zone, user_id=user_id)
    return StatsResponse(
        total            = s.get("total", 0) or 0,
        critical         = s.get("critical", 0) or 0,
        warning          = s.get("warning", 0) or 0,
        healthy          = s.get("healthy", 0) or 0,
        urgent           = s.get("urgent", 0) or 0,
        avg_affected_pct = float(s.get("avg_affected_pct") or 0),
        high_waste       = s.get("high_waste", 0) or 0,
        field_zones      = s.get("field_zones", 0) or 0,
        last_analysis    = s["last_analysis"].isoformat() if s.get("last_analysis") else None,
    )


@router.get("/debug/auth")
async def debug_auth(request: Request):
    """Temporary debug endpoint — shows auth state for troubleshooting."""
    user_id = _get_user_id(request)
    return {
        "auth_enabled":       _auth_enabled(),
        "cookies_received":   list(request.cookies.keys()),
        "aq_session_present": "aq_session" in request.cookies,
        "user_id":            user_id,
        "authenticated":      user_id is not None,
        "secret_key_set":     bool(os.environ.get("SECRET_KEY", "")),
        "google_client_set":  bool(os.environ.get("GOOGLE_CLIENT_ID", "")),
    }


@router.get("/stats/public")
async def get_public_stats():
    """Open stats endpoint — no auth required. Used for the homepage scan counter."""
    try:
        try:
            from apps.api.app.database import get_public_stats
        except ImportError:
            from app.database import get_public_stats  # type: ignore[import]
        return get_public_stats()
    except Exception:
        return {"total_analyses": 0, "critical": 0, "healthy": 0, "zones_monitored": 0}


@router.get("/analyses/{analysis_id}/image")
async def get_analysis_image(analysis_id: int):
    _, _, _, img_fn, _, _, _, _, _ = _get_db()
    data = img_fn(analysis_id)
    if not data:
        raise HTTPException(status_code=404, detail="Image not found")
    # Detect actual format from magic bytes instead of assuming JPEG
    _MAGIC_TYPES = [
        (b"\xff\xd8\xff",       "image/jpeg"),
        (b"\x89PNG\r\n\x1a\n", "image/png"),
        (b"GIF87a",             "image/gif"),
        (b"GIF89a",             "image/gif"),
        (b"RIFF",               "image/webp"),
    ]
    media_type = "image/jpeg"  # safe default
    for magic, mime in _MAGIC_TYPES:
        if data[:len(magic)] == magic:
            media_type = mime
            break
    return Response(content=data, media_type=media_type)




@router.delete("/analyses/{analysis_id}", status_code=204)
async def delete_analysis_endpoint(analysis_id: int):
    """Permanently delete a single analysis record."""
    _, _, _, _, _, _, del_fn, _, _ = _get_db()
    deleted = del_fn(analysis_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return Response(status_code=204)

@router.get("/inference/health", response_model=HealthResponse)
async def check_model_health():
    from src.ai.openrouter_vision import is_available as or_ok
    _, _, _, _, db_ok, _, _, _, _ = _get_db()

    if or_ok():
        engine, msg = "openrouter", "OpenRouter (Gemini 2.0 Flash) is active"
    else:
        try:
            from src.ai.inference_client import get_inference_client
            ready  = get_inference_client().is_ready()
            engine = "onnx" if ready else "heuristic"
            msg    = "ONNX model ready" if ready else "Using heuristic — set OPENROUTER_API_KEY for best results"
        except Exception:
            engine, msg = "heuristic", "Using brightness heuristic"

    return HealthResponse(
        model_ready   = engine != "heuristic",
        active_engine = engine,
        db_connected  = db_ok(),
        model_path    = os.environ.get("MODEL_PATH"),
        message       = msg,
    )
