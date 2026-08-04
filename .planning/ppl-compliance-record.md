# PPL compliance record — MODRYN

**Status**: v1, written at F20 (PPL compliance build, Amendment 13, Epic E4).
**Owned by**: the platform operator. Versioned in the repo alongside `security-checklist-v1.md`.
**Discharges**: `security-checklist-v1.md` row 43 — *"Processing-activities record started; incident-response procedure written"* — as sections 1 and 3.

> ⚠ **Not reviewed by a lawyer and not legal advice.** Every factual claim below is derived from the code as it stands on this branch and carries a citation, so a reviewer can check it rather than take it. The *legal characterisation* of those facts — legal basis, notification thresholds, statutory deadlines — is the open counsel item recorded in the spec's Risk 1, and the places where a legal reading is asserted rather than verified are marked **[counsel]**.

**Rule of maintenance.** This record describes the code, so it goes stale the moment the code moves. Any change that adds a data class, a column holding personal data, a sub-processor, a recipient, or a retention clock **amends this file in the same PR**. Nothing in CI can catch a missed amendment (spec Risk 7); the mitigation is that the platform sub-processor list is a *public* document (`PLATFORM_SUBPROCESSORS_HE`) that publicly promises a new supplier appears in the list *before* it is used.

---

## 0. Who is who, and what this record covers

| Role | Who | Evidence |
|---|---|---|
| **Controller** (בעל מאגר) | **the boutique** — one per tenant. Each boutique is a separate database under the PPL; the platform holds no database of its own about brides. | `architecture.md:13,20`; the manage disclaimer states it to the owner in Hebrew (`copy.md` String 5a clause 2) |
| **Processor** (מחזיק) | **MODRYN**, the platform operator, for every tenant | `PLATFORM_DPA_HE` names MODRYN as the processor (`copy.md` String 3) |
| **Sub-processors** | Railway, Twilio (conditional), AWS — §1.4 below | derived from code, not from the spec |
| **Data subjects** | brides and their companions (booking + walk-in), and the boutique's own staff | four collection points, §1.1 |

**Tenancy is the isolation boundary.** Every table holding personal data carries `tenant_id` and is under **forced** row-level security keyed to `current_setting('app.tenant_id')` (`app/db/rls.py:16` issues `FORCE ROW LEVEL SECURITY`); the application connects as a **non-superuser** role and the worker and API both assert it at boot (`app/db/session.py:44 ensure_safe_database_role`). One boutique cannot read another's subjects, and neither can a bug that forgets a `WHERE`.

### The four shipped collection points

| # | Surface | Route | Personal data taken | Notice shown |
|---|---|---|---|---|
| 1 | Booking form, `details` step | client-side until submit | name, free-text notes, dress/size preference, **marketing opt-in** | the resolved `notice_text` block, in full, above the card |
| 2 | Phone verification | `POST /storefront/otp/send` (`app/notifications/router.py:50`) | mobile number | two navigations after point 1; the field's own purpose hint |
| 3 | Booking create | `POST /storefront/bookings` (`app/booking/router.py:82`) | all of the above, plus terms acceptance | same notice, still on screen |
| 4 | **Walk-in check-in** | `POST /storefront/checkin` (`app/queue/router.py:86`) | name, mobile number, visit type, **marketing opt-in** | `checkin.notice` + `checkin.optIn`, point-specific, including the public-board clause |

Point 4 is **not** in the spec's design (which predates F33) and is the reason this record has a `queue_tickets` class. Staff records are a fifth collection point but not a public form — the employer is controller toward its own staff; see class **F**.

**One publication.** The walk-in queue board (`POST /storefront/queue`, `app/queue/router.py:107`) publishes each waiting woman's **first name only** (`board_display_name`, `app/queue/service.py:200`) on an anonymous public web page scoped by Host. This is a disclosure to the world, not to a processor, and `checkin.notice` states it at the moment of collection.

---

## 1. Processing-activities record (§17B)

Per data class: categories of subject and data, purpose, legal basis, recipients and sub-processors, retention period **with the `Settings` key that enforces it**, security measures.

**Read the retention column with this caveat.** The retention job ships **disarmed**: `retention_enabled: bool = False` (`app/core/config.py:232`, Gate 1 Q2). The clocks below are *implemented, tested and enforceable*, and are *not running on any deployment* until an operator sets `RETENTION_ENABLED=true` — which is gated on F21's tested backup/restore, because the job is an unattended irreversible hard delete. Until then the honest statement of retention for every class is **"the period below, once enabled; indefinite in the meantime"**, and no public document promises otherwise (`copy.md` finding F4: none of the approved Hebrew strings promises a deletion schedule).

### 1.1 The classes

#### A. `customers` — the bride's identity and the boutique's CRM record

| | |
|---|---|
| **Subjects** | brides who completed an online booking. *(A pure walk-in has no row here — see class C and §2.8.)* |
| **Data** | mobile number (E.164), name, free-text `notes`, `tags[]`, marketing-consent timestamp + source, withdrawal timestamp, erasure timestamp (`app/models/customer.py`) |
| **Purpose** | identifying the returning client across bookings; contacting her about her appointment; the boutique's client record |
| **Legal basis** **[counsel]** | her own submission of the data for the appointment she requested (consent + necessity for the service). The marketing flag is a **separate** basis: §30A opt-in, unbundled and default-off |
| **Recipients** | the boutique's OWNER and SHIFT_MANAGER (full record); all five staff roles see the **name** only, on the floor panel (§1.5); Railway (hosting); Twilio (the number only, when sending is enabled) |
| **Retention** | **SCRUB**, not purge. `retention_orphan_customer_seconds` = 30 d (`config.py:241`), and only once no booking points at the row and `erased_at IS NULL` (`app/privacy/retention.py:312-356`). In practice the row therefore lives as long as her longest-lived booking (7 y) and is then anonymised in place |
| **Why scrub** | `bookings.customer_id`, `alteration_tickets.customer_id` and F22's waitlist are no-FK pointers; a purge leaves them dangling with no way to tell "erased" from "never existed" |
| **Security** | forced RLS per tenant; owner/shift-manager gate on every read route (`app/customers/router.py:76`, `app/booking/owner_router.py:83`); `no-store` on every `/manage` response; unique index on `(tenant_id, phone)` so an erasure placeholder is per-row |

#### B. `bookings` — the appointment and the terms-acceptance evidence

| | |
|---|---|
| **Subjects** | brides with an appointment |
| **Data** | appointment time, seat, status, dress name/size, **free-text notes**, terms version + acceptance timestamp, check-in and attendance timestamps, cancellation, and a **hashed** manage-link token (`app/models/booking.py`) |
| **Purpose** | performing the appointment; the boutique's business and tax record; proof of which cancellation terms she accepted |
| **Legal basis** **[counsel]** | performance of the service she asked for; the terms-acceptance columns are the boutique's own evidence |
| **Recipients** | OWNER, SHIFT_MANAGER; the booking id and client label reach all five roles on the floor picker (`app/floor/router.py:472`) |
| **Retention** | **PURGE** at `starts_at` + `retention_bookings_seconds` = 7 y (`config.py:240`), **with that booking's `scheduled_messages` in the same statement batch** (`retention.py:274-309`) |
| **Security** | the manage link is stored as **sha256 only** (`app/booking/tokens.py`), so the database never holds a usable link; RLS; role gate; `no-store` |

#### C. `queue_tickets` — the walk-in check-in

| | |
|---|---|
| **Subjects** | walk-ins, including women who never book online and therefore appear **nowhere else** |
| **Data** | name, mobile number (normalised E.164), visit type, queue day, position/skip state, **marketing opt-in timestamp** (`app/models/queue_ticket.py`) |
| **Purpose** | running the queue for one trading day |
| **Legal basis** **[counsel]** | her submission at the counter for the service she is queueing for. The opt-in is §30A and separate |
| **Recipients** | OWNER, SHIFT_MANAGER (full ticket, `app/queue/manage_router.py:62`); **all five roles** see the name on the floor waitlist; **the public** sees her first name on the queue board |
| **Retention** | **SCRUB** at `queue_day` + `retention_queue_ticket_seconds` = 7 d, floor 2 d (`config.py:238`, `:350`). `name` and `phone` are `NOT NULL`, so blanking is a placeholder (`[erased]` / `erased:{id}`), never NULL (`retention.py:221-255`) |
| **⚠ The scrub is unconditional** | An opted-in ticket is scrubbed like any other. The shipped interim notice promised to keep an opted-in woman's contact detail "until she asks to remove the consent" — i.e. **with no clock at all**, in a store no send path reads. F20 drops that promise (the copy is rewritten) and builds the half she is actually entitled to: the ability to revoke (§2.6, phone arm). Plan DR-11 / `copy.md` F5 |
| **A submission record, not a consent record** | `queue_tickets.marketing_opt_in_at` evidences that *someone typed a number at a counter*. There is no possession proof of any kind on this form. It is **not** promoted into `customers.marketing_consent_at` and must not be: laundering an unverified submission into Spam-Law evidence would degrade every row in that column. **No send path consults it, and none may** (`app/queue/service.py:120-124`; plan DR-10 / Risk R-A) |
| **Security** | RLS; the board response carries a first name and nothing else — no id, no phone, no last name |

#### D. `message_log` + `scheduled_messages` — SMS

| | |
|---|---|
| **Subjects** | brides who received or were queued an SMS |
| **Data** | `message_log`: phone, message **body**, kind, status, carrier message id, error text (`app/models/message_log.py`). `scheduled_messages`: booking id, kind, send time, and the **raw** manage token held until send (`app/models/scheduled_message.py:33`) |
| **Purpose** | delivering the OTP, the confirmation and the reminders; diagnosing a failed send |
| **Legal basis** **[counsel]** | necessary to deliver the service she requested |
| **Recipients** | the boutique (bodies are visible in the customer CRM); **Twilio when sending is enabled** — see §1.4 |
| **Retention** | `message_log`: **PURGE** at `created_at` + `retention_message_log_seconds` = 730 d, floor 180 d (`config.py:239`, `:351`). `scheduled_messages`: purged with their booking (class B), never on a clock of their own |
| **Security** | OTP codes are **masked out of the stored body** before insert (`mask_otp_body`, `app/notifications/validation.py:61`, applied at `service.py:272`); nothing provider-supplied but an integer error code leaves the Twilio adapter, so a 4xx payload quoting the submitted body can never be written to `message_log.error` (`app/notifications/twilio.py` module docstring). `provider_message_id` and `error` are **structurally absent** from the subject export — the response model has no field for them |
| **Erasure guard** | `send_sms` refuses any phone carrying the `erased:` prefix **before** the `message_log` insert and **before** the adapter call. It is the single writer of `message_log`, so the guard holds for callers that do not exist yet |

#### E. `otp_codes` — phone verification

| | |
|---|---|
| **Subjects** | anyone who requested a verification code |
| **Data** | phone, **hashed** code, expiry, attempt count, hashed verification token (`app/models/otp_code.py`) — the code itself is never stored in the clear |
| **Purpose** | proving she controls the number before a booking is created |
| **Legal basis** **[counsel]** | necessary for the service, and a security control the checklist requires |
| **Recipients** | none beyond the boutique's database; Twilio carries the code in the message body when sending is enabled |
| **Retention** | **PURGE** at `created_at` + `retention_otp_seconds` = **900 s** (`config.py:237`). The floor is **computed**, never written as a number: `OTP_TTL_SECONDS + VERIFICATION_TOKEN_TTL_SECONDS` (`config.py:349`), because 15 minutes is *exactly* the longest life anything on the row can have and there is nothing below it that would be safe |
| **Security** | sha256 code and token hashes; per-phone and per-IP rate limits; single-use |

#### F. `staff_users` + `sessions` — the boutique's own employees

| | |
|---|---|
| **Subjects** | the boutique's staff |
| **Data** | email, display name, **argon2** password hash, role, break state, weekly capacity (`app/models/staff_user.py`); sessions hold a sha256 token hash and an expiry only (`app/models/session.py`) |
| **Purpose** | authenticating the console; rostering |
| **Legal basis** **[counsel]** | the employment relationship. **The employer is the controller toward its own staff**; the platform ships the *text* of a staff notice in the manage privacy section and per-employee delivery is the boutique's HR process |
| **Recipients** | the boutique's OWNER (staff CRUD is owner-only, `app/auth/staff_router.py:63`) |
| **Retention** | `sessions`: **PURGE** once `expires_at` has passed **or** the row is revoked — no new setting, because `session_ttl_seconds` (`config.py:24`, 12 h) already writes `expires_at` at mint time and a second knob would be a second source of truth (`retention.py:201-218`). `staff_users`: **no policy at F20** — the ex-staff scrub is F38's, and it inherits this registry's SCRUB shape |
| **Security** | argon2 password hashing (`app/auth/passwords.py`); cookies are `HttpOnly` + `Secure` + `SameSite=Lax` (`app/auth/cookies.py:14-16`); operator password reset via audited CLI only |

#### G. `alteration_tickets` — the atelier ⚠ **gap, stated rather than papered over**

| | |
|---|---|
| **Subjects** | brides with a garment in alterations |
| **Data** | `customer_id` (a pointer, no name snapshot), dress name/size, due date, effort, **free-text `notes` — in practice her measurements** (`app/models/alteration_ticket.py:82`) |
| **Purpose** | running the alterations workflow |
| **Recipients** | OWNER, SHIFT_MANAGER **and SEAMSTRESS** (`app/atelier/router.py:99`). The seamstress board carries `customer_name` and the notes; `customer_phone` is deliberately withheld from it |
| **Retention** | **NONE. This table has no retention policy at F20.** |
| **Erasure** | **The `subject-erase` transaction does not touch it.** Her alteration notes survive an erasure, linked by `customer_id` to a row that by then carries `[erased]` and an `erased_at` stamp |
| **Reading taken** | Recorded, not silently absorbed. The surviving text is a garment record (measurements, hem, bustle) rather than an identity record, and after the erase it resolves only to an anonymised customer row — the same *de-identified with a controlled re-identification key* status as the surviving bookings (§2.5). It is nonetheless free text a person wrote about a named woman, and an erasure that leaves it is weaker than one that does not. **Owner: F21's audit, or F38 (which extends this registry) — whichever comes first. Until then §2.8's manual procedure covers it: the owner clears the notes by hand on the atelier card before invoking the erase.** |

#### H. `payments` — deposits

Amounts, status, timestamps, provider session/transaction ids, booking id (`app/models/payment.py`). **No name, no phone, no free text.** `app_user` holds no `DELETE` on this table or on `tenant_gateway_credentials` (migration `0012:147-148`) — a hard delete would destroy financial evidence and the credential-rotation trail — so **no retention policy may name either**, and a test walks `policy.tables` to prove none does. Consequence, accepted and recorded: the 7-year booking purge leaves a payment row pointing at a booking that no longer exists (plan Risk R-B). Not a disclosure of personal data; a dangling financial record.

#### I. `audit_log` and `platform_audit_log` — the evidence

`audit_log` records tenant-scoped operator actions, including **both** privacy subject routes (`privacy_subject_exported`, `privacy_subject_erased`) and every retention run that actually touched rows. `platform_audit_log` is **INSERT-only** — `app_user` cannot even `SELECT` it (`0004:39-40`).

**Both are exempt from every retention class, permanently and deliberately.** Giving the audit trail a clock would eventually erase the proof of the erasures. That exemption is exactly why the write discipline is strict:

- `details` on a subject route carries `customer_id`, **`phone_last4` only**, counts and `reason` — **never a name, never a full number** (`app/privacy/service.py:571-590`; the shipped `_last4` idiom from `owner.py:93-96`, *"the most of a number that may be written down"*).
- `details` on a retention run carries row counts, the action and the **table names** only.
- The `reason` field is capped at 500 bytes and the manage form carries a hint stating it must record **why, never who** (§2.7).

#### J. Dress media on S3

`dress_media` rows carry a storage key, content type, byte size (`app/models/dress_media.py`). The key embeds `tenant_id`, `dress_id`, `media_id`. **There is no customer-facing upload path anywhere in the product**, so the bucket holds the collection's dress photographs and **no personal data of any bride**. Served by short-lived signed URL.

### 1.2 Summary table — class → clock → `Settings` key

| Class | Action | Clock | `Settings` key | Default | Floor |
|---|---|---|---|---|---|
| `otp_codes` | PURGE | `created_at` + | `retention_otp_seconds` | 900 s | `OTP_TTL_SECONDS + VERIFICATION_TOKEN_TTL_SECONDS` (computed, = 900 s) |
| `sessions` | PURGE | `expires_at` passed, or revoked | *(none — `session_ttl_seconds`)* | 12 h | — |
| `queue_tickets` | SCRUB | `queue_day` + | `retention_queue_ticket_seconds` | 7 d | 2 d |
| `message_log` | PURGE | `created_at` + | `retention_message_log_seconds` | 730 d | 180 d |
| `bookings` (+ their `scheduled_messages`) | PURGE | `starts_at` + | `retention_bookings_seconds` | 7 y | 3 y |
| `customers` | SCRUB | orphaned **and** `created_at` + **and** `erased_at IS NULL` | `retention_orphan_customer_seconds` | 30 d | 7 d |
| — | — | job cadence | `retention_poll_interval_seconds` | 3600 s | 60 s |
| — | — | **master switch** | **`retention_enabled`** | **`False`** | — |

Registry: `app/privacy/retention.py:361-372`. Keys and floors: `app/core/config.py:227-241`, `:326-354`.

Three properties worth stating because they are enforced rather than intended:

1. **Every floor sits within an order of magnitude of the default it guards**, so a *dropped digit* — the realistic fat-finger, not `=0` — is rejected at boot. `RETENTION_BOOKINGS_SECONDS` mistyped one digit short lands at 255 days and is refused; without the floor the next tick would hard-delete every booking older than 255 days including its terms-acceptance evidence.
2. **Retention is platform policy, not tenant policy.** There is no per-tenant retention field and there will not be one: a boutique may not choose its own retention for a duty the platform enforces on its behalf.
3. **The job enumerates `list_all()`, never `list_active()`** — suspended and soft-deleted tenants get their clocks run too. Otherwise a boutique suspended for non-payment or off-boarded would keep every bride's name, phone, notes and SMS body forever, which is precisely where abandoned data sits.

### 1.3 Where the record is written

- Scheduled: the existing `worker` process, third job in the loop, own `try` so a wedged retention run cannot silence another boutique's reminders or F19's deposit sweeper (`app/worker.py:132`, `retention_tick`).
- Operator-invoked: `python -m app.cli retention --operator NAME [--dry-run]`. `--operator` is `required=True` **on this subcommand only** — the five other subcommands default it to `$USER`, and `$USER` on a shared box is not an audit identity for an irreversible multi-tenant delete. One `platform_audit_log` row per invocation.
- `--dry-run` counts what each policy *would* touch and issues no write. **This is how the first real run against production data is inspected before `RETENTION_ENABLED` is ever set.**

### 1.4 Sub-processors

**The principle, applied uniformly**: *the list names every processor the platform is built to use, and says of each whether it is in use today.* The public Hebrew list (`PLATFORM_SUBPROCESSORS_HE`) states that principle in its own opening paragraph, so a conditional entry reads as disclosure rather than as hedging. The list is **platform-owned and structurally un-overridable** — a boutique may rewrite what it promises about processing and may **not** misstate who the processors are (D14).

| Sub-processor | Purpose | Personal data it receives | In use today? | Evidence |
|---|---|---|---|---|
| **Railway** | compute + **managed Postgres** | **all of it** — the database holding every name, phone, note and message body is Railway's | **Yes, unconditionally** | `docs/infra-runbook.md:110-119`: services `api`, `worker`, `Postgres` |
| **Twilio** | SMS delivery | **the mobile number and the full message body** (which carries her appointment time and a manage link) | **Conditionally — and today, no.** `sms_provider` ships **unset** (`config.py:58`) and the only documented deployment runs `APP_ENV=staging` with the `fake` adapter (`infra-runbook.md:123`, `.env.example:33-38`). A real adapter is shipped (`app/notifications/twilio.py`) and `httpx` is a runtime dependency because of it | see below |
| **Amazon Web Services (S3)** | dress photograph storage, region `il-central-1` (Israel) | **none.** No customer-facing upload path exists; keys embed `tenant_id`/`dress_id`/`media_id` | **Yes on the deployed environment** — `media_bucket` ships unset but `infra-runbook.md:211` sets `MEDIA_BUCKET` and `MEDIA_REGION=il-central-1` on both Railway services | `app/storage/s3.py` |
| **Any payments / clearing service** | — | — | **No, and the absence is stated publicly.** `payment_provider` accepts only `"fake"` and `"lemonsqueezy"`, and `_forbid_fake_payment_paths_in_production` raises at boot on **both** when `APP_ENV=production` (`config.py:296-313`). A production tenant therefore **cannot** have a payment gateway configured at all; deposits answer 503 | `config.py:143` |

**Why Twilio is named at all, given it receives nothing today.** The spec instructed, twice, that the record *"must not name Twilio as live, because it isn't"*. That instruction is **stale** and this record amends it rather than following it (plan DR-16 / R-D2). Executing it literally would produce a processing-activities record that omits the carrier every bride's phone number and message body is handed to the moment `SMS_PROVIDER` is set — the exact Risk-7 failure the spec itself names. Asserting Twilio as a present-tense live transfer would be a falsehood on the deployment we actually run. **Only the conditional entry is true in both states**, and note precisely what the boot validator does and does not do: it rejects `"fake"` in production, but `None` **passes** it and `None` is the shipped default and an explicitly supported deployment (OTP send answers 503). So *"in production the only legal value is twilio"* is an invalid inference and is not written here.

**Checked for and not present**: analytics, error tracking (no Sentry), transactional email, CDN, hosted fonts (Hebrew fonts are self-hosted precisely so no external service is called), maps (an outbound `href`, not a request the site makes). The runtime dependency list — `fastapi, uvicorn, sqlalchemy, asyncpg, alembic, pydantic-settings, argon2-cffi, pydantic, boto3, httpx, tzdata, segno` — reaches no service this list omits. **Not named**: Grow (never wired), Lemon Squeezy (a test-mode engine forbidden in production — naming it as a live processor would be a false disclosure), Cloudflare Stream (not built), AWS KMS (`gateway_secret_box` has no such literal yet).

### 1.5 Cross-border transfer

**Railway's region is not documented anywhere in this repo and Railway's defaults are not in Israel.** The public Hebrew list therefore discloses the transfer plainly: the servers and the database are outside Israel, and the information is transferred and stored outside the country. Twilio likewise operates outside Israel. AWS is the only supplier pinned to an Israeli region (`il-central-1`), and it holds none of her data.

**Open item, and it is the most consequential single line in the public copy**: establish the Railway region and name it. Pinning to an EU region is a materially better legal position and is worth doing **before pilot**. **Owner: platform operator. Trigger: pilot go-live.**

### 1.6 Who has access, inside the boutique

`StaffRole` has **five** members (`app/models/constants.py:19-23`), not two, and the console's access surface must be described as it is:

| Role | Full record (name + phone + notes) | Name only | Neither |
|---|---|---|---|
| `owner` | ✅ bookings, customers CRM, queue, atelier, **and the three owner-only privacy routes** | | |
| `shift_manager` | ✅ bookings, customers CRM, queue, atelier, **and `marketing-withdraw`** | | |
| `seamstress` | | ✅ atelier board: `customer_name` + alteration notes (`customer_phone` deliberately withheld) | |
| `reception` | | ✅ floor panel: client label + waiting walk-in names (`/manage/floor`, `/manage/floor/clients`, all five roles) | |
| `sales_assistant` | | ✅ same as reception | |

Full customer phone numbers are reachable only by `owner` and `shift_manager`. The three non-elevated roles reach **names**, on the floor and (for the seamstress) the atelier board. That is F33/F36/F57/F58's shipped and reviewed permission model, not a regression — but it is what this record must describe, or it understates the access surface the product actually has.

### 1.7 Security measures (the record's §17B column, as shipped)

| Measure | As built |
|---|---|
| Tenant isolation | **Forced** RLS on every tenant table, keyed to `current_setting('app.tenant_id')`; non-superuser app role asserted at boot; tenant derived from the **Host**, never from client input |
| Credentials at rest | staff passwords **argon2**; session tokens, manage-link tokens, OTP codes and verification tokens stored as **sha256 only** |
| Session cookies | `HttpOnly` + `Secure` + `SameSite=Lax`, subdomain-scoped |
| Console responses | `Cache-Control: no-store` on every `/manage` router — it matters most on `subject-export`, which answers with a whole person in one document |
| CSRF | `CsrfOriginMiddleware`, gating by **method** rather than by a path list, so every mutating route is fenced by construction |
| Rate limiting | per-tenant fixed-window budgets, **one budget per limiter instance**, on OTP and on all three privacy subject routes |
| Secret handling | Twilio credentials are `SecretStr` and never appear in a repr, a log line or a traceback; gateway credentials are encrypted and never logged |
| Log hygiene | OTP codes masked out of the stored message body; nothing provider-supplied but an integer error code is ever written to `message_log.error` |
| Audit | every operator **mutation and read** on a subject is audited with actor, `customer_id` and `phone_last4` |
| **Not yet in place** | HSTS / CSP / `X-Frame-Options` (checklist row 33), WAF (row 32), **automated backups and a drilled restore (row 44)** — the last of which is why `retention_enabled` ships `False` |

---

## 2. Data-subject-request procedure

Written for the **boutique owner**, who is the controller. The platform's role is to give her the buttons, to audit every press, and to make the destructive one hard to press by accident.

### 2.1 Verifying who is asking — the boutique's step, not the platform's

**The platform does not verify the requester's identity and must not.** A platform that verified identity itself would be acting as controller, which it is not. Its controls are that only an owner may export or erase, that every invocation is audited, and that this document tells the owner how to verify.

Before acting on any request:

1. **Prefer a channel you already hold.** Ring the number on file and confirm the request with the person who answers. A request arriving from that number, or confirmed on a call to it, is the strongest proof available in this product — she proved control of that number to book.
2. **If the request arrives another way** (email, a message from a different number, in person), ask for two facts only a client would know that are **not** in the request itself — e.g. the date and time of a past appointment, or the dress she tried. Do not ask her to send an identity document; you are not required to hold one and holding one creates a new record you would then have to protect.
3. **In person**, an ID may be *inspected* and must not be *copied, photographed or filed*.
4. **If you cannot satisfy yourself**, say so and ask for more. A refusal you can explain is safer than an erasure you cannot justify — and an erasure performed for the wrong person is unrecoverable and is itself a breach.
5. **Record what you did, not who she is.** See §2.7.

### 2.2 The clock

**30 days from receipt** for access and erasure. **[counsel]**

It is **procedural and is not enforced in code** — there is no reminder, no ticket queue and no deadline field, deliberately: nothing in v1 can receive a request electronically, so a request-tracking table would have exactly one writer and one reader, both of them the owner. **Diary the date the request arrived and the date you answered.** F24's client portal is the natural trigger for building the queue.

### 2.3 Which console action serves which right

| Right | Console action | Who may invoke | Notes |
|---|---|---|---|
| **§13 access** — "show me what you hold" | Privacy → **Look up** (`POST /manage/privacy/subject-export`) | OWNER only | Downloads a JSON document. **Hand it to her; the platform does not send it.** |
| **Correction** | phone: F15's booking phone correction. Name and CRM notes/tags: F53's customer detail | OWNER, SHIFT_MANAGER | ⚠ **partial — see §2.9** |
| **§14 erasure** | Privacy → **Erase** (`POST /manage/privacy/subject-erase`) | OWNER only | Irreversible. Two-step, typed confirmation |
| **§30A marketing withdrawal** | **Withdraw marketing consent** — on the privacy panel *and* on the customer's CRM card (`POST /manage/privacy/marketing-withdraw`) | **OWNER and SHIFT_MANAGER** | The lesser action. See §2.6 |

**Why marketing-withdraw is the one privacy route a shift manager may take** (Gate 1 Q4, which overruled the spec's owner-only default): recording a phoned-in opt-out is routine front-desk work, and the person who answers the telephone must be able to honour it while the woman is still on the line. Routing it through the owner would mean telling a caller exercising a statutory right to ring back tomorrow. It destroys nothing, it is idempotent, and it is the lesser action short of erasure. The other three stay owner-only: two of them assemble or destroy a whole person, and the third publishes the boutique's legal notice.

That absence of a gate is a **ruling, not an oversight**, and it is asserted **positively** by `test_marketing_withdraw_is_not_owner_only_in_the_route_table` — because a default-deny walker cannot tell a deliberate omission from a forgotten one. **Adding a `require_role(OWNER)` there to "tidy up" reddens that test.**

### 2.4 The order the API enforces: phone → look-up → id → erase

**The erase is keyed on `customer_id`, never on the phone, and the console cannot skip the look-up.**

The reason is mechanical: step 2 of the erase overwrites `customers.phone` with a placeholder, and the phone look-up is exact equality — so **after the first erase there is no path from her real number back to her row**. Keying the erase on the phone would leave two answers and both are wrong. A 404 on a repeat would contradict "she will click it more than once". A 200-with-zero-counts for any unresolvable phone would mean an owner who mistypes one digit gets a success screen *and* an audit row recording a §14 erasure for a subject who was never touched — **a fabricated compliance record, on the one path where the record is the entire deliverable.**

Keying on the id makes every outcome honest:

| Situation | Answer |
|---|---|
| Unknown phone at look-up | **404 `SUBJECT_NOT_FOUND`** — correct and expected at a look-up step. No audit row: nothing was accessed |
| Erase, unknown `customer_id` | **404**, and **no audit row** |
| Erase, same `customer_id` twice | **200 with zero counts.** The row exists, `erased_at` is set, and the outcome she asked for holds. She tapped twice; that is not an error |
| Erase, live future **confirmed** booking | **409 `SUBJECT_HAS_ACTIVE_BOOKING`** — see §2.10 |

In the console the flow is: type the phone → **Look up** → the resolved subject appears → **Erase** / **Withdraw**, both keyed on the id the look-up returned and both **disabled until it has**. The erase's typed confirmation is **the subject's phone digits re-typed** — an ASCII left-to-right run with no bidi ambiguity in a right-to-left field, already on screen, and not satisfiable by muscle memory.

### 2.5 What erasure removes, and what it does not

**Removed or blanked** (one transaction, holding the per-tenant advisory lock as its *first* statement, so a booking arriving on the public form mid-erase cannot write her real name back onto an erased row):

| Table | What happens |
|---|---|
| `customers` | `name` → `[erased]`; `phone` → `erased:{customer_id}` (per row, so any number of erasures fit under the unique index); `notes` → NULL; `tags` → `{}`; `erased_at` stamped; marketing consent stamped as withdrawn **if one existed** |
| `bookings` (hers) | `notes` → NULL; `manage_token_hash` → NULL — **this is what kills the still-live SMS link** |
| `message_log` | `phone` → placeholder, `body` → `''`, matched on **her phone OR her booking ids**. The `OR` is not belt-and-braces: a past phone correction re-points a booking at an existing customer row and orphans the old rows, so a phone-only predicate would leave her pre-correction number in the log |
| `otp_codes` | **purged** — the whole row is her data |
| `scheduled_messages` (hers) | **purged** — including any raw manage token still held for a future send |

**Not removed — the surviving business record, enumerated so it is a decision and not an omission:**

> `id`, `customer_id`, `appointment_type_id`, `starts_at`, `status`, `seat_index`, `dress_id`, `dress_name`, `dress_size`, `appointment_type_name`, `terms_version_accepted`, `terms_accepted_at`, `attendance_confirmed_at`, **`checked_in_at`**, `cancelled_at`, `cancelled_by`, `created_at`

These are the boutique's business and tax record plus the evidence of which cancellation terms she accepted. Also surviving: the `audit_log` rows recording the export and the erasure (`customer_id` + `phone_last4` + counts + reason), her `payments` rows (amounts and provider ids, no name or phone), and — see class G — her **`alteration_tickets` and their notes**, which this transaction does not reach.

**How to describe that survivor set, precisely, and the wording matters:**

> The surviving rows carry **no name, no phone number and no free text**, and are re-identifiable only by an actor who can already read `audit_log` — the owner and the platform operator, both of whom held the data before the erasure. **It is not anonymous data. It is a de-identified business record with a controlled re-identification key.**

Say that, in those words, if you are ever asked. Calling it "anonymous" would be a claim that fails the first time someone opens the audit log — and the `customer_id` **must** be in that log, because it is the only thing that makes an Amendment-13 complaint answerable at all.

### 2.6 The marketing opt-out — the lesser action short of erasure

**A consent taken with no way to withdraw it is not a consent.** If the only route to stopping marketing were "have your entire record destroyed", the withdrawal right would be theoretical. It is a separate, non-destructive action: **one nullable timestamp, idempotent, nothing lost.**

**Offer it first** whenever the request is really "stop contacting me". Many are.

It has **two arms**, and which one you use depends on how she reached the boutique:

| Arm | Body | What it does | Answer |
|---|---|---|---|
| Booked online | `{"customer_id": …}` | stamps `customers.marketing_consent_withdrawn_at` | `changed: true`, or `false` if already withdrawn or never consented |
| **Walk-in** | `{"phone": …}` | clears `queue_tickets.marketing_opt_in_at` for that tenant and normalised number, **across every day**, not just today — a consent she gave three visits ago is still a consent she is revoking | `changed: true/false` |

Exactly one of the two fields may be sent; the schema rejects both-set and neither-set.

**An unknown phone is a 200 with `changed: false`, not a 404** — and that is deliberate. A woman who never ticked the box and a number the boutique has never seen are the same outcome she asked for, and a 404 here would turn a front-desk revocation into a presence oracle over the queue. An unknown `customer_id` **does** 404, because the console only ever sends one it got from a look-up.

**Withdrawal is additive and never erases the consent.** `marketing_consent_at` stays. Proving a consent *existed at the moment a message was sent* is the Spam-Law defence; clearing it would destroy the evidence. Effective consent = `marketing_consent_at IS NOT NULL AND marketing_consent_withdrawn_at IS NULL`.

**The phone arm never writes `customers`.** It exists so the revocation sentence in the walk-in consent copy is *true for a walk-in*, not to promote her unverified submission into a provable consent (class C).

### 2.7 The `reason` field — record **why**, never **who**

`reason` is optional free text on both subject routes, capped at 500 bytes, and it lands in `audit_log` — **the one table exempt from every retention class, forever.**

- **Write**: «בקשת מחיקה טלפונית שאומתה מול הלקוחה» — *a telephone deletion request, verified with the customer.*
- **Never write**: her name, her number, or any other identifying detail.

The reason is the same reason the audit payload stores only the last four digits: writing a phone number here would put a permanent copy of the identifier into the one table designed never to be erased, **inside the very action that exists to destroy it.** A test asserts no subject name or full number reaches `audit_log.details` — but it fires *after* the owner has typed it. The hint under the field is the only control that fires before.

### 2.8 ⚠ A walk-in who never booked online — the manual procedure

**The console cannot look her up, and this is a known, recorded gap** (plan Risk R-H).

A `customers` row is only ever created inside `create_booking`, and the walk-in queue deliberately does **not** promote a ticket into one. So for a pure walk-in:

- **`marketing-withdraw` works** — use the `phone` arm (§2.6). This is the one right the console serves her.
- **`subject-export` 404s**, and `subject-erase` is unreachable, because it is keyed on the id that look-up would have returned.

**Serve §13 and §14 for her by hand:**

1. Verify her identity per §2.1.
2. **§13 access** — she is entitled to what is held. In practice that is her open or recent queue tickets (name, mobile, visit type, day, queue history) and any fitting-room assignment they produced. Read them off the queue panel and give her a written answer. If she also has an alteration ticket, include its details.
3. **§14 erasure** — for each of her tickets, ask the platform operator to run the erasure by hand against the `queue_tickets` rows for that tenant and number. Do the same for any `alteration_tickets.notes` (class G). **Record the request and the action in your own diary**, since no `audit_log` row is written for a manual operation.
4. **Note the default outcome if she asks nothing**: once retention is enabled, her ticket's name and phone are scrubbed automatically 7 days after the visit.

Extending the look-up to `queue_tickets` would require inventing a subject identity for a table that deliberately has none — there is no uniqueness on it beyond the primary key. That is a design decision F20 declined to make under a blocker. **Owner: user/team. Trigger: F24's client portal, or F46 — whichever first needs a walk-in to be a resolvable subject.**

### 2.9 ⚠ Correction is only partly served

| Datum | Correctable today? |
|---|---|
| Phone number | ✅ F15's booking phone correction |
| Name | ✅ via F53's customer detail card, **or** it updates itself on her next booking |
| CRM `notes` / `tags` | ✅ F53's customer detail card |
| **`bookings.notes`** | ❌ **not correctable by any surface.** |
| **`alteration_tickets.notes`** | ✅ editable on the atelier card |

If she asks for a booking note to be corrected and it cannot be edited, the honest answer is that it can be **removed** — the erase blanks it — but not amended. Recorded as spec Risk 4; F53 was the named trigger and it closed the `customers` half only.

### 2.10 The refusal case — a live future booking

**`subject-erase` refuses with 409 `SUBJECT_HAS_ACTIVE_BOOKING`** while she holds a `confirmed` booking whose `starts_at` is in the future.

This is not obstruction. The erasure duty yields to performing the contract she is still party to: silently erasing a bride with a fitting on Thursday would break the appointment and the SMS link at once, and she would arrive to a boutique with no record of her.

**What to do**: tell her the appointment must be cancelled or completed first, and offer the choice. Then cancel it (or let it pass) and re-run the erase. **Offer the marketing withdrawal in the meantime** — it has no such precondition and is very often what she actually wanted.

### 2.11 What to keep after a request

Keep, in your own diary: the date the request arrived, the channel, how you verified her, what you did, and the date you answered. Keep **no copy of the exported document** once you have handed it over — it is a complete assembly of a person and holding a spare copy is a new risk with no purpose. The platform keeps the audit row automatically; it holds the actor, the id, four digits and your `reason`, and nothing else.

---

## 3. Incident-response procedure

Discharges `security-checklist-v1.md` row 43's second clause. **Written for the platform operator**, with the boutique's own steps marked. **[counsel]** applies to every legal threshold in §3.3.

### 3.1 What counts as an incident

Any event that may have exposed, destroyed or altered personal data without authorisation. Concretely, in this system:

- Cross-tenant leakage — one boutique reading another's subjects. **The highest-severity class this architecture has**, because RLS is the whole isolation model.
- Credential compromise — a staff session, a Railway or AWS key, Twilio credentials, or the database role.
- Unauthorised or unexplained bulk read of `subject-export`, or an erase nobody can account for.
- Data destroyed unintentionally — a mis-set `RETENTION_*` env var, an erase performed on the wrong subject, a bad migration.
- A sub-processor's own breach notice (Railway, Twilio, AWS).
- Manage-link tokens or OTP codes exposed in a log, a screenshot or a support channel.
- Loss or theft of a device holding a live console session.

### 3.2 Detection sources

| Source | What it shows |
|---|---|
| `audit_log` | every privacy export and erase, with actor and timestamp; every retention run that touched rows; every operator mutation |
| `platform_audit_log` | every CLI invocation, with the named operator — **INSERT-only, so it cannot be tidied afterwards** |
| Application logs (Railway, `api` + `worker`) | per-tenant retention failures are logged with `logger.exception` and counted in `failed_tenants` rather than swallowed |
| `message_log.status` / `.error` | delivery anomalies, sends to unexpected numbers |
| The boutique | the most likely reporter — a client says she received something she should not have, or sees someone else's details |
| Sub-processor status pages and security notices | Railway, Twilio, AWS |
| Dependency scanning in CI | `pip-audit` / `npm audit` |

**There is no alerting.** Nothing pages anyone; the worker runs three jobs in one unsupervised loop with no liveness signal (plan Risk R-F). Detection today is a human reading logs or a boutique telephoning. **State that plainly rather than implying a monitored posture, and treat it as the first thing to fix. Owner: F21's hardening pass.**

### 3.3 The response, in order

**Step 1 — Contain, before investigating.** Revoke what can be revoked: rotate the exposed credential, revoke the staff sessions (`sessions` are DB rows; deleting or expiring them logs the actor out immediately), disable the affected staff account. If tenant isolation is in question, **take the service down** rather than leave it serving cross-tenant data — an outage is recoverable and a leak is not.

**Step 2 — Preserve the evidence, and do this *before* anything is cleaned up.** See §3.4. Nothing below is possible without it.

**Step 3 — Establish scope.** Which tenants, which subjects, which data classes, over what window, and by what route. `audit_log` and `platform_audit_log` are the primary sources; Railway request logs are the secondary one.

**Step 4 — Decide on notification.**

- **Always notify the affected boutique(s) immediately.** The boutique is the controller; the platform is its processor, and a processor that learns of a breach and sits on it has failed its first duty. Notify even when the eventual assessment is "no real risk" — **that judgement is the controller's to make, not the processor's.**
- **The regulator (the Privacy Protection Authority).** Israel's Data Security Regulations require notification of a **severe security incident** for databases at the applicable security level, and the Authority may direct that data subjects be notified. **Whether a given incident crosses that threshold, and on what timetable, is a counsel question and must be asked at the time, not guessed from this document.** **[counsel]** The trigger to call counsel is: *any incident where personal data may have left the boutique's control, or where you cannot rule that out.*
- **Data subjects.** Notify where there is a real risk to them — and treat "her mobile number, her name and the free-text notes about her" as a real risk by default. The boutique notifies her; it holds the relationship and it is the controller. The platform supplies the facts.

**Step 5 — Remediate and verify.** Fix the cause, not the symptom. Confirm the fix with a test that would have caught the incident — the cross-tenant isolation suite is the standing example, and it is blocking and never removed.

**Step 6 — Write it up.** One dated entry appended to this file's §3.5: what happened, when it was detected and by whom, scope, what was done, who was notified and when, root cause, and the test or control added. A file with no entries and a file with three honest entries look very different to an auditor, and the second is the credible one.

### 3.4 Evidence to preserve — capture before you clean

1. **`audit_log` and `platform_audit_log` rows** for the window, exported. `platform_audit_log` cannot be altered by the application role at all; `audit_log` has no retention policy, so it will still be there — but export it anyway, because a restore or a rollback could move it.
2. **Application logs from both Railway services** for the window. Railway's retention is finite and shorter than any investigation. **Export first, investigate second.**
3. **A database snapshot at the moment of detection**, if one can be taken. ⚠ **There is no automated backup and no drilled restore today** (checklist row 44) — this step may be impossible, which is itself part of the incident and must be recorded as such.
4. **The exact configuration in force**: every `RETENTION_*` value, `RETENTION_ENABLED`, `SMS_PROVIDER`, `APP_ENV`, and the deployed commit sha. A mis-set env var is a plausible cause and the value must be captured before anyone "fixes" it.
5. **The reporter's own words**, verbatim, and the time they were received.
6. **Do not**: delete logs, `git push --force`, run the retention CLI, re-run a migration, or "clean up" a suspicious row. Every one of those destroys evidence, and doing it after a breach is a second, worse problem.

### 3.5 Incident log

*(No incidents recorded. Append one dated entry per incident, newest last, per §3.3 step 6.)*

---

## Appendix — the security-checklist rows this record touches

| Row | Text | Verdict at F20 |
|---|---|---|
| 39 | Privacy notice per tenant; DPA text in boutique ToS | **green** |
| 40 | Consent captured …; marketing opt-in separate, unbundled, default OFF; **opt-out honored in every marketing send** | **amber** — the send-time clause has no subject until a marketing send exists. *Owner: F46* |
| 41 | PII-scrub job (true erasure, not soft-delete) tested | **green** |
| 42 | Retention jobs per data class running | **amber** — shipped and tested for all six classes, but `retention_enabled` ships `False`. *Owner: F21* (the queue-entry clause **closed at F20**) |
| 43 | Processing-activities record started; incident-response procedure written | **green** — this file, §1 and §3 |

Splitting rows 40 and 42 into their per-owner clauses is F21's edit, not F20's. This table is the input to it.
