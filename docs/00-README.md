# Reka — Foundation Documentation Set

Eight documents that should exist before further code is written. Drafted against the reviewed source (`authentication_*.py`, `cart_*.py`) and the originating modules document.

**Status: all drafts. None approved.** Each carries assumptions requiring confirmation and open items requiring a decision.

---

## Contents

| # | Document | ID | Owner | Read it when |
|---|---|---|---|---|
| 01 | [Access Control Matrix](01-access-control-matrix.md) | REKA-SEC-001 | Security Officer / Tech Lead | Before touching any `permission_classes` |
| 02 | [Architecture Decision Log](02-architecture-decision-log.md) | REKA-ARC-001 | Solution Architect | Before questioning why something was built this way |
| 03 | [Data Model & ERD](03-data-model-and-erd.md) | REKA-DAT-001 | Data Architect | Before writing a migration |
| 04 | [API Design Standards](04-api-design-standards.md) | REKA-API-001 | Tech Lead | Before adding an endpoint |
| 05 | [Test Strategy](05-test-strategy.md) | REKA-QA-001 | QA Lead | Before writing a test, or deciding not to |
| 06 | [Environment Specification](06-environment-specification.md) | REKA-OPS-001 | DevOps | Before deploying anything anywhere |
| 07 | [Software Requirements Specification](07-software-requirements-specification.md) | REKA-REQ-001 | Business Analyst | Before agreeing to build something |
| 08 | [POPIA Compliance Pack](08-popia-compliance-pack.md) | REKA-CMP-001 | Information Officer | Before storing a single real customer record |

---

## Reading order

**New engineer, day one:** 02 → 04 → 01 → 05.
**Product or business stakeholder:** 07 → 08.
**Before go-live:** 01 §11 → 08 §13 → 06 §10.

---

## How these fit together

```
07 SRS ──────────── what we build
   │
   ├── 02 ADRs ───── why we build it this way
   │      │
   │      ├── 03 Data Model ──── what it stores
   │      ├── 04 API Standards ─ how it is exposed
   │      └── 06 Environments ── where it runs
   │
   ├── 01 Access Control ─────── who may do what
   │      │
   │      └── 08 POPIA ───────── what the law requires of all of it
   │
   └── 05 Test Strategy ──────── how we know it works
```

Requirements in 07 trace to controls in 01 and 08, to conventions in 03 and 04, and to named tests in 05. A requirement without a test and a matrix row is not done.

---

## Repository layout

```
docs/
├── README.md
├── access-control-matrix.md
├── data-model.md
├── api-design-standards.md
├── test-strategy.md
├── environment-specification.md
├── software-requirements-specification.md
├── popia/
│   ├── compliance-pack.md
│   ├── paia-manual.md          ← to be drafted with counsel
│   └── privacy-notice.md       ← to be drafted with counsel
└── adr/
    ├── 0001-django-rest-framework.md
    ├── 0002-flutter-client.md
    └── …                        ← split 02 into one file per record
```

Per ADR-0012 these live in the application repository and change through pull requests. Generated artefacts are generated: OpenAPI from `drf-spectacular`, the ERD from `graph_models`, the dependency inventory from `pip-licenses`.

---

## What the drafting surfaced

Ten defects, found by writing the documents rather than by testing.

| ID | Severity | Finding | Where |
|---|---|---|---|
| F-01 | **P0** | `PermissionViewSet` / `RoleViewSet` open to any authenticated user — full privilege escalation | 01 §5.3 |
| F-02 | **P0** | `UserViewSet` exposes every customer's email and phone to any authenticated caller | 01 §5.1 |
| F-03 | **P0** | MFA does not gate access; a full token is issued on password alone | 01 §5.5, §8 |
| F-04 | **P0** | `transfer_cart` accepts an unverified session identifier and destructively merges | 01 §6.2 |
| F-05 | **P0** | Password reset unreachable — serializers written, no view or URL | 01 §5.6 |
| F-06 | **P1** | Guest cart update / remove / save-for-later return 404 for anonymous users | 01 §6.1 |
| F-07 | **P1** | Inventory validated against requested quantity, not resulting quantity | 03 §3 |
| F-08 | **P1** | Discounts stack without limit; totals can go negative | 03 §3, ADR-0009 |
| F-09 | **P2** | RBAC defined but not connected — no `User` ↔ `Role` link exists | 03 §2 |
| F-10 | **P2** | Nothing creates `ShippingEstimate` rows that `select_shipping` reads | 03 §3 |

Five P0s. Each is a few hours of work and each is the kind of thing a penetration test finds in minutes.

---

## Decisions required before Phase 0 closes

| # | Decision | Owner | Blocks |
|---|---|---|---|
| O-1 | Search engine — Meilisearch or OpenSearch (ADR-0008) | Solution Architect | Phase 1 |
| O-2 | Payment provider (ADR-0011) | Product Owner | Phase 3 |
| O-3 | Courier and rate API | Product Owner | Phase 3 |
| O-4 | Confirm single merchant, single warehouse | Product Owner | SRS approval |
| O-5 | Confirm the `User` ↔ `Role` gap is real | Tech Lead | **Immediately** |
| O-6 | Cart price staleness policy | Product Owner | Phase 2 |
| O-7 | Legal review of customer-facing terms | Legal Counsel | Go-live |
| O-8 | Trademark clearance for "Reka" (ADR-0013) | Legal Counsel | Public launch |

---

## Assumptions to confirm or correct

Drawn from the reviewed code. If any is wrong, the affected document changes.

| # | Assumption | Affects |
|---|---|---|
| A1 | No `User` ↔ `Role` relationship exists | 01, 03 — the whole RBAC layer |
| A2 | `Permission.action` and the `can_*` booleans are redundant | 03, ADR-0010 |
| A3 | `Permission.module` is free text, not a choice field | 01 §4, 03 |
| A4 | Roles are generic, with no built-in Admin/Staff/Customer distinction | 01 §3 |
| A5 | `request.cart_session_id` comes from session middleware not seen | 01 §7, ADR-0005 |
| A6 | `Inventory` is a ForeignKey queried with `.first()` where a OneToOne is intended | 03 §4 |

---

## Suggested next steps

1. **Correct the assumptions table.** Fifteen minutes of your time, and it determines whether three of these documents are accurate.
2. **Fix the five P0 findings.** A few hours. Do this before staging holds anything real.
3. **Appoint and register the Information Officer, and start the PAIA manual.** Administrative lead time that cannot be compressed later.
4. **Resolve O-1 and O-4.** Both block Phase 1 planning.
5. **Approve the SRS scope.** 38 Must requirements for v1 against roughly 120 features specified. Someone senior needs to agree to that cut in writing.

---

| | |
|---|---|
| **Version** | 0.1 |
| **Drafted** | 2026-07-28 |
| **Next review** | On approval of the assumptions table |
