import { render, screen, within } from "@testing-library/react";
import { run } from "axe-core";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getBoutiqueOnce } from "../api";
import type { BoutiqueResponse } from "../api";
import { StorefrontLayout } from "../components/StorefrontLayout";
import i18n from "../i18n";
import { PrivacyPage } from "../routes/PrivacyPage";
import { PRIVACY_FIXTURE } from "../test/boutique";

// PPL §11 makes the collection notice a legal obligation and Amendment 13 makes
// the processor relationship and the sub-processor list part of the disclosure,
// so these tests guard what a regulator would check: real document semantics,
// three documents in the order their own text assumes, the boutique's own
// override where she wrote one, the platform list where she may not, and text
// that is text rather than markup.

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return { ...actual, getBoutiqueOnce: vi.fn() };
});

const loadBoutique = vi.mocked(getBoutiqueOnce);

const BOUTIQUE_NAME = "בוטיק אלמה";

function boutique(overrides: Partial<BoutiqueResponse> = {}): BoutiqueResponse {
  return {
    name: BOUTIQUE_NAME,
    essence: null,
    description: null,
    phone: "052-1234567",
    address: null,
    maps_url: null,
    instagram: "alma.bridal",
    hours: [],
    exceptions: [],
    ...PRIVACY_FIXTURE,
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  loadBoutique.mockResolvedValue(boutique());
  window.history.replaceState(null, "", "/privacy");
});

// Scoped to <main>: the layout's own footer carries a link labelled with the
// same words as this page's title, and counting that as if the page rendered it
// would make more than one assertion below pass for free.
async function renderPage(overrides: Partial<BoutiqueResponse> = {}) {
  loadBoutique.mockResolvedValue(boutique(overrides));
  const utils = render(
    <StorefrontLayout>
      <PrivacyPage />
    </StorefrontLayout>,
  );
  await screen.findByRole("heading", { level: 2, name: i18n.t("privacy.noticeHeading") });
  return { ...utils, main: screen.getByRole("main") };
}

describe("PrivacyPage — document semantics", () => {
  it("has exactly one h1", async () => {
    const { main } = await renderPage();

    expect(within(main).getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(within(main).getByRole("heading", { level: 1 })).toHaveTextContent(
      i18n.t("privacy.title"),
    );
  });

  it("never skips a heading level", async () => {
    const { main } = await renderPage();

    const levels = within(main)
      .getAllByRole("heading")
      .map((heading) => Number(heading.tagName.slice(1)));
    expect(levels[0]).toBe(1);
    for (const [index, level] of levels.entries()) {
      if (index > 0) expect(level - levels[index - 1]).toBeLessThanOrEqual(1);
    }
  });

  it("gives each of the three documents its own h2, in the order their text assumes", async () => {
    const { main } = await renderPage();

    // ⚠ ORDER IS THE ASSERTION, not the presence. The DPA clause points FORWARD
    // at the sub-processor list («למעט ספקי התשתית שרשומים בהמשך»), so a list
    // rendered above its own reference leaves that sentence pointing at nothing
    // — a defect no heading-count check can see.
    expect(
      within(main)
        .getAllByRole("heading", { level: 2 })
        .map((heading) => heading.textContent),
    ).toEqual([
      i18n.t("privacy.noticeHeading"),
      i18n.t("privacy.dpaHeading"),
      i18n.t("privacy.subprocessorsHeading"),
    ]);
  });

  it("names the boutique the notice is about", async () => {
    const { main } = await renderPage();

    expect(within(main).getAllByText(BOUTIQUE_NAME).length).toBeGreaterThan(0);
  });

  it("passes axe with zero violations", async () => {
    const { container } = await renderPage();

    const results = await run(container);
    expect(results.violations).toEqual([]);
  }, 20000);
});

describe("PrivacyPage — the text it renders", () => {
  it("renders the platform default when the boutique overrode nothing", async () => {
    const { main } = await renderPage();

    expect(within(main).getByText(/הודעת ברירת מחדל/)).toBeInTheDocument();
  });

  it("renders the boutique's OVERRIDE in place of the default", async () => {
    // The server resolves the override; this page renders whatever won. The
    // negative half is what makes it an assertion: a page that appended the
    // default beneath the override would publish two conflicting notices.
    const { main } = await renderPage({
      privacy_notice_text: "הנוסח של הבוטיק עצמה על {{boutique}}.",
    });

    expect(within(main).getByText(/הנוסח של הבוטיק עצמה/)).toBeInTheDocument();
    expect(within(main).queryByText(/הודעת ברירת מחדל/)).not.toBeInTheDocument();
  });

  it("renders the PLATFORM sub-processor list even when the notice and DPA are overridden", async () => {
    // Gate 1 Q3 / D14, from the reader's side. The server is what makes the list
    // un-overridable — `resolve_privacy` never reads it out of the tenant blob —
    // and this is the assertion that the page does not undo that by, say,
    // rendering the DPA override in the list's slot.
    const { main } = await renderPage({
      privacy_notice_text: "נוסח משלנו.",
      privacy_dpa_text: "סעיף עיבוד משלנו.",
    });

    const list = within(main).getByTestId("privacy-subprocessors");
    expect(list).toHaveTextContent(i18n.t("privacy.subprocessorsHeading"));
    expect(list).toHaveTextContent("ספקי תשתית");
    // The negative half: neither override leaked into the slot it may not reach.
    expect(list).not.toHaveTextContent("סעיף עיבוד משלנו");
    expect(list).not.toHaveTextContent("נוסח משלנו");
  });

  it("splits a document into one <p> per blank line, and preserves the newlines inside a block", async () => {
    // copy.md R1. The three documents carry bullet lists as `•`-prefixed lines
    // inside ONE block: split on every `\n` and each bullet becomes its own
    // paragraph; render the whole document in one element and the blank-line
    // breaks vanish. Both halves are asserted, because the naive fixes for one
    // are the defect in the other.
    const { main } = await renderPage({
      privacy_notice_text: "פסקה ראשונה.\n\nפסקה שנייה:\n• פריט אחד\n• פריט שני",
    });

    const first = within(main).getByText("פסקה ראשונה.");
    expect(first.tagName).toBe("P");
    const second = within(main).getByText(/פסקה שנייה/);
    expect(second.tagName).toBe("P");
    expect(second).not.toBe(first);
    // One element, three lines — and `whitespace-pre-line` is what paints them
    // as three. jsdom applies no CSS, so the class IS the only checkable half.
    expect(second.textContent).toBe("פסקה שנייה:\n• פריט אחד\n• פריט שני");
    expect(second).toHaveClass("whitespace-pre-line");
  });

  it("leaves no empty paragraph behind a trailing or doubled blank line", async () => {
    const { main } = await renderPage({ privacy_notice_text: "פסקה.\n\n\n\nעוד פסקה.\n\n" });

    // A blank <p> announces as an empty paragraph to a screen reader, and these
    // documents are hand-edited by boutique owners in a textarea.
    const empty = within(main)
      .getAllByText(/./)
      .filter((node) => node.tagName === "P" && node.textContent?.trim() === "");
    expect(empty).toEqual([]);
  });
});

describe("PrivacyPage — the boutique name substitution", () => {
  it("leaves no {{boutique}} placeholder unrendered in any of the three documents", async () => {
    await renderPage({
      privacy_notice_text: "א {{boutique}}",
      privacy_dpa_text: "ב {{boutique}}",
      privacy_subprocessors_text: "ג {{boutique}}",
    });

    expect(screen.queryByText(/{{boutique}}/)).not.toBeInTheDocument();
  });

  it("substitutes a name containing $& literally, never as a replacement pattern", async () => {
    // ⚠ `String.replaceAll`'s replacement argument gives `$` special meaning, so
    // a boutique named this would have its own name spliced back into itself —
    // and the tenant, not us, chooses that string. `split`/`join` cannot.
    const { main } = await renderPage({
      name: "סטודיו $& כלות",
      privacy_notice_text: "המידע נשמר אצל {{boutique}}.",
    });

    expect(within(main).getByText(/המידע נשמר אצל/).textContent).toContain("סטודיו $& כלות");
  });

  it("isolates the substituted name so its own punctuation cannot reorder the Hebrew", async () => {
    // copy.md R4. FSI (U+2068) … PDI (U+2069) — what <bdi> does, in a string,
    // because this is an inline substitution into a paragraph rendered as TEXT.
    const { main } = await renderPage({
      name: "Bella Bride",
      privacy_notice_text: "המידע נשמר אצל {{boutique}}.",
    });

    expect(within(main).getByText(/המידע נשמר אצל/).textContent).toContain(
      "⁨Bella Bride⁩",
    );
  });
});

describe("PrivacyPage — what it refuses to do", () => {
  it("renders a <script> in a boutique's override as visible characters", async () => {
    // A statutory document is the one page an attacker would most like to own:
    // it is anonymous, public, and its body is TENANT-AUTHORED. React escapes by
    // default and the test is what keeps a later `dangerouslySetInnerHTML`
    // "fix" from shipping quietly.
    const { main, container } = await renderPage({
      privacy_notice_text: "<script>alert(1)</script> נוסח",
    });

    expect(container.querySelector("script")).toBeNull();
    expect(within(main).getByText(/alert\(1\)/)).toBeInTheDocument();
  });

  it("renders no spinner and no error in place of the statement", async () => {
    // AccessibilityPage's deliberate refusal, applied here for a stronger
    // reason: this page is linked from the footer of every route, so it is
    // where a visitor lands precisely when something else is failing. A page
    // that shows «לא הצלחנו לטעון» instead of the notice has answered a §11
    // request with an outage message.
    loadBoutique.mockRejectedValue(new Error("down"));
    render(
      <StorefrontLayout>
        <PrivacyPage />
      </StorefrontLayout>,
    );
    const heading = await screen.findByRole("heading", { level: 1 });

    expect(heading).toHaveTextContent(i18n.t("privacy.title"));
    // Scoped to <main>: the layout ships the A11yMenu trigger on every route,
    // and counting it here would make the button assertion unsatisfiable rather
    // than meaningful.
    const main = within(screen.getByRole("main"));
    expect(main.queryByRole("status")).toBeNull();
    expect(main.queryByRole("alert")).toBeNull();
    expect(main.queryByRole("button")).toBeNull();
  });
});

describe("the storefront never renders tenant text as markup", () => {
  it("contains no dangerouslySetInnerHTML anywhere in src", async () => {
    // A SOURCE SCAN, and it is deliberately not scoped to this page. The three
    // privacy documents are the most attacker-attractive tenant-authored strings
    // in the product, but `terms_text`, `description` and `notes` are the same
    // class of input — so the assertion that is actually worth holding is that
    // the storefront has no such call site at all.
    const { readFileSync, readdirSync, statSync } = await import("node:fs");
    const { join } = await import("node:path");
    const walk = (dir: string): string[] =>
      readdirSync(dir).flatMap((entry) => {
        const path = join(dir, entry);
        return statSync(path).isDirectory()
          ? walk(path)
          : /\.tsx?$/.test(entry)
            ? [path]
            : [];
      });

    const files = walk(join(process.cwd(), "src")).filter(
      // Tests are the thing doing the guarding, not a source of shipped JSX.
      (path) => !path.includes("__tests__"),
    );
    // A scanner that matched nothing would make the assertion vacuous.
    expect(files.length).toBeGreaterThan(20);
    // `={` and not the bare identifier: three shipped files name the prop in a
    // COMMENT saying they must never use it, and a substring scan would read
    // those as the violation they are warning against.
    const offenders = files.filter((path) =>
      /dangerouslySetInnerHTML\s*=\s*\{/.test(readFileSync(path, "utf8")),
    );
    expect(offenders).toEqual([]);
  });
});
