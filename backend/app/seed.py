"""Idempotent demo data.

    python -m app.seed           # create missing rows, skip existing ones
    python -m app.seed --reset   # wipe all tables first (re-run the demo from scratch)

Each scenario below shows one concept in the dashboard:

  A. Alpha's active case      - trail mixes "own" (Alpha camera) and "network" (Bravo camera) sightings
  B. Bravo's active case      - invisible to Alpha; Bravo sees Alpha's sighting of it as "network"
  C. Pending case             - found by Alpha's camera, owned by nobody, claimable by any agency
  D. Alpha's closed case      - finished work still shows in Alpha's "My Cases"
  E. Not-eligible scan        - stored, but no case (partner said "not eligible")
  F. 5NPE34AF9KH123456        - no data at all: scan it from cam_2050 to watch the new-case flow live
"""
import argparse
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.init_db import create_tables
from app.models import Camera, Case, Scan, Tenant, User
from app.security import hash_password

ALPHA_CASE_VIN = "1FTFW1E51NFA12345"
BRAVO_CASE_VIN = "2T1BURHE5JC123456"
PENDING_VIN = "3FA6P0H75HR123457"
CLOSED_VIN = "1HGCM82633A654321"
NOT_ELIGIBLE_VIN = "1HGCM82633A123450"  # ends in 0 -> the mock partner says "not eligible"
BRAVO_NEW_VIN = "5NPE34AF9KH123456"  # deliberately untouched: scanning it exercises the new-case flow

CREDENTIALS = [
    ("hemanth", "Hemanth@123", "platform admin"),
    ("alpha_agent", "Alpha@123", "Alpha Recovery"),
    ("alpha_agent2", "Alpha@123", "Alpha Recovery (same team as alpha_agent)"),
    ("bravo_agent", "Bravo@123", "Bravo Recovery"),
]

# Scenario scans: (key, camera, plate, vin, days ago, latitude, longitude, place).
# The key becomes a fixed image URL, which is how re-runs recognise scans that already exist.
SCANS = [
    # A. Alpha's case: three sightings by Alpha's own truck + one by Bravo's truck.
    ("a1", "cam_1001", "7XYZ123", ALPHA_CASE_VIN, 13, 33.7838, -84.3830, "Midtown"),
    ("a2", "cam_1001", "7XYZ123", ALPHA_CASE_VIN, 8, 33.7748, -84.2963, "Decatur"),
    ("a3", "cam_1001", "7XYZ123", ALPHA_CASE_VIN, 3, 33.9526, -84.5499, "Marietta"),
    ("a4", "cam_2050", "7XYZ123", ALPHA_CASE_VIN, 1, 33.8470, -84.3733, "Buckhead"),
    # B. Bravo's case: two sightings by Bravo's truck + one by Alpha's truck.
    ("b1", "cam_2050", "4BRV789", BRAVO_CASE_VIN, 10, 33.6407, -84.4277, "Airport"),
    ("b2", "cam_2050", "4BRV789", BRAVO_CASE_VIN, 6, 33.7537, -84.3863, "Downtown"),
    ("b3", "cam_1001", "4BRV789", BRAVO_CASE_VIN, 2, 33.8823, -84.4655, "Smyrna"),
    # C. The sighting that opened the pending case.
    ("c1", "cam_1001", "9PND321", PENDING_VIN, 1, 33.7676, -84.4206, "West End"),
    # D. Old sighting of the car in Alpha's closed case.
    ("d1", "cam_1001", "2CLS654", CLOSED_VIN, 30, 33.7701, -84.3900, "Old Fourth Ward"),
    # E. Scanned, but the partner said "not eligible": stored with no case.
    ("e1", "cam_2050", "8NOP000", NOT_ELIGIBLE_VIN, 4, 33.7900, -84.3200, "Druid Hills"),
]


def seed(db: Session) -> None:
    # The first admin has to be bootstrapped here; after that, admins create everything via the API.
    _user(db, "hemanth", "Hemanth@123", None, role="admin")

    alpha = _tenant(db, "Alpha Recovery")
    bravo = _tenant(db, "Bravo Recovery")
    _camera(db, "cam_1001", alpha, "Alpha Truck 1")
    _camera(db, "cam_2050", bravo, "Bravo Truck 1")
    alpha_agent = _user(db, "alpha_agent", "Alpha@123", alpha)
    _user(db, "alpha_agent2", "Alpha@123", alpha)
    bravo_agent = _user(db, "bravo_agent", "Bravo@123", bravo)

    cases = {
        ALPHA_CASE_VIN: _case(db, ALPHA_CASE_VIN, "active", owner=alpha, origin=alpha, agent=alpha_agent, days_ago=14),
        BRAVO_CASE_VIN: _case(db, BRAVO_CASE_VIN, "active", owner=bravo, origin=bravo, agent=bravo_agent, days_ago=12),
        PENDING_VIN: _case(db, PENDING_VIN, "pending_claim", owner=None, origin=alpha, agent=None, days_ago=1),
        CLOSED_VIN: _case(db, CLOSED_VIN, "closed", owner=alpha, origin=alpha, agent=alpha_agent, days_ago=40),
    }
    cameras = {camera.id: camera for camera in db.scalars(select(Camera))}
    for scan in SCANS:
        _scan(db, cameras, cases, *scan)
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


def _case(
    db: Session,
    vin: str,
    status: str,
    *,
    owner: Tenant | None,
    origin: Tenant,
    agent: User | None,
    days_ago: int,
) -> Case:
    existing = db.scalar(select(Case).where(Case.vin == vin, Case.status == status))
    if existing is not None:
        return existing

    opened = datetime.now(UTC) - timedelta(days=days_ago)
    case = Case(
        vin=vin,
        status=status,
        tenant_id=owner.id if owner else None,  # pending cases belong to nobody
        origin_tenant_id=origin.id,
        assigned_user_id=agent.id if agent else None,
        created_at=opened,
        claimed_at=opened if owner else None,
        closed_at=opened + timedelta(days=5) if status == "closed" else None,
    )
    db.add(case)
    db.flush()
    return case


def _scan(
    db: Session,
    cameras: dict[str, Camera],
    cases: dict[str, Case],
    key: str,
    camera_id: str,
    plate: str,
    vin: str,
    days_ago: int,
    lat: float,
    lon: float,
    place: str,
) -> None:
    image_url = f"https://example.com/scans/seed_{key}_{place.lower().replace(' ', '_')}.jpg"
    if db.scalar(select(Scan.id).where(Scan.image_url == image_url)):
        return

    camera = cameras[camera_id]
    case = cases.get(vin)
    # Same rule as real ingest: a scan is linked only to its own tenant's active case.
    matched = case if case and case.status == "active" and case.tenant_id == camera.tenant_id else None
    db.add(
        Scan(
            tenant_id=camera.tenant_id,
            camera_id=camera.id,
            plate=plate,
            vin=vin,
            latitude=lat,
            longitude=lon,
            scanned_at=datetime.now(UTC) - timedelta(days=days_ago, hours=days_ago % 5),
            image_url=image_url,
            matched_case_id=matched.id if matched else None,
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
        print(f"  {username:<13} / {password:<12} {tenant}")
    print(f"Scan {BRAVO_NEW_VIN} from cam_2050 to watch the new-case flow.")


if __name__ == "__main__":
    main()
