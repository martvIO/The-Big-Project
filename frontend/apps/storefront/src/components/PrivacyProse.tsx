import { cn } from "@boutique/ui";
import { paragraphs, segments } from "../lib/privacyText";

// One privacy document, rendered.
//
// ⚠ THIS COMPONENT EXISTS SO THE TWO SURFACES CANNOT DRIFT. `/privacy` and the
// booking flow's §11 collection notice serve the SAME string off the SAME fetch
// (D13), and before this they each mapped `paragraphs()` to their own `<p>` —
// two copies of one rendering, held together by nobody. A bulleted set of rights
// that is a real list on one screen and one undifferentiated paragraph on the
// other is exactly the drift D13 exists to prevent.
//
// ⚠ Bullet runs become REAL `<ul>/<li>`, which is WCAG 1.3.1 Level A and is why
// this file was written. The three documents carry seventeen `•` lines between
// them and shipped with zero list elements anywhere; axe passes that and cannot
// do otherwise, because axe cannot know text beginning with «•» was meant to be
// a list. The parsing is in `lib/privacyText.ts` — it may not be in the text
// itself, which is a byte-capped, no-HTML, boutique-overridable settings value.
//
// ⚠ NO `dangerouslySetInnerHTML`, on any branch, ever. These are tenant-authored
// strings on an anonymous public page: every value below is a React text child.
export function PrivacyProse({ text, className }: { text: string; className?: string }) {
  return (
    <>
      {paragraphs(text).flatMap((block, blockIndex) =>
        // The index is the key because the blocks ARE the content and never
        // reorder: this list is derived from one immutable string per render,
        // so there is no identity to preserve across one.
        segments(block).map((segment, index) =>
          segment.kind === "list" ? (
            // `list-disc` because Tailwind's preflight strips the UA marker, and
            // `ps-5` because the indent has to follow the writing direction —
            // the physical-side equivalent hangs the markers off the wrong edge
            // in Hebrew. (Naming that class literally here trips qa-greps.sh's
            // physical-direction check, which greps text, not syntax.)
            <ul key={`${blockIndex}-${index}`} className={cn(className, "list-disc ps-5")}>
              {segment.items.map((item, itemIndex) => (
                <li key={itemIndex}>{item}</li>
              ))}
            </ul>
          ) : (
            // `whitespace-pre-line` rides in `className` from both callers and is
            // load-bearing there (copy.md R1): a block's own newlines are the
            // owner's, and CSS collapses them by default.
            <p key={`${blockIndex}-${index}`} className={className}>
              {segment.text}
            </p>
          ),
        ),
      )}
    </>
  );
}
