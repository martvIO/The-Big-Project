import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Dress, DressDetail, DressList } from "../api";
import { CatalogSection } from "../components/CatalogSection";

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ApiError: actual.ApiError,
    errorMessage: actual.errorMessage,
    uploadToStorage: vi.fn(),
    api: {
      listDresses: vi.fn(),
      getDress: vi.fn(),
      createDress: vi.fn(),
      updateDress: vi.fn(),
      archiveDress: vi.fn(),
      restoreDress: vi.fn(),
      replaceVariants: vi.fn(),
      presignMedia: vi.fn(),
      confirmMedia: vi.fn(),
      deleteMedia: vi.fn(),
      reorderMedia: vi.fn(),
    },
  };
});

const { api, ApiError } = await import("../api");
const listDresses = vi.mocked(api.listDresses);
const getDress = vi.mocked(api.getDress);
const createDress = vi.mocked(api.createDress);
const updateDress = vi.mocked(api.updateDress);
const archiveDress = vi.mocked(api.archiveDress);
const restoreDress = vi.mocked(api.restoreDress);

function dress(overrides: Partial<Dress> = {}): Dress {
  return {
    id: "d1",
    name: "עלמה",
    description: null,
    price_agorot: 890000,
    price_visible: true,
    reserved: false,
    sort_order: 0,
    out_of_stock: false,
    total_quantity: 7,
    variant_count: 2,
    media_count: 5,
    cover: null,
    archived: false,
    created_at: "2026-07-24T10:00:00Z",
    updated_at: null,
    ...overrides,
  };
}

function page(items: Dress[], total = items.length, offset = 0): DressList {
  return { items, total, offset, limit: 24 };
}

function detailOf(row: Dress): DressDetail {
  return {
    ...row,
    variants: [],
    media: [],
    media_uploads_enabled: false,
    media_slots_remaining: 12,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("CatalogSection listing", () => {
  it("renders the first-run empty state, not an error", async () => {
    listDresses.mockResolvedValue(page([], 0));
    render(<CatalogSection />);

    expect(await screen.findByText("אין עדיין שמלות בקטלוג")).toBeInTheDocument();
    expect(
      screen.getByText("השמלה הראשונה תופיע כאן ובאתר של הבוטיק."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("distinguishes a filtered dead end from a first-run empty catalog", async () => {
    listDresses.mockResolvedValue(page([], 0));
    render(<CatalogSection />);
    await screen.findByText("אין עדיין שמלות בקטלוג");

    fireEvent.change(screen.getByLabelText("חיפוש שמלה"), { target: { value: "אין כזו" } });

    expect(
      await screen.findByText("לא נמצאו שמלות התואמות לחיפוש."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "ניקוי החיפוש" })).toBeInTheDocument();
  });

  it("renders the three-way stock badge read-only", async () => {
    listDresses.mockResolvedValue(
      page([
        dress({ id: "d1", name: "עלמה", variant_count: 2, total_quantity: 7 }),
        dress({ id: "d2", name: "שירה", variant_count: 3, total_quantity: 0, out_of_stock: true }),
        dress({ id: "d3", name: "נועה", variant_count: 0, total_quantity: 0, out_of_stock: true }),
      ]),
    );
    render(<CatalogSection />);

    await screen.findByText("עלמה");
    expect(screen.getByText(/^במלאי/)).toHaveTextContent("במלאי (7)");
    expect(screen.getByText("אזל מהמלאי")).toBeInTheDocument();
    // A dress with no size matrix is NOT "אזל מהמלאי" — it is unconfigured.
    expect(screen.getByText("לא הוגדרו מידות")).toBeInTheDocument();

    // The badges are text, never controls: the only button per row is the row.
    const rows = screen.getAllByRole("listitem");
    expect(within(rows[0]).getAllByRole("button")).toHaveLength(1);
  });

  it("shows the reserved chip and the hidden-price treatment", async () => {
    listDresses.mockResolvedValue(
      page([
        dress({ id: "d1", name: "שירה", reserved: true }),
        dress({ id: "d2", name: "נועה", price_agorot: null }),
        dress({ id: "d3", name: "מיה", price_agorot: 1580000, price_visible: false }),
      ]),
    );
    render(<CatalogSection />);

    await screen.findByText("שירה");
    expect(screen.getByText("הוזמן")).toBeInTheDocument();
    expect(screen.getAllByText("מחיר בתיאום")).toHaveLength(2);
    expect(screen.getByText("8,900 ₪")).toBeInTheDocument();
  });
});

describe("CatalogSection paging", () => {
  it("pages with offset and disables each pager at its end", async () => {
    listDresses.mockResolvedValue(page([dress()], 61, 0));
    render(<CatalogSection />);
    await screen.findByText("עלמה");

    expect(screen.getByTestId("catalog-count")).toHaveTextContent("מציג 1–24 מתוך 61");
    expect(screen.getByRole("button", { name: "הקודם" })).toBeDisabled();

    listDresses.mockResolvedValue(page([dress({ id: "d9", name: "מיה" })], 61, 24));
    fireEvent.click(screen.getByRole("button", { name: "הבא" }));

    await waitFor(() =>
      expect(listDresses).toHaveBeenLastCalledWith(
        expect.objectContaining({ offset: 24, limit: 24 }),
      ),
    );
    await waitFor(() =>
      expect(screen.getByTestId("catalog-count")).toHaveTextContent("מציג 25–48 מתוך 61"),
    );
    expect(screen.getByRole("button", { name: "הקודם" })).toBeEnabled();
  });
});

describe("CatalogSection search", () => {
  it("debounces by 300ms and resets the offset, issuing one request per pause", async () => {
    listDresses.mockResolvedValue(page([dress()], 61, 24));
    render(<CatalogSection />);
    await screen.findByText("עלמה");

    fireEvent.click(screen.getByRole("button", { name: "הבא" }));
    await waitFor(() => expect(listDresses).toHaveBeenCalledTimes(2));

    vi.useFakeTimers();
    const search = screen.getByLabelText("חיפוש שמלה");
    fireEvent.change(search, { target: { value: "על" } });
    fireEvent.change(search, { target: { value: "עלמ" } });
    fireEvent.change(search, { target: { value: "עלמה" } });

    await act(async () => {
      vi.advanceTimersByTime(299);
    });
    expect(listDresses).toHaveBeenCalledTimes(2);

    await act(async () => {
      vi.advanceTimersByTime(1);
    });
    // One request for three keystrokes, and the page resets to the first page.
    expect(listDresses).toHaveBeenCalledTimes(3);
    expect(listDresses).toHaveBeenLastCalledWith(
      expect.objectContaining({ search: "עלמה", offset: 0 }),
    );
  });

  it("caps the search box at MAX_SEARCH_LENGTH", async () => {
    listDresses.mockResolvedValue(page([]));
    render(<CatalogSection />);
    expect(screen.getByLabelText("חיפוש שמלה")).toHaveAttribute("maxlength", "100");
  });
});

describe("CatalogSection archive filter", () => {
  it("switches the list to archived rows and resets the offset", async () => {
    listDresses.mockResolvedValue(page([dress()], 61, 24));
    render(<CatalogSection />);
    await screen.findByText("עלמה");
    fireEvent.click(screen.getByRole("button", { name: "הבא" }));
    await waitFor(() => expect(listDresses).toHaveBeenCalledTimes(2));

    listDresses.mockResolvedValue(page([dress({ id: "d5", name: "רוני", archived: true })], 1, 0));
    fireEvent.click(screen.getByLabelText("ארכיון"));

    await waitFor(() =>
      expect(listDresses).toHaveBeenLastCalledWith(
        expect.objectContaining({ archived: true, offset: 0 }),
      ),
    );
    expect(await screen.findByText("בארכיון")).toBeInTheDocument();
  });
});

describe("CatalogSection detail hand-off", () => {
  it("patches the changed row in place without refetching the list", async () => {
    const row = dress();
    listDresses.mockResolvedValue(page([row], 1, 0));
    getDress.mockResolvedValue(detailOf(row));
    updateDress.mockResolvedValue({ ...row, name: "עלמה החדשה" });

    render(<CatalogSection />);
    fireEvent.click(await screen.findByRole("button", { name: /עלמה/ }));

    const name = await screen.findByLabelText("שם השמלה *");
    fireEvent.change(name, { target: { value: "עלמה החדשה" } });
    fireEvent.click(screen.getByRole("button", { name: "שמירה" }));
    await waitFor(() => expect(updateDress).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole("button", { name: "חזרה לרשימת השמלות" }));

    expect(await screen.findByText("עלמה החדשה")).toBeInTheDocument();
    // One list fetch for the whole flow — the row is patched from the response.
    expect(listDresses).toHaveBeenCalledTimes(1);
  });

  it("opens a blank editor for a new dress with the sub-cards disabled", async () => {
    listDresses.mockResolvedValue(page([], 0));
    render(<CatalogSection />);
    await screen.findByText("אין עדיין שמלות בקטלוג");

    fireEvent.click(screen.getAllByRole("button", { name: "שמלה חדשה" })[0]);

    expect(await screen.findByRole("button", { name: "יצירת שמלה" })).toBeInTheDocument();
    expect(
      screen.getAllByText("יש לשמור את השמלה לפני הוספת מידות ותמונות"),
    ).toHaveLength(2);
    expect(getDress).not.toHaveBeenCalled();
  });

  it("counts a created dress into the pager instead of leaving total one behind", async () => {
    const created = dress({ id: "d2", name: "רוני" });
    listDresses.mockResolvedValue(page([dress()], 1, 0));
    createDress.mockResolvedValue(created);
    getDress.mockResolvedValue(detailOf(created));

    render(<CatalogSection />);
    await screen.findByText("עלמה");
    expect(screen.getByTestId("catalog-count")).toHaveTextContent("מציג 1–1 מתוך 1");

    fireEvent.click(screen.getByRole("button", { name: "שמלה חדשה" }));
    fireEvent.change(await screen.findByLabelText("שם השמלה *"), {
      target: { value: "רוני" },
    });
    fireEvent.click(screen.getByRole("button", { name: "יצירת שמלה" }));
    await waitFor(() => expect(createDress).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole("button", { name: "חזרה לרשימת השמלות" }));

    // Two rows and a count that says two — the row was appended locally, so a
    // total left at 1 would render "מציג 1–1 מתוך 1" above two rows and would
    // re-enable «הבא» against a page that does not exist.
    expect(await screen.findByText("רוני")).toBeInTheDocument();
    expect(screen.getByTestId("catalog-count")).toHaveTextContent("מציג 1–2 מתוך 2");
    expect(screen.getByRole("button", { name: "הבא" })).toBeDisabled();
    // Still no refetch: the count moves with the patched list, not with a GET.
    expect(listDresses).toHaveBeenCalledTimes(1);
  });

  it("does not double-count when the same dress is saved twice", async () => {
    const created = dress({ id: "d2", name: "רוני" });
    listDresses.mockResolvedValue(page([dress()], 1, 0));
    createDress.mockResolvedValue(created);
    getDress.mockResolvedValue(detailOf(created));
    updateDress.mockResolvedValue({ ...created, name: "רוני 2" });

    render(<CatalogSection />);
    await screen.findByText("עלמה");
    fireEvent.click(screen.getByRole("button", { name: "שמלה חדשה" }));
    fireEvent.change(await screen.findByLabelText("שם השמלה *"), {
      target: { value: "רוני" },
    });
    fireEvent.click(screen.getByRole("button", { name: "יצירת שמלה" }));
    await waitFor(() => expect(createDress).toHaveBeenCalledTimes(1));

    fireEvent.click(await screen.findByRole("button", { name: "שמירה" }));
    await waitFor(() => expect(updateDress).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByRole("button", { name: "חזרה לרשימת השמלות" }));

    expect(await screen.findByText("רוני 2")).toBeInTheDocument();
    expect(screen.getByTestId("catalog-count")).toHaveTextContent("מציג 1–2 מתוך 2");
  });
});

describe("CatalogSection already-done races", () => {
  it("treats a 404 from archive as done rather than surfacing the API's English body", async () => {
    const row = dress();
    listDresses.mockResolvedValue(page([row], 1, 0));
    getDress.mockResolvedValue(detailOf(row));
    // Somebody archived it in another tab: DELETE is predicated on
    // `deleted_at IS NULL`, so the second one 404s.
    archiveDress.mockRejectedValue(new ApiError(404, "NOT_FOUND", "Resource not found."));

    render(<CatalogSection />);
    fireEvent.click(await screen.findByRole("button", { name: /עלמה/ }));
    await screen.findByLabelText("שם השמלה *");

    // Once to open the confirmation, once to go through with it.
    fireEvent.click(screen.getByRole("button", { name: "העברה לארכיון" }));
    fireEvent.click(await screen.findByRole("button", { name: "העברה לארכיון" }));

    // Back on the list, row gone, count decremented — and no English error.
    expect(await screen.findByText("אין עדיין שמלות בקטלוג")).toBeInTheDocument();
    expect(screen.getByTestId("catalog-count")).toHaveTextContent("מציג 0–0 מתוך 0");
    expect(screen.queryByText("Resource not found.")).toBeNull();
  });

  it("treats a 404 from restore as done and re-reads the dress", async () => {
    const archivedRow = dress({ archived: true });
    const restored = detailOf(dress({ archived: false }));
    listDresses.mockResolvedValue(page([archivedRow], 1, 0));
    getDress.mockResolvedValueOnce(detailOf(archivedRow)).mockResolvedValueOnce(restored);
    restoreDress.mockRejectedValue(new ApiError(404, "NOT_FOUND", "Resource not found."));

    render(<CatalogSection />);
    fireEvent.click(await screen.findByRole("button", { name: /עלמה/ }));

    fireEvent.click(await screen.findByRole("button", { name: "שחזור" }));

    await waitFor(() => expect(getDress).toHaveBeenCalledTimes(2));
    // The re-read is what converges: the restore button is gone because the
    // dress is no longer archived.
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: "שחזור" })).toBeNull(),
    );
    expect(screen.queryByText("Resource not found.")).toBeNull();
  });
});
