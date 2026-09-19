"""Auth flows: registration, login, refresh rotation, profile, RBAC gates."""
from tests.conftest import _register


def test_register_and_duplicate(client):
    email, pwd = _register(client, "authdup@test.in")
    r = client.post("/api/v1/auth/register", json={
        "email": email, "password": pwd, "full_name": "Dup",
    })
    assert r.status_code == 201 or r.status_code == 409  # first register may have happened in fixture
    r2 = client.post("/api/v1/auth/register", json={
        "email": email, "password": pwd, "full_name": "Dup",
    })
    assert r2.status_code == 409
    body = r2.json()
    assert "already exists" in body["detail"]


def test_register_is_always_citizen(client):
    r = client.post("/api/v1/auth/register", json={
        "email": "rolecheck@test.in", "password": "citizen-pass", "full_name": "Role Check",
    })
    assert r.status_code == 201
    assert r.json()["role"] == "citizen"


def test_login_success_and_failure(client):
    ok = client.post("/api/v1/auth/login-json", json={"email": "citizen1@test.in", "password": "citizen-pass"})
    assert ok.status_code == 200
    tokens = ok.json()
    assert tokens["access_token"] and tokens["refresh_token"]

    bad = client.post("/api/v1/auth/login-json", json={"email": "citizen1@test.in", "password": "wrong"})
    assert bad.status_code == 401


def test_me_requires_token(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_refresh_rotation(client):
    login = client.post("/api/v1/auth/login-json", json={"email": "citizen1@test.in", "password": "citizen-pass"})
    refresh = login.json()["refresh_token"]
    first = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert first.status_code == 200

    # old refresh token must now be revoked (rotation)
    replay = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert replay.status_code == 401


def test_citizen_cannot_list_actions(client, citizen):
    assert client.get("/api/v1/actions", headers=citizen).status_code == 403


def test_authority_can_list_actions(client, authority):
    r = client.get("/api/v1/actions", headers=authority)
    assert r.status_code == 200
    assert set(r.json().keys()) >= {"items", "total"}


def test_admin_required_for_weight_update(client, authority, admin):
    payload = {"severity": 0.3}
    assert client.put("/api/v1/priorities/weights", json=payload, headers=authority).status_code == 403
    assert client.put("/api/v1/priorities/weights", json=payload, headers=admin).status_code == 200
