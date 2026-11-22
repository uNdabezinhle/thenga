# Northbound Flutter client

Cross-platform client for the Reka API (ADR-0002). Talks to `/api/v1/` with:

- **JWT** access + refresh (secure storage)
- **`X-Cart-Session`** guest cart identity (ADR-0005)
- **`X-App-Version`** header
- Riverpod state, Dio HTTP

## Prerequisites

- Flutter 3.19+ (`flutter doctor`)
- API running: `../scripts/dev.ps1 run` → `http://127.0.0.1:8000`

## Run

```bash
cd mobile

# Android emulator / device (use 10.0.2.2 for host loopback on Android emulator)
flutter run --dart-define=REKA_API_BASE=http://10.0.2.2:8000

# iOS simulator / desktop / web (localhost is fine)
flutter run --dart-define=REKA_API_BASE=http://127.0.0.1:8000

# Chrome
flutter run -d chrome --dart-define=REKA_API_BASE=http://127.0.0.1:8000
```

Default API base (if unset): `http://127.0.0.1:8000`.

## Demo login

| | |
|---|---|
| Email | `jordan@northbound.test` |
| Password | `correct-horse-42` |
| MFA | Enter any 6 digits except `000000`. The app does not submit a code for you. |

## What’s implemented

| Screen | Behaviour |
|---|---|
| Shop | Catalogue, live categories, generated product art |
| Search | Query, brand, price, and sort |
| Product | Detail, variants, reviews, wishlist, add to cart |
| Cart | Qty, discount, shipping, save for later |
| Checkout | Address book, card and EFT via the hosted sandbox, cash on delivery |
| Orders | Lines, totals, history, invoice, cancel, cooling-off |
| Account | Sign-in, MFA, profile, password, addresses, notifications |
| Ops | Staff orders, refunds, reconciliation |

OpenAPI schema for the API lives at repo root [`../openapi.yaml`](../openapi.yaml) (regenerate with `python manage.py spectacular --file ../openapi.yaml`).

## Project layout

```
lib/
  main.dart
  src/
    api/client.dart      # Dio + JWT refresh + cart session
    models/models.dart
    state/providers.dart # Riverpod
    screens/             # Shop, product, cart, orders, account
    theme.dart           # Northbound forest/lime tokens
```
