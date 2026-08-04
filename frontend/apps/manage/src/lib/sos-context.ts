import { createContext, useContext } from "react";
import type { RaisedAlert, RaiseSosRequest, SosAlert } from "../api";
import type { PollTerminal } from "./usePoll";

// Split from sos.tsx for `@boutique/ui`'s shipped reason and no other: a file
// that exports both a component and a hook loses fast refresh, which is what
// `toast-context.ts` sitting beside `Toast.tsx` is already there for. The
// provider is the precedent this whole shape copies, so it is copied whole.

export interface RaiseOutcome {
  /** The created alert, or `null` when the request did not complete. */
  raised: RaisedAlert | null;
  /** `null` when it succeeded OR was terminal; the error otherwise. */
  failure: unknown;
}

export interface SosContextValue {
  /** Live alerts visible to this caller, oldest first. */
  alerts: SosAlert[];
  /** The server's own instant at the last successful read, for elapsed lines. */
  serverNow: string | null;
  terminal: PollTerminal | null;
  /** A 403, or a loop backed off beyond one tick. Renders the persistent strip. */
  channelDown: boolean;
  raise: (body: RaiseSosRequest) => Promise<RaiseOutcome>;
  accept: (alertId: string) => Promise<unknown>;
  resolve: (alertId: string) => Promise<unknown>;
  cancel: (alertId: string) => Promise<unknown>;
}

export const SosContext = createContext<SosContextValue | null>(null);

export function useSos(): SosContextValue {
  const value = useContext(SosContext);
  if (value === null) {
    // Loud rather than inert. A component that reads this outside the provider
    // is one that would render a permanently empty emergency channel — the
    // exact failure this feature exists to make impossible.
    throw new Error("useSos must be used inside <SosProvider>");
  }
  return value;
}
