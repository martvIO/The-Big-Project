import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Card, SectionHeading, Skeleton } from "@boutique/ui";
import { api } from "../api";
import type { DashboardResponse } from "../api";
import { isolateLtr } from "../lib/booking";
import { plainDate } from "../lib/jerusalem";

// The console's landing section, for both roles. It has NO interactive control
// of any kind — no picker, no filter, no retry, no link, no row that opens
// anything. That is the shape, not an omission: the endpoint takes no
// parameters (spec D2), so there is nothing here for a user to change.
//
// Two spans, never one. History ends last Saturday; the forward panel starts
// today. NOTHING here bridges them — Risk 13's 0-6 uncovered days are real, and
// a sentence implying continuity would be a lie the screen tells on the owner's
// behalf. That is why the two range labels are deliberately different words.

// The week-row label, d.m — narrow enough for 375px, and the year lives once
// per panel in the range line. Splits the string exactly like plainDate and for
// the same reason: `week_start` is a plain Jerusalem calendar date, and routing
// one through a Date re-zones a date that was never in a zone.
function dayMonth(iso: string): string {
  const [, month, day] = iso.split("-");
  return `${Number(day)}.${Number(month)}`;
}

// The one hand-built thing on this screen, and it stays inline markup here — no
// new packages/ui component and no promotion (spec D10).
function Bar({ pct }: { pct: number }) {
  // Clamped even though the server already clamps booked <= capacity: one
  // expression, and it is what keeps a contract change from painting outside
  // the track. The isFinite guard is the NaN guard, and it lives HERE rather
  // than at each of the three call sites: a relative bar divides by the largest
  // value in its list, `count / 0` is NaN, and `inline-size: NaN%` is an
  // IGNORED declaration that silently leaves the previous width in a re-render.
  const size = Number.isFinite(pct) ? Math.min(Math.max(pct, 0), 100) : 0;
  return (
    // aria-hidden on the whole bar, always. It is never role="progressbar":
    // that role announces a task's completion, not a ratio of a static
    // quantity, and an AT would read the utilization bar as an in-flight
    // operation. Every value a bar draws is text in the same row — remove every
    // bar and the screen loses nothing.
    <span aria-hidden="true" className="block h-2 rounded-sm bg-border">
      {/* inlineSize, NEVER width — a logical property, so in RTL the fill grows
          from the inline-start (right) edge. */}
      <span
        className="block h-2 rounded-sm bg-gold-strong"
        style={{ inlineSize: `${size}%` }}
      />
    </span>
  );
}

export function DashboardSection() {
  const { t } = useTranslation();
  const [data, setData] = useState<DashboardResponse | null>(null);
  // A boolean, not errorMessage()'s string: the section renders one sentence for
  // ANY ApiError (the BookingsSection shape), so storing the server's message
  // would only risk its verbatim ENGLISH text reaching the landing screen.
  const [loadFailed, setLoadFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .getDashboard()
      .then((result) => {
        if (!cancelled) {
          setData(result);
        }
      })
      .catch(() => {
        if (!cancelled) {
          // Deliberately NOT a zeroed payload — a screen of zeroes under the
          // alert would stack the day-one state on top of an outage message.
          setLoadFailed(true);
        }
      });
    return () => {
      cancelled = true;
    };
    // One fetch, on mount. No interval and no refetch control (D11): twelve
    // complete past weeks change at most once a week, and the forward panel
    // changes when someone books. Neither justifies the console's first
    // repeating fetch, so F51's Risk 3 moves to F34 rather than landing here.
  }, []);

  const loading = data === null && !loadFailed;

  return (
    <div className="space-y-6">
      <SectionHeading as="h2" ornament>
        {t("dashboard.heading")}
      </SectionHeading>

      {data !== null && (
        <p className="text-sm text-ink-muted">
          {t("dashboard.generatedOnLabel")}{" "}
          <bdi dir="ltr">{plainDate(data.generated_on)}</bdi>
        </p>
      )}

      {/* The section's single announced region: the loading text and the total,
          in the one place. No tabIndex — BookingsSection needs one because a
          mutation returns focus there, and nothing here moves focus. */}
      <p role="status" className="text-sm text-ink-muted">
        {loading
          ? t("dashboard.loading")
          : data === null
            ? // The alert already speaks; two announcements for one event is
              // one too many.
              ""
            : isolateLtr(
                t("dashboard.summary", { count: totalOf(data) }),
                String(totalOf(data)),
              )}
      </p>

      {loadFailed && (
        // An outage, not a fault of hers: the muted register, and no retry
        // control — reopening the section refetches.
        <p role="alert" className="text-sm text-ink-muted">
          {t("dashboard.loadFailed")}
        </p>
      )}

      {loading && <Skeleton variant="text" lines={6} />}

      {data !== null && isFirstRun(data) && (
        // One muted line, never an EmptyState — that would hide the forward
        // panel, the one number a day-one boutique can act on. It removes
        // itself the moment any week is non-zero.
        <p className="text-sm text-ink-muted">{t("dashboard.firstRunNote")}</p>
      )}

      {data !== null && (
        <>
          <ForwardPanelCard forward={data.forward} />
          <WeeksCard history={data.history} />
          <RatesCard history={data.history} />
          <CustomersCard history={data.history} />
          <TypesCard history={data.history} />
        </>
      )}
    </div>
  );
}

// sum(weeks[].bookings), summed client-side. Arithmetic over numbers already on
// the wire, not a second definition of anything — the server asserts
// sum(weeks[].bookings) == confirmed + no_show + completed.
function totalOf(data: DashboardResponse): number {
  return data.history.weeks.reduce((sum, week) => sum + week.bookings, 0);
}

function isFirstRun(data: DashboardResponse): boolean {
  return data.history.weeks.every((week) => week.bookings === 0);
}

// A <dt>/<dd> pair, wrapped in a <div> so the pairs can grid. Sub-lines live
// INSIDE the <dd> as a block <span>: a <p> between a <dt> and a <dd> is invalid
// HTML and axe reports it.
function Tile({
  label,
  children,
  help,
}: {
  label: string;
  children: React.ReactNode;
  help?: string;
}) {
  return (
    <div>
      <dt className="text-sm text-ink-muted">{label}</dt>
      <dd className="text-lg font-semibold text-ink">
        {children}
        {help !== undefined && (
          <span className="mt-1 block text-sm font-normal text-ink-muted">{help}</span>
        )}
      </dd>
    </div>
  );
}

const PANEL_HEADING = "text-sm font-semibold text-ink";
const HELP = "text-sm text-ink-muted";
const TILES = "mt-4 grid gap-4 sm:grid-cols-2";
const TABLE_HEAD = "pb-2 text-start text-sm font-normal text-ink-muted";

function DateRange({ from, to }: { from: string; to: string }) {
  // ONE isolate around both dates together, not two: the pair is a single
  // left-to-right run.
  return (
    <bdi dir="ltr">
      {plainDate(from)}–{plainDate(to)}
    </bdi>
  );
}

// Three facts, three renderings (copy.md §0 rule 3). Only the purely numeric
// one is an LTR isolate: dir="ltr" on either Hebrew sentence would reorder it.
function Rate({ value }: { value: number | null }) {
  const { t } = useTranslation();
  if (value === null) {
    return <>{t("dashboard.notEnoughData")}</>;
  }
  const shown = (value * 100).toFixed(1);
  if (shown === "0.0" && value > 0) {
    // A non-zero rate the one-decimal precision cannot display. Without its own
    // string, a boutique with one cancellation in 250 bookings would render 0%
    // and collide with the true-zero fact.
    return <>{t("dashboard.rateUnderFloor")}</>;
  }
  // Uniform precision — 100.0%, not 100% — because a mixed rule is more code
  // and one more thing to get wrong.
  return <bdi dir="ltr">{shown}%</bdi>;
}

function Count({ value }: { value: number }) {
  return <bdi dir="ltr">{value}</bdi>;
}

// The forward panel is FIRST, and that is a decision: a shift manager's job is
// the next seven days, not last quarter, and this is the only panel with a
// non-zero number on a boutique's first day.
function ForwardPanelCard({ forward }: { forward: DashboardResponse["forward"] }) {
  const { t } = useTranslation();
  return (
    <Card>
      <h3 className={PANEL_HEADING}>{t("dashboard.forwardHeading")}</h3>
      <p className={`mt-1 ${HELP}`}>
        {t("dashboard.forwardRange")} <DateRange from={forward.from_date} to={forward.to_date} />
      </p>
      {forward.capacity > 0 ? (
        <>
          <dl className={TILES}>
            <Tile label={t("dashboard.forwardValueLabel")}>
              <Rate value={forward.utilization} />
              {/* The forward bar is ABSOLUTE — its maximum is capacity — and it
                  sits beside a percentage. */}
              <span className="mt-2 block">
                <Bar pct={(forward.utilization ?? 0) * 100} />
              </span>
            </Tile>
            <Tile label={t("dashboard.forwardCapacityLabel")}>
              <Count value={forward.capacity} />
            </Tile>
            <Tile label={t("dashboard.forwardBookedLabel")}>
              <Count value={forward.booked} />
            </Tile>
          </dl>
          <p className={`mt-4 ${HELP}`}>{t("dashboard.forwardHelp")}</p>
        </>
      ) : (
        // Names CLOSED HOURS, not zero demand, and draws no bar: a bar for a
        // value that does not exist is a lie.
        <p className={`mt-4 ${HELP}`}>{t("dashboard.forwardNoHours")}</p>
      )}
    </Card>
  );
}

function WeeksCard({ history }: { history: DashboardResponse["history"] }) {
  const { t } = useTranslation();
  // The weeks bars are RELATIVE — the maximum is the largest value in the
  // visible list — and they sit beside a count, so they read as a comparison
  // with their neighbours rather than a proportion of a whole.
  const max = Math.max(...history.weeks.map((week) => week.bookings));
  return (
    <Card>
      <h3 className={PANEL_HEADING}>{t("dashboard.weeksHeading")}</h3>
      <p className={`mt-1 ${HELP}`}>
        {t("dashboard.weeksRange")} <DateRange from={history.from_date} to={history.to_date} />
      </p>
      <p className={`mt-2 ${HELP}`}>{t("dashboard.weeksHelp")}</p>
      <table className="mt-4 w-full">
        <caption className="sr-only">{t("dashboard.weeksTableCaption")}</caption>
        <thead>
          <tr>
            <th scope="col" className={TABLE_HEAD}>
              {t("dashboard.weekColumn")}
            </th>
            <th scope="col" className={TABLE_HEAD}>
              {t("dashboard.bookingsColumn")}
            </th>
          </tr>
        </thead>
        <tbody>
          {history.weeks.map((week) => (
            <tr key={week.week_start}>
              <th scope="row" className="w-16 py-1 text-start text-sm font-normal text-ink">
                <bdi dir="ltr">{dayMonth(week.week_start)}</bdi>
              </th>
              <td className="py-1">
                <span className="flex items-center gap-2">
                  <span className="min-w-0 grow">
                    <Bar pct={(week.bookings / max) * 100} />
                  </span>
                  <span className="w-8 text-sm text-ink">
                    <Count value={week.bookings} />
                  </span>
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

function RatesCard({ history }: { history: DashboardResponse["history"] }) {
  const { t } = useTranslation();
  return (
    <Card>
      <h3 className={PANEL_HEADING}>{t("dashboard.ratesHeading")}</h3>
      <dl className={TILES}>
        <Tile label={t("dashboard.cancellationRateLabel")} help={t("dashboard.cancellationHelp")}>
          <Rate value={history.cancellation_rate} />
        </Tile>
        {/* Two INDEPENDENT labelled counts, never a partition and never an
            "X of Y": a row cancelled before migration 0010 carries NULL and is
            in neither, so the two need not sum to status_totals.cancelled. */}
        <Tile label={t("dashboard.cancelledByCustomerLabel")}>
          <Count value={history.cancelled_by_customer} />
        </Tile>
        <Tile label={t("dashboard.cancelledByOwnerLabel")}>
          <Count value={history.cancelled_by_owner} />
        </Tile>
        <Tile label={t("dashboard.noShowRateLabel")} help={t("dashboard.noShowHelp")}>
          <Rate value={history.no_show_rate} />
        </Tile>
        {/* Risk 5's bound, made visible: the rate above can be computed over a
            handful of appointments, and this is the count it excludes. */}
        <Tile label={t("dashboard.unclassifiedLabel")} help={t("dashboard.unclassifiedHelp")}>
          <Count value={history.status_totals.confirmed} />
        </Tile>
      </dl>
    </Card>
  );
}

function CustomersCard({ history }: { history: DashboardResponse["history"] }) {
  const { t } = useTranslation();
  const customers = history.customers;
  return (
    <Card>
      <h3 className={PANEL_HEADING}>{t("dashboard.customersHeading")}</h3>
      <p className={`mt-1 ${HELP}`}>{t("dashboard.customersHelp")}</p>
      <dl className={TILES}>
        <Tile label={t("dashboard.customersTotalLabel")}>
          <Count value={customers.total} />
        </Tile>
        <Tile label={t("dashboard.customersNewLabel")}>
          <Count value={customers.new} />
        </Tile>
        <Tile label={t("dashboard.customersReturningLabel")}>
          <Count value={customers.returning} />
        </Tile>
        <Tile label={t("dashboard.repeatRateLabel")} help={t("dashboard.repeatRateHelp")}>
          <Rate value={customers.repeat_rate} />
        </Tile>
      </dl>
    </Card>
  );
}

function TypesCard({ history }: { history: DashboardResponse["history"] }) {
  const { t } = useTranslation();
  const types = history.appointment_types;
  const max = Math.max(...types.map((type) => type.bookings));
  return (
    <Card>
      <h3 className={PANEL_HEADING}>{t("dashboard.typesHeading")}</h3>
      <p className={`mt-1 ${HELP}`}>{t("dashboard.typesHelp")}</p>
      {types.length === 0 ? (
        // One muted line replacing the table — not an EmptyState, not a Card
        // full of nothing.
        <p className={`mt-4 ${HELP}`}>{t("dashboard.typesEmpty")}</p>
      ) : (
        <table className="mt-4 w-full">
          <caption className="sr-only">{t("dashboard.typesTableCaption")}</caption>
          <thead>
            <tr>
              <th scope="col" className={TABLE_HEAD}>
                {t("dashboard.typeColumn")}
              </th>
              <th scope="col" className={TABLE_HEAD}>
                {t("dashboard.bookingsColumn")}
              </th>
            </tr>
          </thead>
          <tbody>
            {types.map((type) => (
              <tr key={type.appointment_type_id}>
                <th scope="row" className="py-1 text-start text-sm font-normal text-ink">
                  {/* Bare bdi: dir="ltr" on a Hebrew name is itself a bidi
                      defect. The name wraps; no truncation and no title. */}
                  <bdi>{type.name}</bdi>
                </th>
                <td className="py-1">
                  <span className="flex items-center gap-2">
                    <span className="min-w-0 grow">
                      <Bar pct={(type.bookings / max) * 100} />
                    </span>
                    <span className="w-8 text-sm text-ink">
                      <Count value={type.bookings} />
                    </span>
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}
