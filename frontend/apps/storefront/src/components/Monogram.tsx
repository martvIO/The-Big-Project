/**
 * The dress detail's no-photo art: the BOUTIQUE's initial in the display serif
 * on paper, inside a gold hairline.
 *
 * It deliberately differs from DressCard's built-in monogram, which uses the
 * DRESS name's first character. The card is one of many in a grid, where the
 * dress name is what distinguishes it from its neighbours; the detail page is
 * the boutique's own room, and repeating the dress name as decorative art next
 * to the <h1> that already says it adds nothing.
 *
 * aria-hidden: the adjacent <h1> carries the dress name, so this is decoration.
 * No <img> is emitted at all, so there is no broken-image glyph to fall back to.
 */
export function Monogram({ boutiqueName }: { boutiqueName: string }) {
  return (
    <div
      aria-hidden="true"
      data-testid="dress-monogram"
      className="flex aspect-[3/4] w-full items-center justify-center rounded-md border border-gold bg-surface"
    >
      <span className="font-display text-3xl text-gold">{boutiqueName.charAt(0)}</span>
    </div>
  );
}
