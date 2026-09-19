"""Analytics, simulator, accessibility, map and misc endpoints."""
from tests.test_reports import _category_id, _create_report


def test_analytics_overview(client, authority):
    r = client.get("/api/v1/analytics/overview", headers=authority)
    assert r.status_code == 200
    body = r.json()
    assert body["total_reports"] >= 1
    assert "active_problems" in body


def test_map_problems_bbox(client, citizen):
    r = client.get("/api/v1/map/problems", headers=citizen,
                   params={"sw_lat": 23.0, "sw_lng": 85.0, "ne_lat": 23.6, "ne_lng": 85.6})
    assert r.status_code == 200
    items = r.json()
    assert isinstance(items, list)
    for item in items:
        assert item["type"] == "problem"
        break


def test_priority_queue_orders_by_score(client, authority):
    r = client.get("/api/v1/priorities", headers=authority)
    assert r.status_code == 200
    scores = [p["score"] for p in r.json()]
    assert scores == sorted(scores, reverse=True), "queue must be score-descending"
    if scores:
        assert set(r.json()[0].keys()) >= {"top_factors"}


def test_simulator_run(client, authority):
    payload = {"budget": 500000, "sectors": ["drainage", "garbage", "water"]}
    r = client.post("/api/v1/simulator/run", headers=authority, json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["problems_addressed"] >= 0
    assert body["estimated_citizens_benefited"] >= 0
    assert 0 <= body["impact_score"] <= 100
    assert "disclaimer" in body


def test_accessibility_gaps(client, authority):
    r = client.get("/api/v1/accessibility/gaps", headers=authority)
    assert r.status_code == 200


def test_global_search(client, authority):
    r = client.get("/api/v1/search", headers=authority, params={"q": "water"})
    assert r.status_code == 200


def test_notifications_flow(client, citizen):
    lst = client.get("/api/v1/notifications", headers=citizen).json()
    assert lst["total"] >= 1, "report creation should have generated notifications"
    unread_before = lst["unread"]
    if unread_before:
        first_unread = next(n for n in lst["items"] if not n["read_at"])
        client.post(f"/api/v1/notifications/{first_unread['id']}/read", headers=citizen)
        after = client.get("/api/v1/notifications", headers=citizen).json()
        assert after["unread"] == unread_before - 1


def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
