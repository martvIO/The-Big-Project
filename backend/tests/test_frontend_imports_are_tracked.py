"""Every relative import in a git-TRACKED frontend module must resolve to a
file that is itself git-tracked.

This is the locally-green / CI-red shape, and it is the third time this repo has
been bitten by a frontend source file that exists on a developer's disk but not
in the commit. Twice it was `.gitignore`'s unanchored Python `lib/`, `dist/` and
`build/` rules silently eating same-named frontend directories; the third was
F33's `apps/storefront/src/lib/checkinTicket.ts`, simply never `git add`ed while
the two committed modules that import it were. In every case the working tree
builds, `pnpm -r test` is green, and the failure appears only on a fresh clone —
`tsc --noEmit` cannot find the module and the app does not build.

Read through `git ls-files` rather than the disk, because the disk is exactly
what lies here. Kept in the fast, no-Node suite for the same reason
`test_frontend_constant_parity.py` is: a regex scrape is enough for specifiers,
and this must fail in the backend job long before anyone waits on a build.

Paths are spelled lowercase (`frontend/...`) because git tracks them lowercase;
macOS resolves them case-insensitively and Linux CI checks them out that way.
"""

import posixpath
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# A specifier is relative when it starts with "." — the only kind whose target
# TypeScript and Vite resolve against the file system, so the only kind a
# missing file can break. Bare specifiers are node_modules' problem, and the
# workspace's own "@boutique/*" packages resolve through pnpm.
#
# `vi.mock` is scraped alongside the import forms deliberately: vitest resolves
# its path the same way, and a mock pointing at a module that is not in the
# commit fails the same way an import does.
SPECIFIER = re.compile(
    r"""(?:\bfrom|\bimport|\bvi\.mock|\brequire)\s*\(?\s*["'](\.[^"']*)["']""",
)

# Extensionless specifiers are the norm in this workspace. The candidate order
# mirrors TypeScript's own: the literal path first (that is how `.css`, `.svg`
# and `.json` imports resolve), then the module extensions, then the directory
# index.
CANDIDATE_SUFFIXES = ("", ".ts", ".tsx", ".d.ts", "/index.ts", "/index.tsx")


def _tracked_frontend_files() -> list[str]:
    completed = subprocess.run(
        ["git", "ls-files", "--", "frontend"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in completed.stdout.splitlines() if line]


def test_every_relative_import_in_a_tracked_frontend_file_is_itself_tracked() -> None:
    tracked = set(_tracked_frontend_files())
    modules = [path for path in tracked if path.endswith((".ts", ".tsx"))]
    assert modules, "no tracked frontend modules found — the git query is broken"

    dangling: list[str] = []
    for path in modules:
        source = (REPO_ROOT / path).read_text(encoding="utf-8")
        parent = Path(path).parent.as_posix()
        for match in SPECIFIER.finditer(source):
            specifier = match.group(1)
            # `posixpath.normpath`, not `Path.joinpath` — Path keeps ".."
            # segments verbatim, and `Path.resolve()` would touch the disk,
            # which is the thing this test may not trust.
            resolved = posixpath.normpath(posixpath.join(parent, specifier))
            if any(f"{resolved}{suffix}" in tracked for suffix in CANDIDATE_SUFFIXES):
                continue
            dangling.append(f"{path} imports {specifier!r} — no tracked file resolves it")

    assert dangling == [], (
        "a committed frontend module imports something that is not in the commit; "
        "a fresh clone does not build:\n  " + "\n  ".join(dangling)
    )
