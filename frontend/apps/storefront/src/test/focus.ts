import { waitFor } from "@testing-library/react";
import { expect } from "vitest";

// Focus is moved from a passive effect, and React flushes those AFTER paint.
// `await findByText(...)` resolves the moment the node is in the DOM, which can
// be one tick BEFORE the effect that focuses it has run — so a synchronous
// `expect(document.activeElement)` right after is a race, and on a loaded CI
// runner it loses. (Proof it is environmental, not a product bug: fc5f7eb8 on
// main is a docs-only commit whose Frontend job failed on this assertion shape
// and went green on a re-run of identical code.)
//
// Poll for the focus to land instead of assuming it already has. This is the
// async-appearance counterpart to navigateAndFlush() in router.test.tsx, which
// covers the synchronous case with act().
//
// Only for POSITIVE assertions. Wrapping a negative ("focus did NOT move here")
// would pass on the first tick and stop detecting a move that happens later.
//
// waitFor stops at the first tick its callback passes, so on its own it also
// stops watching the moment focus ARRIVES — blind to a move that lands one
// commit later and takes it away again. That is the defect class this file
// exists for (a held intent firing on an unrelated render), so the wait is
// followed by a settling task and one strict synchronous re-read. Polling to
// find the move, then asserting to keep it.
export async function expectFocus(node: Element | null): Promise<void> {
  // A selector that quietly returned null would otherwise degrade a real
  // assertion into a confusing full-timeout wait for focus on nothing.
  if (node === null) throw new Error("expectFocus: no node — the selector matched nothing.");
  await waitFor(() => {
    expect(document.activeElement).toBe(node);
  });
  await new Promise((resolve) => setTimeout(resolve, 0));
  expect(document.activeElement).toBe(node);
}
