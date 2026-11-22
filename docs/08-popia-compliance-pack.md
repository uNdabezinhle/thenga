# POPIA Compliance Pack

| | |
|---|---|
| **Document ID** | REKA-CMP-001 |
| **Version** | 0.1 (Draft) |
| **Owner** | Information Officer |
| **Contributors** | Tech Lead, Legal Counsel, DevOps |
| **Jurisdiction** | Republic of South Africa |

> **Not legal advice.** This pack translates statutory obligations into engineering and operational work. Every customer-facing document it references must be drafted or reviewed by a qualified attorney before publication.

---

## 1. Why POPIA and not GDPR

The originating modules document lists "GDPR Compliance" under Security & Compliance. **This is very likely the wrong statute.**

GDPR binds an organisation only where it targets or monitors data subjects in the EU. A business operating from Johannesburg selling to South African customers is bound by:

| Act | Governs |
|---|---|
| **POPIA** (Act 4 of 2013) | Processing of personal information |
| **PAIA** (Act 2 of 2000) | Access to information; the manual obligation |
| **ECTA** (Act 25 of 2002) | Electronic transactions, consumer disclosure, cooling-off |
| **CPA** (Act 68 of 2008) | Consumer rights generally |

Adopt GDPR obligations **only** if the business decides to sell into the EU. Doing so pre-emptively imports cost without benefit — and, more damagingly, creates a false sense that compliance is handled when the binding local obligations remain unmet.

---

## 2. Document register

| # | Document | Owner | Status | Legally required |
|---|---|---|---|---|
| 1 | Information Officer appointment letter | Head of organisation | Not started | Yes |
| 2 | Information Officer registration with the Information Regulator | Information Officer | Not started | **Yes** |
| 3 | PAIA Manual | Information Officer | Not started | **Yes** |
| 4 | Privacy Policy / Notice (customer-facing) | Legal Counsel | Not started | Yes |
| 5 | Records of Processing Activities | Information Officer | This document, §5 | Yes |
| 6 | Personal Information Impact Assessment | Information Officer | Not started | Yes (Regulation 4) |
| 7 | Data Subject Request Procedure | Information Officer | This document, §7 | Yes |
| 8 | Retention & Disposal Schedule | Information Officer | This document, §8 | Yes |
| 9 | Operator (processor) agreements | Legal Counsel | Not started | **Yes** (s21) |
| 10 | Breach Notification Procedure | Security Officer | This document, §10 | **Yes** (s22) |
| 11 | Consent & direct marketing records | Product Owner | Not started | Yes (s69) |
| 12 | Staff awareness training record | Information Officer | Not started | Yes (Regulation 4) |
| 13 | Cross-border transfer assessment | Information Officer | This document, §9 | Yes (s72) |

---

## 3. Roles

| POPIA role | Who | Notes |
|---|---|---|
| **Responsible Party** | The Reka operating company | Determines purpose and means of processing |
| **Information Officer** | By default the head of the organisation | **Must be registered with the Information Regulator before taking up the duties.** Registration is compulsory for all responsible parties |
| **Deputy Information Officer** | Optional | The Information Officer remains accountable regardless of delegation |
| **Operators** | Hosting provider, payment provider, courier, email provider, SMS provider, error-tracking provider, analytics provider | Each requires a written agreement under s21 |

**Information Officer duties (s55 and Regulation 4):** develop and maintain a compliance framework; conduct a personal information impact assessment; develop and maintain a **PAIA manual**; establish internal measures for handling information requests; run internal awareness sessions.

> **The PAIA manual is the most commonly missed obligation.** Every private body must compile one describing what information the organisation holds, how a person may request access to it, and whom to contact. A privacy policy on the website does not satisfy it.

**Action:** appoint and register before development reaches staging. Registration is administrative lead time that cannot be compressed later.

---

## 4. The eight conditions mapped to system controls

| # | Condition | Control in Reka |
|---|---|---|
| 1 | **Accountability** | Information Officer registered. This pack maintained in-repo and reviewed each release |
| 2 | **Processing limitation** | Collect only what a purpose in §5 requires. `date_of_birth` is collected only if age verification is genuinely needed — otherwise removed from the model |
| 3 | **Purpose specification** | §5 records purpose and lawful basis per data category. Retention schedule in §8 |
| 4 | **Further processing limitation** | Order data is not repurposed for marketing without separate consent. Enforced by data access review, not by convention |
| 5 | **Information quality** | Customers can correct their own profile and addresses (REKA-FR-AUTH-017). Staff corrections are audited |
| 6 | **Openness** | Privacy notice presented at registration and linked from every screen collecting personal information. PAIA manual published |
| 7 | **Security safeguards** | §6 |
| 8 | **Data subject participation** | §7 |

---

## 5. Personal information inventory

Classification codes match the Data Model document: **D** direct identifier · **I** indirect · **S** special personal information (s26) · **F** financial.

| Category | Fields | Class | Purpose | Lawful basis | Retention |
|---|---|---|---|---|---|
| Account identity | email, username, phone_number | D | Authentication, service communication | Contract | Account life + 12 months |
| Profile | first_name, last_name, avatar, preferences | D | Personalisation, delivery | Contract | Account life + 12 months |
| Date of birth | date_of_birth | D | **Only if age verification is required** | Legal obligation, or **do not collect** | Account life |
| Address | recipient_name, line1–2, suburb, city, province, postal_code, recipient_phone | D | Delivery | Contract | 7 years with the order |
| Credentials | password hash, MFA secret, backup code hashes | — | Authentication | Contract | Account life |
| Social identity | provider, provider_id, provider tokens | D | Federated sign-in | Consent | Until unlinked |
| Cart & session | cart session identifier, cart contents | I | Shopping | Legitimate interest | 30 days from last activity |
| Order history | order lines, totals, references | I | Fulfilment, tax records | Contract + legal obligation | **7 years — overrides erasure** |
| Payment | provider token, card_last4, card_brand | F | Payment, refunds, disputes | Contract | 7 years |
| Delivery tracking | carrier, tracking number, delivery events | I | Fulfilment | Contract | 3 years |
| Reviews | rating, title, body, author link | I | Product information | Consent | Until withdrawn; anonymise on erasure |
| Support | tickets, correspondence | I, possibly **S** | Customer service | Contract | 3 years |
| Marketing consent | channel, category, timestamp, source | I | Direct marketing | **Consent (s69)** | 3 years after withdrawal, as proof |
| Audit log | actor, IP, user agent, action | I | Security, legal | Legal obligation | 7 years |
| Device tokens | FCM/APNs token, platform | I | Push notification | Consent | Until unregistered |

**Special personal information (s26).** Reka should not process race, health, religion, biometrics or criminal history. **If support correspondence begins capturing health information** — a customer explaining a medical reason for a return — that is special personal information arriving through an unplanned channel. Train support staff not to record it, and review free-text ticket fields periodically.

---

## 6. Security safeguards (s19)

| Control | Requirement | Reference |
|---|---|---|
| Access control | Enforced per the Access Control Matrix, with automated tests | REKA-SEC-001 |
| Least privilege | Staff see only what their role requires. The current open `PermissionViewSet` is a **direct s19 failure** | ACM §5.3 |
| Encryption in transit | TLS 1.2 minimum, HSTS | Env Spec §4 |
| Encryption at rest | Database volumes and object storage encrypted. MFA secrets and provider tokens encrypted at field level | Data Model §2 |
| Password storage | Argon2 | NFR-SEC-002 |
| Card data | Never stored, logged or transmitted. SAQ A | ADR-0011 |
| Audit | Append-only, application cannot modify | ACM §10 |
| Log hygiene | Personal information scrubbed at the formatter, not the call site | Env Spec §11, Rule E-9 |
| Backups | Encrypted, access-controlled, restore-tested quarterly | Env Spec §8 |
| **Non-production data** | **No production personal information in local, CI or staging.** Synthetic only | Env Spec Rule E-2 |
| Patching | Dependency scanning every commit; critical CVEs within 7 days | Test Strategy §9 |
| Penetration testing | Before go-live, annually, and after any authentication change | NFR-SEC-010 |
| Operator oversight | s21 agreements, reviewed annually | §11 |

> A copied production database in staging is the single most common POPIA failure in software teams. It is a breach the moment a developer laptop is lost. Environment Rule E-2 exists for this reason.

---

## 7. Data subject rights

| Right | Section | Implementation | SLA |
|---|---|---|---|
| Be notified of collection | s18 | Privacy notice at registration and at each collection point | At collection |
| Access | s23 | REKA-FR-ADM-004 — export a subject's data as structured JSON | 30 days |
| Correction | s24 | Self-service for profile and addresses; staff correction audited | 30 days |
| Deletion / destruction | s24 | REKA-FR-ADM-005 — see the tension below | 30 days |
| Object to processing | s11(3) | Marketing preference centre; withdrawal honoured immediately | Immediate |
| Object to direct marketing | s69 | Unsubscribe in every message; opt-in recorded with timestamp and source | Immediate |
| Complain to the Regulator | s74 | Contact details in the privacy notice and PAIA manual | — |

### The erasure tension

**A deletion request cannot delete everything, and pretending otherwise is itself non-compliance.** Orders, invoices and payment records are retained under tax and consumer-protection law. The correct behaviour:

| Data | On erasure request |
|---|---|
| Profile, addresses, preferences, avatar, device tokens | Delete |
| Cart, saved items, wishlist | Delete |
| Account credentials, MFA devices, social links | Delete |
| Reviews | Retain content, sever the author link (`SET NULL`) |
| **Orders, order lines, payments, invoices** | **Retain 7 years.** Replace personal identifiers with a pseudonymous reference |
| Audit log | Retain 7 years. Retain the actor reference — an audit log with erasable actors is not an audit log |

The response to the data subject must **state plainly what was deleted and what was retained, and cite the legal basis for retention.** A silent partial deletion is worse than a refusal.

**Engineering implication:** the erasure path is not `user.delete()`. It is a service that walks the model graph applying the table above, writes an audit event, and produces a certificate of what it did. It must be built (REKA-FR-ADM-005) and tested, not improvised on the first request.

---

## 8. Retention & disposal schedule

| Data | Retention | Trigger | Basis |
|---|---|---|---|
| Guest cart | 30 days | Last activity | Legitimate interest |
| Abandoned authenticated cart | 12 months | Last activity | Legitimate interest |
| Account (inactive) | Account life + 12 months | Last sign-in | Contract |
| Orders, invoices, payment records | **7 years** | Order date | Tax legislation |
| Delivery tracking | 3 years | Delivery | Contract |
| Support tickets | 3 years | Closure | Contract |
| Marketing consent records | 3 years after withdrawal | Withdrawal | Proof of consent |
| Audit log | 7 years | Event | Legal, security |
| Application logs | 30 days hot, 12 months cold | Write | Operational |
| Backups | 35 days | Creation | Operational |
| Penetration test reports | 5 years | Issue | Governance |

**Rule.** Disposal is automated, scheduled and logged. A retention schedule nobody executes is evidence of intent, not of compliance. Implement as a `celery-beat` job with a report of what was purged.

---

## 9. Cross-border transfers (s72)

Personal information may leave South Africa only where the recipient is subject to comparable protection, the data subject consents, or it is necessary for contract performance.

| Service | Likely location | Assessment required |
|---|---|---|
| Cloud hosting | Confirm region. **Prefer `af-south-1` (Cape Town)** to avoid the question entirely | Yes |
| Payment provider | Local providers keep processing domestic; international ones do not | Yes |
| Email provider | Commonly US or EU | **Yes** |
| Error tracking (Sentry) | US or EU. **Configure PII scrubbing and consider self-hosting** | **Yes** |
| Push (FCM / APNs) | US | Yes — device tokens are personal information |
| Object storage | Match the hosting region | Yes |

**Action:** complete a transfer assessment per operator before go-live, and record the outcome. Choosing a South African hosting region for the primary datastore removes the largest part of this problem.

---

## 10. Breach notification (s22)

Where there are reasonable grounds to believe personal information has been accessed or acquired by an unauthorised person, the Responsible Party must notify **the Information Regulator and the affected data subjects** as soon as reasonably possible after discovery.

| Step | Owner | Target |
|---|---|---|
| 1. Detect and triage | On-call engineer | Immediate |
| 2. Contain | Security Officer | 1 hour |
| 3. Assess scope — whose data, which fields, how many | Tech Lead + Information Officer | 24 hours |
| 4. Notify the Information Regulator | Information Officer | As soon as reasonably possible |
| 5. Notify affected data subjects | Information Officer | As soon as reasonably possible |
| 6. Remediate | Tech Lead | Per severity |
| 7. Post-incident review, register updated | Security Officer | 14 days |

**Notification to data subjects must state** the nature of the compromise, the measures being taken, what the person can do to protect themselves, and the identity of the unauthorised person where known.

**Prerequisite:** step 3 is impossible without the audit log and the personal information inventory. **You cannot report what you cannot enumerate.** This is the strongest operational argument for building the audit log in Phase 0 rather than Phase 5.

---

## 11. Operator agreements (s21)

Every operator processing personal information on Reka's behalf requires a written agreement establishing that they:

- process only on documented instruction from Reka
- maintain security measures at least equivalent to §6
- notify Reka immediately of any compromise
- do not sub-contract without authorisation
- return or destroy data on termination
- permit audit

| Operator | Category | Agreement |
|---|---|---|
| Hosting provider | Infrastructure | Required |
| Payment provider | Financial | Required |
| Courier | Delivery addresses | Required |
| Email provider | Contact details | Required |
| SMS provider | Phone numbers, MFA codes | Required |
| Error tracking | Potentially anything captured in a trace | **Required — highest risk of accidental capture** |
| Analytics | Behavioural | Required |

> Error tracking deserves particular attention. Sentry captures request bodies and local variables by default. Without scrubbing configured, a stack trace from a checkout error can contain an address, an email and a phone number — silently, at volume, into a third-party system outside South Africa.

---

## 12. Consent & direct marketing (s69)

Direct marketing by electronic means to a person who is **not an existing customer** requires prior consent. For existing customers, marketing about similar products is permitted with a clear opt-out at collection and in every message.

| Requirement | Implementation |
|---|---|
| Opt-in is a deliberate act | Unticked by default. Never bundled with terms acceptance |
| Consent recorded | Channel, category, timestamp, IP, and the exact wording shown |
| Withdrawal honoured immediately | Preference centre plus one-click unsubscribe |
| Withdrawal is as easy as consent | No sign-in required to unsubscribe from email |
| Proof retained | 3 years after withdrawal |

> The Information Regulator has publicly identified direct-marketing non-compliance and breach management as enforcement priorities, and has issued R5 million fines for failures to comply with enforcement notices. Abandoned-cart emails (REKA-FR-NOT-004) are direct marketing and require this treatment.

---

## 13. Engineering backlog

Work that must exist in code, drawn from the sections above.

| # | Item | Phase | Blocking |
|---|---|---|---|
| P-01 | Fix the open `RoleViewSet` / `PermissionViewSet` — a direct s19 failure | 0 | **Go-live** |
| P-02 | Restrict `UserViewSet` queryset — currently exposes all customer contact details | 0 | **Go-live** |
| P-03 | Audit log model and write path | 0 | **Breach reporting** |
| P-04 | PII scrubbing in the logging formatter and Sentry configuration | 0 | Go-live |
| P-05 | Field-level encryption for MFA secrets and provider tokens | 1 | Go-live |
| P-06 | Synthetic data generator for staging | 1 | **Any staging use** |
| P-07 | Data subject export service (REKA-FR-ADM-004) | 4 | Go-live |
| P-08 | Erasure service implementing §7 (REKA-FR-ADM-005) | 4 | Go-live |
| P-09 | Retention purge job implementing §8 | 4 | Go-live |
| P-10 | Consent model and preference centre | 4 | Before any marketing |
| P-11 | Privacy notice presented at registration | 1 | Go-live |
| P-12 | Cookie consent for Flutter Web | 2 | Web launch |
| P-13 | Remove `date_of_birth` unless a purpose is confirmed | 0 | — |
| P-14 | Mask `MFADevice.identifier` and remove `provider_id` from responses | 0 | Go-live |

---

## 14. Compliance calendar

| Activity | Frequency |
|---|---|
| Information Officer registration current | On appointment, and on change |
| PAIA manual review | Annually |
| Personal information inventory review | Every release affecting the data model |
| Operator agreement review | Annually |
| Staff awareness training | On induction, then annually |
| Retention purge verification | Quarterly |
| Penetration test | Annually |
| Breach procedure walkthrough | Annually |
| Cross-border transfer reassessment | On any new operator |
