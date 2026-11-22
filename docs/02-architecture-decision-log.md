# Architecture Decision Log

| | |
|---|---|
| **Document ID** | REKA-ARC-001 |
| **Version** | 0.1 (Draft) |
| **Owner** | Solution Architect |
| **Format** | Michael Nygard ADR |

---

## How to use this log

An ADR records a decision **and the context that made it correct at the time**. It is never edited after acceptance — it is superseded by a later ADR that references it.

In the repository, split each record below into `docs/adr/NNNN-slug.md`. They are collected here only for review convenience.

**Statuses:** Proposed · Accepted · Deprecated · Superseded by ADR-NNNN

**When to write one:** any decision that is expensive to reverse — a framework, a data store, an identity mechanism, a public contract, a naming convention baked into infrastructure. Do not write one for a library you could swap in an afternoon.

| # | Title | Status |
|---|---|---|
| 0001 | Django REST Framework for the backend API | Accepted |
| 0002 | Flutter for the client application | Accepted (supersedes Ionic) |
| 0003 | One application image, many runtime roles | Accepted |
| 0004 | JWT bearer tokens with rotating refresh | Accepted |
| 0005 | Header-based cart session identity | Accepted |
| 0006 | URL-path API versioning | Accepted |
| 0007 | PostgreSQL as system of record, Redis for ephemeral state | Accepted |
| 0008 | Search engine selection | **Proposed — decision required** |
| 0009 | Monetary values as Decimal through a single pricing service | Accepted |
| 0010 | Custom Role/Permission model rather than Django groups | Accepted with conditions |
| 0011 | Payment integration targeting PCI DSS SAQ A | Proposed |
| 0012 | Documentation in-repo as Markdown | Accepted |
| 0013 | Product name "Reka" | Accepted with conditions |

---

## ADR-0001 — Django REST Framework for the backend API

**Status:** Accepted

**Context.** The platform requires fifteen functional modules with heavy relational structure, an administrative interface, role-based access control, and a long operational life. The team has Python capability. Time to first working API matters more than raw request throughput; expected peak load is thousands of requests per minute, not hundreds of thousands.

**Decision.** Build the API with Django and Django REST Framework. Use the ORM as the data access layer. Use `drf-spectacular` to generate the OpenAPI schema from serializers and viewsets.

**Consequences.**
- The Django admin covers a meaningful share of the Admin Dashboard module at near-zero cost, deferring bespoke admin work.
- Migrations, authentication scaffolding and the permission framework are provided rather than built.
- Synchronous WSGI serving is the default; anything requiring persistent connections (live chat) needs a separate ASGI process. See ADR-0003.
- The ORM makes N+1 query patterns easy to write accidentally. Query count assertions are required in tests — see the Test Strategy.
- Serializer-level validation becomes the primary integrity boundary. It is not sufficient on its own; database constraints are still required.

**Alternatives considered.** FastAPI — faster and async-native, but no admin, no ORM, no migrations, and a materially larger volume of code to write for the same fifteen modules. Node/NestJS — no team capability. Rejected both.

---

## ADR-0002 — Flutter for the client application

**Status:** Accepted. Supersedes the initial Ionic selection.

**Context.** The original plan specified Ionic. Ionic renders in a WebView and therefore inherits browser behaviour: cookies, sessions, service-worker push, and instant over-the-air updates. Flutter compiles to native and inherits none of these. The choice was revisited for rendering performance, offline capability and long-term maintainability.

**Decision.** Build the client in Flutter, targeting iOS, Android and — where useful — Flutter Web from one codebase. Riverpod for state, `dio` for HTTP, `flutter_secure_storage` for tokens, Drift for the offline store.

**Consequences.**
- Cookie-based session identity is unavailable. Guest carts require an explicit header. See ADR-0005.
- API versioning becomes load-bearing: store binaries cannot be force-updated, so old versions persist for months. See ADR-0006.
- Push notification delivery moves to FCM and APNs, requiring a device registration endpoint that does not currently exist.
- Email verification and password reset links require Android App Links and iOS Universal Links, which requires nginx to serve `assetlinks.json` and `apple-app-site-association`.
- A genuine offline cart becomes practical, which was impractical in a WebView.
- **iOS builds cannot be containerised.** A macOS build agent is now a hard infrastructure dependency. See ADR-0003.

---

## ADR-0003 — One application image, many runtime roles

**Status:** Accepted

**Context.** The system needs an HTTP API, a WebSocket server, Celery workers on multiple queues, and a scheduler. All four execute the same Django codebase. Building separate images per role multiplies build time, registry storage and version-skew risk.

**Decision.** Build one application image. Differentiate roles by the container `command`. Compose services: `api` (Gunicorn), `ws` (Daphne), `celery-worker`, `celery-worker-priority`, `celery-beat`. Multi-stage build, non-root `USER app`, per-service `HEALTHCHECK`.

**Consequences.**
- Every role always runs the identical code revision. Version skew between web and worker — a classic source of "works on the API, fails in the task" bugs — is structurally impossible.
- The image carries dependencies some roles do not need. Accepted: a few tens of megabytes is cheaper than the skew risk.
- A single rebuild redeploys everything. Deployment must be ordered so that migrations run before any role starts against the new schema.
- iOS build tooling is explicitly out of scope for this image (ADR-0002).

---

## ADR-0004 — JWT bearer tokens with rotating refresh

**Status:** Accepted

**Context.** A mobile client cannot rely on cookie sessions and needs to survive process death and long offline periods. `djangorestframework-simplejwt` is already in use.

**Decision.** Access token 15 minutes, refresh token 14 days with rotation and reuse detection. Access tokens carry `mfa_verified`. Tokens stored in `flutter_secure_storage`. A single `dio` interceptor attaches the header, and refresh is guarded by a mutex so concurrent 401s trigger exactly one refresh.

**Consequences.**
- Revocation is not instantaneous. A stolen access token remains valid for up to 15 minutes. Accepted; the alternative is a datastore lookup per request.
- Refresh rotation requires a blacklist table, which grows and must be pruned on a schedule.
- The `mfa_verified` claim makes authorisation decisions readable from the token without a database hit — but means the claim must never be upgradeable by refresh. See Access Control Matrix §8, Rule M-3.
- Logout must blacklist the refresh token server-side; discarding it client-side is not logout.

---

## ADR-0005 — Header-based cart session identity

**Status:** Accepted

**Context.** `cart_views.py` reads `request.cart_session_id`, which derives from Django session middleware and therefore from a browser cookie. Flutter has no cookie jar by default and no browser session (ADR-0002). Guest carts are a required feature — a large share of first-time shoppers add to cart before creating an account.

**Decision.** The client generates a UUIDv4 on first launch, stores it in `flutter_secure_storage`, and sends it as `X-Cart-Session`. Middleware reads the header and sets `request.cart_session_id`. The server HMAC-signs the identifier so forged values are rejected without a database lookup. The `Cart.session_id` column and the `transfer_cart` merge logic are unchanged.

**Consequences.**
- The transport changes; the data model does not. Existing cart code continues to work.
- This identifier becomes a trust boundary granting data access without authentication. It requires the controls in Access Control Matrix §7 — in particular, `transfer_cart` must verify that the caller was issued the session it presents.
- Flutter Web must use the same header rather than falling back to cookies, so that one code path serves all platforms.
- Session identifiers must never appear in URLs, where they would be captured by access logs and referrer headers.

---

## ADR-0006 — URL-path API versioning

**Status:** Accepted

**Context.** Once the client ships through app stores, old binaries persist. Users defer updates for months; some never update. The server must serve several client generations simultaneously.

**Decision.** All routes under `/api/v1/`. Version in the path, not a header or query parameter. Clients send `X-App-Version`. A `GET /api/v1/app/version-check/` endpoint returns `{min_supported, latest, force_update}` so a build with a known defect can be hard-blocked.

**Consequences.**
- v1 must be supported for a minimum of twelve months after v2 ships. Budget for it.
- A definition of "breaking" is now required, and it is in the API Design Standards. Adding an optional field is not breaking; removing a field, changing a type, tightening validation or changing an error code all are.
- Path versioning is visible in logs and cache keys, which makes traffic distribution across versions measurable — useful when deciding when v1 can be retired.

---

## ADR-0007 — PostgreSQL as system of record, Redis for ephemeral state

**Status:** Accepted

**Context.** The domain is strongly relational — orders, items, variants, inventory, payments — and requires transactional integrity across tables. Separately, the system needs a cache, a Celery broker, a Channels layer and rate-limit counters.

**Decision.** PostgreSQL 16 is the sole system of record. Redis 7 serves cache, broker, Channels backing store and rate-limiting. No business fact lives only in Redis. PgBouncer sits in front of Postgres in production.

**Consequences.**
- Redis can be flushed at any time without data loss. This must remain true; the moment a durable fact lands only in Redis, the operational model breaks.
- Connection pooling is mandatory: Gunicorn workers multiplied by Celery concurrency exhausts default Postgres connection limits quickly.
- Money calculations run inside database transactions, not across service boundaries. See ADR-0009.
- Redis running four workloads on one instance is acceptable at launch; split broker from cache when queue depth begins affecting cache latency.

---

## ADR-0008 — Search engine selection

**Status:** **Proposed. Decision required before Phase 1.**

**Context.** The Product Management module specifies search, filtering, variants, brands and attributes. Postgres full-text search handles free-text adequately but does not handle faceted filtering across variant, brand and attribute dimensions at acceptable latency once the catalogue grows.

**Options.**

| | OpenSearch | Meilisearch | Postgres FTS |
|---|---|---|---|
| Faceted filtering | Strong | Good | Weak |
| Memory floor | ~1 GB | ~100 MB | none (already running) |
| Operational burden | High | Low | None |
| Typo tolerance | Configurable | Excellent default | None |
| Analytics (Search Analytics feature) | Native | Limited | Build yourself |

**Recommendation.** Meilisearch unless the catalogue is expected to exceed roughly 100,000 SKUs or the Search Analytics requirement is firm. The operational saving at launch is significant and migration to OpenSearch later is a re-index, not a rewrite.

**Decision required from:** Product Owner and Solution Architect, before Phase 1 begins.

---

## ADR-0009 — Monetary values as Decimal through a single pricing service

**Status:** Accepted

**Context.** Cart totals are currently computed in `CartSerializer` (`get_total_discount`, `get_shipping_cost`, `get_total`). Order totals will be computed elsewhere. Two implementations of the same arithmetic will diverge. The current implementation also has three concrete defects: percentage discounts produce unrounded fractional cents, discounts can stack without limit, and `subtotal - discount + shipping` has no floor at zero.

**Decision.** All money is `Decimal` with `max_digits=12, decimal_places=2`. Never float. A single `pricing` service module computes cart totals and order totals; serializers call it and never reimplement it. Every computation quantises to two decimal places with `ROUND_HALF_UP` at each step, not only at the end. Totals are floored at zero. Currency is stored explicitly alongside every amount, even while ZAR is the only supported currency.

**Consequences.**
- A cart total and the resulting order total cannot disagree, because they are the same code path.
- Tax and multi-currency become extensions of one module rather than changes in many places.
- Tests for the pricing service are non-negotiable and are named explicitly in the Test Strategy.
- Existing `CartSerializer` methods must be refactored to delegate. This is a prerequisite for Phase 3, not an optimisation.

---

## ADR-0010 — Custom Role/Permission model rather than Django groups

**Status:** Accepted with conditions

**Context.** The codebase defines `Role` and `Permission` models with `module`, `action` and four `can_*` booleans, rather than using Django's built-in `Group` and `Permission`. The modules document specifies three roles with module-scoped access.

**Decision.** Retain the custom model — module-scoped permissions map more directly onto the fifteen-module structure than Django's per-model permissions. Accept it **subject to three conditions**, all of which are blocking:

1. **`Permission.module` becomes a choice field** populated from a single shared enumeration. Free text cannot be matched reliably at check time.
2. **`Permission.action` is removed**, or the four `can_*` booleans are removed. The two are redundant representations of the same fact and will diverge.
3. **A `User` ↔ `Role` relationship must exist.** No such link is visible in the reviewed code, which means roles currently grant nothing. Until this exists the RBAC layer is decorative.

**Consequences.**
- Django's `@permission_required` and admin permission checks do not understand this model. A `HasModulePermission` class must be written and used consistently.
- The Django admin continues to use Django's own permission system. Two authorisation models coexist; the boundary between them must be documented and admin access restricted per Access Control Matrix §9.

**Reconsider if** conditions 1–3 are not met within Phase 0, in which case migrating to Django groups becomes the cheaper path.

---

## ADR-0011 — Payment integration targeting PCI DSS SAQ A

**Status:** Proposed

**Context.** PCI DSS scope is determined by whether cardholder data touches your systems. SAQ A applies where payment capture is fully outsourced — redirect or provider-hosted iframe. SAQ A-EP applies where your page influences the payment form, and carries roughly an order of magnitude more evidence obligations.

**Decision.** Target SAQ A. Card data must never reach Reka servers, logs, or the Flutter client's memory. Use the provider's hosted checkout or native SDK. Store only a provider token and the last four digits.

**Consequences.**
- The checkout flow includes a redirect or a provider-controlled surface, which constrains UX. Accepted deliberately: the compliance saving is large and permanent.
- Payment confirmation arrives by webhook, not by client callback. The client's return from the provider is a UX signal only and must never be trusted to mark an order paid.
- Webhooks require signature verification and idempotency keys — mobile networks retry, and providers retry.
- Refunds are initiated through the provider API; Reka stores the reference, not the instrument.

**Open:** provider selection (Peach, Payfast, Yoco, Ozow, Stripe). Each imposes different Flutter SDK and webhook requirements. Required before Phase 3.

---

## ADR-0012 — Documentation in-repo as Markdown

**Status:** Accepted

**Context.** Documentation held in shared drives drifts from the code within weeks, and drifted documentation is worse than none because it is trusted after it stops being true.

**Decision.** All documents in this set live in `docs/` in the application repository, in Markdown, reviewed through pull requests. Generated artefacts are generated, never hand-maintained: OpenAPI from `drf-spectacular`, the ERD from `django-extensions graph_models`, the dependency inventory from `pip-licenses` and `flutter pub deps`, the changelog from conventional commits.

**Consequences.**
- A change to a `permission_classes` declaration and the corresponding change to the Access Control Matrix arrive in the same pull request, reviewed together.
- Non-technical stakeholders need a rendered view. Publish `docs/` to a static site rather than emailing files.
- CI can enforce coupling: fail the build when specified symbols change without a matching documentation change.

---

## ADR-0013 — Product name "Reka"

**Status:** Accepted with conditions

**Context.** *Reka* means "to buy" in Sesotho (*ho reka*) and Setswana (*go reka*), both widely spoken in Gauteng. Four characters, one pronunciation across South African languages, fits mobile app label limits, valid as a Python identifier.

Two collisions were identified. A South African augmented-reality shopping app launched under the name in 2021 and appears dormant. More significantly, **Reka Afrika** is a Johannesburg e-commerce platform with a registered company entity and an active social presence, though its website appears parked.

**Decision.** Adopt "Reka" as the platform name. Use it for all internal identifiers immediately. Treat the public brand as provisional pending legal clearance.

**Conditions.**
1. CIPC company name search and reservation before incorporation.
2. Trademark search in classes 9, 35 and 42 before any public use.
3. `reka.co.za` secured before the Android `applicationId` is fixed — the identifier is permanent after first Play Store release.
4. The customer-facing name is a single configuration value (`REKA_SITE_BRAND_NAME`) and a Flutter theme constant, never a literal in templates or widgets.

**Consequences.**
- Development proceeds under the name today; the legal question blocks nothing until store submission and public launch.
- If clearance fails, the change is one configuration value and a logo asset, not a refactor. Internal identifiers can remain "reka" indefinitely — no customer ever sees them.
- Non-South African markets: *reka* means "river" in the Slavic languages, *Réka* is a Hungarian given name, and an established Swiss holiday-savings brand uses the name. None affects a South African launch; all matter before European expansion.

---

## Template for new records

```markdown
# ADR-NNNN — <short title>

**Status:** Proposed | Accepted | Deprecated | Superseded by ADR-NNNN
**Date:** YYYY-MM-DD
**Deciders:** <names>

## Context
What forces are at play? What constraints, what evidence?
Written so a reader in two years understands why this was hard.

## Decision
What we are doing. Active voice, present tense.

## Consequences
What becomes easier. What becomes harder. What we accept.
Include the bad ones — an ADR with only benefits is marketing.

## Alternatives considered
What else, and why not.
```
