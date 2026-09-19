"""Priority engine and clustering service unit tests."""
from app.ai import embeddings, severity_rules
from app.db.session import SessionLocal
from app.models.catalog import Category
from app.services.clustering import attach_report
from app.services.priority import apply_priority


def test_priority_weights_sum_and_levels():
    from scripts.seed import PRIORITY_WEIGHTS

    assert abs(sum(PRIORITY_WEIGHTS.values()) - 1.0) < 0.01


def test_severity_rules_detect_urgency_words():
    text = "Live wire fallen on road, children passing, DANGER very urgent"
    assert severity_rules.score_severity(text, {}, "electricity") >= 4

    urgent_text = "No water since ten days, urgent emergency, immediately needed, every night suffering"
    assert severity_rules.score_urgency(urgent_text) >= 4
    calm = "Small crack visible on the wall near park bench"
    assert severity_rules.score_severity(calm, {}, "other") <= 3
    assert severity_rules.score_urgency(calm) <= 2


def test_embeddings_similarity_ranges():
    same = embeddings.similarity("huge pothole near school gate", "pothole near school gate")
    diff = embeddings.similarity("huge pothole near school gate", "street light not working")
    assert same > diff
    assert embeddings.similarity("", "anything") == 0.0


def test_attach_report_merges_within_radius(seeded_db=None):
    with SessionLocal() as db:
        cat = db.query(Category).filter_by(slug="water").first()
        r1 = _mk(db, cat, "Tap dry for a week", "No municipal water at all here.", 23.5001, 85.5001)
        c1, s1 = attach_report(db, r1)
        r2 = _mk(db, cat, "Municipal water never comes", "The tap has been dry a whole week.", 23.5002, 85.5002)
        c2, s2 = attach_report(db, r2)
        db.commit()
        assert c1.id == c2.id, "same-place same-category must merge"
        assert s2 >= 0.62

        r3 = _mk(db, cat, "Complaint about park benches", "Paint peeling off benches far away.", 23.5600, 85.5600)
        c3, _ = attach_report(db, r3)
        db.commit()
        assert c3.id != c1.id


def _mk(db, cat, title, desc, lat, lng):
    from app.models.civic import Report
    from app.services.ids import next_code

    r = Report(code=next_code(db, "report"), title=title, description=desc,
               category_id=cat.id, latitude=lat, longitude=lng,
               ai_severity=4, ai_urgency=4, status="reported", location_source="map")
    db.add(r)
    db.flush()
    return r
