"""
Tests for the analyze endpoint.
Uses a tiny valid JPEG so the upload is accepted even if AI calls fail.
"""
from fastapi.testclient import TestClient

try:
    from app.main import app
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from apps.api.app.main import app

client = TestClient(app)

# Minimal valid 1×1 white JPEG bytes
_TINY_JPEG = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
    b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
    b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\x1e"
    b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00"
    b"\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00"
    b"\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b"
    b"\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02\x04\x03\x05\x05\x04"
    b"\x04\x00\x00\x01}\x01\x02\x03\x00\x04\x11\x05\x12!1A\x06\x13Qa"
    b"\x07\"q\x142\x81\x91\xa1\x08#B\xb1\xc1\x15R\xd1\xf0$3br"
    b"\x82\t\n\x16\x17\x18\x19\x1a%&'()*456789:CDEFGHIJ"
    b"STUVWXYZ\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xfb\xd4P\x00\x00\x00\xff\xd9"
)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_analyze_returns_expected_fields():
    files = {"file": ("farm.jpg", _TINY_JPEG, "image/jpeg")}
    r = client.post("/api/analyze", files=files)
    assert r.status_code == 200, r.text
    data = r.json()
    for field in ("filename", "result", "confidence", "issue_detected", "status"):
        assert field in data, f"Missing field: {field}"
    assert data["filename"] == "farm.jpg"
    assert 0.0 <= float(data["confidence"]) <= 1.0


def test_analyze_rejects_non_image():
    files = {"file": ("data.txt", b"not an image", "text/plain")}
    r = client.post("/api/analyze", files=files)
    assert r.status_code == 400


def test_analyze_with_field_zone():
    files = {"file": ("field.jpg", _TINY_JPEG, "image/jpeg")}
    data  = {"field_zone": "North Field"}
    r = client.post("/api/analyze", files=files, data=data)
    assert r.status_code == 200
    assert r.json().get("field_zone") == "North Field"


def test_stats_endpoint():
    r = client.get("/api/stats")
    assert r.status_code == 200
    for field in ("total", "critical", "warning", "healthy"):
        assert field in r.json()


def test_analyses_list():
    r = client.get("/api/analyses?limit=5")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_trend_endpoint():
    r = client.get("/api/trend?days=7")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_analyze_rejects_oversized_field_zone():
    files = {"file": ("field.jpg", _TINY_JPEG, "image/jpeg")}
    data  = {"field_zone": "A" * 81}
    r = client.post("/api/analyze", files=files, data=data)
    assert r.status_code == 422


def test_analyze_accepts_max_length_field_zone():
    files = {"file": ("field.jpg", _TINY_JPEG, "image/jpeg")}
    data  = {"field_zone": "B" * 80}
    r = client.post("/api/analyze", files=files, data=data)
    assert r.status_code == 200


def test_get_analysis_by_id_not_found():
    r = client.get("/api/analyses/999999999")
    assert r.status_code == 404


def test_get_analysis_by_id_returns_record():
    # First create a record
    files = {"file": ("test_id.jpg", _TINY_JPEG, "image/jpeg")}
    created = client.post("/api/analyze", files=files).json()
    record_id = created.get("id")
    if record_id is None:
        return  # DB not available in this test environment — skip

    r = client.get(f"/api/analyses/{record_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == record_id
    assert data["filename"] == "test_id.jpg"
    assert "confidence" in data
    assert "status" in data


def test_batch_analyze_multiple_images():
    """Uploading three images individually (simulating batch) all return valid responses."""
    for name in ("batch1.jpg", "batch2.jpg", "batch3.jpg"):
        files = {"file": (name, _TINY_JPEG, "image/jpeg")}
        r = client.post("/api/analyze", files=files)
        assert r.status_code == 200, f"Failed for {name}: {r.text}"
        data = r.json()
        assert data["filename"] == name
        assert data["status"] in ("critical", "warning", "healthy", "unknown")


def test_zones_endpoint():
    r = client.get("/api/zones")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_analyses_export_csv():
    r = client.get("/api/analyses/export")
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")


def test_delete_nonexistent_analysis():
    r = client.delete("/api/analyses/999999999")
    assert r.status_code == 404
