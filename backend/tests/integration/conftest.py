import uuid

import pytest
from fastapi.testclient import TestClient

from app import ratelimit
from app.main import app


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    ratelimit.reset_all()
    yield


def make_client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def anon() -> TestClient:
    return make_client()


def register(client: TestClient) -> dict:
    email = f"it-{uuid.uuid4().hex[:10]}@example.com"
    r = client.post("/api/auth/register", json={"email": email, "password": "password123", "display_name": "IT"})
    assert r.status_code == 201, r.text
    return r.json() | {"password": "password123"}


@pytest.fixture
def user_client() -> TestClient:
    c = make_client()
    c.user = register(c)  # type: ignore[attr-defined]
    return c
