# raw/ — intentionally empty

The canonical second-brain schema expects `raw/` to hold immutable copies of source material
(clipped articles, PDFs). **This vault stores no copies.**

The raw corpus for this wiki is **the git working tree at the repo root**, addressed by
repo-relative path. It is immutable in the schema's sense — the wiki never edits it — and
mutable in reality, which is precisely why staleness here is tracked by blob SHA
(`git hash-object`) rather than by filename presence in `wiki/log.md`.

See `.brain/CLAUDE.md` § Deviations, items 4 and 5.

If you ever want to ingest genuinely *external* material into this vault (a vendor's API doc,
a spec PDF, a design reference), drop it here and use `/second-brain-ingest` — that skill's
stock flow is correct for external sources. Use `/brain-ingest` for repo files.
