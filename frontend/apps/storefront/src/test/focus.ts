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
export async function expectFocus(node: Element | null): Promise<void> {
  await waitFor(() => {
    expect(document.activeElement).toBe(node);
  });
}
