import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { DressDetail, Variant } from "../api";
import { VariantMatrix } from "../components/VariantMatrix";

vi.mock("../api", () => ({
  api: {
    replaceVariants: vi.fn(),
  },
  errorMessage: (error: unknown) => (error instanceof Error ? error.message : "שגיאה"),
}));

const { api } = await import("../api");
const replaceVariants = vi.mocked(api.replaceVariants);

function variant(id: string, sizeLabel: string, quantity: number, sortOrder: number): Variant {
  return { id, size_label: sizeLabel, quantity, sort_order: sortOrder };
}

function detail(variants: Variant[]): DressDetail {
  return {
    id: "d1",
    name: "עלמה",
    description: null,
    price_agorot: 890000,
    price_visible: true,
    reserved: false,
    sort_order: 0,
    out_of_stock: false,
    total_quantity: 0,
    variant_count: variants.length,
    media_count: 0,
    cover: null,
    archived: false,
    created_at: "2026-07-24T10:00:00Z",
    updated_at: null,
    variants,
    media: [],
    media_uploads_enabled: true,
    media_slots_remaining: 12,
  };
}

function renderMatrix(variants: Variant[] = []) {
  const onDetail = vi.fn();
  render(
    <VariantMatrix
      dressId="d1"
      variants={variants}
      disabled={false}
      disabledReason={null}
      onDetail={onDetail}
    />,
  );
  return { onDetail };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("VariantMatrix quick entry", () => {
  it("adds a row when an EU size chip is pressed", () => {
    renderMatrix();
    expect(screen.getByText("לא הוגדרו מידות לשמלה הזו.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "38" }));

    // The row's quantity input names itself from the visible "כמות" label plus
    // the visible size chip — never an aria-label that hides the visible text.
    expect(screen.getByLabelText("כמות 38")).toBeInTheDocument();
    expect(replaceVariants).not.toHaveBeenCalled();
  });

  it("marks an already-listed chip in its accessible name, not with aria-pressed", () => {
    renderMatrix([variant("v1", "38", 3, 0)]);
    const chip = screen.getByRole("button", { name: "38 — כבר ברשימה" });
    expect(chip).not.toHaveAttribute("aria-pressed");
    expect(chip).toBeEnabled();
  });
});

describe("VariantMatrix duplicate detection", () => {
  it("refuses a duplicate size inline before any request", () => {
    renderMatrix([variant("v1", "38", 3, 0)]);

    fireEvent.change(screen.getByLabelText("מידה מותאמת"), { target: { value: " 38 " } });
    fireEvent.click(screen.getByRole("button", { name: "הוספה" }));

    expect(screen.getByRole("alert")).toHaveTextContent("המידה «38» כבר קיימת ברשימה.");
    expect(replaceVariants).not.toHaveBeenCalled();
    // One row, not two — and the typed text stays so the owner can correct it.
    expect(screen.getAllByLabelText(/^כמות /)).toHaveLength(1);
    expect(screen.getByLabelText("מידה מותאמת")).toHaveValue(" 38 ");
  });

  it("treats case and whitespace variants as the same size", () => {
    renderMatrix([variant("v1", "US 6", 1, 0)]);

    fireEvent.change(screen.getByLabelText("מידה מותאמת"), { target: { value: "us  6" } });
    fireEvent.click(screen.getByRole("button", { name: "הוספה" }));

    expect(screen.getByRole("alert")).toHaveTextContent("כבר קיימת ברשימה");
    expect(replaceVariants).not.toHaveBeenCalled();
  });
});

describe("VariantMatrix save", () => {
  it("PUTs the whole matrix as one full replace", async () => {
    const { onDetail } = renderMatrix([variant("v1", "38", 3, 0)]);
    replaceVariants.mockResolvedValue(detail([variant("v1", "38", 3, 0)]));

    fireEvent.click(screen.getByRole("button", { name: "40" }));
    fireEvent.change(screen.getByLabelText("כמות 40"), { target: { value: "5" } });
    fireEvent.click(screen.getByRole("button", { name: "שמירת מלאי" }));

    await waitFor(() =>
      expect(replaceVariants).toHaveBeenCalledWith("d1", [
        { size_label: "38", quantity: 3, sort_order: 0 },
        { size_label: "40", quantity: 5, sort_order: 1 },
      ]),
    );
    await waitFor(() => expect(onDetail).toHaveBeenCalledTimes(1));
  });

  it("warns that the dress will read אזל when every quantity is zero", () => {
    renderMatrix([variant("v1", "38", 0, 0)]);
    expect(screen.getByRole("status")).toHaveTextContent(
      "כל המידות במלאי 0 — השמלה תסומן «אזל מהמלאי» בקטלוג הניהול.",
    );
  });
});

describe("VariantMatrix disabled (create mode)", () => {
  it("puts the reason on every disabled control's own visible label", () => {
    render(
      <VariantMatrix
        dressId={null}
        variants={[]}
        disabled
        disabledReason="יש לשמור את השמלה תחילה"
        onDetail={vi.fn()}
      />,
    );

    expect(
      screen.getByText("הוספה מהירה (מידות אירופאיות) — יש לשמור את השמלה תחילה"),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "38" })).toBeDisabled();
    expect(screen.getByLabelText("מידה מותאמת (יש לשמור את השמלה תחילה)")).toBeDisabled();
    // Disabled, but never aria-hidden — the owner must see that sizes exist.
    expect(screen.getByRole("group")).not.toHaveAttribute("aria-hidden");
  });
});
