# Research Insights — themes, empathy, and forward hooks

**Created**: 2026-07-22 · **Inputs**: 5-lens competitive pass (`competitors.md`) + PRD/epics. Interview validation pending (`interview-status.md`) — themes below are evidence-based from the market scan; interviews test the demand-side assumptions.

## Themes

1. **The appointment IS the product.** Every serious player converts to a fitting, not a sale. Storefront hierarchy: photography → booking CTA → trust. (Confirms the brief's flows.)
2. **WhatsApp-first culture is a design constraint, not an enemy.** Booking must beat 10–20 WhatsApp messages while offering wa.me as the familiar side door; confirmations should be WhatsApp-shareable artifacts (E3).
3. **Trust furniture is concrete and local**: real address, live open/closed status, Waze link, tap-to-call, real-bride photos, testimonials. Directories (mit4mit, t.co.il) will be cross-checked regardless — the profile must out-credential them.
4. **Price opacity is strategy, not laziness** — but brides self-qualify by budget. Per-boutique/per-dress visibility (hidden / range / exact) serves couture and ready-to-wear; a price-*band* filter can work even when exact prices are hidden (F8 data, F10 UI).
5. **The premium register is restraint**: near-monochrome chrome, one gold CTA, air, disciplined type. Sale-badge/promo language is the single clearest de-luxury signal in the Israeli market.
6. **Accessibility is a legal-and-brand double win**: lawsuits target exactly our tenants' profile; AA-native + auto-generated statement + first-party menu is both protection and a visible quality marker.

## Empathy snapshots (to be validated in interviews)

**Noa (bride)**: *Says* "אם אין מחירים כנראה שזה יקר מדי בשבילי" · *Thinks* "Is this place my level? Will they laugh at my budget?" · *Does* screenshots dresses at 23:00, sends to sister; DMs three boutiques, hears back from one · *Feels* excited-then-filtered-out.
**Rivka (owner)**: *Says* "כל היום אני על הוואטסאפ" · *Thinks* "A no-show Friday costs me more than this software ever will" · *Does* juggles paper diary + GCal + IG DMs; sends the same price-list photo 30×/week · *Feels* proud of the craft, embarrassed by the website.

## How Might We

1. HMW let a bride judge budget-fit without forcing boutiques to publish prices?
2. HMW make booking a fitting faster than sending one WhatsApp message?
3. HMW make a 3-person boutique look Galia-Lahav-tier online without a designer?
4. HMW make the cancellation policy feel like professionalism instead of hostility?
5. HMW keep WhatsApp as a comfort channel without it re-becoming the booking system?
6. HMW make accessibility a selling point owners brag about?

## Forward hooks (recorded here so later specs inherit them — NOT F9 scope)

| Feature | Hook from research |
|---|---|
| **F8 catalog** | Structured dress attributes from day one (silhouette/neckline/fabric/train + **modest** facet — large religious segment; plus-size, second-dress as local conventions) · price-band field even when hidden · portrait 3:4 enforced at upload w/ crop · required-or-prefilled alt text composed from attributes (compliance via data model) · curated named collections (never year folders) |
| **F10 storefront** | No-login favorites (localStorage) feeding "dresses I want to try" into booking · 3-facet filter max + load-more with "הצגת 24 מתוך 57" progress · "more like this" strip on dress pages · real-brides gallery + testimonials blocks (owner-curated) · optional English toggle (helenakolan pattern) · clean transliterated URL slugs |
| **E3 booking** | Form fields: wedding date (first-class), preferred-contact channel; optional per-boutique budget band · typed appointment menu w/ duration+deposit shown upfront (never hide fees mid-flow) · policy text at confirm step AND in every confirmation message · "any consultant" default · WhatsApp-shareable confirmation · reminder ladder confirm→24h→2h, WhatsApp-first w/ SMS fallback (provider decision F2) |
| **E4 #20 / compliance** | Auto-generated per-tenant הצהרת נגישות page (gov.il checklist as the template), auto-dated, platform-wide bumps · onboarding collects accessibility-coordinator contact + response commitment · physical-salon accessibility fields (parking, ramp, elevator) surfaced near hours · "report an accessibility issue" channel per boutique (cure-window protection) |
| **Marketing/positioning** | "Your brides are yours" — no marketplace, no consumer fees, boutique-branded end-to-end (attacks Fresha/Booksy's worst reviews) · compliance status card in the console as tenant liability protection |

## Rev-1 reconciliations applied from this research

Price convention "5,900 ₪" via enforced `Price` component (LTR-isolated digits) · Waze + Google Maps in `ContactPanel` · first-party `A11yMenu` added to the component system · typography validated (Assistant confirmed as the luxury-tier body; Frank Ruhl Libre kept for display — 7 weights vs Bellefair's 1; Latin-only display serifs banned for Hebrew) · no announcements feature in v1 (stale-content machine) · DressCard reserves a favorites affordance slot (wired in F10).
