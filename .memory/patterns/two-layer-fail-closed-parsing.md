# Pattern: Two-layer fail-closed input parsing

For security-critical identifier parsing (host→slug, and Feature 6's provisioning
CLI slug intake): split extraction from validation and require BOTH to pass.
`extract_slug` returns the raw candidate (or None on structural failure);
`is_valid_slug` independently re-validates charset + reserved list. The consumer
treats "extractor returned None OR validator rejected" as one failure path.

**Why:** each layer catches what the other misses (extractor: structure, domains,
IP/IPv6, ASCII; validator: charset, length, reserved names). A refactor of one
layer can't silently reopen a hole the other still covers — and tests should pin
BOTH layers plus the combined pipeline (see `backend/tests/test_slugs.py`).

**Origin (2026-07-21, Feature 4 review):** the Gate 3.5 reviewer noted several
hostile host shapes failed closed only as an emergent property of the two checks;
tests now lock the pipeline behavior in. Reuse this shape in Feature 6 rather
than a single validation call.
