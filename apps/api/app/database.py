"""
PostgreSQL database layer for AquaSense AI.
Uses a connection pool for efficiency.
"""

import json
import os
import logging
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional, List

import psycopg2
import psycopg2.extras
import psycopg2.pool

logger = logging.getLogger(__name__)

_DDL = """
CREATE TABLE IF NOT EXISTS users (
    id          SERIAL PRIMARY KEY,
    google_id   TEXT UNIQUE NOT NULL,
    email       TEXT UNIQUE NOT NULL,
    name        TEXT,
    picture     TEXT,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS analyses (
    id                  SERIAL PRIMARY KEY,
    filename            TEXT        NOT NULL,
    field_zone          TEXT,
    result              TEXT        NOT NULL CHECK (result IN ('faulty', 'normal', 'unknown')),
    status              TEXT        NOT NULL DEFAULT 'unknown'
                                             CHECK (status IN ('critical', 'warning', 'healthy', 'unknown')),
    confidence          REAL        NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    issue_detected      BOOLEAN     NOT NULL,
    issue_type          TEXT,
    issue_category      TEXT,
    all_issues          JSONB       DEFAULT '[]',
    severity            TEXT,
    urgency             TEXT,
    affected_area_pct   REAL        DEFAULT 0,
    water_waste_risk    TEXT,
    crop_impact         TEXT,
    message             TEXT,
    recommendation      TEXT,
    model_type          TEXT,
    faulty_probability  REAL,
    normal_probability  REAL,
    dataset_path        TEXT,
    dataset_saved       BOOLEAN     DEFAULT FALSE,
    image_data          BYTEA,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for common query patterns (safe to run repeatedly)
CREATE INDEX IF NOT EXISTS idx_analyses_created_at  ON analyses (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_analyses_status       ON analyses (status);
CREATE INDEX IF NOT EXISTS idx_analyses_field_zone   ON analyses (field_zone);
CREATE INDEX IF NOT EXISTS idx_analyses_issue_type   ON analyses (issue_type);

-- Add new columns to existing tables (safe to run repeatedly)
DO $$ BEGIN
    ALTER TABLE analyses ADD COLUMN IF NOT EXISTS field_zone         TEXT;
    ALTER TABLE analyses ADD COLUMN IF NOT EXISTS status             TEXT DEFAULT 'unknown';
    ALTER TABLE analyses ADD COLUMN IF NOT EXISTS issue_category     TEXT;
    ALTER TABLE analyses ADD COLUMN IF NOT EXISTS all_issues         JSONB DEFAULT '[]';
    ALTER TABLE analyses ADD COLUMN IF NOT EXISTS urgency            TEXT;
    ALTER TABLE analyses ADD COLUMN IF NOT EXISTS affected_area_pct  REAL DEFAULT 0;
    ALTER TABLE analyses ADD COLUMN IF NOT EXISTS water_waste_risk   TEXT;
    ALTER TABLE analyses ADD COLUMN IF NOT EXISTS crop_impact        TEXT;
    ALTER TABLE analyses ADD COLUMN IF NOT EXISTS user_id            INTEGER REFERENCES users(id);
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_analyses_user_id ON analyses (user_id);
"""

_SELECT_COLS = """
    id, filename, field_zone, result, status, confidence, issue_detected,
    issue_type, issue_category, all_issues, severity, urgency,
    affected_area_pct, water_waste_risk, crop_impact,
    message, recommendation, model_type,
    faulty_probability, normal_probability,
    dataset_path, dataset_saved, created_at
"""

# ── Connection pool ───────────────────────────────────────────────────────────
_pool: Optional[psycopg2.pool.SimpleConnectionPool] = None
_pool_lock = threading.Lock()


def _url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return url


def _get_pool() -> psycopg2.pool.SimpleConnectionPool:
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = psycopg2.pool.SimpleConnectionPool(
                    minconn=1, maxconn=10, dsn=_url()
                )
                logger.info("DB connection pool created (min=1, max=10)")
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        with _pool_lock:
            if _pool is not None:
                _pool.closeall()
                _pool = None


@contextmanager
def _get_conn():
    pool = _get_pool()
    conn = pool.getconn()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def is_available() -> bool:
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return True
    except Exception:
        return False


def init_db() -> None:
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(_DDL)
                # Clean up orphaned analyses that predate user auth
                cur.execute("DELETE FROM analyses WHERE user_id IS NULL")
                deleted = cur.rowcount
            conn.commit()
        if deleted:
            logger.info(f"PostgreSQL: removed {deleted} orphaned analyses (no user_id)")
        logger.info("PostgreSQL: tables ready")
    except Exception as e:
        logger.warning(f"PostgreSQL init failed: {e}")


def save_analysis(
    filename: str,
    result: str,
    confidence: float,
    issue_detected: bool,
    issue_type: Optional[str],
    severity: Optional[str],
    message: Optional[str],
    recommendation: Optional[str],
    model_type: Optional[str],
    faulty_probability: Optional[float],
    normal_probability: Optional[float],
    dataset_path: Optional[str],
    dataset_saved: bool,
    image_data: Optional[bytes],
    field_zone: Optional[str] = None,
    status: str = "unknown",
    issue_category: Optional[str] = None,
    all_issues: Optional[List[str]] = None,
    urgency: Optional[str] = None,
    affected_area_pct: float = 0.0,
    water_waste_risk: Optional[str] = None,
    crop_impact: Optional[str] = None,
    user_id: Optional[int] = None,
) -> Optional[int]:
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO analyses (
                        filename, field_zone, result, status, confidence, issue_detected,
                        issue_type, issue_category, all_issues, severity, urgency,
                        affected_area_pct, water_waste_risk, crop_impact,
                        message, recommendation, model_type,
                        faulty_probability, normal_probability,
                        dataset_path, dataset_saved, image_data, created_at, user_id
                    ) VALUES (
                        %s,%s,%s,%s,%s,%s,
                        %s,%s,%s,%s,%s,
                        %s,%s,%s,
                        %s,%s,%s,
                        %s,%s,
                        %s,%s,%s,%s,%s
                    ) RETURNING id
                    """,
                    (
                        filename, field_zone, result, status, confidence, issue_detected,
                        issue_type, issue_category, json.dumps(all_issues or []), severity, urgency,
                        affected_area_pct, water_waste_risk, crop_impact,
                        message, recommendation, model_type,
                        faulty_probability, normal_probability,
                        dataset_path, dataset_saved, image_data,
                        datetime.now(timezone.utc), user_id,
                    ),
                )
                row_id = cur.fetchone()[0]
            conn.commit()
        logger.info(f"DB saved id={row_id} [{status}] {filename}")
        return row_id
    except Exception as e:
        logger.warning(f"DB save failed: {e}")
        return None


def get_trend(days: int = 14) -> list:
    """Return daily critical/warning/healthy counts for the last N days."""
    try:
        with _get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        date_trunc('day', created_at)::date            AS day,
                        COUNT(*) FILTER (WHERE status = 'critical')    AS critical,
                        COUNT(*) FILTER (WHERE status = 'warning')     AS warning,
                        COUNT(*) FILTER (WHERE status = 'healthy')     AS healthy,
                        COUNT(*)                                       AS total
                    FROM analyses
                    WHERE created_at >= NOW() - (%s || ' days')::interval
                    GROUP BY 1
                    ORDER BY 1
                """, (str(days),))
                rows = cur.fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.warning(f"DB trend failed: {e}")
        return []


def get_zones(user_id: Optional[int] = None) -> list:
    """Return each unique field zone with its aggregated stats."""
    try:
        user_filter = "AND user_id = %s" if user_id is not None else ""
        params = (user_id,) if user_id is not None else ()
        with _get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(f"""
                    SELECT
                        field_zone,
                        COUNT(*)                                          AS total,
                        COUNT(*) FILTER (WHERE status = 'critical')       AS critical,
                        COUNT(*) FILTER (WHERE status = 'warning')        AS warning,
                        COUNT(*) FILTER (WHERE status = 'healthy')        AS healthy,
                        MAX(created_at)                                   AS last_scan,
                        (
                            SELECT status FROM analyses a2
                            WHERE a2.field_zone = analyses.field_zone
                            {user_filter}
                            ORDER BY created_at DESC LIMIT 1
                        ) AS latest_status
                    FROM analyses
                    WHERE field_zone IS NOT NULL AND field_zone <> ''
                    {user_filter}
                    GROUP BY field_zone
                    ORDER BY MAX(created_at) DESC
                """, params + params)
                rows = cur.fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.warning(f"DB zones failed: {e}")
        return []


def get_analyses(limit: int = 50, offset: int = 0, field_zone: Optional[str] = None,
                 date_from: Optional[str] = None, date_to: Optional[str] = None,
                 issue_type: Optional[str] = None, user_id: Optional[int] = None) -> list:
    try:
        with _get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                conditions, params = [], []
                if user_id is not None:
                    conditions.append("user_id = %s"); params.append(user_id)
                if field_zone:
                    conditions.append("field_zone = %s"); params.append(field_zone)
                if issue_type:
                    conditions.append("issue_type = %s"); params.append(issue_type)
                if date_from:
                    conditions.append("created_at >= %s"); params.append(date_from)
                if date_to:
                    conditions.append("created_at < %s::date + interval '1 day'"); params.append(date_to)
                where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
                params.extend([limit, offset])
                cur.execute(
                    f"SELECT {_SELECT_COLS} FROM analyses {where} ORDER BY created_at DESC LIMIT %s OFFSET %s",
                    params,
                )
                rows = cur.fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.warning(f"DB fetch failed: {e}")
        return []


def get_stats(field_zone: Optional[str] = None, user_id: Optional[int] = None) -> dict:
    """Summary statistics for the dashboard. Pass field_zone to scope to one zone."""
    try:
        conditions, params = [], []
        if user_id is not None:
            conditions.append("user_id = %s"); params.append(user_id)
        if field_zone:
            conditions.append("field_zone = %s"); params.append(field_zone)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        with _get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(f"""
                    SELECT
                        COUNT(*)                                         AS total,
                        COUNT(*) FILTER (WHERE status = 'critical')      AS critical,
                        COUNT(*) FILTER (WHERE status = 'warning')       AS warning,
                        COUNT(*) FILTER (WHERE status = 'healthy')       AS healthy,
                        COUNT(*) FILTER (WHERE urgency = 'immediate')    AS urgent,
                        ROUND(AVG(affected_area_pct)::numeric, 1)        AS avg_affected_pct,
                        COUNT(*) FILTER (WHERE water_waste_risk = 'high')AS high_waste,
                        COUNT(DISTINCT field_zone)
                            FILTER (WHERE field_zone IS NOT NULL)        AS field_zones,
                        MAX(created_at)                                  AS last_analysis
                    FROM analyses {where}
                """, tuple(params))
                row = cur.fetchone()
        return dict(row) if row else {}
    except Exception as e:
        logger.warning(f"DB stats failed: {e}")
        return {}


def get_analysis(analysis_id: int) -> Optional[dict]:
    """Fetch a single analysis record by id (without image_data)."""
    try:
        with _get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    f"SELECT {_SELECT_COLS} FROM analyses WHERE id = %s",
                    (analysis_id,),
                )
                row = cur.fetchone()
        return dict(row) if row else None
    except Exception as e:
        logger.warning(f"DB get_analysis failed: {e}")
        return None


def get_image(analysis_id: int) -> Optional[bytes]:
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT image_data FROM analyses WHERE id=%s", (analysis_id,))
                row = cur.fetchone()
        return bytes(row[0]) if row and row[0] else None
    except Exception as e:
        logger.warning(f"DB image fetch failed: {e}")
        return None


def upsert_user(google_id: str, email: str, name: Optional[str], picture: Optional[str]) -> Optional[dict]:
    """Insert or update a user from Google OAuth. Returns the user row."""
    try:
        with _get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    INSERT INTO users (google_id, email, name, picture, last_login)
                    VALUES (%s, %s, %s, %s, NOW())
                    ON CONFLICT (google_id) DO UPDATE
                        SET email      = EXCLUDED.email,
                            name       = EXCLUDED.name,
                            picture    = EXCLUDED.picture,
                            last_login = NOW()
                    RETURNING id, google_id, email, name, picture, created_at, last_login
                """, (google_id, email, name, picture))
                row = cur.fetchone()
            conn.commit()
        return dict(row) if row else None
    except Exception as e:
        logger.warning(f"DB upsert_user failed: {e}")
        return None


def get_user_by_id(user_id: int) -> Optional[dict]:
    try:
        with _get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT id, google_id, email, name, picture, created_at FROM users WHERE id = %s",
                    (user_id,)
                )
                row = cur.fetchone()
        return dict(row) if row else None
    except Exception as e:
        logger.warning(f"DB get_user_by_id failed: {e}")
        return None


def get_public_stats() -> dict:
    """Lightweight stats for the public homepage counter — no auth required."""
    try:
        with _get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        COUNT(*)                                      AS total_analyses,
                        COUNT(*) FILTER (WHERE status = 'critical')   AS critical,
                        COUNT(*) FILTER (WHERE status = 'healthy')    AS healthy,
                        COUNT(DISTINCT field_zone)
                            FILTER (WHERE field_zone IS NOT NULL)     AS zones_monitored
                    FROM analyses
                """)
                row = cur.fetchone()
        return dict(row) if row else {"total_analyses": 0, "critical": 0, "healthy": 0, "zones_monitored": 0}
    except Exception as e:
        logger.warning(f"DB public_stats failed: {e}")
        return {"total_analyses": 0, "critical": 0, "healthy": 0, "zones_monitored": 0}


def delete_analysis(analysis_id: int) -> bool:
    """Delete a single analysis record. Returns True if a row was deleted."""
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM analyses WHERE id=%s", (analysis_id,))
                deleted = cur.rowcount > 0
            conn.commit()
        return deleted
    except Exception as e:
        logger.warning(f"DB delete failed: {e}")
        return False
