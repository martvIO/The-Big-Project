import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Badge, Button, Card, EmptyState, Select } from "@boutique/ui";
import type { BadgeVariant } from "@boutique/ui";
import { api, ApiError } from "../api";
import type { DispatchResult, FloorClient, Room, RoomAssignment, StaffCard } from "../api";
import { isolateBidi } from "../lib/booking";
import { elapsedLine } from "../lib/elapsed";
import { jerusalemTime } from "../lib/jerusalem";
import { roleLabelKey } from "../lib/roles";
import { RoomDressDialog } from "./RoomDressDialog";
import { RoomHandoverDialog } from "./RoomHandoverDialog";
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
  /**
   * The same payload's staff cards. The handover's colleague list is built from
   * THIS and not from a second request — no new endpoint, no second fetch, and
   * no second thing that can be a tick out of date.
   */
  staff: StaffCard[] | null;
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
  /**
   * An UPDATER and never a finished list: two tiles can be in flight at once
   * (`busy` is per room, `mutate` counts rather than latches), so a handler
   * that rebuilt the list from the `rooms` prop it closed over discarded the
   * other handler's patch. See FloorPanel.applyRooms.
   */
  onRooms: (update: (current: Room[]) => Room[]) => void;
  onCue: (cue: { text: string; name: string | null }) => void;
  /**
   * F58. How many walk-ins are waiting. A COUNT and not the list: this panel
   * neither renders an entry nor picks one — the server takes the head of the
   * queue — so the only thing the tile needs to know is whether there is
   * anybody to take. It decides two things: whether «קחי את הבאה» is rendered
   * at all (§3.1 — an empty queue REMOVES the control rather than refusing the
   * tap), and which of the tile's two controls owns the `controlRefs` slot
   * (DC-2).
   */
  waitlistCount: number;
  /**
   * A dispatch answers the tile AND the queue, so it cannot go through
   * `onRooms`: the parent applies both halves in ONE paint, because a client
   * that patched the tile and waited up to five seconds for the row to leave
   * would render the same woman as in-service and waiting.
   */
  onDispatch: (result: DispatchResult) => void;
}

export function RoomsPanel({
  rooms,
  staff,
  serverNow,
  fetchCount,
  selfId,
  role,
  paused,
  mutate,
  onRooms,
  onCue,
  waitlistCount,
  onDispatch,
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
  // DC-2(b). `disabled` is SHARED and `loading` is not: one tile serves one act
  // at a time, so both controls go dead together — but two spinners on one tile
  // would say two requests are in flight. Written by the two tile handlers and
  // read only by the two `loading` props; never cleared, because it is only ever
  // read while `busy`.
  const [pendingControl, setPendingControl] = useState<
    Record<string, "takeNext" | "claim">
  >({});
  const [tileError, setTileError] = useState<TileError | null>(null);
  const [openDialog, setOpenDialog] = useState<DialogTarget | null>(null);
  // The handover's residual 409 lives INSIDE its dialog rather than on the tile:
  // the shift manager has to pick somebody else, and closing would make her
  // reopen it to do that.
  const [handoverError, setHandoverError] = useState<{
    text: string;
    value: string | null;
  } | null>(null);

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
    // MOVE 5 — a poll tick that removes the OPEN dialog's assignment. The loop
    // is only SUPPRESSED while a mutation is in flight, never while a dialog is
    // merely open, so a colleague releasing the room unmounts the tile and the
    // dialog under the user's hands with focus inside — F57's own shipped MAJOR
    // reproduced one level deeper, and axe sees none of it. Closing here hands
    // the next effect the job of putting focus somewhere real.
    if (openDialog === null || openDialog.kind === "registry" || rooms === null) {
      return;
    }
    const room = rooms.find((item) => item.id === openDialog.roomId);
    if (room?.assignment?.id === openDialog.assignmentId) {
      return;
    }
    setOpenDialog(null);
  }, [rooms, openDialog]);

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

  // The three 404s are DIFFERENT SENTENCES and that is a correction to the
  // spec's single key: «החדר כבר לא זמין» is actively misleading when the room
  // is fine and the fitting simply ended — and equally misleading when the room
  // is fine and the BOOKING she picked is what the server could not find
  // (FloorService.claim raises DomainNotFoundError("booking") for a cancelled,
  // un-checked-in or not-today booking, through the same NOT_FOUND envelope).
  // The wire cannot tell them apart, so the CALLER decides from what it sent.
  const describe = (
    error: unknown,
    target: "room" | "assignment" | "client" | "queue",
  ): Omit<TileError, "id"> => {
    if (error instanceof ApiError && error.status === 409 && error.code === "ROOM_OCCUPIED") {
      const name = error.details?.staff_display_name;
      return name === undefined
        ? { text: t("rooms.error.roomOccupiedUnknown"), value: null, outage: false }
        : { text: t("rooms.error.ROOM_OCCUPIED", { name }), value: name, outage: false };
    }
    if (error instanceof ApiError && error.status === 409 && error.code === "STAFF_OCCUPIED") {
      const room = error.details?.room_label;
      // ⚠ DC-3. THE SUBJECT DEPENDS ON THE VERB. The take-next route sends no
      // staff_user_id — the acting identity is the session cookie — so on a
      // dispatch the "occupied staffer" IS the manager reading the sentence,
      // and F36's third-person «היא כבר בחדר אחר» tells her about herself. A
      // SECOND sentence rather than an edited value: the shipped third person is
      // correct for the handover, where the target genuinely is a colleague, and
      // its literal is asserted in three shipped test files.
      const named =
        target === "queue" ? "rooms.error.staffOccupiedSelf" : "rooms.error.STAFF_OCCUPIED";
      const unknown =
        target === "queue"
          ? "rooms.error.staffOccupiedSelfUnknown"
          : "rooms.error.staffOccupiedUnknown";
      return room === undefined
        ? { text: t(unknown), value: null, outage: false }
        : { text: t(named, { room }), value: room, outage: false };
    }
    if (error instanceof ApiError && error.status === 409 && error.code === "QUEUE_EMPTY") {
      // ⚠ WITHOUT THIS BRANCH IT TAKES THE FALL-THROUGH and tells a manager
      // whose queue is simply empty that the STAFF LIST failed to load, in the
      // muted OUTAGE register — the exact failure the error code is bought to
      // avoid, delivered in the wrong colour on top. A lost race is a normal
      // outcome of this screen (the last woman left between the render and the
      // tap) and it must never read as a fault. `waitlist.empty` plus a full
      // stop, deliberately: the alert answers her tap, the EmptyState one panel
      // below answers the screen.
      return { text: t("rooms.error.QUEUE_EMPTY"), value: null, outage: false };
    }
    if (error instanceof ApiError && error.status === 404) {
      // The client sentence has NO paused twin, and that is not an omission:
      // it promises no next update because the caller has already performed the
      // repair — the pick is dropped and the arrivals list re-read.
      if (target === "client") {
        return { text: t("rooms.error.clientGone"), value: null, outage: false };
      }
      // DC-8. pause() stops the loop and `mode` is read only for the freshness
      // stamp, so a claim is fully available while paused — and «הרשימה תתוקן
      // בעדכון הבא» is then a promise the screen will not keep. Same failure as
      // naming a retry interval, in the EVENT form.
      //
      // `queue` rides the ROOM's sentence: take-next raises
      // DomainNotFoundError("fitting_room") and nothing else, so «הלקוחה כבר לא
      // בחדר» would be a sentence about a fitting that never started.
      const missingRoom = target === "room" || target === "queue";
      const running = missingRoom ? "rooms.error.notFound" : "rooms.error.assignmentGone";
      const stopped = missingRoom
        ? "rooms.error.notFoundPaused"
        : "rooms.error.assignmentGonePaused";
      return { text: t(paused ? stopped : running), value: null, outage: false };
    }
    // A 5xx or a dropped request: the OUTAGE register, and a SHIPPED key rather
    // than errorMessage(error) leaking the server's English onto a Hebrew-only
    // surface.
    return { text: t("staff.loadFailed"), value: null, outage: true };
  };

  const act = async (
    roomId: string,
    target: "room" | "assignment" | "client" | "queue",
    fn: () => Promise<void>,
  ): Promise<unknown> => {
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
    // Returned so a caller can repair state the sentence claims is repaired.
    return failure;
  };

  // NOT optimistic. The tile is patched from the SERVER's own row — every
  // mutation answers exactly what the payload's rooms[] elements carry — so the
  // panel cannot disagree with itself, and on an idempotent re-claim that is
  // what renders the FIRST holder rather than this request's intent.
  //
  // ⚠ The base is the LATEST list and never the captured prop: two tiles in
  // flight together is a supported shape, and the second response to land would
  // otherwise erase the first.
  const patch = (next: Room) => {
    onRooms((current) => current.map((item) => (item.id === next.id ? next : item)));
  };

  // A dialog's write settles differently from a tile control's: focus goes back
  // to the TRIGGER (move 4) rather than to the tile's primary control (move 2),
  // so these two paths deliberately do not go through `act`.
  const dialogDone = (next: Room, cue: { text: string; name: string | null }) => {
    patch(next);
    onCue(cue);
    setOpenDialog(null);
  };

  // ⚠ THE 404 COLLISION, resolved explicitly. `setTileError` and
  // `setOpenDialog(null)` land in one commit, and the [tileError] effect is
  // declared BEFORE the [openDialog] one — so move 1 focuses the alert and move
  // 4 then finds activeElement off <body> and stands down. The native <dialog>'s
  // own focus return fires earlier still, inside Modal's effect, and would
  // otherwise win.
  const dialogFailed = (roomId: string, error: unknown) => {
    setTileError({ id: roomId, ...describe(error, "assignment") });
    setOpenDialog(null);
  };

  const dropPick = (roomId: string) => {
    setClientPick((current) => {
      const { [roomId]: _dropped, ...rest } = current;
      return rest;
    });
  };

  // F58's headline act, and it lives on a TILE rather than on a row: take-next
  // needs a room, and a server-chosen "first free room" would derive a value
  // from a count of existing rows — the read-then-write shape that needs a lock
  // this feature does not want. A tile-mounted control inserts three values the
  // caller already holds.
  const takeNext = (room: Room) => {
    setPendingControl((current) => ({ ...current, [room.id]: "takeNext" }));
    void act(room.id, "queue", async () => {
      // `{}` IS the one-tap take-next on herself, exactly as it is for `claim`:
      // `staff_user_id` is never sent, and the QUEUE chooses the customer —
      // she does not, which is the whole of «הבאה».
      const result = await api.takeNext(room.id, {});
      // Both panels patch from the SERVER's own rows in one paint.
      onDispatch(result);
      // ⚠ The cue names the ROOM and never the walk-in, and the rule bites
      // HARDER here than on a claim: her row LEAVES the payload, so a cue
      // carrying her name would sit in a persistent region on a five-role
      // screen after she has left the shop — the only place it survives.
      onCue({
        text: t("waitlist.dispatchedCue", { room: result.room.label }),
        name: result.room.label,
      });
    });
  };

  const claim = (room: Room) => {
    setPendingControl((current) => ({ ...current, [room.id]: "claim" }));
    // ⚠ THE SENT VALUE FOLLOWS THE LIST, not the map. `clientPick` is written
    // only by the Select and the Select is rendered only while `clients` is
    // non-empty, so a pick can outlive both the control and the booking: one
    // dropped refetch, or an owner undoing a check-in from another device, and
    // an unconditional read would bind a customer the screen does not show as
    // selected — silently, on the surface D9's minimisation argument governs.
    const pick = clientPick[room.id] ?? "";
    const booking = (clients ?? []).some((client) => client.booking_id === pick) ? pick : "";
    void act(room.id, booking === "" ? "room" : "client", async () => {
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
      // ⚠ The pick is SPENT. copy.md §4 makes «ללא לקוחה» the mounted default
      // and calls that the one-tap path; a pick that survived the claim it was
      // made for would bind the previous bride to the next fitting in that room
      // — wrong name on the five-role payload, wrong booking in the audit row,
      // and no error anywhere.
      dropPick(room.id);
      reloadClients();
    }).then((failure) => {
      // A 404 on a claim that CARRIED a booking is the booking's, as far as the
      // panel can tell. The sentence names the client, so the state has to make
      // that sentence true: drop the pick and re-read the arrivals, which turns
      // the retry into the anonymous claim instead of the same refusal forever.
      if (booking !== "" && failure instanceof ApiError && failure.status === 404) {
        dropPick(room.id);
        reloadClients();
      }
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

  const addDress = (room: Room, assignmentId: string, dressId: string, sizeLabel: string | null) => {
    setBusyIds((current) => [...current, room.id]);
    void mutate(async () => {
      const patched = await api.addAssignmentDress(assignmentId, {
        dress_id: dressId,
        ...(sizeLabel === null ? {} : { size_label: sizeLabel }),
      });
      const bound = patched.assignment?.dresses.find((item) => item.dress_id === dressId);
      // A concurrent double-add is a 200 and not a 409 (spec D4): two staffers
      // tapping «ורוניק» at the same instant both wanted the dress in the room,
      // and the dress is in the room.
      dialogDone(patched, {
        text: t("rooms.dressAddedCue", { dress: bound?.dress_name ?? "" }),
        name: bound?.dress_name ?? null,
      });
    }).then((failure) => {
      setBusyIds((current) => current.filter((id) => id !== room.id));
      if (failure !== null) {
        dialogFailed(room.id, failure);
      }
    });
  };

  const handover = (room: Room, assignmentId: string, staffId: string, displayName: string) => {
    setBusyIds((current) => [...current, room.id]);
    setHandoverError(null);
    void mutate(async () => {
      const patched = await api.handoverAssignment(assignmentId, { staff_user_id: staffId });
      dialogDone(patched, {
        text: t("rooms.handedOverCue", { name: displayName }),
        name: displayName,
      });
    }).then((failure) => {
      setBusyIds((current) => current.filter((id) => id !== room.id));
      if (failure === null) {
        return;
      }
      if (failure instanceof ApiError && failure.status === 409) {
        // The race the exclusion cannot close. The dialog STAYS.
        const label = failure.details?.room_label;
        setHandoverError(
          label === undefined
            ? { text: t("rooms.error.staffOccupiedUnknown"), value: null }
            : { text: t("rooms.error.STAFF_OCCUPIED", { room: label }), value: label },
        );
        return;
      }
      dialogFailed(room.id, failure);
    });
  };

  const openFrom = (event: { currentTarget: HTMLButtonElement }, target: DialogTarget) => {
    setHandoverError(null);
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

  // Both dialogs act on ONE tile, so they are rendered from the target rather
  // than per tile: five mounted RoomDressDialogs would be five catalog fetches
  // waiting to happen.
  const target =
    openDialog === null || openDialog.kind === "registry"
      ? null
      : (rooms.find((room) => room.id === openDialog.roomId) ?? null);
  const targetAssignment = target?.assignment ?? null;

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
                      full-width buttons per tile would be a wall.

                      ⚠ DC-4, and this comment is REWRITTEN rather than left
                      standing, because F58 falsifies what it used to say. The
                      old rule was «ONE `secondary` per tile and it is the act
                      that ENDS the tile's current state». A free tile with a
                      non-empty queue now offers TWO acts that end it, serving
                      two different populations: «תפיסת החדר» seats a booked
                      bride picked from the arrivals list, «קחי את הבאה» seats
                      the first walk-in in the queue. Neither is the lesser one
                      and demoting either to `ghost` would say it is. The rule
                      that survives: AT MOST ONE `secondary` PER ACT-TYPE, NEVER
                      `primary` ANYWHERE ON THIS SCREEN, and never more than two
                      `secondary`s on one region — ORDER carries the hierarchy,
                      which is why take-next is FIRST here and first on the
                      wrapped line at 375. */}
                  <div className="flex flex-wrap justify-end gap-3">
                    {assignment === null && room.is_active && waitlistCount > 0 && (
                      <Button
                        ref={(node) => {
                          controlRefs.current.set(room.id, node);
                        }}
                        variant="secondary"
                        size="md"
                        fullWidthMobile={false}
                        // DC-2(b): dead together, spinning apart.
                        disabled={busy}
                        loading={busy && pendingControl[room.id] === "takeNext"}
                        aria-label={t("rooms.takeNextAria", { room: room.label })}
                        onClick={() => takeNext(room)}
                      >
                        {t("rooms.takeNext")}
                      </Button>
                    )}
                    {assignment === null && room.is_active && (
                      <Button
                        ref={(node) => {
                          // ⚠ DC-2(a). `controlRefs` is ONE slot per room and
                          // React runs ref callbacks in TREE order, so an
                          // unguarded callback here runs LAST and silently wins
                          // the slot from the control above — and on a refused
                          // take-next the tile stays free, so ~5s later MOVE 6
                          // hands focus to «תפיסת החדר», a control she never
                          // touched. THE SLOT BELONGS TO THE TILE'S FIRST
                          // CONTROL, which is take-next whenever it is rendered.
                          if (waitlistCount === 0) {
                            controlRefs.current.set(room.id, node);
                          }
                        }}
                        variant="secondary"
                        size="md"
                        fullWidthMobile={false}
                        disabled={busy}
                        loading={busy && pendingControl[room.id] === "claim"}
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

      {target !== null && targetAssignment !== null && (
        <>
          <RoomDressDialog
            open={openDialog?.kind === "dress"}
            room={target}
            busy={busyIds.includes(target.id)}
            onClose={() => setOpenDialog(null)}
            onAdd={(dressId, sizeLabel) =>
              addDress(target, targetAssignment.id, dressId, sizeLabel)
            }
          />
          <RoomHandoverDialog
            open={openDialog?.kind === "handover"}
            assignment={targetAssignment}
            staff={staff ?? []}
            error={handoverError}
            busy={busyIds.includes(target.id)}
            onClose={() => setOpenDialog(null)}
            onConfirm={(staffId, displayName) =>
              handover(target, targetAssignment.id, staffId, displayName)
            }
          />
        </>
      )}
    </div>
  );
}
