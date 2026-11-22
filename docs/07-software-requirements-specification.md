# Software Requirements Specification

| | |
|---|---|
| **Document ID** | REKA-REQ-001 |
| **Version** | 0.1 (Draft) |
| **Owner** | Business Analyst |
| **Approvers** | Product Owner, Solution Architect, Security Officer |
| **Standard** | Adapted from IEEE 830 |

---

## 1. Introduction

### 1.1 Purpose

This specification defines what the Reka commerce platform must do. It is the contract between the business and the build, and the root of the traceability chain: **requirement → design → code → test → UAT script**.

### 1.2 Scope

Reka is a commerce platform comprising a Django REST Framework API and a Flutter client for iOS, Android and web. It supports catalogue browsing, guest and authenticated carts, checkout, payment, fulfilment and post-sale service, with an administrative interface for store operations.

**In scope for v1:** the 38 Must requirements in §4.
**Out of scope for v1:** marketplace multi-vendor, subscriptions, B2B pricing tiers, loyalty programmes, physical point of sale, ERP and CRM integration.

### 1.3 The scope decision this document encodes

The originating modules document specifies fifteen modules containing approximately 120 features. At the observed team size that represents 18–24 months of work before anything reaches a customer.

**This specification deliberately defines a v1 of 38 requirements** and places the remainder in a prioritised backlog (§7). Every requirement carries a MoSCoW priority and a release phase. Anything not marked Must for v1 is explicitly deferred, not forgotten.

### 1.4 Definitions

| Term | Meaning |
|---|---|
| **Guest** | An unauthenticated visitor identified only by a cart session identifier |
| **Cart session identifier** | Client-generated UUID sent as `X-Cart-Session`, server-signed (ADR-0005) |
| **Variant** | A purchasable configuration of a product — size, colour. Stock is held at variant level |
| **Merge** | Transferring a guest cart into an authenticated user's cart on sign-in |
| **Pre-auth token** | A 5-minute token granting access only to MFA verification |
| **Responsible Party** | POPIA term for the entity determining the purpose of processing — the Reka operating company |

### 1.5 Requirement identifiers

`REKA-FR-<MODULE>-<NNN>` for functional, `REKA-NFR-<CATEGORY>-<NNN>` for non-functional. Identifiers are permanent. A withdrawn requirement is marked Withdrawn, never reused.

---

## 2. Overall description

### 2.1 Product perspective

A new build, not a replacement. Two tiers: a stateless DRF API over PostgreSQL, and a Flutter client that holds no business logic beyond presentation and offline queueing. External dependencies: a payment service provider, a courier, an email provider, and FCM/APNs.

### 2.2 Actors

| Actor | Description |
|---|---|
| Guest | Browses, searches, builds a cart. Cannot check out |
| Customer | Registered. Owns profile, cart, saved items, orders, addresses |
| Staff | Processes orders, handles support, manages inventory. Scoped by role |
| Administrator | Full control including roles, permissions, configuration. MFA mandatory |
| System | Scheduled jobs, webhook receivers, notification dispatch |

### 2.3 Operating environment

| | |
|---|---|
| Client | iOS 15+, Android 8.0 (API 26)+, evergreen browsers |
| Network | Assume intermittent 3G. Every screen must have a loading, empty and error state |
| Currency | ZAR only in v1. The data model carries currency explicitly (ADR-0009) |
| Locale | English (South Africa). Others deferred |
| Timezone | Store UTC, display `Africa/Johannesburg` |

### 2.4 Constraints

| ID | Constraint |
|---|---|
| C-1 | Store-distributed binaries cannot be force-updated. The API must serve multiple client generations (ADR-0006) |
| C-2 | Cardholder data must never reach Reka systems. PCI DSS SAQ A (ADR-0011) |
| C-3 | POPIA applies. GDPR does not unless the business targets EU data subjects |
| C-4 | ECTA s43 disclosures, s44 cooling-off and s46 performance obligations apply to every electronic transaction |
| C-5 | iOS builds require a macOS agent |
| C-6 | Load-shedding is normal. The client must degrade gracefully on connectivity loss, not fail |

### 2.5 Assumptions

| ID | Assumption | If false |
|---|---|---|
| AS-1 | Single merchant, not a marketplace | Vendor onboarding, payouts and commission become v1 scope |
| AS-2 | One warehouse | Inventory gains a location dimension throughout |
| AS-3 | One payment provider at launch | Provider abstraction becomes v1, not v2 |
| AS-4 | Catalogue below 100,000 SKUs | ADR-0008 resolves to OpenSearch |
| AS-5 | Domestic delivery only | Customs, duties and international shipping enter scope |

---

## 3. Non-functional requirements

### 3.1 Performance

| ID | Requirement | Priority |
|---|---|---|
| REKA-NFR-PERF-001 | Product list p95 under 300 ms at 200 concurrent users | Must |
| REKA-NFR-PERF-002 | Cart read p95 under 200 ms | Must |
| REKA-NFR-PERF-003 | Checkout submission p95 under 1,200 ms excluding provider time | Must |
| REKA-NFR-PERF-004 | Cold app start to interactive under 3 s on a mid-range Android device | Should |
| REKA-NFR-PERF-005 | Sustain 5× baseline for 10 minutes with error rate below 0.1% | Must |
| REKA-NFR-PERF-006 | Serialising a cart of any size uses a bounded, asserted number of queries | Must |

### 3.2 Availability

| ID | Requirement | Priority |
|---|---|---|
| REKA-NFR-AVL-001 | 99.5% monthly availability for the customer-facing API | Must |
| REKA-NFR-AVL-002 | RPO 15 minutes, RTO 4 hours | Must |
| REKA-NFR-AVL-003 | Restore drill quarterly, timed, result recorded | Must |
| REKA-NFR-AVL-004 | Catalogue browsing remains available when search is down (degrade to database filtering) | Should |

### 3.3 Security

| ID | Requirement | Priority |
|---|---|---|
| REKA-NFR-SEC-001 | Every endpoint enforces the Access Control Matrix and is covered by an authorisation test | Must |
| REKA-NFR-SEC-002 | Passwords hashed with Argon2; Django validators enforced | Must |
| REKA-NFR-SEC-003 | MFA gates privilege issuance, not merely available post-authentication | Must |
| REKA-NFR-SEC-004 | MFA mandatory for Administrator | Must |
| REKA-NFR-SEC-005 | TLS 1.2 minimum, HSTS enabled | Must |
| REKA-NFR-SEC-006 | No cardholder data stored, logged or transmitted through Reka systems | Must |
| REKA-NFR-SEC-007 | Order creation and payment operations idempotent | Must |
| REKA-NFR-SEC-008 | All security-relevant events audited per Access Control Matrix §10 | Must |
| REKA-NFR-SEC-009 | Rate limiting per API Design Standards §11 | Must |
| REKA-NFR-SEC-010 | External penetration test before go-live; high-severity findings remediated | Must |
| REKA-NFR-SEC-011 | Client certificate pinning; no secrets in the shipped binary | Should |

### 3.4 Compliance

| ID | Requirement | Priority |
|---|---|---|
| REKA-NFR-CMP-001 | Information Officer appointed and registered with the Information Regulator | Must |
| REKA-NFR-CMP-002 | PAIA manual published and available | Must |
| REKA-NFR-CMP-003 | Data subject requests fulfilled within 30 days through a defined procedure | Must |
| REKA-NFR-CMP-004 | ECTA s43 disclosures present before order confirmation, with a review-and-withdraw step | Must |
| REKA-NFR-CMP-005 | 7-day cooling-off right honoured and communicated, subject to s42(2) exclusions | Must |
| REKA-NFR-CMP-006 | Orders executed within 30 days or the customer notified (ECTA s46) | Must |
| REKA-NFR-CMP-007 | No production personal information in any non-production environment | Must |
| REKA-NFR-CMP-008 | PCI DSS SAQ A completed before processing live payments | Must |

### 3.5 Usability and accessibility

| ID | Requirement | Priority |
|---|---|---|
| REKA-NFR-USE-001 | Every screen has defined loading, empty and error states | Must |
| REKA-NFR-USE-002 | Errors state what happened and how to proceed; never a raw code | Must |
| REKA-NFR-USE-003 | Legible at 200% system text scale without truncation | Should |
| REKA-NFR-USE-004 | Interactive targets at least 44×44 dp | Should |
| REKA-NFR-USE-005 | Screen reader labels on all interactive elements | Should |
| REKA-NFR-USE-006 | Cart survives app termination and reinstall for authenticated users | Must |

### 3.6 Maintainability

| ID | Requirement | Priority |
|---|---|---|
| REKA-NFR-MNT-001 | Coverage thresholds per Test Strategy §3 enforced in CI | Must |
| REKA-NFR-MNT-002 | OpenAPI schema generated, never hand-maintained | Must |
| REKA-NFR-MNT-003 | Documentation in-repo, reviewed in pull requests (ADR-0012) | Must |
| REKA-NFR-MNT-004 | Structured logging with a correlation identifier on every line | Must |

---

## 4. Functional requirements — v1

Priority: **M**ust · **S**hould · **C**ould · **W**on't (this release)

### 4.1 Authentication (`AUTH`)

| ID | Requirement | Pri | Phase | Status |
|---|---|---|---|---|
| REKA-FR-AUTH-001 | Register with email, username, password and confirmation; passwords must match and satisfy validators | M | 0 | Built |
| REKA-FR-AUTH-002 | Send a verification email on registration; the link expires in 24 hours and is single-use | M | 0 | Partial |
| REKA-FR-AUTH-003 | Prevent order placement until the email is verified | M | 3 | Not built |
| REKA-FR-AUTH-004 | Authenticate with email and password, returning a token pair | M | 0 | Built |
| REKA-FR-AUTH-005 | Where MFA is enrolled, issue a **pre-auth token only** until the second factor is verified | M | 0 | **Not built — defect** |
| REKA-FR-AUTH-006 | Refresh an access token with rotation and reuse detection | M | 0 | Partial |
| REKA-FR-AUTH-007 | Sign out, blacklisting the refresh token server-side | M | 0 | Not built |
| REKA-FR-AUTH-008 | **Request a password reset by email** | M | 0 | **Not built — serializers exist, no view or URL** |
| REKA-FR-AUTH-009 | **Complete a password reset with a single-use, time-limited token** | M | 0 | **Not built** |
| REKA-FR-AUTH-010 | Change password when authenticated, verifying the current password | M | 0 | Built |
| REKA-FR-AUTH-011 | Sign in with Google | S | 1 | Built |
| REKA-FR-AUTH-012 | Sign in with Facebook | C | 2 | Built |
| REKA-FR-AUTH-013 | Enrol an MFA device (authenticator, SMS or email), showing the secret exactly once | S | 1 | Built |
| REKA-FR-AUTH-014 | Verify an MFA code at sign-in, issuing a token carrying `mfa_verified` | M | 0 | Built |
| REKA-FR-AUTH-015 | Generate single-use backup codes, stored hashed | S | 1 | Partial |
| REKA-FR-AUTH-016 | Disable MFA, requiring re-authentication within the last 5 minutes | S | 1 | Partial |
| REKA-FR-AUTH-017 | View and update own profile | M | 0 | Built |
| REKA-FR-AUTH-018 | Administrators manage roles and permissions; **no other actor may** | M | 0 | **Not built — currently open to all** |
| REKA-FR-AUTH-019 | Assign roles to users | M | 0 | **Not built — no User↔Role link exists** |
| REKA-FR-AUTH-020 | Lock an account after 5 consecutive failures, with a defined unlock path | S | 1 | Not built |

### 4.2 Catalogue (`CAT`) — Phase 1

| ID | Requirement | Pri | Phase |
|---|---|---|---|
| REKA-FR-CAT-001 | Browse products with cursor pagination | M | 1 |
| REKA-FR-CAT-002 | Filter by category, brand and price range | M | 1 |
| REKA-FR-CAT-003 | Free-text search with typo tolerance | M | 1 |
| REKA-FR-CAT-004 | Sort by price, rating and recency | M | 1 |
| REKA-FR-CAT-005 | View product detail with images, description and specifications | M | 1 |
| REKA-FR-CAT-006 | Select a variant and see its stock position | M | 1 |
| REKA-FR-CAT-007 | Indicate low stock at or below a configurable threshold | S | 1 |
| REKA-FR-CAT-008 | Prevent selection of an out-of-stock variant | M | 1 |
| REKA-FR-CAT-009 | Browse a category hierarchy | M | 1 |
| REKA-FR-CAT-010 | Read approved reviews with an aggregate rating | S | 2 |
| REKA-FR-CAT-011 | Submit a review, restricted to verified purchasers, held for moderation | S | 2 |
| REKA-FR-CAT-012 | Staff manage products, variants, images and stock through the admin interface | M | 1 |

### 4.3 Cart (`CART`)

| ID | Requirement | Pri | Phase | Status |
|---|---|---|---|---|
| REKA-FR-CART-001 | Guests build a cart identified by a signed session identifier | M | 0 | Built |
| REKA-FR-CART-002 | Add an item, validating stock **against the resulting quantity** | M | 0 | **Defect — validates requested only** |
| REKA-FR-CART-003 | Update quantity; **guests must be able to do this** | M | 0 | **Defect — 404 for guests** |
| REKA-FR-CART-004 | Remove an item; **guests must be able to do this** | M | 0 | **Defect — 404 for guests** |
| REKA-FR-CART-005 | Clear the cart | M | 0 | Built |
| REKA-FR-CART-006 | Cart persists across app restarts and devices for authenticated users | M | 0 | Built |
| REKA-FR-CART-007 | Merge a guest cart on sign-in, **only where the caller was issued that session** | M | 0 | **Defect — no ownership proof** |
| REKA-FR-CART-008 | Merge sums duplicate lines atomically and revalidates stock | M | 0 | Partial |
| REKA-FR-CART-009 | Save a cart item for later; move it back | S | 1 | Built |
| REKA-FR-CART-010 | Apply a discount code, **at most one instance per code per cart** | M | 2 | **Defect — stacks; hard-coded** |
| REKA-FR-CART-011 | Remove an applied discount | M | 2 | Not built |
| REKA-FR-CART-012 | **Generate** shipping estimates for the cart | M | 3 | **Not built — nothing creates these rows** |
| REKA-FR-CART-013 | Select one shipping method | M | 3 | Built |
| REKA-FR-CART-014 | Display subtotal, discount, delivery and total, **never below zero** | M | 0 | **Defect — can go negative** |
| REKA-FR-CART-015 | Snapshot unit price at add time and apply a defined staleness policy | S | 2 | Not built |
| REKA-FR-CART-016 | Queue cart mutations offline and replay on reconnect | S | 2 | Not built |
| REKA-FR-CART-017 | Maintain a wishlist independent of the cart | C | 2 | Not built |

### 4.4 Checkout, orders and payment (`ORD`, `PAY`) — Phase 3

| ID | Requirement | Pri |
|---|---|---|
| REKA-FR-ORD-001 | Maintain an address book with defaults for shipping and billing | M |
| REKA-FR-ORD-002 | Review the complete transaction and costs and withdraw before confirming (ECTA s43) | M |
| REKA-FR-ORD-003 | Place an order, reserving stock atomically | M |
| REKA-FR-ORD-004 | Reject an order where stock has become unavailable, naming the item | M |
| REKA-FR-ORD-005 | Snapshot product name, SKU and unit price onto each order line | M |
| REKA-FR-ORD-006 | Issue a unique, human-quotable order reference | M |
| REKA-FR-ORD-007 | View order history and detail | M |
| REKA-FR-ORD-008 | Track order status against a defined state machine | M |
| REKA-FR-ORD-009 | Record every status transition with actor and timestamp | M |
| REKA-FR-ORD-010 | Cancel before dispatch, releasing reserved stock | M |
| REKA-FR-ORD-011 | Exercise the 7-day cooling-off right where s42(2) does not exclude it | M |
| REKA-FR-ORD-012 | Staff process, pick, pack and dispatch orders | M |
| REKA-FR-ORD-013 | Generate a compliant tax invoice | M |
| REKA-FR-PAY-001 | Pay by card through the provider's hosted surface; no card data reaches Reka | M |
| REKA-FR-PAY-002 | Pay by instant EFT | S |
| REKA-FR-PAY-003 | Confirm payment **solely** by verified webhook, never by client return | M |
| REKA-FR-PAY-004 | Process webhooks idempotently with signature verification | M |
| REKA-FR-PAY-005 | Store only a provider token, last four digits and card brand | M |
| REKA-FR-PAY-006 | Staff issue full or partial refunds through the provider | M |
| REKA-FR-PAY-007 | Reconcile payments against orders daily, exceptions reported | S |

### 4.5 Notifications (`NOT`) — Phase 4

| ID | Requirement | Pri |
|---|---|---|
| REKA-FR-NOT-001 | Email: verification, password reset, order confirmation, dispatch, delivery | M |
| REKA-FR-NOT-002 | Register a device for push and unregister on sign-out | S |
| REKA-FR-NOT-003 | Push on order status change | S |
| REKA-FR-NOT-004 | Abandoned cart reminder, with consent and an unsubscribe path | C |
| REKA-FR-NOT-005 | Manage notification preferences by channel and category | S |
| REKA-FR-NOT-006 | Never send direct marketing without recorded consent (POPIA s69) | M |

### 4.6 Administration (`ADM`)

| ID | Requirement | Pri | Phase |
|---|---|---|---|
| REKA-FR-ADM-001 | Django admin serves catalogue, order and customer management in v1 | M | 1 |
| REKA-FR-ADM-002 | Admin access restricted to an internal path with mandatory MFA | M | 0 |
| REKA-FR-ADM-003 | Every admin write is audited with before and after state | M | 1 |
| REKA-FR-ADM-004 | Export a data subject's personal information on request | M | 4 |
| REKA-FR-ADM-005 | Erase or anonymise a data subject, preserving records under legal retention | M | 4 |
| REKA-FR-ADM-006 | Bespoke admin dashboard with sales overview | C | 5 |

---

## 5. Requirement summary

| Module | Must | Should | Could | Total |
|---|---|---|---|---|
| Authentication | 12 | 7 | 1 | 20 |
| Catalogue | 8 | 4 | 0 | 12 |
| Cart | 12 | 4 | 1 | 17 |
| Orders & payment | 17 | 3 | 0 | 20 |
| Notifications | 2 | 3 | 1 | 6 |
| Administration | 5 | 0 | 1 | 6 |
| **Total** | **56** | **21** | **4** | **81** |

Against approximately 120 features in the originating modules document, of which **38 Must requirements constitute the shippable v1** (Phases 0–3). The remainder is §7.

---

## 6. Traceability

| Requirement | Design | Code | Test | UAT |
|---|---|---|---|---|
| REKA-FR-AUTH-005 | ACM §8 | `apps.authentication.api.views` | `test_password_only_token_is_pre_auth` | UAT-AUTH-03 |
| REKA-FR-CART-007 | ACM §6.2 | `CartViewSet.transfer_cart` | `test_transfer_cart_rejects_foreign_session` | UAT-CART-05 |
| REKA-FR-CART-014 | ADR-0009 | `apps.pricing.services` | `test_total_never_negative` | UAT-CART-08 |

Maintained as a generated matrix in CI, not by hand. Every Must requirement must appear with all five columns populated before UAT sign-off.

---

## 7. Deferred backlog

Present in the modules document, deliberately out of v1. Each requires its own requirements work before scheduling.

**Phase 5+:** promotions engine (campaigns, flash sales, bundles, gift cards, loyalty, referrals), content management (static pages, blog, SEO, banners, FAQ), analytics and reporting (all eight), customer service (help desk, ticketing, live chat), advanced shipping (multi-carrier, label generation, international), product import/export, cross-sell and upsell, bespoke admin dashboard, ERP and CRM integration, multi-warehouse inventory.

**Explicitly Won't for v1:** multi-vendor marketplace, subscriptions, B2B pricing, multi-currency, multi-language, physical point of sale.

---

## 8. Open items blocking approval

| # | Item | Owner | Needed by |
|---|---|---|---|
| O-1 | Search engine decision (ADR-0008) | Solution Architect | Phase 1 start |
| O-2 | Payment provider selection (ADR-0011) | Product Owner | Phase 3 start |
| O-3 | Courier selection and rate API | Product Owner | Phase 3 start |
| O-4 | Confirm single merchant, single warehouse (AS-1, AS-2) | Product Owner | Immediately |
| O-5 | Confirm the User↔Role relationship gap | Tech Lead | Immediately |
| O-6 | Cart price staleness policy — re-price silently or require confirmation | Product Owner | Phase 2 |
| O-7 | Legal review of T&Cs, returns and privacy copy | Legal Counsel | Before go-live |
| O-8 | Trademark clearance for "Reka" (ADR-0013) | Legal Counsel | Before public launch |
