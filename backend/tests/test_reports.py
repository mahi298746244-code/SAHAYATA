"""Report creation pipeline: AI classification, clustering, citizen access."""
from app.db.session import SessionLocal
from app.models.civic import ProblemCluster

CAT_URL = "/api/v1/catalog/categories"


def _category_id(client, headers, slug):
    r = client.get(CAT_URL, headers=headers)
    return next(c["id"] for c in r.json() if c["slug"] == slug)


def _create_report(client, headers, title, desc, lat, lng, category_id=None, **kw):
    data = {
        "title": title, "description": desc,
        "latitude": lat, "longitude": lng, "address_text": kw.get("address", "Test street"),
        "landmark": kw.get("landmark", ""), "ward": kw.get("ward", "1"),
        "location_source": "map",
    }
    if category_id:
        data["category_id"] = category_id
    files = []
    if kw.get("photo"):
        files = [("images", ("test.png", kw["photo"], "image/png"))]
    r = client.post("/api/v1/reports", headers=headers, data=data, files=files)
    assert r.status_code == 201, r.text
    body = r.json()
    # Background pipeline runs synchronously inside TestClient.post(); refetch
    # so AI + clustering results are visible on the returned object.
    detail = client.get(f"/api/v1/reports/{body['code']}", headers=headers).json()
    body.update(detail)
    return body


def _detail(client, headers, code):
    return client.get(f"/api/v1/reports/{code}", headers=headers).json()


def test_create_report_with_ai_classification(client, citizen):
    cid = _category_id(client, citizen, "water")
    body = _create_report(
        client, citizen,
        "No water for three days", "The entire street has no water supply, tanker not coming.",
        23.3600, 85.3300, category_id=cid, landmark="AI test lane",
    )
    assert body["code"].startswith("RPT-")
    # Background pipeline runs synchronously under TestClient → refetch shows AI fields
    d = _detail(client, citizen, body["code"])
    assert (d["ai_severity"] or 0) >= 1
    assert (d["ai_urgency"] or 0) >= 1


def test_duplicate_reports_join_same_cluster(client, citizen):
    cid = _category_id(client, citizen, "water")
    a = _create_report(client, citizen, "Water pipeline leak on main road",
                       "Huge leak flooding the road near the bus stand.", 23.3610, 85.3310,
                       category_id=cid, landmark="Dup lane A")
    b = _create_report(client, citizen, "Pipeline leaking badly here",
                       "Water is wasting since morning near bus stand, please fix.",
                       23.3612, 85.3313, category_id=cid, landmark="Dup lane B")

    with SessionLocal() as db:
        assert a["cluster_code"], "first report must be attached to a cluster"
        assert a["cluster_code"] == b["cluster_code"], "similar nearby reports must merge"
        cluster = db.query(ProblemCluster).filter_by(code=a["cluster_code"]).first()
        assert cluster.report_count >= 2


def test_distant_similar_report_stays_separate(client, citizen):
    cid = _category_id(client, citizen, "water")
    c = _create_report(client, citizen, "No water in other colony",
                       "Completely different area with no supply.", 23.4200, 85.4000,
                       category_id=cid, landmark="Far colony")
    with SessionLocal() as db:
        cluster = db.query(ProblemCluster).filter_by(code=c["cluster_code"]).first()
        assert cluster.report_count == 1, "far-away reports must never merge"


def test_similar_endpoint_lists_cluster_siblings(client, citizen):
    mine = client.get("/api/v1/reports/mine", headers=citizen).json()["items"]
    with_cluster = next((i for i in mine), None)
    r = client.get(f"/api/v1/reports/{with_cluster['code']}/similar", headers=citizen)
    assert r.status_code == 200
    assert "cluster" in r.json() and "reports" in r.json()


def test_citizen_sees_own_reports_and_soft_delete(client, citizen):
    mine = client.get("/api/v1/reports/mine", headers=citizen)
    assert mine.status_code == 200
    items = mine.json()["items"]
    assert items

    target = items[0]["code"]
    del_r = client.delete(f"/api/v1/reports/{target}", headers=citizen)
    assert del_r.status_code == 204

    after = {i["code"] for i in client.get("/api/v1/reports/mine", headers=citizen).json()["items"]}
    assert target not in after


def test_cannot_delete_others_report(client, citizen, citizen2):
    cid = _category_id(client, citizen2, "roads")
    other = _create_report(client, citizen2, "Ownership guard report",
                           "Report used to verify deletion ownership rules.",
                           23.3999, 85.3999, category_id=cid, landmark="Guard lane")["code"]
    r = client.delete(f"/api/v1/reports/{other}", headers=citizen)
    assert r.status_code == 403
    assert client.delete(f"/api/v1/reports/{other}", headers=citizen2).status_code == 204


def test_mine_lists_are_isolated(client, citizen, citizen2):
    c1 = {i["code"] for i in client.get("/api/v1/reports/mine", headers=citizen).json()["items"]}
    c2 = {i["code"] for i in client.get("/api/v1/reports/mine", headers=citizen2).json()["items"]}
    assert c1.isdisjoint(c2)
