# Reka turnkey

Reka is the platform. Northbound is the sample merchant on a hosted install. A turnkey server is the same stack for one merchant.

## Hosted

1. Merchant creates an account.
2. `POST /api/v1/platform/onboarding/` with trading name, package (`till`, `shop`, or `shop_till`), extras, `privacy_accepted: true`, and `empty_catalogue_ok: true`.
3. A 14-day trial has both shop and till. After that, new sales stop until the package is marked active.
4. `GET /api/v1/platform/onboarding/status/` is the go-live checklist.
5. The owner confirms the package with `POST /api/v1/platform/package/` (`package`, optional `addons`). That marks the shop active and does not collect the illustrative price. A downgrade keeps products and orders. Staff cannot confirm it.
6. The public shop is `/?merchant=<slug>` on the phone demo and on Flutter web, and `GET /api/v1/products/?merchant=<slug>`. With no slug, the sample shop is Northbound. Ads on that address are only that shop’s banners. A till-only shop returns an empty catalogue.
7. Prices from `GET /api/v1/platform/packages/` are illustrative. They are not collected.

## Self-hosted

Use the existing container stack. Do not run `seed_northbound` unless you want the Northbound demo catalogue. Point the phone and Flutter clients at this server’s API. Android and iOS are not built on the server.

## Backup

Copy the database volume and the media directory before an upgrade. Restore by replacing those two and starting the stack again. Receipts are generated from orders, not stored as files.

## First run

On an empty server:

```
python manage.py setup_reka --trading-name "Kiosk" --owner-email owner@kiosk.test --password "a-long-secret" --package shop_till
```

That opens one merchant and sends the verification mail. It does not load Northbound. Add `--demo` only when you want the sample outdoor catalogue. Add `--force` to open another merchant beside one that already exists.

## Reminders and ads

Merchants who selected the reminders extra get unpaid-checkout, trial-ending, low-stock, and open-drawer mail. The daily Celery beat task sends them. Operated ad clicks are counted at `POST /api/v1/ads/<id>/click/`. The share for the previous month is emailed on the first day of the month. Gross is an illustrative rand per click, not a charge to shoppers. The owner turns operated placements off with `PATCH /api/v1/platform/ads/`. The mail log is `GET /api/v1/notifications/log/`.

## PayFast

Leave keys empty until the merchant is ready. Card and EFT stay on the sandbox. Cash and card-present on the till do not need PayFast. A failed card or EFT sends one transactional mail. An abandoned checkout is released by the existing pending-payment task and does not send that mail.

## Who sees which orders

The staff order list, dispatch, and counter receipt follow the signed-in merchant. Sample staff, who have no membership, see orders with no merchant. A merchant member does not see the Northbound orders. Do not add the sample staff user to a second shop. A shopper still sees every order on their own account.

## Catalogue, staff, and a second store

`POST /api/v1/platform/catalogue/` accepts `rows` of name, sku, price, and quantity, a `csv` string with that header, or `sample: true` for two plain products. It does not copy Northbound. `POST /api/v1/platform/staff/` invites by email and does not make them site staff. A second store needs the extra_store extra: `POST /api/v1/platform/stores/`. Live PayFast keys are `POST /api/v1/platform/payfast/` and are not returned by the API.
