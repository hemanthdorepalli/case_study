# Plate Scan & Case Matching Service

A multi-tenant service for vehicle-recovery agencies. License Plate Recognition (LPR) cameras post every scan to
a webhook. Each scan is matched to the agency's open repossession case, or it opens a new **pending** case that any
agency can claim. Agency staff use a small React dashboard to see their cases, follow a vehicle's location trail,
and claim pending cases.

- **Backend:** FastAPI, SQLAlchemy 2.0 (sync), psycopg 3, PostgreSQL, Pydantic v2, PyJWT and bcrypt (`backend/`)
- **Frontend:** React + Vite (plain JavaScript), react-router-dom, fetch (`frontend/`)
- **Design notes:** ER diagram, tenancy model, notifications and the AWS plan are in [DESIGN.md](DESIGN.md)

```
backend/
  app/
    config.py  database.py  models.py  init_db.py  main.py
    schemas.py          Pydantic request/response models
    security.py         bcrypt, JWT, get_current_user
    services/
      eligibility.py    HTTP client for the partner-network check
      scan_service.py   ingest logic (existing-case / new-case flows)
      case_service.py   case queries + claim; ALL case tenant-scoping lives here
    routers/            auth.py, scans.py, cases.py, mock.py
    seed.py             demo data
  tests/                pytest suite (uses the separate plate_scan_test DB)
frontend/               React dashboard
scripts/                demo_scans.sh / demo_scans.ps1 (simulate cameras)
```

## Prerequisites

- Python 3.11+
- PostgreSQL 14+ running and reachable with the credentials in `DATABASE_URL`. The user needs permission to
  create databases (the default `postgres` superuser has it).
- Node.js 18+ and npm

You don't need to create any databases or tables by hand. `plate_scan` and its tables are created automatically when
the API starts, when you run `python -m app.seed`, or with `python -m app.init_db`. The tests create
`plate_scan_test` the same way.

## Setup and run

### 1. Backend

**Mac / Linux**
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"   # paste the output into JWT_SECRET_KEY in .env
python -m app.seed
uvicorn app.main:app --reload --reload-dir app
```

**Windows (PowerShell)**
```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"   # paste the output into JWT_SECRET_KEY in .env
python -m app.seed
uvicorn app.main:app --reload --reload-dir app
```

- The API runs at http://localhost:8000, with interactive docs at http://localhost:8000/docs.
- `--reload-dir app` limits the auto-reloader to source code. Without it, uvicorn also watches `venv/`, which lives
  inside `backend/`.
- The app refuses to start if `JWT_SECRET_KEY` is missing or shorter than 32 characters.

`backend/.env` settings (see `.env.example`):

| Variable | Default / example | Notes |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://postgres:postgres@localhost:5432/plate_scan` | A plain `postgresql://` URL is accepted too and switched to psycopg 3. |
| `JWT_SECRET_KEY` | none (required) | 64-char hex from `secrets.token_hex(32)`. |
| `JWT_ALGORITHM` | `HS256` | |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | |
| `MOCK_ELIGIBILITY_URL` | `http://localhost:8000/mock/partner-network/eligibility` | Must point at the running API's port. |
| `ELIGIBILITY_TIMEOUT_SECONDS` | `3` | On timeout or error, the VIN is treated as "not eligible". |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated list. |

### 2. Seed data

```bash
python -m app.seed           # idempotent: creates whatever is missing, skips what exists
python -m app.seed --reset   # empties ALL tables first, so the demo can be replayed from scratch
```

| Username | Password | Role | Tenant | Camera |
|---|---|---|---|---|
| `hemanth` | `Hemanth@123` | platform admin | none | – |
| `alpha_agent` | `Alpha@123` | staff | Alpha Recovery | `cam_1001` (Alpha Truck 1) |
| `bravo_agent` | `Bravo@123` | staff | Bravo Recovery | `cam_2050` (Bravo Truck 1) |

The seed bootstraps the first admin. After that, the admin creates tenants, staff users and cameras from the
dashboard's **Admin** page or the `/api/v1/admin/*` API.

- Alpha has an **active** case for VIN `1FTFW1E51NFA12345`, assigned to `alpha_agent`, with 3 earlier Atlanta-area
  sightings from `cam_1001`.
- VIN `5NPE34AF9KH123456` has **no** case, so scanning it exercises the new-case flow.

### 3. Frontend

```bash
cd frontend
cp .env.example .env          # Windows: Copy-Item .env.example .env   (VITE_API_URL=http://localhost:8000)
npm install
npm run dev                   # http://localhost:5173
```

Staff users see these pages:
- **My Cases:** your tenant's cases, with a status filter. Click a row to open it.
- **Case detail:** case info and the location trail, with "View on map" links to OpenStreetMap.
- **Claimable Cases:** every `pending_claim` case in the network, each with a **Claim** button.

The platform admin (`hemanth`) sees only the **Admin** page, which lists tenants, staff users and cameras and has a
form to create each one.

The dashboard never calls `POST /api/v1/scans`; only cameras use that endpoint.

### 4. Tests

```bash
cd backend
pytest              # with the venv activated
```

The tests use a separate database, `plate_scan_test`, on the same server as `DATABASE_URL` (override it with
`TEST_DATABASE_URL`). The fixtures truncate and re-seed every table before each test, and they refuse to run against
a database whose name doesn't end in `_test`. The test schema is dropped and recreated at the start of each run, so it
always matches the models. The partner-eligibility dependency is overridden with an in-process fake. There are 37
tests covering:
- auth
- the four ingest flows, including a real two-thread race on the same new VIN
- claim, the trail and tenant isolation
- admin permissions

## Demo walkthrough (curl)

Start the API and run `python -m app.seed --reset`. The commands below use bash (Mac, Linux, or Git Bash/WSL on
Windows). On Windows PowerShell, `.\scripts\demo_scans.ps1` sends the same scans as steps 1–2 and more.

```bash
API=http://localhost:8000
token() { curl -s -X POST $API/api/v1/auth/login -H 'Content-Type: application/json' \
  -d "{\"username\":\"$1\",\"password\":\"$2\"}" | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])"; }
ALPHA=$(token alpha_agent Alpha@123)
BRAVO=$(token bravo_agent Bravo@123)

# 1) Existing-case flow: Alpha's camera sees the VIN of Alpha's active case
curl -s -X POST $API/api/v1/scans -H 'Content-Type: application/json' -d '{"camera_id":"cam_1001","plate":"7XYZ123","vin":"1FTFW1E51NFA12345","latitude":33.7490,"longitude":-84.3880,"scanned_at":"2026-09-01T14:32:00Z","image_url":"https://example.com/scans/img_88213.jpg"}'
# -> {"scan_id":4,"tenant_id":1,"flow":"existing_case","case_id":1}

# 2) New-case flow: Bravo's camera sees a VIN nobody has a case for -> pending_claim case, owned by nobody
curl -s -X POST $API/api/v1/scans -H 'Content-Type: application/json' -d '{"camera_id":"cam_2050","plate":"8ABC456","vin":"5NPE34AF9KH123456","latitude":33.8490,"longitude":-84.3733,"scanned_at":"2026-09-01T15:10:00Z","image_url":"https://example.com/scans/img_88214.jpg"}'
# -> {"scan_id":5,"tenant_id":2,"flow":"new_case_created","case_id":2}

# 3) Every tenant sees pending cases
curl -s "$API/api/v1/cases?status=pending_claim" -H "Authorization: Bearer $ALPHA"

# 4) Cross-tenant claim: Alpha claims the case that Bravo's camera found
curl -s -X POST $API/api/v1/cases/2/claim -H "Authorization: Bearer $ALPHA"
# -> {"id":2,...,"status":"active","is_mine":true,...}

# 5) Bravo is too late
curl -s -X POST $API/api/v1/cases/2/claim -H "Authorization: Bearer $BRAVO"
# -> 409 {"detail":"Case is not claimable (current status: active)"}

# 6) Alpha's trail for case 2 includes Bravo's sighting, with the location only
curl -s $API/api/v1/cases/2/scans -H "Authorization: Bearer $ALPHA"
# -> [{"source":"network","plate":"8ABC456","vin":"5NPE34AF9KH123456","latitude":33.849,"longitude":-84.3733,"scanned_at":"..."}]

# 7) Isolation: Bravo can't see or touch Alpha's case 1 (404, same as a case that doesn't exist)
curl -s "$API/api/v1/cases" -H "Authorization: Bearer $BRAVO"
curl -s -w ' %{http_code}\n' $API/api/v1/cases/1/scans -H "Authorization: Bearer $BRAVO"

# 8) Not eligible (VIN ends in 0): the scan is stored, but no case is opened
curl -s -X POST $API/api/v1/scans -H 'Content-Type: application/json' -d '{"camera_id":"cam_2050","plate":"9TRK000","vin":"1HGCM82633A123450","latitude":33.76,"longitude":-84.39,"scanned_at":"2026-09-01T16:00:00Z"}'
# -> {"scan_id":6,"tenant_id":2,"flow":"not_eligible","case_id":null}
```

`./scripts/demo_scans.sh` (or `.\scripts\demo_scans.ps1`) sends a full set of sample scans: existing case, new
case, duplicate, a network sighting of Alpha's VIN, not eligible, and an unknown camera.

## API

| Method & path | Auth | Purpose |
|---|---|---|
| `POST /api/v1/auth/login` | – | `{username, password}` → `{access_token, token_type, user}` |
| `GET /api/v1/auth/me` | Bearer | Current user and tenant (`tenant_id`/`tenant_name` are `null` for the admin) |
| `POST /api/v1/scans` | – (camera webhook) | Ingest a scan → `201 {scan_id, tenant_id, flow, case_id}` |
| `GET /api/v1/cases?status=` | Staff | Own cases (any status) plus all `pending_claim` cases, newest first |
| `GET /api/v1/cases/{id}` | Staff | One visible case (added for the dashboard's detail page) |
| `POST /api/v1/cases/{id}/claim` | Staff | Atomically claim a pending case |
| `GET /api/v1/cases/{id}/scans` | Staff | Location trail (owner only); other tenants' sightings are redacted |
| `GET`, `POST /api/v1/admin/tenants` | Admin | List tenants (with user and camera counts) / create `{name}` |
| `GET`, `POST /api/v1/admin/users` | Admin | List users (`?tenant_id=`) / create a staff user `{username, password, tenant_id}` |
| `GET`, `POST /api/v1/admin/cameras` | Admin | List cameras (`?tenant_id=`) / register `{id, tenant_id, label}` |
| `POST /mock/partner-network/eligibility` | – | Mock partner: `still_eligible_for_repo = VIN doesn't end in "0"` |

`flow` is one of:
- `existing_case`: this tenant has an active case for the VIN, so the scan is linked to it.
- `already_open_elsewhere`: the VIN already has a pending case, or another tenant's active case. Its id and owner
  are not revealed.
- `new_case_created`: no open case existed and the partner says the VIN is eligible, so a `pending_claim` case was
  opened.
- `not_eligible`: no open case existed and the partner says no, or couldn't be reached.

Errors always use the shape `{"detail": "..."}`:
- 401: missing or invalid token
- 403: inactive camera, or the wrong role (an admin calling a case endpoint, or staff calling an admin endpoint)
- 404: unknown camera, a case you can't see, or an unknown tenant in an admin request
- 409: the case can't be claimed, or the tenant name, username or camera id already exists
- 422: validation error

## Design decisions and assumptions

- **Where the tenant comes from.** Ingest takes the tenant from the registered camera. API calls take it from the
  user row loaded from the DB on every request. The JWT's `tenant_id`/`role` claims and any `tenant_id` in a request
  body are ignored, and there are tests for both.
- **Sharing sighting locations.** A case owner's trail includes every scan of the VIN, from any tenant's cameras.
  Other tenants' scans show only the location, time, plate and VIN. The camera id, image URL and tenant are hidden.
  The reasoning: sharing *where* the vehicle was serves the case owner, while camera identity and fleet coverage stay
  tenant-private. Pending cases have no trail until someone claims them.
- **404 rather than 403** for other tenants' cases, so a caller can't tell "exists but isn't yours" from "doesn't
  exist".
- **Platform admin vs staff.** An `admin` runs the platform and belongs to no tenant. A `staff` user always belongs to
  exactly one tenant. The `ck_users_role_matches_tenant` CHECK constraint enforces this in the database, which is why
  `users.tenant_id` is nullable.
  - Admins can create tenants, staff users and cameras, but get 403 on every case endpoint, so they never see
    agency case or scan data.
  - The admin API only creates `staff` users and ignores any `role` in the body; new admins are added by the seed or
    the DB.
  - Admin endpoints take the target `tenant_id` from the request body. That's deliberate: choosing which agency to
    manage is the admin's job. Staff endpoints still take the tenant only from the DB user.
- **Passwords** for new users must be 8–72 bytes. bcrypt ignores everything after 72 bytes, so longer passwords are
  rejected rather than silently truncated.
- **Claim conflicts.** A failed claim returns 409 to the owning tenant and to the *originating* tenant, whose camera
  opened the case and who therefore already knows it exists. They learn only its status, never the new owner.
  Everyone else gets 404. This satisfies both "re-claim → 409" and "other tenant → 404".
- **Eligibility fails closed.** If the partner is unreachable, times out, or returns a malformed response, the VIN is
  treated as not eligible and a warning is logged. The scan is still stored.
- **What `scan_count` counts.** For your own cases it's every sighting, matching the trail. For pending cases it's
  only your own cameras' scans, because network sightings aren't visible before a claim.
- **`matched_case_id`** is set only in the existing-case flow, as specified. The trail is built from the VIN, so it
  also includes scans from before the case was opened.
- **Validation.** VINs are 17 characters, uppercased, letters and digits only, with no I, O or Q (no check-digit
  validation). Plates are trimmed, uppercased and 1–16 characters. `scanned_at` must include a timezone. Unknown
  payload fields are ignored.
- **IDs.** Integer ids are used for simplicity. Camera ids are the external device ids (for example `cam_1001`).
- **Schema changes** happen through `create_all` on startup; there are no migrations yet. `create_all` doesn't alter
  existing tables. A database created before the admin role was added needs:
  ```sql
  ALTER TABLE users ALTER COLUMN tenant_id DROP NOT NULL;
  ALTER TABLE users ADD CONSTRAINT ck_users_role_matches_tenant CHECK (
    (role = 'admin' AND tenant_id IS NULL) OR (role = 'staff' AND tenant_id IS NOT NULL));
  ```

## What is simplified or incomplete

- The camera webhook is unauthenticated, as the brief specifies. The only protection is that the camera must be
  registered and active.
- The eligibility HTTP call runs synchronously inside the ingest request and its DB transaction, for up to
  `ELIGIBILITY_TIMEOUT_SECONDS`.
- Tokens:
  - access tokens only: no refresh tokens or revocation
  - the dashboard keeps the token in `localStorage`
  - no rate limiting on login
- Missing endpoints and UI:
  - closing or reassigning cases
  - deactivating, editing or deleting users, cameras and tenants (the admin can only create them)
  - password reset
  - a tenant-level admin role
- No pagination on case lists or trails.
- No map view: the dashboard links to OpenStreetMap instead.
- No Alembic migrations.
- No frontend tests: the UI was checked by hand and with a headless-browser script.
- The frontend uses Vite 6 and React Router 6 so it keeps working on Node 18.

## What I'd do next

1. Authenticate cameras with a per-camera API key or HMAC signature, and add an idempotency key so camera retries
   don't create duplicate scans.
2. Move ingest behind a queue (API Gateway → SQS → worker). Do the eligibility check outside the DB transaction, with
   retries and short-lived caching.
3. Add Alembic migrations, and a CI pipeline that runs the tests against a Postgres service container.
4. Add Postgres row-level security as defense in depth for tenant scoping.
5. Add case lifecycle endpoints (close, reassign) with role checks and an audit log, and paginate lists and trails.
6. Implement the notifications described in DESIGN.md: new pending case and new sighting on my case, delivered to
   the dashboard over WebSocket.
7. Dashboard: a Leaflet map of the trail, an httpOnly-cookie session instead of `localStorage`, and Vitest +
   Playwright tests.

## Troubleshooting

- **`JWT_SECRET_KEY is not set`:** create `backend/.env` from `.env.example` and set a secret.
- **`password authentication failed`:** fix the user and password in `DATABASE_URL`.
- **`no pg_hba.conf entry for host …`:** PostgreSQL runs on Windows but the backend runs in WSL. Add a line such as
  `host all all 172.16.0.0/12 scram-sha-256` to `pg_hba.conf`, set `listen_addresses = '*'`, and restart PostgreSQL.
  Alternatively, run PostgreSQL inside WSL.
- **Every new VIN comes back `not_eligible`:** `MOCK_ELIGIBILITY_URL` doesn't point at the port the API is running
  on. Check the warning in the API log.
- **CORS error in the browser:** open the dashboard at http://localhost:5173, or add your origin to `CORS_ORIGINS`.
