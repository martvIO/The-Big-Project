---
name: brain-sync
description: Reconcile the .brain code wiki with the repo — rewrite stale pages, remove orphans, regenerate the index. Use when the SessionStart summary reports stale or orphan pages, or after a batch of code changes.
---

# /brain-sync

Bring `.brain/` back in step with the working tree. This is the **only** sanctioned way to
fix drift — never reconcile pages inline in the middle of unrelated work.

Read `.brain/CLAUDE.md` first if you have not already this session.

## 1. Assess

```bash
bash .brain/scripts/brain-scan.sh --summary --max 0
```

Report the counts to the user. If `pending.tsv` has entries, skim it for the narrative of
*what changed recently and when* — but remember the queue is advisory only. The authority for
what needs work is always the scan, which recomputes `page.blob != git hash-object(file)`.

## 2. Rewrite stale pages (cap: 25 per invocation)

For each stale path, in order, up to 25 (the cap bounds a single invocation so a long-neglected
wiki cannot blow the session's context — tell the user how many were deferred):

1. Read the page's `commit:` field.
2. `git log --oneline <commit>..HEAD -- <path>` — what touched it.
3. `git diff <commit>..HEAD -- <path>` — exactly what changed.
4. **Rewrite only the sections the diff affects.** Do not regenerate the page from scratch:
   it is roughly 5× cheaper and it preserves hand-written `## Notes`.
   If the diff is whitespace/formatting only, just refresh the frontmatter.
5. Update `blob:` (`git hash-object <path>`), `commit:` (`git rev-parse HEAD`), and `updated:`.

If a file's *role* changed enough to alter its `Depends On` / `Depended On By` links, update the
counterpart pages too — a one-sided link is a lint failure.

## 3. Missing pages — report, do not build

```bash
bash .brain/scripts/brain-scan.sh --missing --max 0 | sed 's|/[^/]*$||' | sort | uniq -c | sort -rn
```

Report the count grouped by directory and name the next unbuilt wave. Then **stop** and offer
`/brain-ingest <dir>`. Building pages is an ingest operation, not a sync operation — do not do
it here.

## 4. Orphans

An orphan is a page whose `path` is no longer in `git ls-files` (file deleted or renamed).

For each: confirm with the user, then delete the page and remove its entry from the parent
`_index.md`. Before deleting, report which inbound `[[wikilinks]]` will break:

```bash
grep -rl "\[\[<path>\]\]" .brain/wiki/
```

If it was a **rename**, prefer moving the page to the new path and updating inbound links over
delete-and-recreate — that preserves the hand-written content.

## 5. Regenerate and log

```bash
bash .brain/scripts/brain-index.sh
bash .brain/scripts/brain-scan.sh --lint
```

Fix any lint failures. Then append exactly one entry to `.brain/wiki/log.md`:

```
## [YYYY-MM-DD] sync | 12 stale reconciled, 1 orphan removed
Rewrote pages for backend/app/auth/*. Removed page for deleted backend/app/old.py.
```

Rotate the queue if it has grown past 500 lines:

```bash
[ "$(wc -l < .brain/queue/pending.tsv)" -gt 500 ] && \
  mv .brain/queue/pending.tsv ".brain/queue/pending.$(date +%Y%m).tsv"
```

## Rules

- The code is right; the page is wrong. Never edit a repo file to make a page true.
- Never hand-edit `.brain/wiki/index.md` — it is generated.
- `.brain/wiki/log.md` is append-only. Never edit an existing entry.
- `.brain/` is excluded from its own corpus. The wiki does not document itself.
