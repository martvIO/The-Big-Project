// The tab-scoped courtesy pointer to the most recent check-in made from this
// browsing context. It is NOT a security control and it is NOT dedup — the
// server holds nothing that maps a person to a ticket, by design.
//
// Session scope on purpose: one browser tab, one visit, gone when the tab
// closes. A store that outlived the tab would keep offering a stranger's ticket
// on a shared phone or a door tablet, and the id it holds is a live capability.
// The argument for the scope is in spec D8.
//
// The key is a BARE constant rather than anything per-boutique. The store is
// already partitioned by origin and every boutique is its own subdomain, so
// origin partitioning is what provides the isolation. (There is nothing to build
// a per-boutique key from either: BoutiqueResponse carries the display name,
// which the owner can rename — a rename would silently orphan every live
// pointer.)
//
// Its own module so the three call sites — a successful create, /checkin's
// mount, and the position page's terminals — share one key string.
const KEY = "checkin:ticket";

// A kiosk profile or a browser set to block all site data makes the store throw
// on ACCESS, not on write. /checkin is printed on a physical sign in the shop
// window, so an unguarded read would blank the product's most deep-linked page
// over a courtesy pointer.
function store(): Storage | null {
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

export function readCheckinTicket(): string | null {
  return store()?.getItem(KEY) ?? null;
}

export function writeCheckinTicket(ticketId: string): void {
  store()?.setItem(KEY, ticketId);
}

export function clearCheckinTicket(): void {
  store()?.removeItem(KEY);
}
