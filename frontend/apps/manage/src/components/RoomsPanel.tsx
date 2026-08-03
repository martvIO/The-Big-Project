import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Badge, Button, Card, EmptyState, Select } from "@boutique/ui";
import type { BadgeVariant } from "@boutique/ui";
import { api, ApiError } from "../api";
import type { FloorClient, Room, RoomAssignment } from "../api";
import { isolateBidi } from "../lib/booking";
import { elapsedLine } from "../lib/elapsed";
import { jerusalemTime } from "../lib/jerusalem";
import { roleLabelKey } from "../lib/roles";
import { RoomsRegistryDialog } from "./RoomsRegistryDialog";

// F36. One tile per fitting room, inside FloorPanel and UNDER ITS POLL.
//
// **A CHILD, not a sibling** (spec D15): no usePoll instance, no timer, no pause
// control and no announced region of its own. It receives the rooms, the
// server's instant, the shared `mutate` dance and the shared cue setter as
// props. Three things fall out and each is an a11y win rather than an
// architectural convenience — one SC 2.2.2 mechanism instead of two, one
// role="status" so a room cue and a break cue cannot talk over each other, and
// one freshness claim that is true of the rooms and the staff cards
// simultaneously because they arrive in the same response.
//
// ⚠ Which control EXISTS is the rendered form of the authorization axes. A 403
// is TERMINAL for the whole floor screen (usePoll.terminalOf returns "access"
// for any 403), and for the three floor roles that is the entire product going
// dark — so a control the server would refuse is never rendered at all. No
// disabled button, no lock glyph, no «אין לך הרשאה» line, no tooltip. The
// absence is cosmetics; the control is the server's check.

const ELEVATED = new Set(["owner", "shift_manager"]);

// The one place a room's status becomes a word. THREE outcomes and no fallback:
// occupancy wins the Badge, and the out-of-service flag takes a word line when
// it loses (§2.3) — a person is standing in that room, and a screen that puts
// «מחוץ לשירות» where «תפוס» belongs denies something a shift manager can see
// through the curtain.
function badgeOf(room: Room): { variant: BadgeVariant; labelKey: string } {
  if (room.assignment !== null) {
    return { variant: "neutral", labelKey: "rooms.occupied" };
  }
  return room.is_active
    ? { variant: "success", labelKey: "rooms.free" }
    : { variant: "muted", labelKey: "rooms.inactive" };
}

// Whether the focused element sits inside a tile that the incoming list drops.
// FloorPanel's `departingCardHoldsFocus` shape, asking the question one tile at
// a time.
function departingTileHoldsFocus(incoming: readonly Room[]): boolean {
  const active = document.activeElement;
  if (!(active instanceof Element)) {
    return false;
  }
  const held = active.closest("[data-room-id]")?.getAttribute("data-room-id");
  if (held === undefined || held === null) {
    return false;
  }
  return !incoming.some((room) => room.id === held);
}

// Which dialog is open, and on which tile. The dialogs themselves are separate
// components; what lives here is the trigger, the target and the focus return,
// because the trigger is a tile control and the tile is this component's.
type DialogTarget =
  | { kind: "registry" }
  | { kind: "dress" | "handover"; roomId: string; assignmentId: string; label: string };

// A refused action, scoped to its tile. `value` is the ONE interpolated run the
// sentence carries — a name or a room label — which has to render inside a bare
// <bdi> and cannot be found in a flat string after the fact. `outage` picks the
// register: a mapped code is a NOTICE (--color-warning-text), an unmapped one is
// an OUTAGE (--color-ink-muted). Never --color-danger: nothing that can go wrong
// on this surface is her fault.
interface TileError {
  id: string;
  text: string;
  value: string | null;
  outage: boolean;
}

interface RoomsPanelProps {
  /** Every live room, active and inactive, in the server's own order. */
  rooms: Room[] | null;
  /** The envelope's own instant — the elapsed anchor, never the device clock. */
  serverNow: string | null;
  /**
   * How many ticks have SUCCEEDED. A counter and not the payload, because the
   * tile alert's promise («הרשימה תתוקן בעדכון הבא») is kept by the update
   * happening and not by the update differing: a tick that answers a byte-equal
   * list is still the update that was promised. FloorPanel keeps the same rule
   * for its own card alert by clearing it imperatively inside `load`, which a
   * child cannot do.
   */
  fetchCount: number;
  selfId: string;
  role: string;
  /** `mode !== "running"`. DC-8: a stopped panel has no next update to promise. */
  paused: boolean;
  /** FloorPanel's shared five-part dance. Null means done, anything else is the error. */
  mutate: (fn: () => Promise<void>) => Promise<unknown>;
  onRooms: (next: Room[]) => void;
  onCue: (cue: { text: string; name: string | null }) => void;
}

export function RoomsPanel({
  rooms,
  serverNow,
  fetchCount,
  selfId,
  role,
  paused,
  mutate,
  onRooms,
  onCue,
}: RoomsPanelProps) {
  const { t } = useTranslation();

  // ⚠ KEYED BY ROOM ID, never by index (DC-4). Tiles are keyed by room.id too,
  // so React preserves the subtree and a repaint mutates text nodes inside a
  // stable element — a tick landing with a client selected on tile 3 leaves that
  // selection alone. Keyed by position, the same tick's reorder would bind the
  // next claim to the wrong bride with no error anywhere.
  const [clientPick, setClientPick] = useState<Record<string, string>>({});
  const [clients, setClients] = useState<FloorClient[] | null>(null);
  const [clientsTruncated, setClientsTruncated] = useState(false);
  const [busyIds, setBusyIds] = useState<readonly string[]>([]);
  const [tileError, setTileError] = useState<TileError | null>(null);
  const [openDialog, setOpenDialog] = useState<DialogTarget | null>(null);

  const headingRef = useRef<HTMLHeadingElement>(null);
  const tileAlertRef = useRef<HTMLParagraphElement>(null);
  // The tile's CURRENT primary control, by room id. Keyed by id and not held as
  // one ref because the free and occupied action rows have different shapes — a
  // Select appears and disappears beside the button — so React may or may not
  // reuse the DOM node, and the design must not depend on which.
  const controlRefs = useRef(new Map<string, HTMLButtonElement | null>());
  const dialogTriggerRef = useRef<HTMLButtonElement | null>(null);
  const restoreFocusRef = useRef<string | null>(null);
  const reclaimFocusRef = useRef<string | null>(null);
  const focusHeadingRef = useRef(false);
  const roomsRef = useRef<Room[] | null>(null);
  const fetchRef = useRef(fetchCount);

  // ⚠ BOTH OF THESE RUN DURING RENDER, because this is the only moment the old
  // DOM and the new list exist together: by the time an effect runs the
  // departing tile is already gone and the focused alert is already unmounted,
  // activeElement has dropped to <body>, and the question cannot be asked any
  // more. FloorPanel:147 does exactly this inside `load` for the same reason.
  if (fetchRef.current !== fetchCount) {
    fetchRef.current = fetchCount;
    // MOVE 6, and DC-1: the alert this tick is about to clear may be HOLDING
    // FOCUS. It promises «הרשימה תתוקן בעדכון הבא» and this is the update that
    // keeps it — about five seconds after the refusal, with no user action at
    // all. Removing a focused node drops activeElement to <body>, so her next
    // Tab restarts at the skip link. FloorPanel:167 is the shipped analogue.
    if (tileAlertRef.current !== null && document.activeElement === tileAlertRef.current) {
      reclaimFocusRef.current = tileError?.id ?? null;
    }
  }
  if (roomsRef.current !== rooms) {
    const previous = roomsRef.current;
    roomsRef.current = rooms;
    if (previous !== null && rooms !== null) {
      // MOVE 3, and DC-6: a tile leaves by a registry delete OR by a TICK —
      // another elevated user deleting a room from her own device, which
      // arrives through the rooms payload and not through this user's handler.
      focusHeadingRef.current = departingTileHoldsFocus(rooms);
    }
  }

  useEffect(() => {
    // ONE SHOT, on mount and never on the tick (spec D16). The claim path
    // refetches after each success, which is the other trigger and the only
    // other one — no timer and no cache.
    //
    // A failed or empty list is not an error state: the picker is ABSENT and
    // the claim proceeds anonymously, which is the ordinary early-morning tile.
    let cancelled = false;
    api
      .listFloorClients()
      .then((list) => {
        if (!cancelled) {
          setClients(list.clients);
          setClientsTruncated(list.truncated);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setClients([]);
          setClientsTruncated(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    // The tile alert's own promise, kept: every successful tick clears it.
    // Keyed on the COUNTER and not on `rooms`, because a tick that answers an
    // unchanged list still kept the promise — and a failed tick never gets
    // here, so a refused claim's sentence survives exactly as long as the panel
    // has nothing newer to say.
    setTileError(null);
  }, [fetchCount]);

  useEffect(() => {
    // MOVE 1 — after a FAILED action, focus moves into the tile's alert. Keyed
    // on the error state rather than raised inside the handler, because the
    // alert node does not exist yet when setTileError runs. THE FAILURE PATH IS
    // THE ONE THAT GETS FORGOTTEN: this bug class shipped three times in this
    // repo and axe walked past all three, because axe cannot see a focus move
    // that never happened.
    if (tileError !== null) {
      tileAlertRef.current?.focus();
      return;
    }
    // MOVE 6 — …and when a tick CLEARS it while it held focus, hand focus back
    // to that tile's own control, where she was when she tapped.
    const reclaim = reclaimFocusRef.current;
    reclaimFocusRef.current = null;
    if (reclaim === null || document.activeElement !== document.body) {
      return;
    }
    const control = controlRefs.current.get(reclaim);
    if (control !== undefined && control !== null) {
      control.focus();
      return;
    }
    headingRef.current?.focus();
  }, [tileError]);

  useEffect(() => {
    // MOVE 2 — after a SUCCESSFUL action, focus returns to the tile's current
    // primary control. @boutique/ui's Button is disabled={disabled || loading},
    // so a real browser blurred the tapped control the instant the request
    // started; the body guard is what stops this stealing focus from wherever
    // she moved it in the meantime.
    const pending = restoreFocusRef.current;
    if (pending === null || busyIds.includes(pending)) {
      return;
    }
    restoreFocusRef.current = null;
    if (document.activeElement !== document.body) {
      return;
    }
    const control = controlRefs.current.get(pending);
    if (control !== undefined && control !== null) {
      control.focus();
      return;
    }
    headingRef.current?.focus();
  }, [busyIds]);

  useEffect(() => {
    // MOVE 3 — a tile that LEFT the list while holding focus hands focus to the
    // rooms heading. The flag is set during render, above, because that is the
    // only moment both lists exist.
    if (!focusHeadingRef.current) {
      return;
    }
    focusHeadingRef.current = false;
    if (document.activeElement === document.body) {
      headingRef.current?.focus();
    }
  }, [rooms]);

  useEffect(() => {
    // MOVE 4 — closing a dialog returns focus to the tile's trigger, falling
    // back to the h3 when that trigger is gone (F51's shipped isConnected
    // shape, StaffSection.tsx:80-92). The native <dialog>'s own return fires
    // second and would otherwise win, which is why the collision is resolved
    // here explicitly and not left to the platform.
    if (openDialog !== null) {
      return;
    }
    const trigger = dialogTriggerRef.current;
    if (trigger === null) {
      return;
    }
    dialogTriggerRef.current = null;
    if (document.activeElement !== document.body) {
      return;
    }
    if (trigger.isConnected) {
      trigger.focus();
      return;
    }
    headingRef.current?.focus();
  }, [openDialog]);

  const reloadClients = () => {
    api
      .listFloorClients()
      .then((list) => {
        setClients(list.clients);
        setClientsTruncated(list.truncated);
      })
      .catch(() => {
        setClients([]);
        setClientsTruncated(false);
      });
  };

  // The two 404s are DIFFERENT SENTENCES and that is a correction to the spec's
  // single key: «החדר כבר לא זמין» is actively misleading when the room is fine
  // and the fitting simply ended.
  const describe = (error: unknown, target: "room" | "assignment"): Omit<TileError, "id"> => {
    if (error instanceof ApiError && error.status === 409 && error.code === "ROOM_OCCUPIED") {
      const name = error.details?.staff_display_name;
      return name === undefined
        ? { text: t("rooms.error.roomOccupiedUnknown"), value: null, outage: false }
        : { text: t("rooms.error.ROOM_OCCUPIED", { name }), value: name, outage: false };
    }
    if (error instanceof ApiError && error.status === 409 && error.code === "STAFF_OCCUPIED") {
      const room = error.details?.room_label;
      return room === undefined
        ? { text: t("rooms.error.staffOccupiedUnknown"), value: null, outage: false }
        : { text: t("rooms.error.STAFF_OCCUPIED", { room }), value: room, outage: false };
    }
    if (error instanceof ApiError && error.status === 404) {
      // DC-8. pause() stops the loop and `mode` is read only for the freshness
      // stamp, so a claim is fully available while paused — and «הרשימה תתוקן
      // בעדכון הבא» is then a promise the screen will not keep. Same failure as
      // naming a retry interval, in the EVENT form.
      const running = target === "room" ? "rooms.error.notFound" : "rooms.error.assignmentGone";
      const stopped =
        target === "room" ? "rooms.error.notFoundPaused" : "rooms.error.assignmentGonePaused";
      return { text: t(paused ? stopped : running), value: null, outage: false };
    }
    // A 5xx or a dropped request: the OUTAGE register, and a SHIPPED key rather
    // than errorMessage(error) leaking the server's English onto a Hebrew-only
    // surface.
    return { text: t("staff.loadFailed"), value: null, outage: true };
  };

  const act = async (roomId: string, target: "room" | "assignment", fn: () => Promise<void>) => {
    setBusyIds((current) => [...current, roomId]);
    setTileError(null);
    restoreFocusRef.current = roomId;
    const failure = await mutate(fn);
    setBusyIds((current) => current.filter((id) => id !== roomId));
    if (failure !== null) {
      // Move 1 owns the failure path; clearing this stops move 2 grabbing focus
      // for one commit on its way past.
      restoreFocusRef.current = null;
      setTileError({ id: roomId, ...describe(failure, target) });
    }
  };

  // NOT optimistic. The tile is patched from the SERVER's own row — every
  // mutation answers exactly what the payload's rooms[] elements carry — so the
  // panel cannot disagree with itself, and on an idempotent re-claim that is
  // what renders the FIRST holder rather than this request's intent.
  const patch = (next: Room) => {
    onRooms((rooms ?? []).map((item) => (item.id === next.id ? next : item)));
  };

  const claim = (room: Room) => {
    const booking = clientPick[room.id] ?? "";
    void act(room.id, "room", async () => {
      // `{}` IS the one-tap anonymous claim on herself — the default path, and
      // the only one available before the day's first arrival. `staff_user_id`
      // is never sent: the acting identity is the session cookie.
      const patched = await api.claimRoom(room.id, booking === "" ? {} : { booking_id: booking });
      patch(patched);
      // The cue names the ROOM and never the client. The region is PERSISTENT —
      // nothing clears it on a timer — so a bride's name in it would sit on a
      // five-role screen for an arbitrary length of time, in a room she is
      // standing in. The tile one line away carries her name for exactly as long
      // as the fitting lasts.
      onCue({ text: t("rooms.claimedCue", { room: patched.label }), name: patched.label });
      reloadClients();
    });
  };

  const release = (room: Room, assignment: RoomAssignment) => {
    void act(room.id, "assignment", async () => {
      const patched = await api.releaseAssignment(assignment.id);
      patch(patched);
      // A second release is a 200 that writes nothing and reads identically:
      // she wanted the room free, the room is free.
      onCue({ text: t("rooms.releasedCue", { room: patched.label }), name: patched.label });
    });
  };

  const removeDress = (room: Room, assignmentId: string, bindingId: string, dress: string) => {
    void act(room.id, "assignment", async () => {
      const patched = await api.removeAssignmentDress(assignmentId, bindingId);
      patch(patched);
      onCue({ text: t("rooms.dressRemovedCue", { dress }), name: dress });
    });
  };

  const openFrom = (event: { currentTarget: HTMLButtonElement }, target: DialogTarget) => {
    dialogTriggerRef.current = event.currentTarget;
    setOpenDialog(target);
  };

  const elevated = ELEVATED.has(role);

  // The h3 renders in EVERY state including R-empty (DC-10), because it is move
  // 3's and move 6's focus-rescue target: deleting your only room returns the
  // panel to the EmptyState and replaces the heading-row trigger with the CTA,
  // and the rescue target has to survive both transitions.
  const heading = (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h3 ref={headingRef} tabIndex={-1} className="text-base font-semibold text-ink">
        {t("rooms.heading")}
      </h3>
      {elevated && rooms !== null && rooms.length > 0 && (
        <Button
          variant="ghost"
          size="md"
          fullWidthMobile={false}
          onClick={(event) => openFrom(event, { kind: "registry" })}
        >
          {t("rooms.manage")}
        </Button>
      )}
    </div>
  );

  // R-load is FloorPanel's Skeleton: nothing is auto-updating yet and there is
  // no room list to be current about.
  if (rooms === null) {
    return null;
  }

  const registry = (
    <RoomsRegistryDialog
      open={openDialog?.kind === "registry"}
      onClose={() => setOpenDialog(null)}
      rooms={rooms}
      onRooms={onRooms}
      mutate={mutate}
    />
  );

  return (
    <div className="space-y-3">
      {heading}

      <Card>
        {rooms.length === 0 ? (
          // No body in either case: for the two roles who can act the title plus
          // a button is the whole instruction, and for the three who cannot a
          // body would be a paragraph explaining a capability they do not have.
          <EmptyState
            title={t("rooms.empty")}
            action={
              elevated ? (
                <Button
                  variant="secondary"
                  size="md"
                  fullWidthMobile={false}
                  onClick={(event) => openFrom(event, { kind: "registry" })}
                >
                  {t("rooms.emptyCta")}
                </Button>
              ) : undefined
            }
          />
        ) : (
          <ul className="divide-y divide-border">
            {rooms.map((room) => {
              const assignment = room.assignment;
              const badge = badgeOf(room);
              const busy = busyIds.includes(room.id);
              const mayRelease =
                assignment !== null && (assignment.staff_user_id === selfId || elevated);
              const roleKey = assignment === null ? null : roleLabelKey(assignment.staff_role ?? "");
              const picker =
                assignment === null && room.is_active && clients !== null && clients.length > 0;
              return (
                <li
                  key={room.id}
                  data-room-id={room.id}
                  className="flex flex-col gap-3 py-4 sm:flex-row sm:items-start"
                >
                  <div className="min-w-0 grow space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      {/* Bare <bdi>, never dir="ltr" — a boutique may type «הבמה»
                          or «VIP Room» and forcing LTR on the first reverses its
                          words. No truncation and no ellipsis, ever: a panel that
                          abbreviates makes two rooms look like one. */}
                      <bdi
                        className={`font-semibold break-words ${
                          room.is_active ? "text-ink" : "text-ink-muted"
                        }`}
                      >
                        {room.label}
                      </bdi>
                      {/* ONE Badge per tile and it is the occupancy. The holder's
                          role is muted words: two pills in 295px teaches the
                          reader to scan colours instead of words, which is how a
                          status vocabulary dies. */}
                      <Badge variant={badge.variant}>{t(badge.labelKey)}</Badge>
                    </div>

                    {/* Out of service AND occupied: one Badge, both facts. */}
                    {!room.is_active && assignment !== null && (
                      <p className="text-sm text-ink-muted">{t("rooms.inactive")}</p>
                    )}

                    {assignment !== null && (
                      <>
                        {assignment.staff_display_name === null ? (
                          // D11's GHOST HOLDER: F51's soft_delete has no
                          // interaction rule with an open assignment, so a
                          // staffer removed mid-fitting leaves a live assignment
                          // with no card on the floor. The tile says so and does
                          // not speculate about why.
                          <p className="text-sm break-words text-ink">{t("rooms.holderGone")}</p>
                        ) : (
                          <p>
                            <bdi className="font-semibold break-words text-ink">
                              {assignment.staff_display_name}
                            </bdi>
                          </p>
                        )}
                        {/* DC-12. roleLabelKey answers `string | null`, and the
                            tile takes the OMIT branch on an unrecognised role:
                            a raw slug under a Hebrew name on a tile is noise,
                            where on a staff card it is the only thing
                            distinguishing two cards. Dropped for a ghost holder
                            too — there is no role to show. */}
                        {assignment.staff_display_name !== null && roleKey !== null && (
                          <p className="text-sm text-ink-muted">
                            <bdi>{t(roleKey)}</bdi>
                          </p>
                        )}
                        {/* The client's name is its own element beside a muted
                            label word, never interpolated into a sentence — which
                            is why this feature needs no third bidi helper. */}
                        {assignment.client_label === null ? (
                          <p className="text-sm break-words text-ink-muted">
                            {t("rooms.anonymous")}
                          </p>
                        ) : (
                          <p className="text-sm break-words text-ink">
                            <span className="text-ink-muted">{t("rooms.clientLabel")}</span>{" "}
                            <bdi>{assignment.client_label}</bdi>
                          </p>
                        )}
                        {serverNow !== null && (
                          <p className="text-sm text-ink">
                            {elapsedLine(t, serverNow, assignment.assigned_at)}
                          </p>
                        )}
                        {assignment.dresses.length > 0 && (
                          <>
                            {/* A <p>, not a heading, and the <ul> gets no
                                accessible name: aria-labelledby would need a
                                useId() per tile to avoid duplicate ids across
                                five rooms, and buys a name this paragraph
                                already gives in document order. */}
                            <p className="text-sm text-ink-muted">{t("rooms.dresses")}</p>
                            <ul>
                              {assignment.dresses.map((binding) => (
                                <li
                                  key={binding.id}
                                  className="flex items-center justify-between gap-3 text-sm text-ink"
                                >
                                  {/* DC-7: min-w-0 or a long gown name cannot
                                      shrink and pushes «הסרה» out of a 295px
                                      tile. */}
                                  <span className="min-w-0 break-words">
                                    <bdi>{binding.dress_name}</bdi>
                                    {binding.dress_size !== null && (
                                      <>
                                        {" · "}
                                        <bdi dir="ltr">{binding.dress_size}</bdi>
                                      </>
                                    )}
                                  </span>
                                  <Button
                                    variant="ghost"
                                    size="md"
                                    fullWidthMobile={false}
                                    loading={busy}
                                    // Names the DRESS and not the room: five
                                    // rooms with four gowns each is twenty
                                    // «הסרה» buttons, and the gown is what she
                                    // is pointing at.
                                    aria-label={t("rooms.removeDressAria", {
                                      dress: binding.dress_name,
                                    })}
                                    onClick={() =>
                                      removeDress(
                                        room,
                                        assignment.id,
                                        binding.id,
                                        binding.dress_name,
                                      )
                                    }
                                  >
                                    {t("rooms.removeDress")}
                                  </Button>
                                </li>
                              ))}
                            </ul>
                          </>
                        )}
                      </>
                    )}

                    {picker && (
                      <>
                        {/* The VISIBLE label carries the room, which is what
                            disambiguates up to six identical pickers — and it
                            makes the accessible name BE the visible label, so
                            WCAG 2.5.3 holds by construction rather than by an
                            assertion. min-h-11 because Select declares no
                            min-h-* at all (deck F-4), so cn()'s plain join has
                            no fight to lose. */}
                        <Select
                          label={t("rooms.clientPick", { room: room.label })}
                          className="min-h-11"
                          value={clientPick[room.id] ?? ""}
                          onChange={(event) =>
                            setClientPick((current) => ({
                              ...current,
                              [room.id]: event.target.value,
                            }))
                          }
                        >
                          <option value="">{t("rooms.clientNone")}</option>
                          {(clients ?? []).map((client) => (
                            <option key={client.booking_id} value={client.booking_id}>
                              {`${client.client_label ?? t("rooms.anonymous")} · ${jerusalemTime(
                                client.starts_at,
                              )}`}
                            </option>
                          ))}
                        </Select>
                        {clientsTruncated && (
                          <p className="text-sm text-ink-muted">{t("rooms.clientsTruncated")}</p>
                        )}
                      </>
                    )}

                    {tileError?.id === room.id && (
                      <p
                        ref={tileAlertRef}
                        role="alert"
                        tabIndex={-1}
                        className={
                          tileError.outage
                            ? "text-sm text-ink-muted"
                            : "text-sm font-semibold text-warning-text"
                        }
                      >
                        {tileError.value === null
                          ? tileError.text
                          : isolateBidi(tileError.text, tileError.value)}
                      </p>
                    )}
                  </div>

                  {/* Controls wrap to a second line rather than shrinking: three
                      full-width buttons per tile would be a wall. ONE `secondary`
                      per tile and it is the act that ENDS the tile's current
                      state — the time-critical one, because a bride is waiting. */}
                  <div className="flex flex-wrap justify-end gap-3">
                    {assignment === null && room.is_active && (
                      <Button
                        ref={(node) => {
                          controlRefs.current.set(room.id, node);
                        }}
                        variant="secondary"
                        size="md"
                        fullWidthMobile={false}
                        loading={busy}
                        aria-label={t("rooms.claimAria", { room: room.label })}
                        onClick={() => claim(room)}
                      >
                        {t("rooms.claim")}
                      </Button>
                    )}
                    {assignment !== null && (
                      <>
                        {/* All five roles, no ownership check (spec D4): a
                            colleague fetching a second gown for a fitting
                            already in progress is the normal case on a shop
                            floor, and binding a dress is not a destructive act
                            on the holder's room. */}
                        <Button
                          variant="ghost"
                          size="md"
                          fullWidthMobile={false}
                          aria-label={t("rooms.addDressAria", { room: room.label })}
                          onClick={(event) =>
                            openFrom(event, {
                              kind: "dress",
                              roomId: room.id,
                              assignmentId: assignment.id,
                              label: room.label,
                            })
                          }
                        >
                          {t("rooms.addDress")}
                        </Button>
                        {/* A handover TAKES a room from one worker and gives it
                            to another who has not consented, so "any staffer may
                            act on herself" does not reach it (spec D8). */}
                        {elevated && (
                          <Button
                            variant="ghost"
                            size="md"
                            fullWidthMobile={false}
                            aria-label={t("rooms.handoverAria", { room: room.label })}
                            onClick={(event) =>
                              openFrom(event, {
                                kind: "handover",
                                roomId: room.id,
                                assignmentId: assignment.id,
                                label: room.label,
                              })
                            }
                          >
                            {t("rooms.handover")}
                          </Button>
                        )}
                        {/* One tap, no confirm: it is reversible in one tap, it
                            writes one timestamp, and a shift manager clearing up
                            after somebody who went home does it several times a
                            shift. */}
                        {mayRelease && (
                          <Button
                            ref={(node) => {
                              controlRefs.current.set(room.id, node);
                            }}
                            variant="secondary"
                            size="md"
                            fullWidthMobile={false}
                            loading={busy}
                            aria-label={t("rooms.releaseAria", { room: room.label })}
                            onClick={() => release(room, assignment)}
                          >
                            {t("rooms.release")}
                          </Button>
                        )}
                      </>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </Card>

      {registry}
    </div>
  );
}
