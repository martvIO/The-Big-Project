"""Named bounds for the privacy surface.

Deliberately NOT `Settings` fields: F8's rule is that `Settings` carries
deployment identity and never product policy, and the size of a legal document
is product policy. (The retention *periods* are the exception the plan argues
separately — they are an operator's policy dial, not a document's shape.)
"""

# The cap on ONE stored override — `notice_text` or `dpa_text` — measured in
# UTF-8 BYTES, because that is what Postgres stores and Hebrew is two bytes a
# character. A character cap would silently halve the allowance for the only
# language these documents are written in.
#
# 8 KB is chosen against the platform defaults it must hold: the longest is the
# collection notice at 3 746 bytes, so a boutique's own lawyer can roughly double
# it before hitting the wall. `test_privacy_text.py` asserts every default fits,
# which is what keeps the editor from prefilling text it would then refuse to
# save back.
MAX_PRIVACY_TEXT_BYTES = 8 * 1024

# The two placeholders a SCRUB writes in place of a person. They live here rather
# than in `retention.py` because the erase ENDPOINT (F20 C4) writes exactly the
# same pair, and `notifications/service.py` reads the prefix to refuse a send —
# three modules, one spelling, no import cycle through the retention registry.
#
# ASCII and one LTR run: an RTL console renders it with no bidi care at all, and
# the alternative (exposing `erased_at` on every owner row plus new manage copy)
# is two schema changes and a frontend change to say what one literal says.
ERASED_NAME = "[erased]"
# PER-ROW, never a constant: `idx_customers_tenant_phone_unique` is UNIQUE on
# (tenant_id, phone), so the placeholder is `erased:{id}`. A constant would make
# the SECOND row in a 500-row scrub chunk raise, roll the whole chunk back, and
# repeat that failure on every tick for every tenant past the clock, permanently.
# It is also un-sendable: `normalize_israeli_mobile` rejects it outright.
ERASED_PHONE_PREFIX = "erased:"
