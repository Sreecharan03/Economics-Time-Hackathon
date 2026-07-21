"""
Unlike compliance-service/schedule-service (pure Python, no DB), this service
needs a real Postgres+pgvector instance -- there is no meaningful way to unit
test cosine ranking without a real vector index. Tests run against whatever
DATABASE_URL points to (defaults to localhost:5432, matching a local
`docker compose -f infra/docker-compose.yml up -d postgres`) and seed it once
per test session via the real seed_rfis.py, not a mocked DB layer.
"""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.main import app  # noqa: E402
import seed_rfis  # noqa: E402


@pytest.fixture(scope="session")
def seeded_db():
    seed_rfis.main()


@pytest.fixture()
def client(seeded_db):
    # DB seeding only happens for tests that actually request `client` (i.e.
    # test_api.py) -- previously this was session-scoped `autouse=True`,
    # which meant test_embeddings.py's pure embedding-math tests silently
    # required a live Postgres connection too, even though they never touch
    # the DB. That coupling broke this exact test file when Postgres wasn't
    # reachable, for no reason related to what those tests actually check.
    return TestClient(app)
