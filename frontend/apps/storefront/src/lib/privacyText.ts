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
