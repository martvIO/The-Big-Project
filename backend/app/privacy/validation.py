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
