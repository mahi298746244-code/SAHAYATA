"""Full accountability loop: action lifecycle, evidence, citizen verification."""
CAT_URL = "/api/v1/catalog/categories"


def _category_id(client, headers, slug):
    r = client.get(CAT_URL, headers=headers)
    return next(c["id"] for c in r.json() if c["slug"] == slug)


def _departments(client, headers):
    return client.get("/api/v1/catalog/departments", headers=headers).json()


def _make_problem(client, citizen):
    cid = _category_id(client, citizen, "drainage")
    data = {"title": "Drain blocked causing flood", "description": "Whole lane waterlogged, mosquitoes breeding.",
            "latitude": 23.3801, "longitude": 85.3501, "landmark": "Action test lane",
            "ward": "5", "location_source": "map", "category_id": cid}
    r = client.post("/api/v1/reports", headers=citizen, data=data)
    assert r.status_code == 201
    code = r.json()["code"]
    detail = client.get(f"/api/v1/reports/{code}", headers=citizen).json()
    code = detail["cluster_code"]
    assert code
    return code


def _problem_detail(client, headers, code):
    return client.get(f"/api/v1/problems/{code}", headers=headers).json()


def test_full_lifecycle_to_verified(client, citizen, authority):
    problem = _make_problem(client, citizen)
    dept_id = _departments(client, authority)[0]["id"]

    # invalid transition first: assigned → closed is not allowed later anyway; start correctly
    r = client.post("/api/v1/actions", headers=authority, json={
        "problem_id": problem, "department_id": dept_id,
        "team_name": "Drain Crew 1", "notes": "Jetting machine scheduled",
        "estimated_cost": 8000,
    })
    assert r.status_code == 201, r.text
    action = r.json()["code"]
    assert r.json()["status"] == "assigned"

    # illegal jump: assigned → completed must be rejected
    bad = client.patch(f"/api/v1/actions/{action}", headers=authority, json={"status": "completed"})
    assert bad.status_code == 409

    ok1 = client.patch(f"/api/v1/actions/{action}", headers=authority, json={"status": "in_progress"})
    assert ok1.status_code == 200 and ok1.json()["status"] == "in_progress"

    ev = client.post(f"/api/v1/actions/{action}/evidence", headers=authority,
                     data={"note": "Drain cleared, desilted 40m stretch."})
    assert ev.status_code == 201, ev.text
    assert ev.json()["status"] == "verification_pending"
    assert _problem_detail(client, authority, problem)["status"] == "verification_pending"

    # a citizen who never reported this cannot verify
    stranger = client.post("/api/v1/verifications", headers=_other_citizens_headers(client), json={
        "problem_id": problem, "verdict": "yes", "comment": ""})
    assert stranger.status_code == 403

    # the reporting citizen confirms resolution
    ver = client.post("/api/v1/verifications", headers=citizen, json={
        "problem_id": problem, "verdict": "yes", "comment": "Water flows now, good work."})
    assert ver.status_code == 201
    detail = _problem_detail(client, authority, problem)
    assert detail["status"] == "verified"


def _other_citizens_headers(client):
    from tests.conftest import _login
    try:
        return _login(client, "citizen2@test.in", "citizen-pass")
    except AssertionError:
        from tests.conftest import _register
        _register(client, "citizen2@test.in")
        return _login(client, "citizen2@test.in", "citizen-pass")


def test_rejected_verification_reopens_problem(client, citizen2, authority):
    problem = _make_problem(client, citizen2)
    dept_id = _departments(client, authority)[1]["id"]
    act = client.post("/api/v1/actions", headers=authority, json={
        "problem_id": problem, "department_id": dept_id, "team_name": "Crew X",
        "notes": "Preliminary clearing done",
    }).json()["code"]

    client.patch(f"/api/v1/actions/{act}", headers=authority, json={"status": "in_progress"})
    client.post(f"/api/v1/actions/{act}/evidence", headers=authority,
                data={"note": "Partially cleared; will monitor."})

    rej = client.post("/api/v1/verifications", headers=citizen2, json={
        "problem_id": problem, "verdict": "no", "comment": "Still blocked at the corner."})
    assert rej.status_code == 201

    detail = _problem_detail(client, authority, problem)
    assert detail["status"] == "action_required"
    hist = client.get(f"/api/v1/verifications/problem/{problem}", headers=citizen2).json()
    assert [h["verdict"] for h in hist] == ["no"]


def test_verification_requires_pending_status(client, citizen, authority):
    """Cannot verify a problem that is not awaiting verification."""
    problem = _make_problem(client, citizen)  # status: reported/action_required
    r = client.post("/api/v1/verifications", headers=citizen, json={
        "problem_id": problem, "verdict": "yes"})
    assert r.status_code == 409


def test_action_list_filter_by_status(client, authority):
    r = client.get("/api/v1/actions", headers=authority, params={"status": "closed"})
    assert r.status_code == 200
    for item in r.json()["items"]:
        assert item["status"] == "closed"
