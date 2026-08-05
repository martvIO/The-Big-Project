#!/usr/bin/env node
// Guards every lever that can make the gating `pnpm audit` exit 0 on a live advisory.
//
// R34 is not "the audit is quiet", it is "the audit GATES". The moment the audit
// job became blocking (F21 Task 2), the settings pnpm reads to filter advisories
// became the levers that can silence it — so the levers need their own lock.
// Without this script the scaffold is prose: package.json is strict JSON and
// cannot carry a comment, and none of pnpm's ignore settings has any concept of
// an expiry, so "an expired waiver reds the build" would be a sentence in a
// planning document and nothing else.
//
// ⚠ THE LEVER SURFACE IS SIX WIDE, NOT ONE, AND EVERY ENTRY BELOW WAS RUN
// AGAINST THE PINNED BINARY (pnpm 10.34.5, `packageManager`) ON A SCRATCH
// PROJECT WITH lodash@4.17.20 — 5 advisories, 2 high, `pnpm audit` exit 1 —
// rather than read out of the docs. Each one took that exit code to 0:
//
//   1. package.json        pnpm.auditConfig.ignoreGhsas  (dist/pnpm.cjs:148584)
//   2. package.json        pnpm.auditConfig.ignoreCves   (dist/pnpm.cjs:148594)
//   3. pnpm-workspace.yaml auditConfig.ignoreGhsas       — settings live here in pnpm 10
//   4. pnpm-workspace.yaml auditConfig.ignoreCves
//   5. .npmrc              audit-level=<severity>        (dist/pnpm.cjs:148604-148605)
//   6. pnpm-workspace.yaml auditLevel: <severity>        — same setting, camelCase
//
// The 2026-08-05 review found this script reading ONLY #1, and demonstrated #2
// and #3 end to end. #5 and #6 are a severity FLOOR rather than an id list —
// `audit-level=critical` drops every high, moderate and low advisory and exits
// 0 — and neither the review nor the previous author had them. Ruled out by the
// same experiment, and recorded so nobody re-tests them: `pnpm.auditLevel` and a
// top-level `auditLevel` in package.json are NOT read (pnpm picks only
// `auditConfig` out of `manifest.pnpm`, dist/pnpm.cjs:18287-18311), and neither
// is a camelCase `auditLevel=` in .npmrc.
//
// THE RULE THIS SCRIPT ENFORCES, in one sentence: an advisory may be silenced
// only by an id, only in frontend/package.json, and only with a rationale row
// that expires. Everything else is banned outright rather than waiver-checked —
// a severity floor silences an unbounded, unnamed set of advisories that do not
// exist yet, so no rationale row can honestly describe it, and a second file
// holding ignore lists is a second place a reviewer has to remember to look.
//
// Waiver shape, in frontend/package.json:
//
//   "pnpm": { "auditConfig": { "ignoreGhsas": ["GHSA-xxxx-xxxx-xxxx"] } },
//   "auditWaivers": {
//     "GHSA-xxxx-xxxx-xxxx": {
//       "why":     "one sentence: why this advisory does not reach this product",
//       "added":   "2026-08-05",
//       "expires": "2026-11-03"
//     }
//   }
//
// An `ignoreCves` waiver keys on the CVE id in the same map: the id is the key
// either way, because which list silenced it does not change what has to be
// written down.
//
// The backend half is `uvx pip-audit --ignore-vuln <id>` in ci.yml, which can
// carry its four fields in a YAML comment beside the flag because YAML has
// comments and JSON does not.
//
// Run: node frontend/scripts/audit-waivers.mjs   (exit 0 = clean)
// The self-test below runs FIRST on every invocation. It costs microseconds, and
// it means the command CI already runs is also the test that this guard still
// detects each of the six levers — so a bypass cannot be reopened by a future
// pnpm or a future contributor while the gate goes on printing `ok`.

import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const MAX_WAIVER_DAYS = 90;
const REQUIRED_FIELDS = ["why", "added", "expires"];
const DAY_MS = 86400000;

// Substring, not an anchored key match: YAML accepts `"auditConfig":` at any
// indentation, and a quoted or oddly-placed key must not slip past. A mention
// inside a comment reds too — that fails CLOSED, which is the right direction
// for a file whose only job here is to hold no audit setting at all.
const BANNED_IN_WORKSPACE = ["auditConfig", "auditLevel", "audit-level"];
const BANNED_IN_NPMRC = ["audit-level", "auditlevel", "auditconfig"];

/** A real calendar day in ISO form, or null. */
function isoDay(value) {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const date = new Date(`${value}T00:00:00Z`);
  // `9999-99-99` is ISO-SHAPED and parses to NaN, which made every comparison
  // below false and disabled all three date checks at once. `2026-02-30` parses
  // fine and rolls over to March 2 — the round-trip is what catches that one.
  if (Number.isNaN(date.getTime())) return null;
  return date.toISOString().slice(0, 10) === value ? date : null;
}

/**
 * The whole judgement, as a pure function, so the self-test can drive it with
 * the reviewer's bypasses instead of with the repo's real files.
 *
 * `npmrcs` is [{path, text}] for the .npmrc files pnpm would actually read.
 */
export function auditWaiverProblems({ manifest, workspaceYaml, npmrcs = [], today }) {
  const problems = [];

  const auditConfig = manifest.pnpm?.auditConfig ?? {};
  const silenced = [
    ...(auditConfig.ignoreGhsas ?? []).map((id) => [id, "pnpm.auditConfig.ignoreGhsas"]),
    ...(auditConfig.ignoreCves ?? []).map((id) => [id, "pnpm.auditConfig.ignoreCves"]),
  ];
  for (const key of Object.keys(auditConfig)) {
    if (key !== "ignoreGhsas" && key !== "ignoreCves") {
      problems.push(`package.json: pnpm.auditConfig.${key} is a setting this guard does not understand. If pnpm has grown a new way to filter advisories, teach this script about it before using it.`);
    }
  }
  if (manifest.pnpm?.auditLevel !== undefined || manifest.auditLevel !== undefined) {
    problems.push(`package.json: an "auditLevel" key is set. pnpm does not read it here today, so it silences nothing — but writing it means someone believes it does, and one pnpm release could make them right. Delete it.`);
  }

  if (workspaceYaml !== null && workspaceYaml !== undefined) {
    for (const token of BANNED_IN_WORKSPACE) {
      if (workspaceYaml.includes(token)) {
        problems.push(`pnpm-workspace.yaml: contains "${token}". pnpm reads audit settings from here too, and a waiver kept here would carry no rationale row. Silence advisories by id in package.json's pnpm.auditConfig, or not at all.`);
      }
    }
  }

  for (const { path, text } of npmrcs) {
    const lower = text.toLowerCase();
    for (const token of BANNED_IN_NPMRC) {
      if (lower.includes(token)) {
        problems.push(`${path}: contains "${token}". A severity floor (audit-level) drops every advisory below it — an unbounded, unnamed set that no rationale row can describe. There is no waiver for this; remove it.`);
      }
    }
  }

  // `_doc` is the human-facing note that stands in for the comment JSON will not carry.
  const waivers = Object.fromEntries(
    Object.entries(manifest.auditWaivers ?? {}).filter(([id]) => id !== "_doc"),
  );
  const silencedIds = new Set(silenced.map(([id]) => id));

  for (const [id, where] of silenced) {
    const waiver = waivers[id];
    if (!waiver) {
      problems.push(`${id}: silenced in ${where} with no auditWaivers row. A waiver with no written rationale is exactly what this gate exists to prevent.`);
      continue;
    }
    for (const field of REQUIRED_FIELDS) {
      if (!waiver[field]) problems.push(`${id}: waiver is missing "${field}".`);
    }
    const added = isoDay(waiver.added);
    const expires = isoDay(waiver.expires);
    for (const [field, parsed] of [["added", added], ["expires", expires]]) {
      if (waiver[field] && parsed === null) {
        problems.push(`${id}: "${field}" must be a REAL calendar day in ISO form (YYYY-MM-DD), got ${JSON.stringify(waiver[field])}.`);
      }
    }
    if (added === null || expires === null) continue;

    // Every window is measured against TODAY, never only against `added`. A cap
    // on the SPAN alone left the ANCHOR free: {"added":"2099-01-01",
    // "expires":"2099-01-05"} is a four-day, in-cap, well-formed waiver that
    // never expires, and it reads as scrupulous in review.
    if (added > today) {
      problems.push(`${id}: "added" (${waiver.added}) is in the future. A waiver anchored ahead of today never starts, and therefore never expires.`);
    }
    if (expires < today) {
      problems.push(`${id}: waiver EXPIRED on ${waiver.expires}. Re-audit the advisory, then either fix it or write a new waiver with a new rationale. Do not extend this one in place.`);
    }
    if (expires - today > MAX_WAIVER_DAYS * DAY_MS) {
      problems.push(`${id}: waiver runs to ${waiver.expires}, more than ${MAX_WAIVER_DAYS} days from today. An expiry nobody ever has to reach is a permanent blind spot wearing a temporary name.`);
    }
    const span = Math.round((expires - added) / DAY_MS);
    if (span > MAX_WAIVER_DAYS) {
      problems.push(`${id}: waiver runs ${span} days (${waiver.added} to ${waiver.expires}); the maximum is ${MAX_WAIVER_DAYS}. Write a new waiver rather than extending one in place.`);
    }
    if (span < 0) {
      problems.push(`${id}: "expires" (${waiver.expires}) precedes "added" (${waiver.added}).`);
    }
  }

  for (const id of Object.keys(waivers)) {
    if (!silencedIds.has(id)) {
      problems.push(`${id}: has an auditWaivers row but is not silenced in pnpm.auditConfig. Prune the row rather than leaving it to cover something later.`);
    }
  }

  return problems;
}

// --- the self-test ------------------------------------------------------------
//
// One case per lever, plus the two expiry defeats the review demonstrated, plus
// two clean controls. The controls are not decoration: without them every
// assertion below would still pass if this checker were changed to return a
// problem unconditionally, which is the shape a broken guard most often takes
// once someone "fixes" a false positive.

const CLEAN = { pnpm: { auditConfig: { ignoreGhsas: [] } } };
const TODAY = new Date("2026-08-05T00:00:00Z");
const GHSA = "GHSA-35jh-r3h4-6jhm";
const CVE = "CVE-2021-23337";
const WHY = "the advisory's sink is not reachable from this product";
const GOOD_WAIVER = { why: WHY, added: "2026-08-01", expires: "2026-09-01" };

function selfTest() {
  const run = (input) => auditWaiverProblems({ workspaceYaml: null, today: TODAY, ...input });
  const reds = (label, input) => {
    if (run(input).length === 0) {
      throw new Error(`audit-waivers self-test: ${label} was NOT caught — the guard has a bypass`);
    }
  };
  const passes = (label, input) => {
    const problems = run(input);
    if (problems.length > 0) {
      throw new Error(`audit-waivers self-test: ${label} was wrongly rejected: ${problems.join("; ")}`);
    }
  };

  passes("a clean manifest", { manifest: CLEAN });
  passes("a well-formed waiver", {
    manifest: { pnpm: { auditConfig: { ignoreGhsas: [GHSA] } }, auditWaivers: { [GHSA]: GOOD_WAIVER } },
  });

  reds("lever 1: ignoreGhsas with no rationale", {
    manifest: { pnpm: { auditConfig: { ignoreGhsas: [GHSA] } } },
  });
  reds("lever 2: ignoreCves with no rationale", {
    manifest: { pnpm: { auditConfig: { ignoreCves: [CVE] } } },
  });
  reds("lever 3: auditConfig.ignoreGhsas in pnpm-workspace.yaml", {
    manifest: CLEAN,
    workspaceYaml: `packages:\n  - apps/*\nauditConfig:\n  ignoreGhsas:\n    - ${GHSA}\n`,
  });
  reds("lever 4: auditConfig.ignoreCves in pnpm-workspace.yaml", {
    manifest: CLEAN,
    workspaceYaml: `auditConfig:\n  ignoreCves:\n    - ${CVE}\n`,
  });
  reds("lever 5: an audit-level floor in .npmrc", {
    manifest: CLEAN,
    npmrcs: [{ path: ".npmrc", text: "audit-level=critical\n" }],
  });
  reds("lever 6: an auditLevel floor in pnpm-workspace.yaml", {
    manifest: CLEAN,
    workspaceYaml: "auditLevel: critical\n",
  });

  reds("a future-anchored waiver that never expires", {
    manifest: {
      pnpm: { auditConfig: { ignoreGhsas: [GHSA] } },
      auditWaivers: { [GHSA]: { why: WHY, added: "2099-01-01", expires: "2099-01-05" } },
    },
  });
  reds("an ISO-shaped date that is not a real day", {
    manifest: {
      pnpm: { auditConfig: { ignoreGhsas: [GHSA] } },
      auditWaivers: { [GHSA]: { why: WHY, added: "2026-08-01", expires: "9999-99-99" } },
    },
  });
  reds("a date that rolls over into the next month", {
    manifest: {
      pnpm: { auditConfig: { ignoreGhsas: [GHSA] } },
      auditWaivers: { [GHSA]: { why: WHY, added: "2026-08-01", expires: "2026-02-30" } },
    },
  });
  reds("an expired waiver", {
    manifest: {
      pnpm: { auditConfig: { ignoreGhsas: [GHSA] } },
      auditWaivers: { [GHSA]: { why: WHY, added: "2026-01-01", expires: "2026-03-01" } },
    },
  });
  reds("a rationale row for an advisory nobody silences", {
    manifest: { ...CLEAN, auditWaivers: { [GHSA]: GOOD_WAIVER } },
  });
}

// --- the real run -------------------------------------------------------------

const here = dirname(fileURLToPath(import.meta.url));
const frontend = join(here, "..");
const repoRoot = join(frontend, "..");

const read = (path) => (existsSync(path) ? readFileSync(path, "utf8") : null);

function main() {
  const manifest = JSON.parse(readFileSync(join(frontend, "package.json"), "utf8"));
  // The .npmrc files pnpm ACTUALLY reads for this `pnpm audit`, whose working
  // directory is `frontend/` (ci.yml's `audit` job): the project one at that
  // cwd — which is also the workspace root — plus the repo root as belt and
  // braces. A per-package .npmrc deeper in the tree is not consulted by this
  // invocation, so listing one here would be theatre.
  const npmrcs = [
    { path: "frontend/.npmrc", text: read(join(frontend, ".npmrc")) },
    { path: ".npmrc", text: read(join(repoRoot, ".npmrc")) },
  ].filter(({ text }) => text !== null);

  const problems = auditWaiverProblems({
    manifest,
    workspaceYaml: read(join(frontend, "pnpm-workspace.yaml")),
    npmrcs,
    today: new Date(new Date().toISOString().slice(0, 10)),
  });

  if (problems.length > 0) {
    console.error("Dependency-audit waivers are not in good standing:\n");
    for (const problem of problems) console.error(`  - ${problem}`);
    console.error("");
    process.exit(1);
  }

  const config = manifest.pnpm?.auditConfig ?? {};
  const count = (config.ignoreGhsas ?? []).length + (config.ignoreCves ?? []).length;
  console.log(
    count === 0
      ? "ok  no dependency-audit waivers in force, and no audit setting outside package.json"
      : `ok  ${count} dependency-audit waiver(s), all with a rationale and an unexpired end date`,
  );
}

selfTest();
main();
