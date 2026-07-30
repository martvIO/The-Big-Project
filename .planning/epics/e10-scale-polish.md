# Epic: E10 — Scale & Polish: Arabic, WhatsApp, Video, Billing, SEO

**Created**: 2026-07-30
**Status**: planning — **roadmap only.** E10 is the tail of the program (ROADMAP: depends on E5+); no feature here gets a spec until its turn arrives, feature by feature, through the same `/spartan:spec` → `/spartan:plan` → `/spartan:build` pipeline every shipped feature has used. This file records the feature split and the decisions the 2026-07-30 interview has already forced on it.

**Numbering**: global scheme, **F45–F49**, promoted from the roadmap's E10-local stub #1–#5. Mapping: #1→F45, #2→F46, #3→F47, #4→F48, #5→F49. The roadmap's title for #2 — "WhatsApp Business API **migration**" — is now wrong: **Interview Q14 turned it into a per-boutique toggle over an SMS default.** F46's brief is the corrected scope.
**Owner**: team
**PRD**: cross-cutting — §2 (per-boutique toggles), §3 (dress media), §5 (platform billing), §6 (comms channels)

---

## Why

E10 is where the platform stops being a pilot. Four of its five features remove a ceiling rather than add a workflow: Arabic doubles the addressable customer base in a country where a fifth of brides don't read Hebrew comfortably; a second comms channel meets brides where they actually read; video is the only honest way to show how a gown moves; automated billing is what makes tenant #10 cost the operator nothing extra to serve; and SEO/prerender plus the owner calendar are the two "the product feels unfinished" complaints that will come out of the pilot.

**E10 is a polish epic and its features are largely independent of each other** — F46 (comms), F47 (media), F48 (money) and F49 (SEO + calendar) touch four disjoint parts of the system and share no data model. **Its internal order is therefore flexible**: take whichever is unblocked. The one hard ordering constraint is **F45**, which depends on every prior feature having shipped its untranslated `ar` resource keys (Interview Q3), so it wants to run **last** in the epic — one translation pass over a closed string set beats five.

Two features are also flexible only on paper because they are **externally blocked by user-owned applications with multi-week lead times** (Meta verification for F46, a Cloudflare Stream account for F47). Per pre-decided #2 the loop parks a blocked feature and moves on; per pre-decided #42 the Meta filing goes in **now, regardless**, so it is aging while the rest of the epic proceeds.

---

## Success Criteria

- [ ] An Arabic-speaking bride browses the catalog, completes a booking and receives her confirmation/reminder messages **in Arabic**, on the same RTL layout Hebrew already uses (no directional rework — pre-decided #47), with a language switcher; the untranslated-`ar`-key debt accumulated since Interview Q3 is closed and a key-parity check keeps it closed
- [ ] A boutique turns WhatsApp on from its own settings and its brides receive confirmations over WhatsApp via Twilio — while **SMS remains the default and authoritative channel for every boutique that has not opted in, and for OTP always** (Interview Q14, chosen against the recommendation); nothing about an SMS-only boutique's behaviour changes
- [ ] An owner uploads a short clip to a dress in `/manage`; the platform transcodes it on Cloudflare Stream and the storefront dress page plays it, keyboard-operable and AA-compliant, with **no reels feed anywhere** (Interview Q16)
- [ ] The operator issues a monthly invoice per tenant — flat base fee plus messaging metered from the existing `message_log` — carrying 18% VAT from the operator's Israeli entity, with **no tax-authority allocation-number integration** and a hard refusal to issue above the allocation threshold (pre-decided #45)
- [ ] Public storefront routes are prerendered at publish time with a per-tenant `sitemap.xml` and `robots.txt` (**not SSR** — pre-decided #46), `/book/*` and `/manage` excluded from indexing; the owner sees her bookings as a month/week calendar layered over F15's existing list API with **no new endpoints and no calendar library** (pre-decided #48)

---

## Features

| # | Feature | Status | Spec | Plan | Depends On |
|---|---------|--------|------|------|------------|
| 45 | Arabic strings + comms templates (go-live) | todo | — | — | F9, F10, F14, F16, F20, F24 · **plus every other string-bearing feature (F15–F44, F46–F49) having shipped its `ar` keys** (Interview Q3) |
| 46 | WhatsApp as a per-boutique channel | todo | — | — | F11, F16, F27 · **externally blocked**: Meta business verification + Twilio WhatsApp sender |
| 47 | Dress-page video + media pipeline | todo | — | — | F8, F9, F10 · **externally blocked**: Cloudflare Stream account |
| 48 | Automated platform billing | todo | — | — | F3, F11, F25 · F46 if it ships first (per-channel rates) · **Gate 1 STOPS for the user** (Interview Q1) |
| 49 | Storefront SEO/prerender + owner calendar | todo | — | — | F4, F8, F9, F10 (SEO half) · F12, F15 (calendar half) |

**Sequencing**: take the unblocked one. F48 and F49 depend on nothing external and are the natural starting pair — F49 needs only shipped code (F15's list API, F10's routes), and F48 needs only F25's console plus a `message_log` that has existed since F11. F46 and F47 are parked behind user-owned applications and get re-checked every iteration (pre-decided #2). **F45 goes last** for the reason in Why: sequenced earlier, F46–F49 would each owe a *translated* `ar` bundle at build time instead of a placeholder one, which is a worse deal than waiting.

**Design gate**: Interview Q2 names only F34 and F42 as novel interaction patterns. Every E10 screen — the language switcher, the video player on the dress page, the invoice list in the console, the month/week calendar grid — is assembled from existing `packages/ui` components against existing tokens and **self-approves** (designer + `design-critic` must both accept). All of them ship Hebrew-first RTL and must pass the blocking `Frontend E2E (Playwright + axe)` job; IS 5568 / WCAG 2.0 AA is a legal requirement, not a gate formality (pre-decided #38's rule, applied here).

---

## Feature Briefs

### Feature 45: Arabic strings + comms templates (L)

**Not a retrofit — the go-live feature.** Per **Interview Q3**, every feature from F15 onward ships `ar` resource keys alongside Hebrew, left untranslated, precisely so that Arabic launch is a translation job rather than a 28-feature sweep. F45 is that translation plus the switch that turns it on.

**IN**: `ar` bundles added to the existing i18next setup in `Frontend/apps/storefront/src/i18n/` and `Frontend/apps/manage/src/i18n/` (**pre-decided #47** — reuse the current RTL layout wholesale); translation of every accumulated untranslated `ar` key; **authoring `ar` from scratch for the pre-Q3 surface** — F9/F10/F14 shipped Hebrew-only (`storefront/src/i18n/he.ts` is ~200 keys today with no sibling `ar` file), so F45 is a translation pass *and* a first-authoring pass, which is what makes it L; a language switcher persisting the choice; `ar` locale formatting for numbers/dates/weekdays via `Intl` (the Israeli week stays Sun–Thu); `lang` attribute switching on `<html>`; and comms templates in Arabic selected per customer off `customers.language`, so F16's confirmation/reminder bodies and F46's WhatsApp templates render in the bride's language.

**OUT**: any directional or layout rework — **no direction-switching logic, no second stylesheet** (#47: Hebrew already paid for RTL and Arabic is also RTL); English; Arabic in the operator platform console (F25 — internal, one operator, Hebrew/English is fine); **and machine-translated legal/policy copy.** The F20 privacy notice, the boutique ToS/DPA and F16's SMS bodies carry legal weight and their Hebrew is already flagged not-lawyer-reviewed (Q8) with counsel sign-off on SMS bodies still a standing gate (Q5) — **those strings need a human Arabic reviewer the user must find** (see Risks). Shipping the product surface in Arabic while legal screens stay Hebrew-only is a legal call for the user, not for the loop.

Also in scope, cheap and worth it: a **key-parity check** (every `he` key has an `ar` key) wired into the existing lint/typecheck path, so Q3's per-feature obligation stops being honour-system.

### Feature 46: WhatsApp as a per-boutique channel (M)

**Interview Q14, chosen against the recommendation: SMS stays the DEFAULT and authoritative channel; WhatsApp is a per-boutique toggle.** This is not a migration and the brief must not be read as one — nothing existing changes behaviour, one channel stays the source of truth, and the accepted cost is that both codepaths exist while most brides keep receiving the channel they are least likely to read.

**IN**: a WhatsApp adapter behind the port that already exists — `Backend/app/notifications/base.py`'s sender Protocol, alongside the fake/unconfigured/real adapters — delivered **through Twilio, not Meta's Cloud API** (**pre-decided #43**: F11 already shipped the provider port and Twilio is the chosen SMS vendor, so a direct Cloud API integration would mean a second set of credentials, webhooks and billing for the same messages). Channel selection stays inside `NotificationService`, which remains the single writer of `message_log`; a `channel` column is added to `message_log` by migration (TEXT, default `sms`) so the Spam-Law evidence trail records which channel carried each send and F48 can meter the two at different rates. The toggle lives in `tenants.settings` JSONB under the `toggles` key, written through F7's atomic single-statement merge (**pre-decided #19**) and surfaced in F27's matrix. Plus: WhatsApp template registration/approval bookkeeping, delivery-status webhook handling, and **SMS fallback** when a WhatsApp send fails or the number is not on WhatsApp — because a confirmation that silently doesn't arrive is worse than the channel the bride ignores.

**OUT**: Meta Cloud API direct integration (#43); any flip of the default, any per-boutique-forced migration, any change to an SMS-only boutique's behaviour (Q14); inbound conversational replies, chat UI, chatbot; marketing broadcasts (Israel's Spam Law requires a separate unbundled marketing opt-in and WhatsApp marketing templates are a different approval class entirely); **and OTP over WhatsApp** — the OTP primitive (F11) is the authentication path for customer booking *and* for staff login (Interview Q11: staff sign in by phone + SMS OTP), and putting template-approval latency plus a second delivery-failure mode on the auth path buys nothing. This epic's reading; F46's spec confirms it.

### Feature 47: Dress-page video + media pipeline (M)

**Interview Q16: short clips on dress pages only** — the owner uploads, the platform transcodes and serves. Movement is the honest reason a gown needs video, and it attaches to a page that already exists rather than a new feed that depends on a weekly content habit.

**IN**: an upload control on the dress editor in `apps/manage`, modelled on F8's presign → upload → confirm flow but pointed at **Cloudflare Stream** via a direct-creator-upload URL (**pre-decided #44** — bundled encoding, storage, delivery and CDN at one per-minute price with no egress fees; **not Mux, not self-hosted ffmpeg**). Playback on F10's `DressPage`: one clip per dress, poster frame, muted, no autoplay. A `dress_videos` sibling table rather than a `kind` discriminator on `dress_media` is this epic's lean, decided at spec: `dress_media`'s invariants don't hold for a Stream asset — its `storage_key` embeds the row's own id and is never mutated, whereas a Stream asset has a provider uid and gains a `ready` state only after transcode. Tenant-prefixed asset naming and signed playback consistent with architecture §4.

**Accessibility is in scope and legally load-bearing**: keyboard-operable controls, no autoplay beyond WCAG 2.2.2's limit, `prefers-reduced-motion` respected. **Clips are enforced silent** — the upload path rejects (or strips) an audio track — so WCAG 1.2.2 Captions (Level A) never becomes an obligation the boutique can't meet. Enforced in code, not by owner discipline (see Risks).

**OUT**: a storefront reels feed of any kind (Q16 — explicitly not built); Mux, self-hosted ffmpeg (#44); customer- or staff-generated video; live streaming; video in comms (SMS/WhatsApp bodies stay text); video anywhere but a dress page; and multi-clip galleries per dress (one clip; a second is a follow-up if the pilot asks).

### Feature 48: Automated platform billing (L)

**Interview Q15: flat base fee plus metered messaging.** Messaging is the only cost that scales with a tenant's behaviour, and the per-tenant `message_log` needed to meter it has existed since F11 — that is the whole reason this shape was chosen.

**F48 is a money feature, so per Interview Q1 its spec STOPS for the user.** It presents its spec at Gate 1 and waits; it does not self-approve like the rest of the epic.

**IN**: platform-scoped tables (no `tenant_id`, RLS-exempt registries in the manner of `tenants` and `platform_audit_log`) for plans, per-tenant subscription, and issued invoices; a monthly metering job on the existing worker entrypoint that counts each tenant's `message_log` rows for the period — **billing rows whose status is `sent`, not `queued` or `failed`**, since that is the operator's own Twilio cost basis, and per channel once F46 exists; invoice line items of base fee + metered messaging + **18% VAT from the operator's Israeli entity** (**pre-decided #45**); amounts in ILS agorot end to end; invoice issue + list surfaced in F25's console, every issuance written to `audit_log`.

**OUT**: **the tax authority's allocation-number (מספר הקצאה) clearance API** — explicitly out per #45, on the basis that a monthly per-boutique fee sits far below the ₪10,000 (Jan 2026) / ₪5,000 (Jun 2026) thresholds. The consequence must be stated rather than buried: **this caps invoice amounts under the allocation-number threshold**, so F48 asserts each invoice total against the live threshold and refuses to issue above it (see Risks). Also out: charging the boutique automatically (no stored card, no direct debit, no Grow-based platform collection — Grow credentials are per-tenant for *her* customers, not for the platform to bill her); dunning and auto-suspension (suspension stays the audited operator action F6/F25 already ships); currencies other than ILS; usage-based pricing on anything but messaging; revenue share on the boutique's deposits.

### Feature 49: Storefront SEO/prerender + owner calendar polish (L)

Two independent halves in one feature, as the roadmap bundles them: both are polish layered over surfaces that already shipped, and neither is big enough to stand alone.

**SEO half.** **Interview Q17: the storefront sits alongside the boutique's existing site** — her Wix site and Instagram link into it, so SEO shrinks to being findable and fast. **IN**: build-time prerender of the public routes the hand-rolled router already enumerates in `storefront/src/router.tsx` (`/`, `/dress/:id`, `/about`, `/accessibility`), plus per-tenant `sitemap.xml` and `robots.txt` resolved by Host through the existing tenancy middleware; per-dress `<title>`, meta description and OpenGraph from the catalog; canonical URLs on `{slug}.modryn.co.il`; `LocalBusiness` JSON-LD from the boutique profile (the one structured-data type a physical shop earns back). **Not SSR** (**pre-decided #46**: the storefront is a Vite SPA and catalog changes are owner-triggered, so re-prerendering on publish is far cheaper than operating an SSR process per tenant).

The spec's central question, named here so it isn't discovered late: "build-time" cannot mean "at `vite build` time" for per-tenant catalog content. The lean is **one shell build plus a per-(tenant, route) HTML snapshot regenerated by a worker job on catalog publish**, cached and served ahead of the SPA — which is what #46's basis actually describes. Snapshot cache keys and storage paths are tenant-scoped, and F3's permanent CI isolation suite must cover them.

**SEO OUT**: per-boutique custom domains, certificate management, any DNS support surface (Q17 — custom domains become a paid upgrade once the pilot proves out); SSR (#46); indexing of `/book/*` or `/manage`, both of which ship `noindex`; analytics or tag-manager integration; content/backlink work.

**Calendar half.** **IN**: a month and week rendering in `apps/manage` **layered over F15's existing bookings list API** — **pre-decided #48: no new endpoints, and no calendar library.** A hand-rolled RTL grid over the Israeli week (Sun–Thu, short Friday, Saturday closed) sourced from F12's availability engine, which is the single source of the tenant's week (pre-decided #33). Clicking a day drops into F15's existing day-filtered list. Keyboard-navigable grid, AA contrast, axe-clean.

**Calendar OUT**: any new endpoint or query param (#48); a calendar dependency; drag-to-reschedule (reschedule stays F15's slot picker, which already carries the deposit); the staff roster overlay (that is F40's board); owner-side `.ics` export (customer `.ics` is F24).

---

## Risks

- **Meta Business / WhatsApp verification is user-owned and not filed.** `external-applications.md` row #5 is `not-started` with a multi-week worst case. **Pre-decided #42: file it now regardless of the channel answer** and move the tracker row to `filed` — it is free, it is slow, and Q14's toggle answer does not remove the need for it. Until it clears, F46 is parked (pre-decided #2). **Owner: user.**
- **F46 sits behind two user-owned gates, not one.** The Twilio WhatsApp sender stacks on top of `external-applications.md` row #4 (SMS sender-ID registration), which is still `blocked — needs the user`. WhatsApp templates then need their own per-template approval. **Owner: user** for the account and filings; team for the template inventory.
- **F47 needs a Cloudflare Stream account** — a new `external-applications.md` row, user-owned, and a **paid per-minute service**, so it needs a spend guardrail at signup the way AWS got an AWS Budgets budget in F2. **Owner: user.**
- **Arabic legal and policy copy needs a human Arabic reviewer the user must find.** This is the one part of F45 the loop cannot do: the F20 collection notice, the boutique ToS/DPA and F16's SMS bodies are legally operative text, the Hebrew defaults are already recorded as not-lawyer-reviewed (Q8) with counsel sign-off outstanding on the SMS bodies (Q5), and Amendment 13 requires the collection notice to be comprehensible at the moment of collection. **A machine-translated privacy notice is worse than no Arabic notice.** **Owner: user** — find an Arabic legal reviewer, or accept Hebrew-only legal screens behind the switcher as a recorded decision.
- **F48's invoice amounts are capped by design, and that cap is legal.** Declining the allocation-number API (#45) is correct at a monthly per-boutique fee, but the thresholds are falling — ₪10,000 (Jan 2026) → ₪5,000 (Jun 2026). F48 must assert every invoice total below the live threshold and refuse to issue above it with an operator alert, so the platform never quietly issues a non-compliant invoice. A tenant growing past it forces the integration. **Owner: user/operator** for the threshold decision; team for the assertion.
- **The operator's own Israeli invoicing obligations are not the boutique's.** F48 issues invoices in the operator's name from the operator's entity, with a statutory retention obligation on them. The invoice format wants the operator's bookkeeper/accountant to look at it once before the first real issuance. **Owner: user.**
- **A prerendered snapshot served under the wrong Host is a cross-tenant catalog leak** — exactly the existential risk F3's permanent isolation suite exists for. Snapshot keys, cache keys and CDN paths are tenant-prefixed and the isolation suite gains cases for them; this is spec scope in F49, not an afterthought. **Owner: team.**
- **Video accessibility is a legal exposure, not a nicety.** IS 5568 / WCAG 2.0 AA is required by law, and a clip with speech triggers WCAG 1.2.2 Captions at Level A — an obligation a boutique owner uploading from her phone will not meet. F47 therefore enforces silence at the upload boundary rather than trusting discipline. **Owner: team** (enforced in code); the boutique remains controller for the content.
- **F45 assumes Q3 was honoured feature by feature, and nothing mechanically checks that today.** If any feature between F15 and F49 skipped its `ar` keys, F45 finds out as untranslated screens. Mitigation is cheap and belongs to the first feature that ships `ar` keys: a `he`/`ar` key-parity check in the existing lint path. Named here so F45 is a translation job, not archaeology. **Owner: team.**

---

## Notes

- **E10's features are largely independent and its internal order is flexible** — that is the epic's defining property and the reason two externally-blocked features don't stall it. The single ordering rule: **F45 last**, because it depends on every prior feature having shipped its `ar` keys (Interview Q3).
- The roadmap's E10 #2 title ("WhatsApp Business API migration") predates **Interview Q14** and is superseded: WhatsApp is a per-boutique toggle over an SMS default, chosen by the user against the recommendation. No spec in this epic may reintroduce a migration reading.
- Where the roadmap's deferral list says "Arabic strings, WhatsApp, video reels, analytics", note that **video reels was narrowed to dress-page clips** (Q16) and **analytics is not an E10 feature** — E9's workshop throughput analytics (pre-decided #41) is the only analytics the program commits to. No analytics feature is invented here.
- F48 is the only E10 feature whose Gate 1 stops for the user (Interview Q1, which names it explicitly). F45, F46, F47 and F49 self-approve.
- Cross-epic reach-back: F46 widens `message_log` (F11) and reuses F16's `scheduled_messages` worker; F48 reads `message_log` as its meter and lands its UI in F25's console; F49's calendar reads F15's list API unchanged and F12's week; F47 extends F8's catalog editor and F10's dress page; F45 touches every string-bearing feature in the program.
