from fastapi.testclient import TestClient
from app.main import app
from PIL import Image
from io import BytesIO

client = TestClient(app)


def make_jpeg_bytes():
    img = Image.new('RGB', (64, 64), color=(200, 120, 50))
    buf = BytesIO()
    img.save(buf, format='JPEG')
    buf.seek(0)
    return buf.read()


def test_analyze_with_real_image():
    data = {"file": ("real.jpg", make_jpeg_bytes(), "image/jpeg")}
    r = client.post('/api/analyze', files=data)
    assert r.status_code == 200
    j = r.json()
    assert 'filename' in j
    assert 'result' in j
    assert 'confidence' in j
 