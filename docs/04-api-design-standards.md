# API Design Standards

| | |
|---|---|
| **Document ID** | REKA-API-001 |
| **Version** | 0.1 (Draft) |
| **Owner** | Tech Lead (Backend) |
| **Audience** | Backend engineers, Flutter engineers, QA |
| **Enforcement** | Pull request review. Violations are blocking, not advisory |

---

## 1. Why this document is strict

The API is a contract with binaries you cannot update. Once a Flutter build ships through the App Store, its expectations are frozen for as long as users decline to update — realistically twelve months. A convention adopted casually in week three becomes permanent in week twelve.

Everything here is mandatory for new endpoints. Existing endpoints migrate when touched.

---

## 2. Base URL and versioning

```
https://api.reka.co.za/api/v1/<module>/<resource>/
```

| Rule | Detail |
|---|---|
| Version in the path | `/api/v1/`. Not a header, not a query parameter. Visible in logs, cache keys and traffic analytics |
| Version bumps | Only for breaking changes (§3). Never for additions |
| Support window | v1 supported at minimum 12 months after v2 ships |
| Trailing slash | Required. Django's `APPEND_SLASH` redirects, and a redirect on a POST silently drops the body in some HTTP clients |
| Module segment | Matches the app label: `auth`, `cart`, `products`, `orders`, `payments`, `shipping`, `promotions` |

### Version check endpoint

```
GET /api/v1/app/version-check/
→ 200 { "min_supported": "1.2.0", "latest": "1.6.1",
        "force_update": false, "message": null }
```

The client calls this on cold start. A build with a known payment defect can be hard-blocked without a store release.

---

## 3. What counts as breaking

**Breaking — requires a version bump:**

- Removing or renaming a field, endpoint or error code
- Changing a field's type or its nullability from nullable to required
- Tightening validation so previously accepted input is rejected
- Changing the meaning of an existing value
- Changing pagination style
- Changing an HTTP status code for an existing condition

**Not breaking — ship freely:**

- Adding an optional request field with a default
- Adding a response field
- Adding a new endpoint
- Adding a new enum value **where the client is documented to tolerate unknown values** — this must be true of the Flutter models from day one, or every new order status becomes a breaking change
- Relaxing validation

**Rule.** Flutter models must never use exhaustive `switch` on a server-supplied enum without a default branch. This single habit determines whether order statuses can evolve.

---

## 4. Resources and methods

| Convention | Rule |
|---|---|
| Nouns, plural, kebab-case | `/saved-items/`, not `/savedItem/` or `/getSavedItems/` |
| Nesting | Maximum one level. `/orders/{id}/items/` is fine; deeper is not |
| Actions | Where a verb is unavoidable, use a sub-resource: `POST /cart/items/{id}/save-for-later/`. Keep these rare |
| Identifiers | Opaque to the client. Never parse an ID |

| Method | Semantics | Idempotent |
|---|---|---|
| GET | Read. Never mutates. Never has a body | Yes |
| POST | Create, or a non-idempotent action | No |
| PUT | Full replace | Yes |
| PATCH | Partial update | Yes |
| DELETE | Remove | Yes |

**Rule.** `DELETE` returning 204 must be safe to repeat. Deleting an already-deleted resource returns 204, not 404 — the client may be retrying after a dropped response.

> The current `MFAViewSet.disable` gets this right by accident: `filter(...).delete()` on an empty set returns 204. Make it deliberate.

---

## 5. Status codes

| Code | Use | Do not use for |
|---|---|---|
| 200 | Successful read or update | Creation |
| 201 | Created. Include `Location` | |
| 202 | Accepted for async processing | Anything the client must treat as done |
| 204 | Success, no body | |
| 400 | Malformed or semantically invalid input | Authorisation failures |
| 401 | Missing, malformed or expired credentials | A valid identity lacking permission |
| 403 | Valid identity, insufficient permission | Missing credentials |
| 404 | Not found, **or found but not visible to this caller** | |
| 409 | State conflict — already paid, already cancelled | Validation errors |
| 422 | Not used. Use 400 | |
| 429 | Rate limited. Include `Retry-After` | |
| 500 | Unhandled. Never deliberate | |

**Rule 401 vs 403.** 401 means *authenticate*. 403 means *you did authenticate and it is not enough*. Getting this wrong makes the Flutter interceptor loop: it sees 401, refreshes the token, retries, gets 401 again, refreshes again.

**Rule 404 for hidden objects.** Requesting a resource belonging to someone else returns 404, not 403. A 403 confirms the object exists, which is an enumeration oracle.

---

## 6. Error envelope

Every non-2xx response uses one shape. No exceptions.

```json
{
  "error": {
    "code": "cart_item_out_of_stock",
    "message": "Only 2 of this item are available.",
    "field": "quantity",
    "details": { "available": 2, "requested": 5 },
    "request_id": "01JC8X2K9M4QRTVW"
  }
}
```

| Key | Rule |
|---|---|
| `code` | **Stable, machine-readable, snake_case.** The client branches on this and never on `message` |
| `message` | Human-readable, end-user safe, localisable. May change without a version bump |
| `field` | Present for validation errors. Names the offending request field |
| `details` | Structured context the client can render. Optional |
| `request_id` | Always present. Matches the server log entry and the `X-Request-ID` response header |

Multiple validation failures:

```json
{ "error": { "code": "validation_failed", "message": "Check the highlighted fields.",
  "errors": [ { "field": "email", "code": "already_registered", "message": "..." },
               { "field": "password", "code": "too_common",      "message": "..." } ],
  "request_id": "01JC8X2K9M4QRTVW" } }
```

**This requires a custom `EXCEPTION_HANDLER`.** DRF's default emits `{"field": ["message"]}` and `{"detail": "..."}` inconsistently, which is what the current code produces. The Flutter client would need to parse three shapes. Write the handler in Phase 0.

**Never leak** stack traces, SQL, internal paths, library versions, or whether an email address is registered.

### Error code catalogue (seed)

| Code | Status | Meaning |
|---|---|---|
| `validation_failed` | 400 | One or more fields invalid |
| `authentication_failed` | 401 | Bad credentials |
| `token_expired` | 401 | Access token expired — client refreshes |
| `token_invalid` | 401 | Malformed or revoked — client signs out |
| `mfa_required` | 401 | Second factor outstanding |
| `mfa_code_invalid` | 400 | Wrong code |
| `permission_denied` | 403 | Authenticated, not authorised |
| `mfa_verification_required` | 403 | Operation needs `mfa_verified` |
| `not_found` | 404 | Absent or not visible |
| `cart_item_out_of_stock` | 409 | Insufficient inventory |
| `discount_code_invalid` | 400 | Unknown or expired code |
| `discount_already_applied` | 409 | Code already on this cart |
| `cart_session_invalid` | 400 | Forged or expired session identifier |
| `order_already_paid` | 409 | Duplicate payment attempt |
| `rate_limited` | 429 | Too many requests |
| `app_version_unsupported` | 426 | Client below `min_supported` |

The catalogue is append-only. A code's meaning never changes.

---

## 7. Headers

### Request

| Header | When | Notes |
|---|---|---|
| `Authorization: Bearer <jwt>` | Authenticated | |
| `X-Cart-Session: <uuid>` | Always | Guest identity (ADR-0005). Cart module only |
| `X-App-Version: 1.4.2 (312)` | Always | Version and build number |
| `X-Request-ID: <ulid>` | Always | Client-generated. Echoed back |
| `Idempotency-Key: <uuid>` | Order creation, payment | Required. See §9 |
| `Accept-Language` | Always | Reserved for localisation |

### Response

| Header | Notes |
|---|---|
| `X-Request-ID` | Echoed or generated |
| `RateLimit-Limit`, `RateLimit-Remaining`, `RateLimit-Reset` | On rate-limited endpoints |
| `Retry-After` | On 429 and 503 |
| `Cache-Control` | `no-store` on anything containing personal information |

---

## 8. Pagination, filtering, shaping

### Pagination

Cursor pagination for anything that grows unboundedly — products, orders, reviews, audit events. Offset pagination drifts when rows are inserted mid-scroll, which produces duplicate and skipped items in an infinite-scroll list.

```json
{ "results": [ … ],
  "next": "https://api.reka.co.za/api/v1/products/?cursor=cD0yMDI2",
  "previous": null,
  "page_size": 20 }
```

Default page size 20, maximum 100. Requests above the maximum are clamped, not rejected.

**No total count on cursor-paginated endpoints.** `COUNT(*)` on a large filtered table is expensive and the client does not need it for infinite scroll. Where a count is genuinely required, provide a separate endpoint.

### Filtering and sorting

```
GET /api/v1/products/?category=packs&brand=northbound&price_min=100&sort=-rating
```

Snake_case parameters. Sort prefixed `-` for descending. **Only whitelisted fields are sortable** — an unrestricted `order_by` from user input is a denial-of-service vector against unindexed columns.

### Response shaping

Default responses are thin. Expansion is explicit:

```
GET /api/v1/cart/cart/?expand=items.product,items.variant
```

> `CartItemSerializer` currently nests full product **and** variant detail on every item unconditionally. On a ten-item cart over a 3G connection this is a large, mostly unused payload. Make expansion opt-in.

---

## 9. Idempotency

Required on `POST /orders/` and all payment operations. Strongly recommended on `POST /cart/cart/add_item/`.

1. Client generates a UUID per logical operation and sends `Idempotency-Key`.
2. Server stores key → response for 24 hours.
3. A repeat with the same key returns the stored response without re-executing.
4. A repeat with the same key but a *different* body returns 409 `idempotency_key_reused`.
5. The client reuses the key across retries of the same attempt, and generates a new one for a genuinely new attempt.

Without this, a customer on the Gautrain who loses signal mid-checkout gets charged twice.

---

## 10. Data conventions

| Type | Rule | Example |
|---|---|---|
| JSON keys | snake_case | `total_items` |
| Timestamps | ISO 8601, UTC, `Z` suffix | `2026-07-28T09:15:00Z` |
| Dates | ISO 8601 date only | `2026-07-28` |
| Money | **String**, two decimals, with an explicit currency field | `{"amount": "1299.00", "currency": "ZAR"}` |
| Booleans | True booleans | not `"true"`, not `1` |
| Enums | Lowercase snake_case strings | `"awaiting_payment"` |
| Null vs absent | `null` means known-empty; absent means not requested | |
| Empty collections | `[]`, never `null` | |

**Money as a string is not fussiness.** JSON numbers are IEEE 754 doubles. `0.1 + 0.2` is not `0.3`. Dart's `double` has the same behaviour. Serialise as a string, parse to `Decimal` server-side and `Decimal` (package:decimal) client-side. This pairs with ADR-0009.

**Timezone.** Store and transmit UTC. Render in `Africa/Johannesburg`. Never transmit local time.

---

## 11. Rate limiting

| Endpoint class | Limit | Scope |
|---|---|---|
| `POST /auth/token/` | 10/min, then lockout after 5 failures | IP + account |
| `POST /auth/users/` | 5/hour | IP |
| `POST /auth/password-reset/` | 3/hour | IP + email |
| `POST /auth/mfa/verify/` | 5/5 min | Account |
| Cart mutations | 60/min | Session or user |
| Catalogue reads | 300/min | IP |
| Everything else authenticated | 120/min | User |

Enforced at nginx for coarse IP limits and in the application for account-scoped limits. Application-level counters live in Redis.

**Rule.** Authentication failures must return an identical response and take comparable time whether the account exists or not. No user enumeration through status codes, message text or timing.

---

## 12. OpenAPI

| Rule | Detail |
|---|---|
| Generated, never hand-written | `drf-spectacular` from serializers and viewsets |
| CI publishes the schema | Artefact on every main build |
| **CI diffs the schema** | A pull request changing the schema must say so in its description. An unannounced breaking diff fails the build |
| Every endpoint documented | `@extend_schema` with summary, description, and at least one example per response code |
| Flutter models generated from the schema | Not hand-transcribed. Hand-transcription is where field-name typos become production bugs |

---

## 13. Checklist for a new endpoint

- [ ] Under `/api/v1/<module>/`, plural noun, kebab-case, trailing slash
- [ ] Correct method and status codes per §5
- [ ] `permission_classes` explicit — never inherited by accident
- [ ] Corresponding row exists in the Access Control Matrix
- [ ] Object-level ownership enforced, not just `get_queryset` filtering
- [ ] Errors use the §6 envelope with codes from the catalogue
- [ ] Cursor pagination on any list that can grow
- [ ] Sortable and filterable fields whitelisted
- [ ] Rate limit assigned
- [ ] `@extend_schema` with examples
- [ ] Idempotency key required if it creates or charges
- [ ] Money as string with currency
- [ ] No personal information in URLs, query strings or logs
- [ ] `Cache-Control: no-store` if the response contains personal information
- [ ] Tests: happy path, validation failure, unauthenticated, unauthorised, other user's object
- [ ] Query count asserted
