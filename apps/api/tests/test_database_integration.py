"""
Integration tests for the database layer.

Requires a live PostgreSQL instance. Set DATABASE_URL in .env or environment:
  DATABASE_URL=postgresql://aqua:aqua@localhost:5432/aquasense

Run:
  pytest apps/api/tests/test_database_integration.py -v
"""

import os
import pytest
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

# Skip entire module if no DB is configured
pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set — skipping DB integration tests",
)


@pytest.fixture(scope="module")
def db():
    """Import database module and ensure schema is initialised."""
    try:
        from apps.api.app import database
    except ImportError:
        from app import database  # type: ignore[import]
    database.init_db()
    return database


@pytest.fixture
def saved_id(db):
    """Insert one analysis row and return its id. Cleaned up after test."""
    row_id = db.save_analysis(
        filename="test_img.jpg",
        result="faulty",
        confidence=0.91,
        issue_detected=True,
        issue_type="pipe_leak",
        severity="high",
        message="Test pipe leak",
        recommendation="Replace pipe",
        model_type="heuristic",
        faulty_probability=0.91,
        normal_probability=0.09,
        dataset_path=None,
        dataset_saved=False,
        image_data=b"\xff\xd8\xff\xe0" + b"\x00" * 100,  # minimal JPEG header
        field_zone="North Field",
        status="critical",
        issue_category="irrigation_system",
        all_issues=["pipe_leak"],
        urgency="immediate",
        affected_area_pct=35.0,
        water_waste_risk="high",
        crop_impact="Severe",
    )
    assert row_id is not None, "save_analysis should return an integer id"
    yield row_id
    # Cleanup
    db.delete_analysis(row_id)


def test_save_and_fetch(db, saved_id):
    rows = db.get_analyses(limit=5)
    ids = [r["id"] for r in rows]
    assert saved_id in ids, "Saved row should appear in get_analyses()"


def test_fetch_with_field_zone(db, saved_id):
    rows = db.get_analyses(limit=10, field_zone="North Field")
    assert any(r["id"] == saved_id for r in rows)

    rows_other = db.get_analyses(limit=10, field_zone="Nonexistent Zone")
    assert all(r["id"] != saved_id for r in rows_other)


def test_fetch_with_date_filter(db, saved_id):
    from datetime import date, timedelta
    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    rows = db.get_analyses(limit=10, date_from=today, date_to=tomorrow)
    assert any(r["id"] == saved_id for r in rows)


def test_fetch_pagination(db, saved_id):
    all_rows   = db.get_analyses(limit=100, offset=0)
    paged_rows = db.get_analyses(limit=100, offset=len(all_rows))
    assert len(paged_rows) == 0, "Offset past end should return empty list"


def test_image_retrieval(db, saved_id):
    data = db.get_image(saved_id)
    assert data is not None, "Stored image_data should be retrievable"
    assert data[:4] == b"\xff\xd8\xff\xe0", "Retrieved bytes should match stored JPEG header"


def test_stats(db, saved_id):
    stats = db.get_stats()
    assert "total" in stats
    assert stats["total"] >= 1


def test_trend(db, saved_id):
    rows = db.get_trend(days=7)
    assert isinstance(rows, list)
    if rows:
        assert "day" in rows[0]
        assert "critical" in rows[0]


def test_delete(db, saved_id):
    result = db.delete_analysis(saved_id)
    assert result is True, "delete_analysis should return True on success"

    rows = db.get_analyses(limit=100)
    assert all(r["id"] != saved_id for r in rows), "Deleted row should not appear in results"

    # Prevent the fixture from trying to delete again
    # (already deleted here — fixture cleanup will silently fail, that's fine)


def test_delete_nonexistent(db):
    result = db.delete_analysis(999999999)
    assert result is False, "delete_analysis should return False for missing id"


def test_is_available(db):
    assert db.is_available() is True, "is_available() should return True with a live DB"
