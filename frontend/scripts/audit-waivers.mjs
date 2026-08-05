#!/usr/bin/env node
// Guards the waiver list that `pnpm audit` obeys.
//
// R34 is not "the audit is quiet", it is "the audit GATES". The moment the
// audit job became blocking (F21 Task 2), `pnpm.auditConfig.ignoreGhsas` became
// the one lever that can silence it — so the lever needs its own lock. Without
// this script the scaffold is prose: package.json is strict JSON and cannot
// carry a comment, and pnpm's ignoreGhsas has no concept of an expiry, so
// "an expired waiver reds the build" would be a sentence in a planning document
// and nothing else.
//
// Three things red here, and each is a real failure mode rather than a style rule:
//
//   1. a silenced advisory with no rationale row — the precise thing spec D4
//      says this checklist row exists to prevent;
//   2. a rationale row for an advisory nobody is silencing — a stale waiver that
//      would quietly cover the NEXT advisory to reuse that id slot in review;
//   3. an expiry that has passed, is missing, or is further out than
//      MAX_WAIVER_DAYS — because an expiry nobody bounds is decorative, and
//      "expires": "2099-01-01" defeats the whole mechanism in one keystroke.
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
// The backend half is `uvx pip-audit --ignore-vuln <id>` in ci.yml, which can
// carry its four fields in a YAML comment beside the flag because YAML has
// comments and JSON does not.
//
// Run: node frontend/scripts/audit-waivers.mjs   (exit 0 = clean)

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const MAX_WAIVER_DAYS = 90;
const REQUIRED_FIELDS = ["why", "added", "expires"];
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

const manifestPath = join(dirname(fileURLToPath(import.meta.url)), "..", "package.json");
const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));

const silenced = manifest.pnpm?.auditConfig?.ignoreGhsas ?? [];
// `_doc` is the human-facing note that stands in for the comment JSON will not carry.
const waivers = Object.fromEntries(
  Object.entries(manifest.auditWaivers ?? {}).filter(([id]) => id !== "_doc"),
);

const problems = [];
const today = new Date(new Date().toISOString().slice(0, 10));

for (const id of silenced) {
  const waiver = waivers[id];
  if (!waiver) {
    problems.push(`${id}: silenced in pnpm.auditConfig.ignoreGhsas with no auditWaivers row. A waiver with no written rationale is exactly what this gate exists to prevent.`);
    continue;
  }
  for (const field of REQUIRED_FIELDS) {
    if (!waiver[field]) problems.push(`${id}: waiver is missing "${field}".`);
  }
  for (const field of ["added", "expires"]) {
    if (waiver[field] && !ISO_DATE.test(waiver[field])) {
      problems.push(`${id}: "${field}" must be an ISO date (YYYY-MM-DD), got ${JSON.stringify(waiver[field])}.`);
    }
  }
  if (!ISO_DATE.test(waiver.added ?? "") || !ISO_DATE.test(waiver.expires ?? "")) continue;

  const added = new Date(waiver.added);
  const expires = new Date(waiver.expires);
  if (expires < today) {
    problems.push(`${id}: waiver EXPIRED on ${waiver.expires}. Re-audit the advisory, then either fix it or write a new waiver with a new rationale. Do not extend this one in place.`);
  }
  const span = Math.round((expires - added) / 86400000);
  if (span > MAX_WAIVER_DAYS) {
    problems.push(`${id}: waiver runs ${span} days (${waiver.added} to ${waiver.expires}); the maximum is ${MAX_WAIVER_DAYS}. An unbounded expiry is a permanent blind spot wearing a temporary name.`);
  }
  if (span < 0) {
    problems.push(`${id}: "expires" (${waiver.expires}) precedes "added" (${waiver.added}).`);
  }
}

for (const id of Object.keys(waivers)) {
  if (!silenced.includes(id)) {
    problems.push(`${id}: has an auditWaivers row but is not in pnpm.auditConfig.ignoreGhsas. Prune the row rather than leaving it to cover something later.`);
  }
}

if (problems.length > 0) {
  console.error("Dependency-audit waivers are not in good standing:\n");
  for (const problem of problems) console.error(`  - ${problem}`);
  console.error("");
  process.exit(1);
}

console.log(
  silenced.length === 0
    ? "ok  no dependency-audit waivers in force"
    : `ok  ${silenced.length} dependency-audit waiver(s), all with a rationale and an unexpired end date`,
);
