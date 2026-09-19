"""Pytest fixtures: isolated SQLite database + API client + authenticated users."""
import os
import pathlib
import sys

BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1]
TEST_DB = BACKEND_DIR / "data" / "test_sahayata.db"

# Must be set BEFORE any app module import (Settings reads env at import time).
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["RATE_LIMIT_DEFAULT"] = "1000/minute"
os.environ["RATE_LIMIT_AUTH"] = "1000/minute"
os.environ["ADMIN_EMAIL"] = "admin@test.gov"
os.environ["ADMIN_PASSWORD"] = "admin-test-pass"

sys.path.insert(0, str(BACKEND_DIR))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

if TEST_DB.exists():
    TEST_DB.unlink()

from app.db.session import SessionLocal, create_all  # noqa: E402
from app.models.user import Role, User  # noqa: E402
from app.core.security import hash_password  # noqa: E402


@pytest.fixture(scope="session")
def seeded_db():
    """Create schema and base catalog once for the whole test session."""
    create_all()
    sys.path.insert(0, str(BACKEND_DIR / "scripts"))
    import seed as seed_module

    with SessionLocal() as session:
        seed_module.seed_base(session)
        # dedicated authority user for API tests
        authority_role = session.query(Role).filter_by(name="authority").first()
        if not session.query(User).filter_by(email="authority@test.gov").first():
            session.add(User(
                email="authority@test.gov", full_name="Test Authority",
                password_hash=hash_password("authority-pass"),
                role_id=authority_role.id,
            ))
            session.commit()
    yield


@pytest.fixture(scope="session")
def client(seeded_db):
    from app.main import app

    with TestClient(app) as c:
        yield c


def _register(client, email, password="citizen-pass"):
    r = client.post("/api/v1/auth/register", json={
        "email": email, "password": password, "full_name": email.split("@")[0].title(),
    })
    if r.status_code == 409:  # already registered in this session
        client.post("/api/v1/auth/login-json", json={"email": email, "password": password})
    return email, password


def _login(client, email, password):
    r = client.post("/api/v1/auth/login-json", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def citizen(client):
    _register(client, "citizen1@test.in")
    return _login(client, "citizen1@test.in", "citizen-pass")


@pytest.fixture(scope="session")
def citizen2(client):
    _register(client, "citizen2@test.in")
    return _login(client, "citizen2@test.in", "citizen-pass")


@pytest.fixture(scope="session")
def authority(client):
    return _login(client, "authority@test.gov", "authority-pass")


@pytest.fixture(scope="session")
def admin(client):
    return _login(client, "admin@test.gov", "admin-test-pass")
