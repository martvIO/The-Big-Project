import { useEffect, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, cn } from "@boutique/ui";

/**
 * A six-line clamp with a disclosure toggle.
 *
 * LINE-based (`line-clamp-6`), never a pixel height: qa §8 names a px-height
 * clamp as a 200%-text-resize breaker, because the text grows and the box does
 * not.
 *
 * Overflow is MEASURED rather than guessed from a character count. A character
 * heuristic is wrong in exactly the case §8 tests — at 200% text size the same
 * string wraps to more lines, so a description that needed no toggle at 100%
 * needs one at 200%, and a fixed threshold cannot know that. Measuring also
 * survives a narrow column and a long unbroken word.
 *
 * The toggle carries aria-expanded AND aria-controls: it is a disclosure
 * widget, and §8 requires the state be exposed to assistive tech rather than
 * left implicit in the visible label.
 */
export function DescriptionClamp({ text }: { text: string }) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);
  const [clampable, setClampable] = useState(false);
  const paragraphRef = useRef<HTMLParagraphElement>(null);
  const id = useId();

  useEffect(() => {
    const measure = () => {
      const el = paragraphRef.current;
      if (el === null) return;
      // Only meaningful while the clamp is applied; once expanded there is no
      // overflow to detect, and the toggle must stay rendered regardless.
      if (expanded) return;
      setClampable(el.scrollHeight > el.clientHeight + 1);
    };
    measure();
    window.addEventListener("resize", measure);
    // The A11yMenu's boosts are data attributes on <html> — data-a11y-text-size
    // moves the root font size and fires NO resize event, so without this the
    // description silently truncates with no toggle to reveal it, for the very
    // visitor who asked for larger text. Watching every attribute (rather than
    // filtering to one name) also covers the readable-font boost, and costs one
    // extra measure per menu toggle.
    const rootAttributes = new MutationObserver(measure);
    rootAttributes.observe(document.documentElement, { attributes: true });
    return () => {
      window.removeEventListener("resize", measure);
      rootAttributes.disconnect();
    };
  }, [text, expanded]);

  return (
    <div className="flex flex-col items-start gap-2">
      {/* text-base carries the design's 1.6 line-height from the theme — adding
          a leading- utility here would override the token. */}
      <p
        ref={paragraphRef}
        id={id}
        className={cn("text-base text-ink-muted", !expanded && "line-clamp-6")}
      >
        {text}
      </p>
      {(clampable || expanded) && (
        <Button
          variant="ghost"
          size="sm"
          aria-expanded={expanded}
          aria-controls={id}
          onClick={() => {
            setExpanded((open) => !open);
          }}
        >
          {expanded ? t("dress.less") : t("dress.more")}
        </Button>
      )}
    </div>
  );
}
