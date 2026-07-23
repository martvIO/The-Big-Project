---
tags: [symlink]
sources: [<PATH>]
created: <DATE>
updated: <DATE>
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: <PATH>
blob: <GIT_HASH_OBJECT>
commit: <GIT_HEAD>
kind: symlink
applicability: active
---

# <PATH>

Symlink → `<TARGET>`.

Content is documented at [[<TARGET_PATH>]] — this page is a stub so that the 1:1
invariant (one page per tracked file) holds. Git tracks symlinks as mode `120000`
blobs whose content is the target path string, so `blob` above is the hash of that
string, not of the target's contents.
