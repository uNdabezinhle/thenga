# Northbound / Reka

Outdoor gear commerce platform built from the foundation docs in [`docs/`](docs/) and the UX in [`northbound-prototype.html`](northbound-prototype.html).

| Layer | Stack |
|---|---|
| API | Django 5 + Django REST Framework (`/api/v1/`) |
| Auth | JWT (simplejwt) with rotating refresh, MFA pre-auth tokens |
| Data | PostgreSQL (Docker) or SQLite (local zero-config) |
| Client | Northbound web UI (prototype design, live API) |
| Money | Decimal pricing service (ADR-0009) |

## Quick start (local, SQLite)

Requires **Python 3.12+** (3.11 also fine).

```powershell
# Windows
.\scripts\dev.ps1 setup
.\scripts\dev.ps1 run
```

```bash
# macOS / Linux
./scripts/dev.sh setup
./scripts/dev.sh run
```

Or manually:

```bash
cd backend && python -m venv .venv && source .venv/bin/activate   # or .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate && python manage.py seed_northbound
python manage.py runserver
```

Open **http://127.0.0.1:8000/** — SPA + API (same origin).  
Swagger: **http://127.0.0.1:8000/api/docs/**

### Demo accounts

| Role | Email | Password | Notes |
|---|---|---|---|
| Customer | `jordan@northbound.test` | `correct-horse-42` | MFA enrolled — any 6 digits except `000000` |
| Staff | `staff@northbound.test` | `staff-ops-42` | Refunds + staff order list |
| Admin | `admin@northbound.test` | `admin-change-me` | Django admin at `/admin/` |

Coupon: **`DISCOUNT20`** (20% off subtotal).

## Docker Compose

Docker Desktop is required. Android and iOS builds are not part of this stack; use the Flutter SDK on the host for those.

```bash
docker compose up --build
```

| Service | URL |
|---|---|
| Flutter web | http://localhost:8080 |
| Phone demo | http://localhost:3000 |
| API, Swagger, admin | http://localhost:8000/ |
| Mailpit | http://localhost:8025 |
| Postgres | localhost:5432 (`reka` / `reka`) |

The dev stack migrates and seeds demo data. Postgres keeps its data until `docker compose down -v`.

Production uses the same images, does not seed, and does not publish Postgres or Redis:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

Flutter is on port 80. The phone demo stays on port 3000.

## API surface

Base: `http://127.0.0.1:8000/api/v1/`

| Module | Routes |
|---|---|
| App | `GET /app/version-check/` |
| Auth | `POST /auth/users/`, `POST /auth/token/`, `POST /auth/token/refresh/`, `POST /auth/logout/`, password reset, MFA, profiles, roles |
| Catalogue | `GET /products/`, `GET /products/{id}/`, categories & brands under `products/meta/` |
| Cart | `GET/POST …/cart/cart/`, add/update/remove, discounts, shipping, transfer, saved-items |
| Orders | `POST /orders/`, `GET /orders/`, tracking, invoice, advance, cancel, addresses |
| Payments | initiate, sandbox webhooks, **staff refunds** (`POST /payments/refunds/`) |
| Staff ops | `GET /orders/staff/`, advance any order, issue full/partial refunds |

Headers (ADR-0005 / API standards):

- `Authorization: Bearer <access>`
- `X-Cart-Session: <uuid>` — guest cart identity
- `X-App-Version: 1.0.0 (build 1)`
- `Idempotency-Key` on order create

OpenAPI: http://127.0.0.1:8000/api/docs/

## What was implemented from the docs

- **P0 fixes** from `docs/00-README.md`: RBAC admin-only roles/permissions, User↔Role link, MFA pre-auth tokens, password reset endpoints, guest cart update/remove, transfer_cart ownership check, stock vs resulting quantity, non-stacking discounts, totals floored at zero, shipping estimate generation
- **Data model** for identity, catalogue, cart, orders/payments (sandbox)
- **Pricing service** shared by cart and order placement
- **Northbound seed catalogue** matching the prototype products
- **Error envelope** (`apps/core/exceptions.py`)

## Project layout

```
backend/
  reka/           # settings, urls
  apps/
    accounts/     # users, MFA, RBAC, JWT
    catalogue/    # products, variants, inventory
    cart/         # guest + auth carts
    orders/       # checkout, tracking
    pricing/      # Decimal totals (ADR-0009)
    core/         # middleware, pagination, version check
frontend/         # Northbound live client
docs/             # foundation documentation set
```

## Notifications (REKA-FR-NOT-001)

Transactional email (console backend locally; real SMTP via `EMAIL_BACKEND`):

| Event | Template |
|---|---|
| Registration | `email_verification` |
| Password reset | `password_reset` |
| Payment confirmed | `order_confirmation` |
| Out for delivery | `order_dispatched` |

Preferences: `GET/PATCH /api/v1/notifications/preferences/` (marketing opt-in, POPIA s69).  
Devices: `POST/DELETE /api/v1/notifications/devices/` for push registration.

With Redis + Celery (`CELERY_TASK_ALWAYS_EAGER=false`), emails queue on `celery-worker`. Local default is eager/inline.

Health: `GET /health/live/` · `GET /health/ready/`

## Cooling-off (ECTA s44 / REKA-FR-ORD-011)

Within **7 days** of payment confirmation, the customer may cancel and receive a **full refund**, unless a line item is flagged `cooling_off_excluded` (s42(2)).

```http
GET  /api/v1/orders/{reference}/cooling-off/
POST /api/v1/orders/{reference}/cooling-off/exercise/
{ "reason": "Changed mind" }
```

Order payloads include `cooling_off: { eligible, deadline, days_remaining, … }`. The SPA shows **Exercise 7-day cooling-off** when eligible.

## Staff console (SPA)

Sign in as **`staff@northbound.test` / `staff-ops-42`**. An **Ops** tab appears with:

- Today’s reconciliation snapshot  
- Filterable order list  
- **Advance** fulfilment  
- **Refund** (prompt for amount; blank = full)

## Abandoned checkouts

Pending payments older than 2 hours auto-cancel and release reserved stock:

```bash
python manage.py release_stale_payments --hours 2
```

Celery beat runs this every 15 minutes when workers are up (`payments.release_stale_pending`).

## Staff refunds (REKA-FR-PAY-006)

Staff/admin only (`IsStaffRole`):

```http
POST /api/v1/payments/refunds/
Idempotency-Key: <uuid>
{ "order_reference": "NB-123456", "amount": "50.00", "reason": "Damaged in transit" }
```

Omit `amount` for the full remaining balance. Partial refunds set payment to `partially_refunded`; a full refund transitions the order to `refunded`. Provider call is sandbox today (synthetic `RFND-…` reference) — swap in Yoco/Payfast without changing the API.

```http
GET /api/v1/orders/staff/
GET /api/v1/orders/staff/{reference}/
POST /api/v1/orders/staff/{reference}/advance/
GET /api/v1/payments/refunds/list/
```

## Tax invoices (REKA-FR-ORD-013)

After payment: `GET /api/v1/orders/{reference}/invoice/` returns a print-ready HTML tax invoice (VAT-inclusive split at 15%, merchant details from settings). The SPA **Orders** screen has **View tax invoice**.

## Payments (ADR-0011 / SAQ A)

Card data never hits Reka. Checkout creates an order in `awaiting_payment` with stock **reserved**, then a hosted session. Confirmation is accepted **only** via signed provider notification (webhook / ITN), not the client return.

```
POST /api/v1/orders/          → order + payment.pending + redirect_url
POST /api/v1/payments/webhooks/sandbox/   (HMAC)  → payment_confirmed + stock commit
POST /api/v1/payments/webhooks/payfast/   (ITN)   → same confirm path
POST /api/v1/payments/sandbox/complete/   (auth)  → signs + runs sandbox webhook path
```

**Provider selection** (`PAYMENT_PROVIDER`):

| Value | Behaviour |
|---|---|
| `sandbox` (default) | Local hosted page; no external network |
| `payfast` | Payfast hosted checkout when `PAYFAST_MERCHANT_ID` + `PAYFAST_MERCHANT_KEY` are set; otherwise falls back to sandbox |

COD skips hosted capture and confirms immediately.

**Reconciliation** (staff): `GET /api/v1/payments/reconciliation/?date=YYYY-MM-DD` — daily captured/refunded totals and exception list (REKA-FR-PAY-007).

## Tests

```bash
cd backend
python manage.py test apps.pricing apps.accounts apps.cart apps.orders apps.payments apps.notifications
```

Also runs in GitHub Actions (`.github/workflows/ci.yml`) against Postgres 16.

## Security & production

- **Security headers** middleware (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `no-store` on PII APIs)
- **DEBUG=false** refuses weak/default `DJANGO_SECRET_KEY`
- Deploy checks: `python manage.py check --deploy`
- Edge config: [`deploy/nginx.prod.conf`](deploy/nginx.prod.conf)
- Prod compose: `docker compose -f docker-compose.prod.yml --env-file .env.prod up -d`

## Push notifications

Device registration: `POST /api/v1/notifications/devices/`.  
Order status transitions emit push (dry-run logged when `FCM_SERVER_KEY` is unset). Set the key to enable FCM HTTP send.

## Flutter client

ADR-0002 Flutter app lives in [`mobile/`](mobile/):

```bash
# terminal 1 — API
.\scripts\dev.ps1 run

# terminal 2 — Flutter (Chrome), for hot reload
cd mobile
flutter run -d chrome --dart-define=REKA_API_BASE=http://127.0.0.1:8000
```

`docker compose up` also serves a built Flutter web app at http://localhost:8080. Rebuild the `flutter` image after Dart changes.

See [`mobile/README.md`](mobile/README.md). OpenAPI: [`openapi.yaml`](openapi.yaml)  
Regenerate: `cd backend && python manage.py spectacular --file ../openapi.yaml`
