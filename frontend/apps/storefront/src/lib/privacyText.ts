// Rendering the three statutory privacy documents (F20).
//
// The strings arrive from `GET /storefront/boutique` as PLAIN TEXT carrying a
// `{{boutique}}` token, and both surfaces that render them — `/privacy` and the
// booking form's `details` step — need the same two transformations. They live
// here rather than in either page so the two cannot drift: a legal document
// that reads differently depending on which screen you found it on is worse
// than one that reads badly on both.

// The placeholder token, matching the shipped `he.ts` convention (`{{boutique}}`,
// `{{name}}`) so one spelling spans the backend constants and the i18n values.
const BOUTIQUE_TOKEN = "{{boutique}}";

// U+2068 FIRST STRONG ISOLATE … U+2069 POP DIRECTIONAL ISOLATE. What `<bdi>`
// does, in a plain string. See `substituteBoutique` for why the string form is
// the one needed here.
const FSI = "⁨";
const PDI = "⁩";

/**
 * Fill `{{boutique}}` in with the boutique's own name.
 *
 * ⚠ `split`/`join`, NEVER `String.prototype.replaceAll`. The replacement
 * argument of `replaceAll` gives `$` special meaning — a boutique named
 * «סטודיו $& כלות» would have its own name spliced back into itself — and it is
 * the tenant, not us, who chooses that string. `split`/`join` treats both sides
 * as literals and cannot fail. (`str.format()`'s equivalent trap is why the
 * backend constants document the same rule: an overriding boutique whose text
 * contains a `{` would otherwise blank a legally-required document.)
 *
 * ⚠ Substitution runs AFTER resolution, on whichever text won — platform default
 * or boutique override. An overriding boutique who kept the placeholder gets her
 * name, not the literal characters `{{boutique}}`, on her own privacy page.
 *
 * The isolate is not decoration either. A name carrying its own punctuation,
 * digits or mixed script reorders the Hebrew around it under UAX#9, and this is
 * an inline substitution into a paragraph rather than an element we could wrap
 * in `<bdi>` — the text is rendered as text, and `dangerouslySetInnerHTML` is
 * banned on this surface. FSI/PDI are the string-level form of the same thing,
 * contain no `<`, and are invisible.
 */
export function substituteBoutique(text: string, boutiqueName: string | null): string {
  // A boutique whose fetch has not landed yet still gets a readable document:
  // the token is dropped rather than printed. `/privacy` is a statutory page and
  // renders no spinner in place of the statement, so this branch is reachable.
  const name = boutiqueName === null ? "" : `${FSI}${boutiqueName}${PDI}`;
  return text.split(BOUTIQUE_TOKEN).join(name);
}

/**
 * Split a document into its paragraphs on BLANK LINES.
 *
 * A single newline inside a block is left alone — every bullet list in the three
 * documents is one block of `•`-prefixed lines, and splitting on `\n` would turn
 * each bullet into its own `<p>`. The caller renders each block in a
 * `white-space: pre-line` element, which is what makes the intra-block newlines
 * visible (copy.md R1).
 *
 * Empty blocks are dropped: a document with a trailing newline or a doubled
 * blank line must not render an empty `<p>`, which announces as a blank
 * paragraph to a screen reader.
 */
export function paragraphs(text: string): string[] {
  return text
    .split(/\n\s*\n/)
    .map((block) => block.trim())
    .filter((block) => block !== "");
}

/** One run of prose, or one bullet list, in document order. */
export type Segment = { kind: "prose"; text: string } | { kind: "list"; items: string[] };

// The three documents write every list the same way — a lead line, then
// consecutive lines each opening with U+2022. `PLATFORM_NOTICE_HE` alone has
// three such runs, and the platform carries seventeen bullet lines in total.
const BULLET = "•";

/**
 * Split ONE block into its prose runs and its bullet runs.
 *
 * ⚠ THE PARSING BELONGS HERE, IN THE RENDERER, AND NOT IN THE TEXT. The three
 * documents are settings values: byte-capped at 8192, no-HTML by invariant (a
 * backend test asserts no `<` appears in any platform constant, because these
 * are tenant-authored text on an anonymous public page and any HTML path is
 * stored XSS), and boutique-overridable. Markup cannot be put in them, so the
 * only place `•` can become `<li>` is at the point of render — which is also the
 * only way BOTH surfaces get it, D13's requirement that `/privacy` and the §11
 * collection notice render the same text the same way.
 *
 * Consecutive bullets join ONE list; anything between two runs closes the first
 * — «למי המידע מגיע» must not announce as an item of «מה אנחנו מבקשות».
 *
 * The glyph is stripped from each item: the marker is the `<li>`'s own, and a
 * literal `•` beside it would be painted twice and announced twice.
 *
 * ⚠ Non-bullet lines are RE-JOINED with `\n` rather than becoming one paragraph
 * each. The caller renders prose in a `white-space: pre-line` element (copy.md
 * R1) — an owner hand-editing a textarea wraps her own lines, and each of those
 * is not a paragraph.
 */
export function segments(block: string): Segment[] {
  const out: Segment[] = [];
  for (const line of block.split("\n")) {
    const trimmed = line.trim();
    const last = out[out.length - 1];
    if (trimmed.startsWith(BULLET)) {
      const item = trimmed.slice(BULLET.length).trim();
      if (last?.kind === "list") {
        last.items.push(item);
      } else {
        out.push({ kind: "list", items: [item] });
      }
    } else if (last?.kind === "prose") {
      last.text += `\n${line}`;
    } else {
      out.push({ kind: "prose", text: line });
    }
  }
  // Same rule `paragraphs` applies: a prose run that is only whitespace
  // announces as a blank paragraph. An empty `<li>` cannot arise — a line that
  // is a bare `•` yields an empty item, which is content the owner typed.
  return out.filter((segment) => segment.kind === "list" || segment.text.trim() !== "");
}
