# Access Control Matrix

| | |
|---|---|
| **Document ID** | REKA-SEC-001 |
| **Version** | 0.1 (Draft) |
| **Status** | For review |
| **Owner** | Security Officer / Tech Lead |
| **Reviewers** | Solution Architect, Information Officer |
| **Applies to** | Reka commerce platform — API tier |
| **Review cycle** | Every release, and on any change to a `permission_classes` declaration |

---

## 1. Purpose

This document is the single authoritative statement of **who may do what to which object** in the Reka platform. It exists because authorisation logic in a DRF project is scattered across `permission_classes`, `get_queryset`, `get_permissions` and object-level checks, and no single file reveals the effective policy.

Every rule here must be enforced in code **and** covered by an automated test. A rule without a test is a wish.

**Scope:** API-tier authorisation. Out of scope: network segmentation (see Environment Specification), physical access, and Django admin site access (governed separately in §9).

---

## 2. Assumptions requiring confirmation

These could not be determined from the files reviewed (`authentication_serializers.py`, `authentication_urls.py`, `authentication_views.py`, `cart_serializers.py`, `cart_urls.py`, `cart_views.py`). **Confirm or correct before this document is approved.**

| # | Assumption | Why it matters |
|---|---|---|
| A1 | The `User` model has no link to `Role`. `UserSerializer` exposes no role field, and no `UserRole` model or M2M appears anywhere. | If true, the entire RBAC layer is **defined but not connected** — roles exist as rows that grant nothing. This is the single largest gap in the model. |
| A2 | `Permission.action` and the four `can_*` booleans are redundant representations of the same fact. | Two sources of truth for one decision. One must be removed. |
| A3 | `Permission.module` is a free-text field, not a choice field. | Free text cannot be reliably matched at permission-check time. Typos silently deny or grant. |
| A4 | There is no `is_staff_role` distinction beyond Django's built-in `is_staff`. | The modules document specifies three roles (Admin, Customer, Staff); the code models roles generically. |
| A5 | `request.cart_session_id` is set by middleware not included in the reviewed files. | The trust boundary for guest carts depends entirely on how this value is derived. See §7. |

---

## 3. Actors

| ID | Actor | Definition | Authentication |
|---|---|---|---|
| **AN** | Anonymous | No credentials. Has a client-generated cart session identifier only. | None |
| **CU** | Customer | Authenticated end user. Owns a cart, profile, saved items, orders. | JWT access token |
| **CU-M** | Customer (MFA-verified) | As Customer, but the presented token carries `mfa_verified: true`. | JWT with MFA claim |
| **ST** | Staff | Employee with operational duties (order processing, support). Scoped by `Role`/`Permission`. | JWT + role assignment |
| **AD** | Administrator | Full platform control including role and permission management. | JWT + MFA (mandatory) |
| **SY** | System | Internal service identity: Celery workers, webhook receivers, health checks. | Service token or in-cluster network trust |

**Rule A-1.** Every actor above Anonymous is subject to object-level ownership checks. Membership in a role never implies access to an arbitrary object; it grants access to a *class* of operation, which is then narrowed by ownership.

**Rule A-2.** Administrator is not a Django superuser by default. Superuser access is a break-glass identity governed by §9.

---

## 4. Permission primitives to implement

Five classes. Everything in §5 and §6 is expressed in terms of these.

| Class | Responsibility |
|---|---|
| `IsAuthenticatedCustomer` | Rejects anonymous. Standard DRF `IsAuthenticated` with an explicit name. |
| `HasModulePermission` | Reads `Role` → `Permission` rows for the request user, matches `module` against a `required_module` attribute on the view and the HTTP method against the corresponding `can_*` flag. |
| `IsObjectOwner` | Object-level. Compares a configurable owner path (`obj.user`, `obj.cart.user`) against `request.user`. |
| `IsCartOwner` | Object-level, dual-identity. Matches `obj.user == request.user` for authenticated requests, or `obj.session_id == request.cart_session_id` for anonymous. Resolves the guest-cart gap in §7. |
| `IsMFAVerified` | Asserts `mfa_verified is True` in the token payload. |

**Rule P-1.** `HasModulePermission` requires `Permission.module` to become a choice field populated from a single enumeration constant shared with the module registry. Free text is not acceptable (assumption A3).

**Rule P-2.** Permission classes compose with AND. Where OR is required, write an explicit named class rather than overriding `get_permissions` with branching logic — branching in `get_permissions` is how the current `reset_password_*` inconsistency arose.

---

## 5. Matrix — Authentication module

Legend: **✔** permitted · **✘** denied · **OWN** permitted for own records only · **MFA** additionally requires `mfa_verified` · **⚠** current code deviates from this policy

### 5.1 Users (`/api/v1/auth/users/`)

| Operation | AN | CU | ST | AD | Notes |
|---|---|---|---|---|---|
| Create (register) | ✔ | ✔ | ✔ | ✔ | Rate-limited: 5/hour/IP |
| List | ✘ | ✘ ⚠ | ✔ | ✔ | **Current code returns every user to any authenticated caller** |
| Retrieve | OWN ✘ | OWN ⚠ | ✔ | ✔ | |
| Update / partial update | ✘ | OWN ⚠ | ✘ | ✔ | Staff must not edit customer credentials |
| Delete | ✘ | OWN | ✘ | ✔ MFA | Soft delete; see POPIA pack §7 |
| `change_password` | ✘ | OWN | OWN | OWN | Requires current password (already enforced) |
| Change another user's password | ✘ | ✘ | ✘ | ✘ | **Never.** Admins trigger a reset, they do not set passwords |

### 5.2 Profiles (`/api/v1/auth/profiles/`)

| Operation | AN | CU | ST | AD |
|---|---|---|---|---|
| List | ✘ | OWN | ✔ | ✔ |
| Retrieve / Update | ✘ | OWN | OWN + read-any | ✔ |
| Delete | ✘ | ✘ | ✘ | ✔ MFA |

Current `get_queryset` correctly filters to `user=self.request.user`, but `queryset = UserProfile.objects.all()` remains as the class attribute. DRF uses `get_queryset()` for list and detail routes, so this is presently safe — but it is safe by accident. Remove the broad class attribute or scope it.

### 5.3 Roles and Permissions (`/api/v1/auth/roles/`, `/permissions/`)

| Operation | AN | CU | ST | AD |
|---|---|---|---|---|
| List | ✘ | ✘ ⚠ | ✔ read-only | ✔ |
| Create / Update / Delete | ✘ | ✘ ⚠ | ✘ ⚠ | ✔ MFA |

> **P0 — Privilege escalation.** `RoleViewSet` and `PermissionViewSet` are both `ModelViewSet` with `permission_classes = [IsAuthenticated]` and no queryset filtering. Any registered customer can `POST /api/v1/auth/permissions/` granting a role `can_delete` on any module, then assign themselves that role (if A1 is false) or wait for it to be granted. This is complete compromise of the authorisation model by design, not by bug. **Fix before any deployment, including staging with real data.**

### 5.4 Social accounts (`/api/v1/auth/social-accounts/`)

| Operation | AN | CU | ST | AD |
|---|---|---|---|---|
| List / Retrieve | ✘ | OWN | ✘ | ✔ |
| Create | ✘ | ✘ | ✘ | ✘ |
| Delete (unlink) | ✘ | OWN | ✘ | ✔ |

Creation must occur only inside `handle_social_auth`, never via the API. A user who can POST a `SocialAccount` with an arbitrary `provider_id` can bind their account to another person's identity provider record. Set the serializer to read-only and remove `create` from the router, or restrict `http_method_names`.

`provider_id` and any stored provider tokens must never be returned in a response body. The current `SocialAccountSerializer` exposes `provider_id`.

### 5.5 MFA (`/api/v1/auth/mfa/`)

| Operation | AN | CU | Notes |
|---|---|---|---|
| `setup` | ✘ | OWN | Returns the shared secret **once**; never retrievable again |
| `verify_setup` | ✘ | OWN | Activates the device |
| `verify` | ✘ | OWN | Exchanges a pre-auth token for a full token. See §8 |
| `generate_backup_codes` | ✘ | OWN MFA | Requires an already-verified session |
| `disable` | ✘ | OWN MFA | Requires re-authentication within the last 5 minutes |

> **P0 — MFA does not gate anything.** `TokenObtainPairView` issues a fully privileged token on password alone. `MFAViewSet.verify` then requires `IsAuthenticated` — meaning the caller is already fully authenticated before they prove the second factor. An attacker holding only the password has complete access and can simply never call `verify`. See §8 for the corrected flow.

> **P1 — `disable` has no re-authentication step.** An attacker with a stolen access token removes the second factor with a single DELETE. `MFADevice.objects.filter(user=request.user).delete()` also silently succeeds when no devices exist, returning 204 and giving no signal.

### 5.6 Unauthenticated endpoints

| Endpoint | Justification | Required control |
|---|---|---|
| `POST /auth/token/` | Login | Rate limit 10/min/IP; lockout after 5 failures per account; no user enumeration in error text |
| `POST /auth/token/refresh/` | Session continuity | Rotation with reuse detection; blacklist on reuse |
| `POST /auth/users/` | Registration | Rate limit 5/hour/IP; email verification required before order placement |
| `GET /auth/verify-email/<token>/` | Email confirmation | Single-use, 24-hour expiry, constant-time comparison |
| `POST /auth/social/google/`, `/facebook/` | Social login | Validate audience and issuer claims server-side |
| `POST /auth/password-reset/` | **Does not exist** | See below |

> **P0 — Password reset is unreachable.** `get_permissions` whitelists `reset_password_request` and `reset_password_confirm` as `AllowAny`, and `PasswordResetRequestSerializer` / `PasswordResetConfirmSerializer` are fully written — but no action, view or URL implements them. Users cannot recover an account today. The whitelist entries are dead code that will silently start granting anonymous access the moment someone adds actions with those names.

---

## 6. Matrix — Cart module

### 6.1 Cart (`/api/v1/cart/cart/`)

| Operation | AN (own session) | CU (own cart) | Other users' carts | ST | AD |
|---|---|---|---|---|---|
| Retrieve | ✔ | ✔ | ✘ | ✔ read | ✔ |
| `add_item` | ✔ | ✔ | ✘ | ✘ | ✘ |
| `update_item` | ✔ ⚠ | ✔ | ✘ | ✘ | ✘ |
| `remove_item` | ✔ ⚠ | ✔ | ✘ | ✘ | ✘ |
| `save_for_later` | ✘ | ✔ | ✘ | ✘ | ✘ |
| `apply_discount` | ✔ | ✔ | ✘ | ✘ | ✘ |
| `select_shipping` | ✔ | ✔ | ✘ | ✘ | ✘ |
| `clear` | ✔ | ✔ | ✘ | ✘ | ✘ |
| `transfer_cart` | ✘ | ✔ | ✘ | ✘ | ✘ |

> **P1 — Guest cart is half-wired.** `update_item`, `remove_item` and `save_for_later` all query `CartItem.objects.get(cart__user=request.user, ...)` under a viewset declared `permission_classes = [AllowAny]`. For an anonymous caller `request.user` is `AnonymousUser`, so the lookup raises `DoesNotExist` and returns 404. Guests can add to a cart but cannot modify it. Replace with `IsCartOwner` object-level checks that accept either identity.

> **`save_for_later` is correctly customer-only** — a saved item belongs to a user account, and there is no anonymous equivalent. The UI must hide this control for guests rather than letting it 404.

### 6.2 `transfer_cart` — the highest-risk endpoint in the platform

Current implementation accepts `session_id` from the request body and merges whatever active cart matches it into the caller's cart.

> **P0 — No ownership proof.** Any authenticated user who supplies another person's session identifier absorbs that person's cart. Session identifiers travel in headers and logs, appear in error reports, and are guessable if generated predictably. The merge is also destructive: `session_cart.delete()` means the victim's cart is gone, not copied.

**Required controls:**

1. The client must present the session identifier it was **issued**, and the server must be able to prove it issued it. Sign it (HMAC with a server key) at creation and verify the signature on transfer.
2. Bind the session cart to the request that created it — store the issuing IP prefix or a first-party cookie alongside, and require a match.
3. Reject transfer of any session cart older than a configured TTL (suggest 30 days).
4. Log every transfer with both cart IDs to the audit trail (§10).
5. Make the merge non-destructive: mark the session cart inactive rather than deleting, retained for the dispute window.

### 6.3 Saved items (`/api/v1/cart/saved-items/`)

| Operation | AN | CU | ST | AD |
|---|---|---|---|---|
| List / Retrieve | ✘ | OWN | ✘ | ✔ |
| Create | ✘ | OWN | ✘ | ✘ |
| Delete | ✘ | OWN | ✘ | ✔ |
| `move_to_cart` | ✘ | OWN | ✘ | ✘ |

`SavedForLaterViewSet.get_queryset` correctly filters by user, and `move_to_cart` uses `self.get_object()` which respects that queryset. This is the one place in the reviewed code where object-level ownership is enforced correctly. Use it as the reference pattern.

---

## 7. Trust boundary — the cart session identifier

The guest cart identity is the weakest trust boundary in the system, because it is the only identifier that grants access to data without authentication.

| Property | Requirement |
|---|---|
| Generation | Client-generated UUIDv4, or server-issued on first cart interaction. Must not be sequential, derived from user data, or reused across devices. |
| Transport | `X-Cart-Session` request header. Never a URL path or query parameter — those land in access logs, browser history and referrer headers. |
| Storage (client) | `flutter_secure_storage` (Keychain / Keystore). Not shared preferences. |
| Integrity | HMAC-signed by the server so a forged or enumerated value is rejected without a database lookup. |
| Lifetime | 30 days from last activity, then the cart is expired and the identifier is invalid. |
| Scope | Grants access to exactly one `Cart` row and its children. Never to user, profile, order or payment data. |
| On authentication | Consumed by `transfer_cart`, then invalidated. A new identifier is issued on logout. |

**Rule T-1.** No endpoint outside the Cart module may accept `X-Cart-Session` as an authorisation input.

---

## 8. Corrected authentication flow

The current flow issues full privilege before the second factor. The corrected flow:

```
1. POST /auth/token/            {email, password}
   ├─ MFA not enrolled  → 200 {access, refresh}                    [full privilege]
   └─ MFA enrolled      → 200 {pre_auth_token, mfa_required: true}  [no privilege]

2. POST /auth/mfa/verify/       {code, device_type}
   Authorization: Bearer <pre_auth_token>
   → 200 {access, refresh}   access carries mfa_verified: true
```

| Token | Lifetime | Claims | Grants |
|---|---|---|---|
| `pre_auth_token` | 5 minutes | `scope: "mfa_pending"`, `user_id` | `POST /auth/mfa/verify/` **only** |
| `access` | 15 minutes | `mfa_verified: bool` | Per this matrix |
| `refresh` | 14 days, rotating | — | Token refresh only |

**Rule M-1.** A dedicated permission class must reject any request presenting a `mfa_pending`-scoped token at any endpoint other than MFA verification. Scope enforcement cannot rely on the absence of other claims.

**Rule M-2.** Operations marked **MFA** in §5 and §6 require `mfa_verified: true` even when the user has no MFA device enrolled. In that case the operation is refused with a 403 instructing the user to enrol — it does not fall through to permitted.

**Rule M-3.** Refresh must not upgrade privilege. A refresh presented against a token issued before MFA verification returns an access token with `mfa_verified: false`.

---

## 9. Django admin and break-glass access

| Control | Requirement |
|---|---|
| Network exposure | Admin site bound to an internal path, reachable only via VPN or IP allowlist. Never on the public origin. |
| Accounts | Named individual accounts. No shared `admin` account. |
| MFA | Mandatory, no exceptions. |
| Superuser | Break-glass only. Credentials held in escrow, split knowledge, checked out through a logged process, rotated after every use. |
| Session | 30-minute idle timeout. |
| Audit | Every admin action written to the audit log (§10) with actor, object, before/after. |

---

## 10. Audit requirements

The following must be written to an append-only audit log, retained 7 years (aligned to the tax record retention period; see POPIA pack §8 for the full schedule).

| Event | Fields |
|---|---|
| Authentication success / failure | actor, IP, user agent, method (password / social / MFA / backup code) |
| MFA enrol, verify, disable, backup code generation and consumption | actor, device id, outcome |
| Password change / reset | actor, initiator, IP |
| Role or Permission create / update / delete | actor, target role, before/after JSON |
| Role assignment or revocation | actor, subject, role |
| `transfer_cart` | actor, source cart id, target cart id, item count |
| Order state transition | actor (may be SY), order id, from, to |
| Refund issued | actor, order id, amount, reason |
| Any admin-site write | actor, model, pk, before/after |
| Personal information export or erasure | actor, subject, scope, ticket reference |

**Rule L-1.** Audit records must not contain passwords, tokens, card data, MFA secrets or backup codes — hashed, truncated or omitted.

**Rule L-2.** The audit log must be writable by the application and not modifiable by it. Ship to a separate store with append-only retention.

---

## 11. Findings summary

| ID | Severity | Finding | Reference |
|---|---|---|---|
| F-01 | **P0** | `PermissionViewSet` and `RoleViewSet` open to any authenticated user — full privilege escalation | §5.3 |
| F-02 | **P0** | `UserViewSet.queryset = User.objects.all()` exposes all users' email and phone to any authenticated caller | §5.1 |
| F-03 | **P0** | MFA does not gate access; full token issued on password alone | §5.5, §8 |
| F-04 | **P0** | `transfer_cart` accepts an unverified session identifier and destructively merges | §6.2 |
| F-05 | **P0** | Password reset unreachable; permission whitelist references non-existent actions | §5.6 |
| F-06 | **P1** | Guest cart update / remove / save-for-later return 404 for anonymous users | §6.1 |
| F-07 | **P1** | `mfa/disable` requires no re-authentication | §5.5 |
| F-08 | **P1** | `SocialAccount` creatable via API; `provider_id` exposed in responses | §5.4 |
| F-09 | **P2** | RBAC defined but apparently not connected to users (assumption A1) | §2 |
| F-10 | **P2** | `Permission.module` free text; `action` duplicates the `can_*` flags | §2 |

---

## 12. Verification

Each rule requires an automated test. Minimum suite before this document can be marked Approved:

| Test | Asserts |
|---|---|
| `test_customer_cannot_list_users` | 403 for CU on `GET /auth/users/` |
| `test_customer_cannot_create_permission` | 403 for CU on `POST /auth/permissions/` |
| `test_customer_cannot_read_other_profile` | 404 for CU on another user's profile |
| `test_password_only_token_is_pre_auth` | Token from `/token/` for an MFA-enrolled user is rejected at every endpoint except `/mfa/verify/` |
| `test_mfa_disable_requires_recent_auth` | 403 without recent re-authentication |
| `test_guest_can_update_own_cart_item` | 200 for AN with a valid `X-Cart-Session` |
| `test_guest_cannot_update_foreign_cart_item` | 404 for AN with a different session identifier |
| `test_transfer_cart_rejects_unsigned_session` | 400 for a forged session identifier |
| `test_transfer_cart_rejects_foreign_session` | 403 where the session was not issued to the caller |
| `test_social_account_create_is_not_routed` | 405 on `POST /auth/social-accounts/` |

**Rule V-1.** A pull request that changes any `permission_classes`, `get_permissions` or `get_queryset` declaration must reference this document and update it in the same commit. CI should fail the build if those symbols change without a corresponding change to this file.

---

## 13. Change log

| Version | Date | Author | Change |
|---|---|---|---|
| 0.1 | *(pending)* | *(pending)* | Initial draft from code review of the authentication and cart modules |
