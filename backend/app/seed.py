"""Idempotent demo data.

    python -m app.seed           # create missing rows, skip existing ones
    python -m app.seed --reset   # wipe all tables first (re-run the demo from scratch)
"""
import argparse
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.init_db import create_tables
from app.models import OPEN_CASE_STATUSES, Camera, Case, Scan, Tenant, User
from app.security import hash_password

ALPHA_CASE_VIN = "1FTFW1E51NFA12345"
ALPHA_CASE_PLATE = "7XYZ123"
BRAVO_NEW_VIN = "5NPE34AF9KH123456"  # deliberately has no case: scanning it exercises the new-case flow

CREDENTIALS = [
    ("hemanth", "Hemanth@123", "platform admin"),
    ("alpha_agent", "Alpha@123", "Alpha Recovery"),
    ("bravo_agent", "Bravo@123", "Bravo Recovery"),
]

# (days ago, latitude, longitude, place) - older sightings by Alpha's own truck around Atlanta.
ALPHA_TRAIL = [
    (13, 33.7838, -84.3830, "midtown"),
    (8, 33.7748, -84.2963, "decatur"),
    (3, 33.9526, -84.5499, "marietta"),
]


def seed(db: Session) -> None:
    # The first admin has to be bootstrapped here; after that, admins create everything via the API.
    _user(db, "hemanth", "Hemanth@123", None, role="admin")

    alpha = _tenant(db, "Alpha Recovery")
    bravo = _tenant(db, "Bravo Recovery")
    _camera(db, "cam_1001", alpha, "Alpha Truck 1")
    _camera(db, "cam_2050", bravo, "Bravo Truck 1")
    alpha_agent = _user(db, "alpha_agent", "Alpha@123", alpha)
    _user(db, "bravo_agent", "Bravo@123", bravo)

    case = _alpha_active_case(db, alpha, alpha_agent)
    _alpha_trail_scans(db, alpha, case)
    db.commit()


def _tenant(db: Session, name: str) -> Tenant:
    tenant = db.scalar(select(Tenant).where(Tenant.name == name))
    if tenant is None:
        tenant = Tenant(name=name)
        db.add(tenant)
        db.flush()
    return tenant


def _camera(db: Session, camera_id: str, tenant: Tenant, label: str) -> Camera:
    camera = db.get(Camera, camera_id)
    if camera is None:
        camera = Camera(id=camera_id, tenant_id=tenant.id, label=label)
        db.add(camera)
        db.flush()
    return camera


def _user(db: Session, username: str, password: str, tenant: Tenant | None, role: str = "staff") -> User:
    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        user = User(
            tenant_id=tenant.id if tenant else None,
            username=username,
            password_hash=hash_password(password),
            role=role,
        )
        db.add(user)
        db.flush()
    return user


def _alpha_active_case(db: Session, alpha: Tenant, agent: User) -> Case | None:
    existing = db.scalar(
        select(Case).where(Case.vin == ALPHA_CASE_VIN, Case.status.in_(OPEN_CASE_STATUSES))
    )
    if existing is not None:
        if existing.tenant_id != alpha.id:
            print(f"Note: an open case for {ALPHA_CASE_VIN} exists outside Alpha; leaving it alone.")
            return None
        return existing

    opened = datetime.now(UTC) - timedelta(days=14)
    case = Case(
        vin=ALPHA_CASE_VIN,
        status="active",
        tenant_id=alpha.id,
        origin_tenant_id=alpha.id,
        assigned_user_id=agent.id,
        created_at=opened,
        claimed_at=opened,
    )
    db.add(case)
    db.flush()
    return case


def _alpha_trail_scans(db: Session, alpha: Tenant, case: Case | None) -> None:
    now = datetime.now(UTC)
    for days_ago, lat, lon, place in ALPHA_TRAIL:
        # A fixed image URL identifies each seed scan, so re-runs don't duplicate them.
        image_url = f"https://example.com/scans/seed_alpha_{place}.jpg"
        if db.scalar(select(Scan.id).where(Scan.image_url == image_url)):
            continue
        db.add(
            Scan(
                tenant_id=alpha.id,
                camera_id="cam_1001",
                plate=ALPHA_CASE_PLATE,
                vin=ALPHA_CASE_VIN,
                latitude=lat,
                longitude=lon,
                scanned_at=now - timedelta(days=days_ago, hours=days_ago % 5),
                image_url=image_url,
                matched_case_id=case.id if case else None,
            )
        )
    db.flush()


ID_STARTS = {"tenants": 1001, "users": 101}


def reset(db: Session) -> None:
    db.execute(text("TRUNCATE scans, cases, cameras, users, tenants RESTART IDENTITY CASCADE"))
    # Also covers databases created before the models declared these start values.
    for table, start in ID_STARTS.items():
        db.execute(text(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), {start}, false)"))
    db.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo data.")
    parser.add_argument("--reset", action="store_true", help="delete ALL rows before seeding")
    args = parser.parse_args()

    create_tables()
    with SessionLocal() as db:
        if args.reset:
            reset(db)
            print("All tables emptied.")
        seed(db)

    print("Seed complete. Demo logins:")
    for username, password, tenant in CREDENTIALS:
        print(f"  {username:<12} / {password:<12} ({tenant})")
    print(f"Alpha has an active case for VIN {ALPHA_CASE_VIN}; VIN {BRAVO_NEW_VIN} has no case yet.")


if __name__ == "__main__":
    main()
