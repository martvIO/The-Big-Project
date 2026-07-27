// oxlint-disable react/only-export-components -- the route table, navigate() and
// the two components are one unit; splitting them to buy fast refresh on a
// four-route file is not a trade worth making.
import { useEffect, useRef, useSyncExternalStore } from "react";
import type { AnchorHTMLAttributes, MouseEvent, ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { About } from "./pages/About";
import { Accessibility } from "./pages/Accessibility";
import { Catalog } from "./pages/Catalog";
import { DressDetail } from "./pages/DressDetail";

// ponytail: hand-rolled router. The workspace carries no router dependency and
// the storefront has four flat routes, so this is ~40 lines instead of one.
// Ceiling: no nested routes, no scroll restoration, no code splitting, no
// route-level data loaders — pages fetch their own. Swap in react-router when
// E3's booking flow needs nested layouts; ROUTES below is the seam.
// Side effect worth keeping: with no back() to call, the qa-checklist ban on
// history-based back navigation is structural rather than a grep.

export type RouteName = "catalog" | "dress" | "about" | "accessibility";

export type RouteMatch =
  | { name: "catalog" }
  | { name: "dress"; dressId: string }
  | { name: "about" }
  | { name: "accessibility" };

// The id of App.tsx's <main tabindex="-1">. Focus lands here after every client
// navigation, and the SkipLink targets it.
export const MAIN_ID = "main";

// pushState fires no event of its own — this is how the store learns about a
// programmatic navigation. popstate covers the browser's own back/forward.
const NAVIGATION_EVENT = "storefront:navigation";

const DOC_TITLE_KEYS: Record<RouteName, string> = {
  catalog: "doc.catalog",
  dress: "doc.dress",
  about: "doc.about",
  accessibility: "doc.accessibility",
};

const DRESS_PATH = /^\/dress\/([^/]+)$/;

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

  const dress = DRESS_PATH.exec(path);
  if (dress) return { name: "dress", dressId: decodeId(dress[1]) };

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

export function navigate(to: string): void {
  window.history.pushState(null, "", to);
  window.dispatchEvent(new Event(NAVIGATION_EVENT));
}

export interface LinkProps extends Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href"> {
  to: string;
  children: ReactNode;
}

// A real <a href> that upgrades a plain left click to a client navigation.
export function Link({ to, children, onClick, ...rest }: LinkProps) {
  const handleClick = (event: MouseEvent<HTMLAnchorElement>) => {
    onClick?.(event);
    // Modifier and non-primary clicks fall through to the browser so
    // "open in new tab" keeps working — storefront links live in an Instagram
    // bio and get opened that way constantly.
    if (
      event.defaultPrevented ||
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey
    ) {
      return;
    }
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
    // page, so the title changes and focus lands at the top of the new content.
    document.getElementById(MAIN_ID)?.focus();
  }, [pathname, match.name, t]);

  switch (match.name) {
    case "dress":
      return <DressDetail dressId={match.dressId} />;
    case "about":
      return <About />;
    case "accessibility":
      return <Accessibility />;
    default:
      return <Catalog />;
  }
}
