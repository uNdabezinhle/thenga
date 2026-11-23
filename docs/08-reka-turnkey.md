# Reka turnkey

Reka is the platform. Northbound is the sample merchant on a hosted install. A turnkey server is the same stack for one merchant.

## Hosted

1. Merchant creates an account.
2. `POST /api/v1/platform/onboarding/` with trading name, package (`till`, `shop`, or `shop_till`), extras, `privacy_accepted: true`, and `empty_catalogue_ok: true`.
3. A 14-day trial has both shop and till. After that, new sales stop until the package is marked active.
4. `GET /api/v1/platform/onboarding/status/` is the go-live checklist.
5. The public shop for that merchant is the product list with `?merchant=<slug>`. Till-only shops return an empty list.
6. Prices from `GET /api/v1/platform/packages/` are illustrative. They are not collected.

## Self-hosted

Use the existing container stack. Do not run `seed_northbound` unless you want the Northbound demo catalogue. Point the phone and Flutter clients at this server’s API. Android and iOS are not built on the server.

## Backup

Copy the database volume and the media directory before an upgrade. Restore by replacing those two and starting the stack again. Receipts are generated from orders, not stored as files.

## PayFast

Leave keys empty until the merchant is ready. Card and EFT stay on the sandbox. Cash and card-present on the till do not need PayFast.

## Not isolated yet

Orders and the staff ops list are still global. A second merchant should not be given the sample staff login. Catalogue rows are isolated when `Product.merchant` is set. The sample catalogue has no merchant and stays on Northbound.
