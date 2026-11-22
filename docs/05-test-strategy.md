# Test Strategy

| | |
|---|---|
| **Document ID** | REKA-QA-001 |
| **Version** | 0.1 (Draft) |
| **Owner** | QA Lead |
| **Applies to** | Reka API, Flutter client, infrastructure |

---

## 1. Principle

Test where failure costs money or trust. In an e-commerce platform that means, in order: **money, inventory, authorisation, and the guest-to-account transition.** A misaligned button costs a support ticket. A discount that stacks five times costs revenue on every order until someone notices.

Coverage percentage is a weak signal and is not a target in itself. The targets in §3 exist to catch regressions in untested regions, not to be optimised toward.

---

## 2. Test levels

| Level | Scope | Tooling | Runs |
|---|---|---|---|
| Unit | One function or class, no I/O | `pytest` | Every commit |
| Integration | Serializer → view → database | `pytest-django`, real Postgres in CI | Every commit |
| Contract | Response shape against the OpenAPI schema | `schemathesis` | Every commit |
| Widget | Flutter widgets in isolation | `flutter_test`, `mocktail` | Every commit |
| End-to-end | Full stack, real containers | `integration_test` / Patrol | Nightly + pre-release |
| Performance | Load and soak | `k6` | Weekly + pre-release |
| Security | Static, dependency, dynamic | `bandit`, `pip-audit`, OWASP ZAP | Every commit / weekly |
| UAT | Business acceptance | Manual scripts | Per release |

**Rule.** CI runs against a real PostgreSQL and Redis container. SQLite is not used at any level. Partial unique indexes, `num_nonnulls` checks and transaction semantics — precisely the constraints protecting the cart model — do not exist in SQLite, so a green SQLite suite proves nothing about production.

---

## 3. Coverage targets

| Area | Line | Branch | Rationale |
|---|---|---|---|
| `pricing` service | **100%** | **100%** | Every branch is a currency amount |
| Inventory reservation | **100%** | **95%** | Oversell is unrecoverable |
| Permission classes | **100%** | **100%** | Each uncovered branch is a potential privilege escalation |
| Serializer validation | 90% | 85% | Primary integrity boundary |
| Views | 85% | 75% | |
| Celery tasks | 80% | 70% | |
| Flutter state notifiers | 80% | — | |
| Flutter widgets | 60% | — | Diminishing returns above this |
| Overall | 80% | 70% | CI gate |

---

## 4. Mandatory test cases

These are not examples. Each corresponds to a defect identified in code review or a rule in another document, and each must exist before the relevant module can be marked complete.

### 4.1 Money — `pricing` service (ADR-0009)

| Test | Asserts |
|---|---|
| `test_percentage_discount_rounds_half_up` | 20% of R33.33 is R6.67, not R6.666 |
| `test_total_never_negative` | Discount exceeding subtotal floors the total at zero, does not go negative |
| `test_discount_cannot_stack` | Applying `DISCOUNT20` twice yields one discount |
| `test_percentage_discount_capped_at_100` | Amount > 100 on a percentage discount is rejected |
| `test_shipping_excluded_from_percentage_discount` | Discount applies to the subtotal, not the delivery charge |
| `test_cart_total_equals_order_total` | The same basket priced as a cart and as an order produces identical figures — **the single most important test in the suite** |
| `test_money_never_float` | Property test: no code path converts an amount to `float` |
| `test_line_totals_sum_to_subtotal` | Rounding at line level sums to the stated subtotal |

### 4.2 Inventory

| Test | Asserts |
|---|---|
| `test_repeated_add_respects_stock` | Adding 5 twice against 6 stock fails on the second call. **Currently fails: validation checks requested quantity, not resulting quantity** |
| `test_merge_carts_revalidates_stock` | `merge_carts` cannot produce a line exceeding available stock |
| `test_concurrent_checkout_does_not_oversell` | Two simultaneous checkouts of the last unit: one succeeds, one gets 409 |
| `test_reservation_released_on_cancel` | Cancellation returns reserved units to available |
| `test_reservation_expires` | An abandoned reservation is released after its timeout |
| `test_variant_inventory_is_one_to_one` | No product carries a quantity independent of its variants |

### 4.3 Authorisation — mirrors Access Control Matrix §12

| Test | Asserts |
|---|---|
| `test_customer_cannot_list_users` | 403. **Currently fails** |
| `test_customer_cannot_create_permission` | 403. **Currently fails — privilege escalation** |
| `test_customer_cannot_modify_role` | 403. **Currently fails** |
| `test_customer_cannot_read_other_profile` | 404 |
| `test_password_only_token_is_pre_auth` | An MFA-enrolled user's password-only token is rejected everywhere except `/mfa/verify/`. **Currently fails** |
| `test_mfa_disable_requires_recent_auth` | 403 without re-authentication |
| `test_refresh_does_not_upgrade_mfa_claim` | Refreshing a pre-MFA token yields `mfa_verified: false` |
| `test_social_account_not_creatable_via_api` | 405 |
| `test_provider_id_not_in_response` | `provider_id` absent from every serialised `SocialAccount` |

### 4.4 Cart identity and merge

| Test | Asserts |
|---|---|
| `test_guest_can_update_own_cart_item` | 200 with a valid `X-Cart-Session`. **Currently fails — 404** |
| `test_guest_cannot_update_foreign_cart_item` | 404 with a different session |
| `test_transfer_cart_rejects_unsigned_session` | 400 on a forged identifier |
| `test_transfer_cart_rejects_foreign_session` | 403 where the session was not issued to the caller. **Currently fails — any session id is accepted** |
| `test_merge_sums_duplicate_lines` | Same product and variant in both carts sums quantities |
| `test_merge_is_atomic` | An exception mid-merge leaves both carts unchanged |
| `test_merge_preserves_discounts_once` | A discount present in both carts is not applied twice |
| `test_second_active_cart_cannot_be_created` | Partial unique index rejects a race |

### 4.5 Payments and orders (Phase 3)

| Test | Asserts |
|---|---|
| `test_duplicate_idempotency_key_returns_cached` | Second identical request does not re-charge |
| `test_idempotency_key_with_different_body_conflicts` | 409 |
| `test_webhook_signature_required` | Unsigned webhook rejected |
| `test_webhook_replay_is_idempotent` | Same event twice produces one state change |
| `test_client_return_does_not_mark_paid` | Only the webhook transitions the order to paid |
| `test_invalid_status_transition_rejected` | Cancelled cannot become shipped |
| `test_no_card_data_persisted` | Scan all writes; no PAN, CVV or expiry anywhere |

### 4.6 Performance regression

| Test | Asserts |
|---|---|
| `test_cart_serialization_query_count` | `assertNumQueries` — serialising a ten-item cart stays within a fixed budget. **Currently exceeds it: direct `CartSerializer(cart)` calls bypass the prefetch** |
| `test_product_list_query_count` | Constant regardless of page size |

**Rule.** Query-count assertions are a first-class test type, not an optimisation. They are the only practical defence against ORM N+1 regressions, and they fail loudly the moment someone adds a nested serializer.

---

## 5. Flutter testing

| Level | Scope |
|---|---|
| Unit | Pricing display, validators, date and money formatting, model serialisation round-trips |
| Notifier | State transitions with a mocked repository — sign-in, cart mutation, offline queue drain |
| Widget | Golden tests for cart, product detail, checkout at three text scales |
| Integration | Full flows on a real emulator against a seeded API |

**Required integration flows:** guest browse → add to cart → sign in → **verify merge** → checkout → order tracking. Registration → email verification deep link → MFA enrol. Token expiry mid-session → silent refresh → retry with no user-visible interruption. Airplane mode → queued cart mutation → reconnect → replay.

**Required negative cases:** 401 during a request, malformed JSON, unknown enum value from the server, HTTP 500, timeout, and an app-version block from `/version-check/`.

**Rule.** The unknown-enum test is mandatory on every model with a server-supplied enum. It is what makes §3 of the API Design Standards true in practice rather than in theory.

---

## 6. Test data

| Rule | Detail |
|---|---|
| **No production personal information in any lower environment.** Ever | POPIA s19. A copied production dump in staging is a reportable breach waiting to happen |
| Factories, not fixtures | `factory_boy`. Fixture files rot silently against schema changes |
| Seeded randomness | Random data with a logged seed. Reproducible failures |
| Realistic South African data | ZAR amounts, `+27` numbers, nine provinces, four-digit postal codes, names drawn from a synthetic multilingual set |
| Deterministic time | `freezegun`. No test depends on wall-clock time |
| External calls stubbed | `responses` / `respx`. No test touches a real payment or courier API |

Where production-shaped data is genuinely needed for performance work, generate it synthetically at production **volume** with production **distribution** — not production content.

---

## 7. CI gates

| Stage | Gate | Blocking |
|---|---|---|
| Lint | `ruff`, `black --check`, `dart analyze` | Yes |
| Type | `mypy` on `pricing`, `permissions`, `payments` | Yes |
| Unit + integration | All pass | Yes |
| Coverage | Meets §3 thresholds | Yes |
| Contract | Responses validate against the schema | Yes |
| Schema diff | Breaking change must be declared in the PR description | Yes |
| Security static | `bandit` — no high severity | Yes |
| Dependencies | `pip-audit`, `flutter pub outdated` — no known critical CVE | Yes |
| Migration check | `makemigrations --check --dry-run` clean | Yes |
| Docs coupling | Change to `permission_classes` requires a change to the Access Control Matrix | Yes |
| E2E | Nightly | No — reported, not blocking |

---

## 8. Performance testing

| Scenario | Target |
|---|---|
| Product list, p95 | < 300 ms |
| Product detail, p95 | < 250 ms |
| Cart read, p95 | < 200 ms |
| Add to cart, p95 | < 400 ms |
| Checkout submit, p95 | < 1,200 ms |
| Sustained load | 200 concurrent users, 30 min, error rate < 0.1% |
| Peak | 5× baseline for 10 min — the Black Friday assumption |
| Soak | 4 hours; memory and connection counts flat |

Run against staging at production sizing. Test the **database**, not the cache: a warm-cache load test measures Redis.

---

## 9. Security testing

| Activity | Frequency |
|---|---|
| `bandit`, `pip-audit`, `npm audit` equivalents | Every commit |
| OWASP ZAP baseline against staging | Weekly |
| Dependency review | Monthly |
| **External penetration test** | Before go-live, then annually and after any change to authentication |
| Access Control Matrix reconciliation | Every release — read the code, confirm it matches |
| Secret scanning (`gitleaks`) | Every commit, plus full history on first run |

**Mobile-specific:** certificate pinning verified; no secrets in the APK or IPA (`apktool` inspection); tokens confirmed in Keychain/Keystore and not shared preferences; screenshots suppressed on payment screens; no personal information in device logs.

---

## 10. Defect management

| Severity | Definition | Response | Fix |
|---|---|---|---|
| S1 Critical | Data loss, financial loss, security breach, checkout down | 1 hour | Immediate hotfix |
| S2 Major | Core journey blocked, no workaround | 4 hours | Current sprint |
| S3 Minor | Feature impaired, workaround exists | 2 days | Next sprint |
| S4 Cosmetic | Visual or copy | Best effort | Backlog |

Every bug report carries: environment, app and API version, `X-Request-ID`, steps, expected, actual, evidence.

**Rule.** Every S1 and S2 gets a regression test written **before** the fix is merged. The test must fail on the unfixed code — a test written after the fix proves only that the fix compiles.

---

## 11. UAT

Conducted by business stakeholders on staging with synthetic data, against scripts traceable to the SRS requirement IDs.

**Exit criteria:** all S1 and S2 defects closed. All Access Control Matrix tests passing. Penetration test findings at high severity or above remediated. Performance targets met. POPIA data subject request procedure demonstrated end to end. Formal sign-off recorded.

---

## 12. Definition of Done

A story is done when:

- [ ] Acceptance criteria met and demonstrated
- [ ] Unit and integration tests written and passing
- [ ] Coverage thresholds met for the touched area
- [ ] Authorisation tests present where an endpoint was added or changed
- [ ] Access Control Matrix updated in the same pull request if permissions changed
- [ ] OpenAPI schema regenerated; breaking changes declared
- [ ] Query count asserted where a serializer or queryset changed
- [ ] No new high-severity static or dependency findings
- [ ] No personal information added to logs
- [ ] Reviewed and approved by someone who did not write it
