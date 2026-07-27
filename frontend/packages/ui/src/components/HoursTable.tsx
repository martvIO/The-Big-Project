import { cn } from "../lib/styles";
import { groupWeeklyRules } from "../lib/hours";
import type { WeeklyRule } from "../lib/hours";

export interface HoursTableProps {
  rules: WeeklyRule[];
  // Seven Hebrew day labels, Sun-first (index 0 = Sunday, 6 = Saturday).
  dayLabels: string[];
  // Literal "סגור" for days with no window.
  closedLabel: string;
  rangeSeparator?: string;
  className?: string;
}

// Renders the whole Israeli week Sun-first. Every day is accounted for; a day
// with no window shows the literal closed label (Saturday is the standing case).
export function HoursTable({ rules, dayLabels, closedLabel, rangeSeparator = "–", className }: HoursTableProps) {
  const rows = groupWeeklyRules(rules);
  const dayText = (startDay: number, endDay: number) =>
    startDay === endDay ? dayLabels[startDay] : `${dayLabels[startDay]}${rangeSeparator}${dayLabels[endDay]}`;

  return (
    <table className={cn("w-full text-base", className)}>
      <tbody>
        {rows.map((row) => (
          <tr key={row.startDay}>
            <th scope="row" className="py-1 text-start font-normal text-ink">
              {dayText(row.startDay, row.endDay)}
            </th>
            <td className="py-1 text-end text-ink-muted">
              {row.closed ? (
                closedLabel
              ) : (
                row.windows.map((win, i) => (
                  <bdi key={i} dir="ltr" className="ms-2 first:ms-0">
                    {win.open}
                    {rangeSeparator}
                    {win.close}
                  </bdi>
                ))
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
