"""SAHAYATA seed script.

Usage:
    python scripts/seed.py            # base catalog + admin account
    python scripts/seed.py --demo     # additionally load clearly-flagged DEMO data

Demo rows are always marked is_demo=True so they can never be confused with
production records (and can be filtered out of dashboards).
"""
import argparse
import io
import math
import secrets
import struct
import sys
import zlib
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.core.logging import configure_logging  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.base import utcnow  # noqa: E402
from app.db.session import SessionLocal, create_all  # noqa: E402
from app.models.catalog import Category, Department  # noqa: E402
from app.models.geo import Facility  # noqa: E402
from app.models.system import SimulationParameter  # noqa: E402
from app.models.user import Role, User  # noqa: E402

configure_logging()

# Category-tinted palettes used by the demo photo generator.
CATEGORY_TINT = {
    "water": (59, 130, 246),
    "roads": (168, 162, 158),
    "street_lighting": (250, 204, 21),
    "garbage": (34, 197, 94),
    "drainage": (14, 165, 233),
    "electricity": (239, 68, 68),
    "healthcare": (16, 185, 129),
    "public_transport": (168, 85, 247),
    "public_safety": (244, 63, 94),
    "sanitation": (20, 184, 166),
}


def _demo_png(seed_int: int, base=(99, 102, 241), w=320, h=200) -> bytes:
    """Dependency-free placeholder 'photo': tinted gradient + soft blobs.

    Keeps demo galleries visually alive without shipping binary assets or
    requiring Pillow. Deterministic per seed_int.
    """
    s = (seed_int * 2654435761 + 12345) & 0x7FFFFFFF
    r0, g0, b0 = base
    r1, g1, b1 = (min(255, c // 2 + 60) for c in base)
    circles = []
    for _ in range(3):
        s = (s * 1103515245 + 12345) & 0x7FFFFFFF
        cx = s % w
        s = (s * 1103515245 + 12345) & 0x7FFFFFFF
        cy = s % h
        circles.append((cx, cy, 28 + s % 46))
    rows = []
    for y in range(h):
        t = y / (h - 1)
        wave = math.sin(y * 0.09) * 9
        row = bytearray(b"\x00")
        spans = []
        for cx, cy, rad in circles:
            dy2 = (y - cy) ** 2
            if dy2 < rad * rad:
                dx = int(math.sqrt(rad * rad - dy2))
                spans.append((cx - dx, cx + dx, rad))
        for x in range(w):
            rr = r0 + (r1 - r0) * t + wave
            gg = g0 + (g1 - g0) * t + wave
            bb = b0 + (b1 - b0) * t + wave
            for x0, x1, rad in spans:
                if x0 <= x <= x1:
                    d2 = (x - (x0 + x1) / 2) ** 2 + 0.0
                    k = 0.22 * (1 - d2 / (rad * rad))
                    rr += (255 - rr) * k
                    gg += (255 - gg) * k
                    bb += (255 - bb) * k
            row += bytes((int(rr) & 255, int(gg) & 255, int(bb) & 255))
        rows.append(bytes(row))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(
            ">I", zlib.crc32(tag + data) & 0xFFFFFFFF
        )

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(b"".join(rows), 6)) + chunk(b"IEND", b"")


ROLES = [
    ("citizen", "Reports civic issues and verifies resolutions"),
    ("authority", "Municipal/government staff who triage and act"),
    ("admin", "Full administrative control"),
]

DEPARTMENTS = [
    ("Public Works Department", "pwd", "Roads, bridges and public infrastructure"),
    ("Water Supply & Sanitation", "water", "Pipelines, water supply and sewerage"),
    ("Electricity Board", "electricity", "Power distribution and street lighting"),
    ("Solid Waste Management", "garbage", "Garbage collection and disposal"),
    ("Health Department", "healthcare", "PHCs, dispensaries and health camps"),
    ("Education Department", "education", "Schools and anganwadi centres"),
    ("Transport Cell", "public_transport", "City bus service and shelters"),
    ("Safety & Security Cell", "public_safety", "Coordination with police/safety services"),
]

CATEGORIES = [
    ("Roads", "roads", "#f97316", "road", ["pothole", "road damage", "gadha"]),
    ("Water", "water", "#0ea5e9", "droplets", ["no water", "leakage", "contamination"]),
    ("Electricity", "electricity", "#eab308", "zap", ["power cut", "transformer", "wire"]),
    ("Garbage/Waste", "garbage", "#84cc16", "trash-2", ["garbage", "kachra", "dump"]),
    ("Drainage", "drainage", "#06b6d4", "waves", ["drain", "nali", "sewer", "waterlogging"]),
    ("Street Lighting", "street_lighting", "#a855f7", "lamp", ["street light", "batti", "dark"]),
    ("Healthcare", "healthcare", "#ef4444", "heart-pulse", ["doctor", "medicine", "ambulance"]),
    ("Education", "education", "#6366f1", "graduation-cap", ["school", "teacher", "anganwadi"]),
    ("Public Safety", "public_safety", "#f43f5e", "shield-alert", ["stray dogs", "theft", "patrolling"]),
    ("Sanitation", "sanitation", "#14b8a6", "spray-can", ["toilet", "safai", "defecation"]),
    ("Public Transport", "public_transport", "#8b5cf6", "bus", ["bus", "shelter", "auto stand"]),
    ("Environment", "environment", "#22c55e", "leaf", ["tree cutting", "pollution", "lake"]),
    ("Other", "other", "#64748b", "circle-help", []),
]

# category slug -> department slug (default ownership)
CATEGORY_DEPARTMENT = {
    "roads": "pwd", "drainage": "water", "water": "water",
    "electricity": "electricity", "street_lighting": "electricity",
    "garbage": "garbage", "sanitation": "garbage",
    "healthcare": "healthcare", "education": "education",
    "public_transport": "public_transport", "public_safety": "public_safety",
}

PRIORITY_WEIGHTS = {
    "severity": 0.25, "urgency": 0.20, "population": 0.20,
    "density": 0.15, "accessibility": 0.10, "safety": 0.10,
}

SIMULATOR_DEFAULTS = {
    "cost_per_problem": {"water": 120000, "healthcare": 250000, "roads": 80000},
    "beneficiaries_per_problem": {"water": 900, "healthcare": 2500, "roads": 1200},
}

SETTLEMENTS = [
    {"name": "Ward 4 – Hindpiri", "type": "ward", "lat": 23.3620, "lng": 85.3320, "population": 14500},
    {"name": "Village Chota Nagri", "type": "village", "lat": 23.2880, "lng": 85.2100, "population": 6200},
    {"name": "Ward 12 – Doranda", "type": "ward", "lat": 23.3550, "lng": 85.3570, "population": 22000},
]

FACILITIES = [
    ("RIMS Hospital", "healthcare", 23.3441, 85.3096, "full", "Tertiary care"),
    ("Hindpiri PHC", "healthcare", 23.3615, 85.3315, "limited", "OPD only, day time"),
    ("Chota Nagri Sub-centre", "healthcare", 23.2900, 85.2150, "basic", "ASHA worker post"),
    ("Govt Middle School Hindpiri", "education", 23.3630, 85.3300, "full", None),
    ("Chota Nagri Primary School", "education", 23.2870, 85.2080, "limited", "2 rooms"),
    ("Overhead Tank Ward-4", "water", 23.3600, 85.3340, "full", None),
    ("Chota Nagri Handpump Cluster", "water", 23.2920, 85.2120, "basic", "3 handpumps"),
    ("Fire Station Doranda", "emergency", 23.3540, 85.3590, "full", None),
]


def seed_base(db) -> None:
    for name, desc in ROLES:
        if not db.query(Role).filter_by(name=name).first():
            db.add(Role(name=name, description=desc))
    db.commit()
    roles = {r.name: r for r in db.query(Role).all()}

    dept_map = {}
    for name, slug, desc in DEPARTMENTS:
        d = db.query(Department).filter_by(slug=slug).first()
        if not d:
            d = Department(name=name, slug=slug, description=desc)
            db.add(d)
            db.flush()
        dept_map[slug] = d

    cat_map = {}
    for i, (name, slug, color, icon, kws) in enumerate(CATEGORIES):
        c = db.query(Category).filter_by(slug=slug).first()
        if not c:
            c = Category(
                name=name, slug=slug, color=color, icon=icon, keywords=kws,
                department_id=dept_map[CATEGORY_DEPARTMENT[slug]].id if slug in CATEGORY_DEPARTMENT else None,
                display_order=i,
            )
            db.add(c)
            db.flush()
        cat_map[slug] = c

    params = [
        ("priority.weights", PRIORITY_WEIGHTS, "Priority engine component weights (sum normalised)"),
        ("simulator.defaults", SIMULATOR_DEFAULTS, "Impact simulator planning assumptions (estimates only)"),
        ("accessibility.settlements", SETTLEMENTS, "Settlements used for accessibility gap analysis"),
        ("accessibility.thresholds_km",
         {"healthcare": 10.0, "education": 5.0, "water": 2.0, "emergency": 15.0},
         "Distance beyond which a settlement is flagged as a gap"),
    ]
    for key, value, desc in params:
        if not db.get(SimulationParameter, key):
            db.add(SimulationParameter(key=key, value_json=value, description=desc))

    admin_email = settings.ADMIN_EMAIL or "admin@sahayata.gov.in"
    admin = db.query(User).filter_by(email=admin_email).first()
    if not admin:
        password = settings.ADMIN_PASSWORD or secrets.token_urlsafe(12)
        admin = User(
            email=admin_email, full_name="System Administrator",
            password_hash=hash_password(password), role_id=roles["admin"].id,
        )
        db.add(admin)
        db.commit()
        print("\n" + "=" * 60)
        print(f"ADMIN ACCOUNT CREATED")
        print(f"  email:    {admin_email}")
        print(f"  password: {password}")
        print("  (store it now – this is printed only once)")
        print("=" * 60 + "\n")

    db.commit()
    print(f"Base seed complete: {len(roles)} roles, {len(dept_map)} departments, "
          f"{len(cat_map)} categories.")


def seed_demo(db) -> None:
    """Clearly-flagged demo dataset around the Ranchi region."""
    from app.models.civic import ReportMedia
    from app.services.clustering import attach_report
    from app.services.accessibility import compute_gaps
    from app.services.storage import get_storage

    citizen_role = db.query(Role).filter_by(name="citizen").first()
    authority_role = db.query(Role).filter_by(name="authority").first()
    pwd = hash_password("demo12345")

    citizens = []
    demo_people = [
        ("Aarti Kumari", "aarti.demo@sahayata.in"), ("Ramesh Oraon", "ramesh.demo@sahayata.in"),
        ("Sunita Devi", "sunita.demo@sahayata.in"), ("Imran Khan", "imran.demo@sahayata.in"),
        ("Priya Sharma", "priya.demo@sahayata.in"), ("Joseph Tirkey", "joseph.demo@sahayata.in"),
    ]
    for full_name, email in demo_people:
        u = db.query(User).filter_by(email=email).first()
        if not u:
            u = User(email=email, full_name=full_name, password_hash=pwd,
                     role_id=citizen_role.id, is_demo=True)
            db.add(u)
            db.flush()
        citizens.append(u)

    authority = db.query(User).filter_by(email="officer.demo@sahayata.in").first()
    if not authority:
        authority = User(email="officer.demo@sahayata.in", full_name="Ward Officer (Demo)",
                         password_hash=pwd, role_id=authority_role.id, is_demo=True)
        db.add(authority)
        db.flush()

    cats = {c.slug: c for c in db.query(Category).all()}
    depts = {d.slug: d for d in db.query(Department).all()}

    base_lat, base_lng = settings.DEFAULT_CENTER_LAT, settings.DEFAULT_CENTER_LNG

    # (title, description, category_slug, lat, lng, landmark, ward, severity, urgency)
    reports_def = [
        ("No drinking water since four days", "Entire lane has no supply; buying cans at Rs 40.", "water", 23.3620, 85.3325, "Near Hanuman Mandir", "Ward 4", 4, 4),
        ("Water tanker not reaching us", "Elderly people are suffering, please send tanker urgently.", "water", 23.3625, 85.3330, "Hindpiri main road", "Ward 4", 4, 5),
        ("Pipeline burst flooding street", "Muddy water everywhere since morning.", "water", 23.3618, 85.3318, "Opposite PHC gate", "Ward 4", 4, 4),
        ("Contaminated water smell", "Water smells like sewage, afraid of disease outbreak.", "water", 23.3622, 85.3328, "Ward 4 community tap", "Ward 4", 5, 4),
        ("Paani nahi aa raha hai", "Char din se paani band hai hamare ghar mein.", "water", 23.3627, 85.3322, "Hindpiri gali no 3", "Ward 4", 4, 4),
        ("School road full of potholes", "Children fall while cycling; two bikes slipped yesterday.", "roads", 23.3460, 85.3120, "Near Govt School gate", "Ward 7", 4, 4),
        ("Deep pothole near school", "Auto drivers avoid this stretch, very dangerous.", "roads", 23.3462, 85.3124, "School road junction", "Ward 7", 4, 4),
        ("Gaddha sadak mein bahut bada", "Roz accident ho raha hai wahan.", "roads", 23.3458, 85.3123, "Sadak near mandir", "Ward 7", 4, 3),
        ("Street light dead for weeks", "Whole stretch dark after 7pm, women feel unsafe.", "street_lighting", 23.3500, 85.3200, "Park lane", "Ward 8", 3, 3),
        ("Batti nahi jal rahi hai", "Do hafte se andhera hai gali mein.", "street_lighting", 23.3502, 85.3198, "Gali no 5", "Ward 8", 3, 3),
        ("Garbage not collected ten days", "Stray dogs spreading waste all over.", "garbage", 23.3400, 85.3050, "Market collection point", "Ward 3", 3, 3),
        ("Kachre ka dher badboo", "School ke bagal mein kachra pada hai.", "garbage", 23.3398, 85.3053, "Behind school", "Ward 3", 3, 3),
        ("Drain overflowing near clinic", "Mosquitoes increasing, dengue risk.", "drainage", 23.3560, 85.3400, "Doranda main chowk", "Ward 12", 4, 4),
        ("Naali jam hai", "Ganda paani sadak par aa gaya hai.", "drainage", 23.3558, 85.3403, "Clinic road", "Ward 12", 3, 3),
        ("Transformer sparking nightly", "Burnt smell; whole block power cuts.", "electricity", 23.3480, 85.3250, "Substation lane", "Ward 6", 4, 4),
        ("Live wire hanging low", "Very dangerous for children going to school.", "electricity", 23.3482, 85.3248, "Near anganwadi", "Ward 6", 5, 5),
        ("No doctor at dispensary three days", "Patients turned away without medicine.", "healthcare", 23.2905, 85.2140, "Chota Nagri sub-centre", "Village", 4, 4),
        ("Bus shelter completely broken", "No roof, elderly wait in rain.", "public_transport", 23.3430, 85.3100, "Bus stop main road", "Ward 2", 2, 2),
        ("Stray dog pack near playground", "Two children bitten this week.", "public_safety", 23.3410, 85.3150, "Playground road", "Ward 2", 4, 4),
        ("Public toilet unusable", "Doors broken, never cleaned.", "sanitation", 23.3445, 85.3070, "Station road", "Ward 2", 3, 3),
    ]

    created = 0
    from app.models.civic import Report

    for idx, (title, desc, cat_slug, lat, lng, lm, ward, sev, urg) in enumerate(reports_def):
        code_exists = db.query(Report).filter_by(is_demo=True).count() > 0
        person = citizens[idx % len(citizens)]
        rep = Report(
            title=title, description=desc,
            category_id=cats[cat_slug].id, subcategory=None, category_source="user",
            latitude=lat, longitude=lng, address_text=f"{lm}, Ranchi", landmark=lm,
            ward=ward, location_source="map", ai_severity=sev, ai_urgency=urg,
            ai_status="done", status="reported", is_demo=True,
            citizen_id=person.id,
        )
        from app.services.ids import next_code

        rep.code = next_code(db, "report")
        db.add(rep)
        db.flush()
        attach_report(db, rep)  # clusters + priority + notifications
        info = get_storage().save(
            io.BytesIO(_demo_png(idx, CATEGORY_TINT.get(cat_slug, (99, 102, 241)))),
            f"demo-{idx}.png", "image/png",
        )
        db.add(ReportMedia(
            report_id=rep.id, kind="image", storage_key=info["key"],
            mime_type="image/png", size_bytes=info["size_bytes"], sha256=info["sha256"],
            width=320, height=200, processing_status="skipped",
        ))
        created += 1

    print(f"Demo reports inserted & clustered: {created}")

    # Facilities
    fac_count = db.query(Facility).filter_by(is_demo=True).count()
    if fac_count == 0:
        for name, ftype, lat, lng, level, note in FACILITIES:
            db.add(Facility(name=name, facility_type=ftype, latitude=lat, longitude=lng,
                            district="Ranchi", service_level=level, capacity_note=note, is_demo=True))
        db.commit()

    gaps_now = compute_gaps(db)
    print(f"Accessibility gap rows computed: {gaps_now}")

    # ----- Demo action & verification lifecycle -----
    from datetime import timedelta

    from app.models.work import Action, ActionResource, EvidenceMedia, ResolutionEvidence, Verification
    from app.services.ids import next_code
    from app.services.priority import apply_priority

    admin = db.query(User).filter_by(
        email=settings.ADMIN_EMAIL or "admin@sahayata.gov.in"
    ).first()
    clusters_now = db.query(ProblemCluster).filter_by(is_demo=True).all()
    water_cluster = max(clusters_now, key=lambda c: c.report_count, default=None)
    garbage_cluster = next(
        (c for c in clusters_now if c.title.lower().startswith("garbage")), None
    )
    light_cluster = next(
        (c for c in clusters_now if "lighting" in c.title.lower()), None
    )

    def _mk_action(cluster, dept_slug, team, resources, cost, days, status, notes,
                   started_days_ago=0):
        a = Action(
            code=next_code(db, "action"), cluster_id=cluster.id,
            department_id=depts[dept_slug].id, officer_id=authority.id,
            team_name=team, resources_needed=resources, estimated_cost=cost,
            deadline=utcnow() + timedelta(days=days),
            priority_level_snapshot=cluster.priority_level,
            priority_score_snapshot=cluster.priority_score,
            status=status, notes=notes, created_by_id=admin.id if admin else None,
        )
        if started_days_ago:
            a.started_at = utcnow() - timedelta(days=started_days_ago)
        db.add(a)
        db.flush()
        return a

    if water_cluster and water_cluster.report_count >= 3:
        a1 = _mk_action(water_cluster, "water", "Ward-4 Water Supply Team",
                        "Tanker x2; pipeline joints; valves", 45000.0, 0, "closed",
                        "Leaking joint replaced at Hanuman Mandir junction; pressure normal.",
                        started_days_ago=2)
        a1.completed_at = utcnow() - timedelta(hours=20)
        a1.closed_at = utcnow() - timedelta(hours=6)
        ev = ResolutionEvidence(
            action_id=a1.id, latitude=water_cluster.latitude, longitude=water_cluster.longitude,
            submitted_by_id=authority.id,
            note="Joint replaced and road restored. Supply monitored for 12 hours.",
            completion_details="New 90mm pipe section installed; two tankers arranged during repair window.",
        )
        db.add(ev)
        db.flush()
        einfo = get_storage().save(io.BytesIO(_demo_png(991, CATEGORY_TINT["water"])), "demo-evidence.png", "image/png")
        m_ev = ReportMedia(
            report_id=None, kind="image", storage_key=einfo["key"], mime_type="image/png",
            size_bytes=einfo["size_bytes"], sha256=einfo["sha256"],
            width=320, height=200, processing_status="skipped", created_by_role="authority",
        )
        db.add(m_ev)
        db.flush()
        db.add(EvidenceMedia(evidence_id=ev.id, media_id=m_ev.id))
        db.add(Verification(cluster_id=water_cluster.id, action_id=a1.id,
                            citizen_id=citizens[0].id, verdict="yes",
                            comment="Water is back since yesterday evening, thank you."))
        water_cluster.status = "closed"
        water_cluster.resolved_at = utcnow() - timedelta(hours=6)
        apply_priority(db, water_cluster)

    if garbage_cluster:
        a2 = _mk_action(garbage_cluster, "water", "Sanitation Squad 3",
                        "Tipper truck x1; workers x4", 12000.0, 1, "in_progress",
                        "Clearing accumulated waste; second pass tomorrow morning.",
                        started_days_ago=1)
        db.add(ActionResource(action_id=a2.id, resource_type="Tipper truck",
                              quantity=1, unit_cost=8000.0))
        garbage_cluster.status = "assigned"

    if light_cluster:
        _mk_action(light_cluster, "electricity", "Streetlight Maintenance Cell",
                   "LED fitting x4; ladder; electrician x2", 18000.0, 3, "assigned",
                   "Awaiting pole access permission from ward office.")

    db.commit()
    print("Demo actions & verifications seeded.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed SAHAYATA database")
    parser.add_argument("--demo", action="store_true", help="load clearly-flagged demo data")
    parser.add_argument("--reset-demo", action="store_true", help="delete existing demo rows first")
    args = parser.parse_args()

    create_all()
    with SessionLocal() as session:
        seed_base(session)
        if args.reset_demo:
            from app.models.civic import ClusterReport, ProblemCluster, Report, ReportMedia
            from app.models.geo import AccessibilityGap, Facility
            from app.models.system import AuditLog, Notification, SimulationParameter
            from app.models.user import RefreshToken
            from app.models.work import Action, ActionResource, EvidenceMedia, ResolutionEvidence, Verification

            demo_clusters = session.query(ProblemCluster).filter_by(is_demo=True).all()
            demo_reports = session.query(Report).filter_by(is_demo=True).all()
            cluster_ids = [c.id for c in demo_clusters]
            report_ids = [r.id for r in demo_reports]

            action_ids = [a.id for a in session.query(Action).filter(Action.cluster_id.in_(cluster_ids)).all()]
            ev_ids = [e.id for e in session.query(ResolutionEvidence).filter(ResolutionEvidence.action_id.in_(action_ids)).all()]

            def bulk_del(model, col, values):
                if values:
                    session.query(model).filter(col.in_(values)).delete(synchronize_session=False)

            session.query(Verification).filter(Verification.cluster_id.in_(cluster_ids)).delete(synchronize_session=False)
            bulk_del(EvidenceMedia, EvidenceMedia.evidence_id, ev_ids)
            bulk_del(ResolutionEvidence, ResolutionEvidence.id, ev_ids)
            bulk_del(ActionResource, ActionResource.action_id, action_ids)
            session.query(Action).filter(Action.id.in_(action_ids)).delete(synchronize_session=False)
            session.query(ClusterReport).filter(ClusterReport.report_id.in_(report_ids)).delete(synchronize_session=False)
            bulk_del(ReportMedia, ReportMedia.report_id, report_ids)
            session.query(Notification).filter(Notification.recipient_id.in_(
                [u.id for u in session.query(User).filter_by(is_demo=True).all()]
            )).delete(synchronize_session=False)
            demo_user_ids = [u.id for u in session.query(User).filter_by(is_demo=True).all()]
            bulk_del(RefreshToken, RefreshToken.user_id, demo_user_ids)
            session.query(AuditLog).filter(AuditLog.actor_id.in_(demo_user_ids)).delete(synchronize_session=False)
            session.query(SimulationParameter).filter(
                SimulationParameter.updated_by_id.in_(demo_user_ids)
            ).update({SimulationParameter.updated_by_id: None}, synchronize_session=False)
            # derived data – recomputed after re-seed
            session.query(AccessibilityGap).delete(synchronize_session=False)
            session.query(Facility).filter_by(is_demo=True).delete(synchronize_session=False)
            # reports <-> clusters are circularly linked; break the cycle first
            session.query(Report).filter(Report.id.in_(report_ids)).update(
                {Report.cluster_id: None}, synchronize_session=False
            )
            session.query(ProblemCluster).filter(ProblemCluster.id.in_(cluster_ids)).delete(synchronize_session=False)
            session.query(Report).filter(Report.id.in_(report_ids)).delete(synchronize_session=False)
            # users last – everything above references them
            session.query(User).filter_by(is_demo=True).delete(synchronize_session=False)
            session.commit()
            print(f"Demo data wiped: {len(demo_reports)} reports, {len(demo_clusters)} clusters.")
        if args.demo:
            seed_demo(session)
            print("DEMO data loaded (all rows flagged is_demo=True).")
