import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import "../i18n";
import type { AvailabilityState } from "../api";
import {
  ShiftAvailabilityFieldset,
  UNANSWERED,
} from "../components/ShiftAvailabilityFieldset";

// The fieldset is rendered DIRECTLY here. It owns no fetch, no timer and no
// announced region — the two panes that mount it own those — so everything below
// is reachable with the props they hand it.

const MORNING = "11111111-1111-1111-1111-111111111111";
const EVENING = "22222222-2222-2222-2222-222222222222";

function mount(props: Partial<Parameters<typeof ShiftAvailabilityFieldset>[0]> = {}) {
  const onChange = vi.fn();
  render(
    <ShiftAvailabilityFieldset
      templateId={MORNING}
      legend="משמרת בוקר · 09:00–14:00"
      value={UNANSWERED}
      onChange={onChange}
      {...props}
    />,
  );
  return onChange;
}

describe("the four options", () => {
  it("renders the three states plus «לא נרשם», in that order", () => {
    mount();
    expect(screen.getAllByRole("radio").map((input) => input.getAttribute("value"))).toEqual([
      "available",
      "unavailable",
      "preferred",
      "",
    ]);
    for (const label of ["זמינה", "לא זמינה", "מעדיפה", "לא נרשם"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it("checks «לא נרשם» when there is no live entry", () => {
    // ⚠ D8: the ABSENCE of a row is the state, and this is its NAME on screen.
    // Pre-checking «זמינה» instead would let a save assert something she never
    // said — the dishonesty `recorded_by` exists to prevent one decision
    // earlier. Pre-checking this one asserts precisely the truth.
    mount();
    expect(screen.getByRole("radio", { name: "לא נרשם" })).toBeChecked();
    for (const name of ["זמינה", "לא זמינה", "מעדיפה"]) {
      expect(screen.getByRole("radio", { name })).not.toBeChecked();
    }
  });

  it("yields null when she withdraws an answer", () => {
    // ⚠ THE WHOLE REASON THE FOURTH OPTION EXISTS. A native radio cannot be
    // un-checked, so with three options a mis-tapped «מעדיפה» would be
    // overwritable but never withdrawable — and it would ship to F40 as advisory
    // input she never gave. `null` maps to «omit this template from the PUT»,
    // which is D8's own clear path.
    const onChange = mount({ value: "preferred" as AvailabilityState });
    fireEvent.click(screen.getByRole("radio", { name: "לא נרשם" }));
    expect(onChange).toHaveBeenCalledWith(UNANSWERED);
  });

  it("yields the state she picked", () => {
    const onChange = mount();
    fireEvent.click(screen.getByRole("radio", { name: "מעדיפה" }));
    expect(onChange).toHaveBeenCalledWith("preferred");
  });

  it("gives every option a 44px target", () => {
    // IS 5568 / WCAG 2.0 AA is a LEGAL gate here, not a preference. `min-h-11`
    // is 44px; `Button size="sm"` (36px) is forbidden everywhere in this feature.
    mount();
    for (const radio of screen.getAllByRole("radio")) {
      expect(radio.closest("label")?.className).toContain("min-h-11");
    }
  });
});

describe("the group name", () => {
  it("gives two shifts on ONE weekday different groups", () => {
    // ⚠ THE LOAD-BEARING ASSERTION IN THIS FILE. Overlapping same-day templates
    // are legal and expected (D2), and a `name` keyed on the WEEKDAY would fuse
    // them into one radio group — so answering the afternoon would silently
    // clear the morning, with no error anywhere and no failing test unless one
    // exists.
    const onChange = vi.fn();
    const { container } = render(
      <>
        <ShiftAvailabilityFieldset
          templateId={MORNING}
          legend="משמרת בוקר · 09:00–14:00"
          value={"available" as AvailabilityState}
          onChange={onChange}
        />
        <ShiftAvailabilityFieldset
          templateId={EVENING}
          legend="משמרת ערב · 16:00–21:00"
          value={"unavailable" as AvailabilityState}
          onChange={onChange}
        />
      </>,
    );
    const names = new Set(
      Array.from(container.querySelectorAll<HTMLInputElement>("input[type=radio]")).map(
        (input) => input.name,
      ),
    );
    expect(names.size).toBe(2);

    // And the behavioural half: answering one leaves the other's answer standing.
    const groups = screen.getAllByRole("group");
    expect(within(groups[0]).getByRole("radio", { name: "זמינה" })).toBeChecked();
    expect(within(groups[1]).getByRole("radio", { name: "לא זמינה" })).toBeChecked();
    fireEvent.click(within(groups[1]).getByRole("radio", { name: "מעדיפה" }));
    expect(within(groups[0]).getByRole("radio", { name: "זמינה" })).toBeChecked();
  });
});

describe("the attribution line", () => {
  it("is absent when she recorded it herself", () => {
    mount({ value: "available" as AvailabilityState });
    expect(screen.queryByText(/נרשם על ידי/)).not.toBeInTheDocument();
    expect(screen.getByRole("group")).not.toHaveAttribute("aria-describedby");
  });

  it("names the recorder and describes the GROUP rather than each radio", () => {
    // On the fieldset's `aria-describedby`, so it is announced once on entering
    // the group rather than repeated on each of the four radios — and never
    // dropped, which a plain <p> after the radios would be for anyone arrowing
    // through.
    mount({ value: "available" as AvailabilityState, recordedByName: "דנה כהן" });
    const group = screen.getByRole("group");
    const describedBy = group.getAttribute("aria-describedby");
    expect(describedBy).toBeTruthy();
    const line = document.getElementById(describedBy as string);
    expect(line?.textContent).toBe("נרשם על ידי דנה כהן.");
  });

  it("isolates a Latin-script name in a BARE <bdi>", () => {
    // ⚠ R19. The full stop lands immediately after the name, so without the
    // island «Ronit Bar» renders «נרשם על ידי .Ronit Bar» — on a line that is
    // both seen and spoken. `dir="ltr"` would be its own defect: three of the
    // four names on this surface are Hebrew.
    mount({ value: "available" as AvailabilityState, recordedByName: "Ronit Bar" });
    const island = screen.getByText("Ronit Bar");
    expect(island.tagName).toBe("BDI");
    expect(island).not.toHaveAttribute("dir");
  });
});

describe("the locked mount", () => {
  it("disables every option without changing which one is checked", () => {
    mount({ value: "preferred" as AvailabilityState, disabled: true });
    for (const radio of screen.getAllByRole("radio")) {
      expect(radio).toBeDisabled();
    }
    expect(screen.getByRole("radio", { name: "מעדיפה" })).toBeChecked();
  });
});
