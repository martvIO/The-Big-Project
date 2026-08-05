"""Every BLOCKING job in `ci.yml` must be a deploy gate — mechanically, not by memory.

F21 added `e2e` to `deploy-staging.needs` with a written argument: *"a legal
accessibility requirement that does not block a deploy is not a gate — it is a
report."* The 2026-08-05 review pointed out that the argument applies verbatim to
`audit`, the job the same feature had just taken off `continue-on-error`, and
that `audit` was NOT in `needs`. On a push to `main` — which is unprotected in
this repo — a red `audit` reds the workflow and `deploy-staging` runs anyway.

So the rule stops being a sentence somebody has to remember at the moment they
flip `continue-on-error`, and becomes this file: a job is either warn-only, or it
gates the deploy. There is no third state, and the next job to graduate from
warn-only cannot quietly skip the `needs` line.

WHY THE SCAN IS TEXTUAL. `import yaml` fails `mypy` here (no `types-PyYAML` in
the lock, and adding a dependency to type one test file is worse than this), and
the shape being read is two fixed forms: a job header at two-space indent, and
`needs: [...]` on one line. The anti-vacuity legs below are what make a textual
scan honest — a scanner that silently found nothing would otherwise pass.

Paths are spelled lowercase (`.github/...`) for the same reason the other
repo-hygiene tests are: git tracks them that way and Linux CI checks them out
that way.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"

# The id grammar GitHub Actions actually accepts — letters, `_`, `-`, digits,
# any case — not the lowercase-and-hyphen subset this repo happens to use today.
# The narrow form was found by the 2026-08-05 round-2 review: a job named
# `deploy_prod:` was invisible to the scan and got swallowed into the previous
# job's block, so `test_the_job_table_is_the_one_this_file_reasons_about` passed
# while contradicting its own docstring, and the new job was never classified.
_JOB_HEADER = re.compile(r"^  ([A-Za-z_][A-Za-z0-9_-]*):\s*$")
_NEEDS = re.compile(r"^    needs:\s*\[([^\]]*)\]\s*$")

# The deployer itself cannot be its own prerequisite. Everything else that runs
# on a pull request is either a gate or warn-only.
DEPLOYER = "deploy-staging"


def _jobs(text: str | None = None) -> dict[str, str]:
    """`{job name: the job's own block, verbatim}`. `text` is for the parser's own
    test, which needs a workflow that does not exist on disk."""
    lines = (WORKFLOW.read_text(encoding="utf-8") if text is None else text).splitlines()
    start = lines.index("jobs:")
    blocks: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines[start + 1 :]:
        header = _JOB_HEADER.match(line)
        if header is not None:
            current = header.group(1)
            blocks[current] = []
            continue
        if line and not line.startswith(" "):
            current = None
            continue
        if current is not None:
            blocks[current].append(line)
    return {name: "\n".join(body) for name, body in blocks.items()}


def _directives(block: str) -> list[str]:
    """The block's real YAML lines, comments dropped.

    Not fussiness: this workflow ARGUES with itself in comments — the `audit`
    job's own note says `--ignore-registry-errors` is "the same defect as
    continue-on-error wearing another name" — so a naive substring search finds
    the warning rather than the setting, and reads a warn-only job that is not.
    """
    return [line for line in block.splitlines() if not line.strip().startswith("#")]


def _deploy_needs(block: str) -> list[str]:
    for line in block.splitlines():
        match = _NEEDS.match(line)
        if match is not None:
            return [name.strip() for name in match.group(1).split(",") if name.strip()]
    raise AssertionError(f"{DEPLOYER} declares no `needs:` — it gates on nothing at all")


def test_the_job_table_is_the_one_this_file_reasons_about() -> None:
    """Anti-vacuity, and a change detector. A scan that found no jobs, or a new
    job nobody classified, would make every assertion below pass while proving
    nothing about the workflow that actually runs."""
    assert set(_jobs()) == {"backend", "frontend", "e2e", "brain", DEPLOYER, "audit"}, (
        f"ci.yml's job set moved: {sorted(_jobs())}. Add the new job to this list "
        "and decide, deliberately, whether it is warn-only or a deploy gate."
    )


def test_every_blocking_job_gates_the_deploy() -> None:
    """The whole rule. `continue-on-error: true` is the ONLY exemption, and it is
    the honest one: such a job cannot red the workflow, so it cannot be a gate."""
    jobs = _jobs()
    warn_only = {
        name
        for name, block in jobs.items()
        if any(line.strip() == "continue-on-error: true" for line in _directives(block))
    }
    blocking = set(jobs) - warn_only - {DEPLOYER}
    needs = set(_deploy_needs(jobs[DEPLOYER]))

    # Without a live warn-only job the exemption arm is never exercised, and this
    # test would pass just as well if the exemption were spelled wrong.
    assert warn_only, "no job is continue-on-error — the warn-only arm of this rule is untested"

    assert blocking == needs, (
        "blocking jobs missing from deploy-staging.needs (a red job that does not "
        f"stop the deploy is a report, not a gate): {sorted(blocking - needs)}; "
        f"and needs names jobs that are warn-only or gone: {sorted(needs - blocking)}"
    )


def test_the_audit_job_still_blocks_and_still_runs_the_waiver_guard_first() -> None:
    """Row R34's two mechanical claims, in one place. The ORDER matters and is
    the reason the guard is a separate step: an expired or unexplained waiver
    must red with its own message, rather than let `pnpm audit` pass quietly on a
    silence nobody owns."""
    audit = "\n".join(_directives(_jobs()["audit"]))
    assert "continue-on-error" not in audit, "the audit job went warn-only again"
    assert "--ignore-registry-errors" not in audit, (
        "--ignore-registry-errors turns every registry outage into a silent pass"
    )
    guard = audit.index("node frontend/scripts/audit-waivers.mjs")
    assert guard < audit.index("run: pnpm audit"), (
        "the waiver guard no longer runs before `pnpm audit` — a silenced advisory "
        "with no rationale would now pass the audit before the guard ever spoke"
    )


def test_the_audit_job_sets_no_audit_level_env() -> None:
    """The one `pnpm audit` bypass `audit-waivers.mjs` structurally cannot see.

    That script guards the three FILES pnpm reads settings from. It cannot guard
    the environment, and `npm_config_audit_level=critical pnpm audit` exits 0 on
    a project with five live advisories — verified against the pinned
    pnpm@10.34.5, the same scratch project as the nine file-borne levers. npm's
    config layer accepts either case, so both spellings are refused here.

    Lower severity than the file levers (it takes a workflow edit, not a
    config-file edit) but real, and the script's header presents an enumeration —
    so it is closed where workflow shape is already the subject rather than left
    as a footnote nobody owns.
    """
    workflow = WORKFLOW.read_text(encoding="utf-8").lower()
    assert "npm_config_audit_level" not in workflow, (
        "ci.yml sets npm_config_audit_level. A severity floor supplied through the "
        "environment silences an unbounded, unnamed set of advisories and never "
        "appears in any file frontend/scripts/audit-waivers.mjs reads."
    )


def test_the_job_parser_reads_every_id_github_actions_allows() -> None:
    """Anti-vacuity for the scanner itself, on a workflow that is not on disk.

    A job id may contain `_` and uppercase. The parser used to match
    `[a-z][a-z0-9-]*`, so `deploy_prod:` was not seen as a header at all — its
    body was appended to the previous job's block, which meant the job-table
    assertion above passed while a wholly unclassified job sat in the file, and
    `test_every_blocking_job_gates_the_deploy` never saw it.
    """
    synthetic = "\n".join(
        [
            "jobs:",
            "  backend:",
            "    runs-on: ubuntu-latest",
            "  deploy_prod:",
            "    runs-on: ubuntu-latest",
            "  Lint2:",
            "    continue-on-error: true",
        ]
    )
    assert set(_jobs(synthetic)) == {"backend", "deploy_prod", "Lint2"}, (
        "the job-header pattern does not read every id GitHub Actions accepts, so a "
        "new job can be added to ci.yml without this file ever classifying it"
    )
