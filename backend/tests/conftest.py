import os
import sys
import tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp(prefix="insp-test-")
os.environ.update(DATA_DIR=_tmp, AUTO_SEED="0", SEED_EQUIPMENT="60", SEED_NDT="600", SEED_SIGNALS="80",
                  SEED_IMAGES="10", NDT_TRAIN_PER_CLASS="200", SECRET_KEY="test-secret-key-0123456789abcdef",
                  DEMO_PASSWORD="Test@12345")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session")
def client():
    from app.main import app
    from app.seed import seed
    seed(verbose=False)
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def tokens(client):
    out = {}
    for u in ("admin", "manager", "inspector", "ndt", "corrosion", "rbi", "hse", "asset"):
        r = client.post("/api/auth/login", json={"username": u, "password": "Test@12345"})
        assert r.status_code == 200, r.text
        out[u] = {"Authorization": "Bearer " + r.json()["access_token"]}
    return out
