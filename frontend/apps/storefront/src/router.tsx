// oxlint-disable react/only-export-components -- the route table, navigate() and
// the two components are one unit; splitting them to buy fast refresh on a
// one-screen file is not a trade worth making.
import { useEffect, useRef, useSyncExternalStore } from "react";
import type { AnchorHTMLAttributes, MouseEvent as ReactMouseEvent, ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { AboutPage } from "./routes/AboutPage";
import { AccessibilityPage } from "./routes/AccessibilityPage";
import { BookPage } from "./routes/BookPage";
import { CatalogPage } from "./routes/CatalogPage";
import { CheckinPage } from "./routes/CheckinPage";
import { DressPage } from "./routes/DressPage";
import { ManageBookingPage } from "./routes/ManageBookingPage";
import { QueuePositionPage } from "./routes/QueuePositionPage";

// ponytail: hand-rolled router. The workspace carries no router dependency and
// the storefront has a handful of flat routes, so this is ~90 lines instead of
// one. Ceiling: no scroll restoration, no code splitting, no route-level data
// loaders — pages fetch their own. The booking flow needed no nesting after
// all: StorefrontLayout mounts ABOVE the Router in App.tsx, so /book/* already
// renders inside the shell and no dependency was added for it.
// Side effect worth keeping: with no back() to call, the qa-checklist ban on
// history-based back navigation is structural rather than a grep.

export type RouteName =
  | "catalog"
  | "dress"
  | "about"
  | "accessibility"
  | "book"
  | "manage"
  | "checkin"
  | "queuePosition";

// A closed set, which is what lets /book/{step} and /book/{step}/{dressId}
// share a shape: no dress id can ever be read as a step. `pay` joins it in flow
// order — it sits between the commit and the confirmation, and is reached only
// when a deposit is actually due.
export const BOOK_STEPS = ["slot", "details", "terms", "verify", "pay", "confirm"] as const;

export type BookStep = (typeof BOOK_STEPS)[number];

export type RouteMatch =
  | { name: "catalog" }
  | { name: "dress"; dressId: string }
  | { name: "about" }
  | { name: "accessibility" }
  | { name: "book"; step: BookStep; dressId?: string }
  // The token is opaque and is NOT validated here: an unknown or rotated token
  // has to reach the page so the page can render its own invalid-link state.
  | { name: "manage"; token: string }
  | { name: "checkin" }
  // Same rule, same reason: the ticket id is opaque here. An unknown, swept or
  // mistyped ticket has to reach the page so the page can render its own
  // not-found state and offer a way back to /checkin.
  | { name: "queuePosition"; ticketId: string };

// The id of StorefrontLayout's <main tabindex="-1">. Focus lands here after
// every client navigation, and the SkipLink targets it.
export const MAIN_ID = "content";

// pushState fires no event of its own — this is how the store learns about a
// programmatic navigation. popstate covers the browser's own back/forward.
const NAVIGATION_EVENT = "storefront:navigation";

const DOC_TITLE_KEYS: Record<RouteName, string> = {
  catalog: "document.catalog",
  dress: "document.dress",
  about: "document.about",
  accessibility: "document.accessibility",
  // One title for all five steps. BookPage must not write its own: React
  // flushes a child's passive effects before its parent's, so the effect below
  // would run last and clobber a per-step title.
  book: "document.book",
  // One title for all six manage states. She arrived from a text message, and an
  // outcome ("cancelled") does not belong in the tab strip.
  manage: "document.manageTitle",
  checkin: "document.checkin",
  // One title for every state of the position page, and it NEVER carries the
  // ticket id. The id is the capability, and a tab strip is read over a shoulder
  // in a shop. F33 establishes that rule; router.test.tsx is what holds it.
  queuePosition: "document.queuePosition",
};

const DRESS_PATH = /^\/dress\/([^/]+)$/;
const BOOK_PATH = /^\/book(?:\/([^/]+)(?:\/([^/]+))?)?$/;
// Short on purpose (spec D7): the URL rides inside a UCS-2 Hebrew SMS where every
// character is segment budget. /manage-booking/{token} would spend ~14 extra
// characters per message forever.
const MANAGE_PATH = /^\/b\/([^/]+)$/;
// Short for the same reason MANAGE_PATH is, plus one of its own: /checkin is
// printed on a physical sign in the shop window and this path is what the QR
// beside it resolves to, so every character is ink and every character is a
// chance to mistype. Deliberately disjoint from the /queue F59 adds: this
// pattern cannot match /queue and an exact /queue match cannot match /q/… .
const QUEUE_PATH = /^\/q\/([^/]+)$/;

function isBookStep(value: string): value is BookStep {
  return (BOOK_STEPS as readonly string[]).includes(value);
}

function decodeId(raw: string): string {
  try {
    return decodeURIComponent(raw);
  } catch {
    // A hand-typed URL with a stray "%" must 404 as a dress id, not throw out
    // of render and blank the page.
    return raw;
  }
}

export function matchRoute(pathname: string): RouteMatch {
  const path = pathname.replace(/\/+$/, "") || "/";
  if (path === "/about") return { name: "about" };
  if (path === "/accessibility") return { name: "accessibility" };
  if (path === "/checkin") return { name: "checkin" };

  const dress = DRESS_PATH.exec(path);
  if (dress) return { name: "dress", dressId: decodeId(dress[1]) };

  // BEFORE the catalog fallthrough, and that ordering is load-bearing: a bad
  // token must render the page's invalid-link state, never be silently swallowed
  // into the collection (spec D7/D8). Anything after /b/ matches.
  const manage = MANAGE_PATH.exec(path);
  if (manage) return { name: "manage", token: decodeId(manage[1]) };

  // Also BEFORE the catalog fallthrough, for the identical reason: a swept or
  // mistyped ticket must reach the position page's own not-found state. A woman
  // standing in the doorway who gets a dress grid instead has no way to learn
  // that her place in the queue is gone.
  const queue = QUEUE_PATH.exec(path);
  if (queue) return { name: "queuePosition", ticketId: decodeId(queue[1]) };

  const book = BOOK_PATH.exec(path);
  if (book !== null) {
    // Bare /book opens the flow on its first step rather than 404ing a URL a
    // bride can reasonably type. An unknown step is not a step, so it falls
    // through to the catalog below with every other unmatched path.
    const step = book[1] ?? "slot";
    const dressId = book[2];
    if (isBookStep(step)) {
      return dressId === undefined
        ? { name: "book", step }
        : { name: "book", step, dressId: decodeId(dressId) };
    }
  }

  // Everything else is the collection. The design ships no 404 page, and a
  // stale link out of an Instagram bio should land on the dresses, not a wall.
  return { name: "catalog" };
}

function subscribe(onStoreChange: () => void): () => void {
  window.addEventListener("popstate", onStoreChange);
  window.addEventListener(NAVIGATION_EVENT, onStoreChange);
  return () => {
    window.removeEventListener("popstate", onStoreChange);
    window.removeEventListener(NAVIGATION_EVENT, onStoreChange);
  };
}

function currentPathname(): string {
  return window.location.pathname;
}

export function usePathname(): string {
  return useSyncExternalStore(subscribe, currentPathname, currentPathname);
}

/**
 * `replace` is for GUARD redirects only — a step bouncing her off itself
 * because it has nothing to work with. Pushed, those trap the back button:
 * from /book/confirm, Back lands on /book/verify, the guard pushes
 * /book/confirm again, and the catalog is unreachable by Back forever.
 *
 * R26's accepted growing stack is the other case — a mid-flow recovery that
 * takes her somewhere she can act — and stays a push.
 */
export function navigate(to: string, options: { replace?: boolean } = {}): void {
  if (options.replace === true) {
    window.history.replaceState(null, "", to);
  } else {
    window.history.pushState(null, "", to);
  }
  window.dispatchEvent(new Event(NAVIGATION_EVENT));
}

/**
 * The hand-off OUT of the app — the payment provider's hosted page. A document
 * navigation, not a history push, which is why it is not `navigate`.
 *
 * An object with a method rather than a bare exported function, for two reasons
 * that are not style. `window.location`'s members are [LegacyUnforgeable] own
 * properties, so `vi.spyOn(window.location, "assign")` throws and jsdom refuses
 * the navigation outright — the call has to be replaceable somewhere. And this
 * module sits in an import CYCLE with the page that calls it (router imports
 * BookPage imports router), which makes `vi.mock`'s live binding resolve to the
 * real function inside the factory's own `importActual` — silently, so the test
 * passes its render assertions and simply never sees the redirect. A property
 * needs neither trick. A hand-off on a money surface that no test can observe
 * is one nobody notices breaking.
 */
export const handOff = {
  leave(url: string): void {
    window.location.assign(url);
  },
};

/**
 * Whether a click on `anchor` should become a client navigation.
 *
 * The exclusion list is the contract, not an optimisation. Stated loosely as
 * "same-origin left click without modifiers", this swallows SkipLink — a plain
 * <a href="#content"> — so preventDefault() would fire, the browser would never
 * perform the fragment navigation, focus would never move, and the WCAG item
 * the e2e suite asserts would silently fail. ContactPanel's tel: links and its
 * target="_blank" externals are the same class of problem.
 *
 * Shared by Link and by the root delegation below so the two can never drift:
 * DressCard renders a raw <a href> and takes no onNavigate prop, so delegation
 * is the only way to intercept the grid without reopening a gate-passed
 * component.
 */
export function shouldIntercept(
  event: Pick<MouseEvent, "defaultPrevented" | "button" | "metaKey" | "ctrlKey" | "shiftKey" | "altKey">,
  anchor: HTMLAnchorElement,
): boolean {
  if (
    event.defaultPrevented ||
    event.button !== 0 ||
    event.metaKey ||
    event.ctrlKey ||
    event.shiftKey ||
    event.altKey
  ) {
    // Modifier and non-primary clicks fall through to the browser so
    // "open in new tab" keeps working — storefront links live in an Instagram
    // bio and get opened that way constantly.
    return false;
  }
  if (anchor.target !== "" && anchor.target !== "_self") return false;
  if (anchor.hasAttribute("download")) return false;
  if (
    anchor.rel
      .split(/\s+/)
      .filter(Boolean)
      .includes("external")
  ) {
    return false;
  }

  let url: URL;
  try {
    url = new URL(anchor.href, window.location.href);
  } catch {
    return false;
  }
  // tel:, mailto:, whatsapp: — the browser owns every one of these.
  if (url.protocol !== "http:" && url.protocol !== "https:") return false;
  if (url.origin !== window.location.origin) return false;
  // Hash-only, or a hash on the page we are already on: this is the skip link
  // and any in-page anchor. Let the browser do the fragment jump.
  if (url.hash !== "" && url.pathname === window.location.pathname) return false;
  return true;
}

export interface LinkProps extends Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href"> {
  to: string;
  children: ReactNode;
}

// A real <a href> that upgrades a plain left click to a client navigation.
export function Link({ to, children, onClick, ...rest }: LinkProps) {
  const handleClick = (event: ReactMouseEvent<HTMLAnchorElement>) => {
    onClick?.(event);
    if (!shouldIntercept(event, event.currentTarget)) return;
    event.preventDefault();
    navigate(to);
  };

  return (
    <a {...rest} href={to} onClick={handleClick}>
      {children}
    </a>
  );
}

export function Router() {
  const { t } = useTranslation();
  const pathname = usePathname();
  const match = matchRoute(pathname);
  // Keyed on the path rather than a boolean so React 19 StrictMode's
  // double-invoked effect doesn't read as a navigation and steal focus.
  const handledPath = useRef<string | null>(null);

  // ONE delegated listener at the app root. This is what lets a raw <a href>
  // rendered inside a gate-passed packages/ui component (DressCard) become a
  // client navigation without that component taking an onNavigate prop.
  useEffect(() => {
    const onClick = (event: MouseEvent) => {
      const target = event.target;
      if (!(target instanceof Element)) return;
      const anchor = target.closest("a");
      if (anchor === null) return;
      if (!shouldIntercept(event, anchor)) return;
      event.preventDefault();
      navigate(anchor.getAttribute("href") ?? "/");
    };
    document.addEventListener("click", onClick);
    return () => {
      document.removeEventListener("click", onClick);
    };
  }, []);

  useEffect(() => {
    document.title = t(DOC_TITLE_KEYS[match.name]);
    const previous = handledPath.current;
    handledPath.current = pathname;
    if (previous === null || previous === pathname) {
      // First paint: the browser owns focus and the skip link is the first
      // stop. Taking focus here would defeat it.
      return;
    }
    // WCAG 2.4.2 (Level A) + focus management: a client navigation replaces the
    // page, so the title changes, focus lands at the top of the new content and
    // the viewport returns to the top. Without the scroll reset a bride who
    // taps a card in grid row 5 lands on the dress page still scrolled to row 5.
    window.scrollTo(0, 0);
    document.getElementById(MAIN_ID)?.focus();
  }, [pathname, match.name, t]);

  switch (match.name) {
    case "dress":
      return <DressPage dressId={match.dressId} />;
    case "about":
      return <AboutPage />;
    case "accessibility":
      return <AccessibilityPage />;
    case "book":
      return <BookPage step={match.step} dressId={match.dressId} />;
    case "manage":
      return <ManageBookingPage token={match.token} />;
    case "checkin":
      return <CheckinPage />;
    case "queuePosition":
      return <QueuePositionPage ticketId={match.ticketId} />;
    // ⚠ A missing `case` compiles clean, typechecks clean and renders the dress
    // grid under the route's own title, because of the fallthrough below —
    // DOC_TITLE_KEYS is compiler-forced but this switch is not. `checkin`
    // shipped that way for one commit and every title assertion stayed green.
    // What catches it is the pair of render assertions in router.test.tsx that
    // check the page mounted AND that the catalogue did not.
    default:
      return <CatalogPage />;
  }
}
