import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { DressDetail, Media, PresignResponse } from "../api";
import { MediaGallery } from "../components/MediaGallery";

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ApiError: actual.ApiError,
    errorMessage: actual.errorMessage,
    api: {
      getDress: vi.fn(),
      presignMedia: vi.fn(),
      confirmMedia: vi.fn(),
      deleteMedia: vi.fn(),
      reorderMedia: vi.fn(),
    },
    uploadToStorage: vi.fn(),
  };
});

const { api, ApiError, uploadToStorage } = await import("../api");
const presignMedia = vi.mocked(api.presignMedia);
const confirmMedia = vi.mocked(api.confirmMedia);
const deleteMedia = vi.mocked(api.deleteMedia);
const reorderMedia = vi.mocked(api.reorderMedia);
const getDress = vi.mocked(api.getDress);
const upload = vi.mocked(uploadToStorage);

// Every mocked call appends here, so "sequential on the wire" is one assertion.
let calls: string[] = [];

function media(id: string, sortOrder: number): Media {
  return {
    id,
    sort_order: sortOrder,
    content_type: "image/jpeg",
    byte_size: 3_200_000,
    url: `https://media.example.test/${id}.jpg?sig=x`,
    url_expires_at: "2026-07-24T10:15:00Z",
  };
}

function detail(rows: Media[]): DressDetail {
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
    media_count: rows.length,
    cover: rows[0] ?? null,
    archived: false,
    created_at: "2026-07-24T10:00:00Z",
    updated_at: null,
    variants: [],
    media: rows,
    media_uploads_enabled: true,
    media_slots_remaining: 12 - rows.length,
  };
}

function presign(mediaId: string): PresignResponse {
  return {
    media_id: mediaId,
    url: "https://media.example.test/boutique-media",
    fields: { key: `tenants/t1/dresses/d1/media/${mediaId}.jpg`, "Content-Type": "image/jpeg" },
    expires_in: 300,
    max_bytes: 10_485_760,
  };
}

function photo(name: string, size = 3_200_000): File {
  const file = new File([new Uint8Array([0xff, 0xd8, 0xff])], name, { type: "image/jpeg" });
  Object.defineProperty(file, "size", { value: size });
  return file;
}

function renderGallery(
  overrides: Partial<Parameters<typeof MediaGallery>[0]> = {},
): { onDetail: ReturnType<typeof vi.fn> } {
  const onDetail = vi.fn();
  render(
    <MediaGallery
      dressId="d1"
      dressName="עלמה"
      media={[]}
      uploadsEnabled
      slotsRemaining={12}
      disabled={false}
      disabledReason={null}
      onDetail={onDetail}
      {...overrides}
    />,
  );
  return { onDetail };
}

function selectFiles(files: File[]) {
  const input = screen.getByLabelText("הוספת תמונות");
  fireEvent.change(input, { target: { files } });
}

beforeEach(() => {
  vi.clearAllMocks();
  calls = [];
  let minted = 0;
  presignMedia.mockImplementation(async () => {
    minted += 1;
    const id = `m${minted}`;
    calls.push(`presign:${id}`);
    return presign(id);
  });
  // `uploadToStorage` takes the STRUCTURAL {url, fields} pair it actually reads
  // — F38's staff presign carries no `media_id` — so the id this log needs comes
  // off the mock's own envelope rather than off the parameter type.
  upload.mockImplementation(async (request) => {
    calls.push(`upload:${(request as PresignResponse).media_id}`);
  });
  confirmMedia.mockImplementation(async (_dressId: string, mediaId: string) => {
    calls.push(`confirm:${mediaId}`);
    return detail([media(mediaId, 0)]);
  });
  deleteMedia.mockImplementation(async (_dressId: string, mediaId: string) => {
    calls.push(`delete:${mediaId}`);
    return detail([]);
  });
});

describe("MediaGallery upload orchestration", () => {
  it("runs presign → upload → confirm for each file", async () => {
    const { onDetail } = renderGallery();
    selectFiles([photo("IMG_4821.jpg")]);

    await waitFor(() => expect(calls).toEqual(["presign:m1", "upload:m1", "confirm:m1"]));
    expect(presignMedia).toHaveBeenCalledWith("d1", {
      content_type: "image/jpeg",
      byte_size: 3_200_000,
    });
    await waitFor(() => expect(onDetail).toHaveBeenCalledTimes(1));
  });

  it("is strictly sequential on the wire — file 2 presigns only after file 1 confirms", async () => {
    renderGallery();
    selectFiles([photo("IMG_4821.jpg"), photo("IMG_4822.jpg")]);

    await waitFor(() => expect(calls).toHaveLength(6));
    expect(calls).toEqual([
      "presign:m1",
      "upload:m1",
      "confirm:m1",
      "presign:m2",
      "upload:m2",
      "confirm:m2",
    ]);
  });

  it("isolates a mid-queue failure to its own row, releases the pending slot and continues", async () => {
    renderGallery();
    upload.mockImplementationOnce(async () => {
      calls.push("upload:m1:failed");
      throw new ApiError(0, "UPLOAD_BLOCKED", "לא ניתן היה להעלות את הקובץ. בדקי את החיבור ונסי שוב.");
    });

    selectFiles([photo("IMG_4821.jpg"), photo("IMG_4822.jpg")]);

    // The pending row is deleted so the gallery slot is freed immediately.
    await waitFor(() => expect(deleteMedia).toHaveBeenCalledWith("d1", "m1"));
    // The queue keeps going: file 2 completes.
    await waitFor(() => expect(calls).toContain("confirm:m2"));
    // The retry button names its file — three bare "נסי שוב" buttons would be
    // unnavigable from a screen reader's buttons list.
    expect(
      screen.getByRole("button", { name: "נסי שוב — IMG_4821.jpg" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/לא ניתן היה להעלות את הקובץ/)).toBeInTheDocument();
  });

  it("leaves the pending row alone on a transient storage 5xx and re-confirms it on retry", async () => {
    renderGallery();
    confirmMedia.mockImplementationOnce(async (_dressId: string, mediaId: string) => {
      calls.push(`confirm:${mediaId}:503`);
      throw new ApiError(
        503,
        "MEDIA_STORAGE_UNAVAILABLE",
        "Image storage is temporarily unavailable.",
      );
    });

    selectFiles([photo("IMG_4821.jpg")]);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "נסי שוב — IMG_4821.jpg" })).toBeInTheDocument(),
    );
    // The server left the row pending and confirmable; destroying it would
    // force a full re-upload of an object that already reached the bucket.
    expect(deleteMedia).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "נסי שוב — IMG_4821.jpg" }));

    // The retry re-confirms the SAME media id — no second presign, no re-POST.
    await waitFor(() => expect(calls).toContain("confirm:m1"));
    expect(calls).toEqual(["presign:m1", "upload:m1", "confirm:m1:503", "confirm:m1"]);
    expect(presignMedia).toHaveBeenCalledTimes(1);
    expect(upload).toHaveBeenCalledTimes(1);
  });

  it("still deletes the pending row when the confirm failure is not a storage outage", async () => {
    renderGallery();
    confirmMedia.mockImplementationOnce(async (_dressId: string, mediaId: string) => {
      calls.push(`confirm:${mediaId}:mismatch`);
      throw new ApiError(409, "MEDIA_MISMATCH", "Uploaded object does not match.");
    });

    selectFiles([photo("IMG_4821.jpg")]);

    await waitFor(() => expect(deleteMedia).toHaveBeenCalledWith("d1", "m1"));
    expect(screen.getByText("הקובץ אינו תמונה תקינה.")).toBeInTheDocument();

    // With the row released, the retry has to start from a fresh presign.
    fireEvent.click(screen.getByRole("button", { name: "נסי שוב — IMG_4821.jpg" }));
    await waitFor(() => expect(presignMedia).toHaveBeenCalledTimes(2));
    expect(calls).toContain("confirm:m2");
  });

  it("blocks the selection against media_slots_remaining before any request", async () => {
    renderGallery({ slotsRemaining: 1 });
    selectFiles([photo("IMG_4821.jpg"), photo("IMG_4822.jpg")]);

    await waitFor(() => expect(presignMedia).toHaveBeenCalledTimes(1));
    expect(screen.getByRole("alert")).toHaveTextContent("1 קבצים לא צורפו — פרטים ברשימה למטה");
    expect(
      screen.getByText("ניתן להעלות עד 12 תמונות לשמלה — נותרו 1"),
    ).toBeInTheDocument();
  });

  it("rejects an unaccepted type client-side with no request and no retry offer", async () => {
    renderGallery();
    const heic = new File([new Uint8Array([0])], "IMG_4823.heic", { type: "image/heic" });
    Object.defineProperty(heic, "size", { value: 6_000_000 });
    selectFiles([heic]);

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(presignMedia).not.toHaveBeenCalled();
    expect(screen.getByText("HEIC אינו נתמך. שמרי כ-JPG")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /נסי שוב/ })).toBeNull();
  });
});

describe("MediaGallery storage-disabled state", () => {
  it("renders a calm notice and keeps the reason on the disabled input's visible label", () => {
    renderGallery({ uploadsEnabled: false, slotsRemaining: 12 });

    expect(screen.getByRole("status")).toHaveTextContent("העלאת תמונות עדיין לא זמינה");
    // `disabled` alone drops the control from the tab order, so the reason has
    // to live on the visible label.
    const input = screen.getByLabelText("הוספת תמונות (לא זמין כרגע)");
    expect(input).toBeDisabled();
  });
});

describe("MediaGallery reorder", () => {
  it("keeps focus on the same logical button after an optimistic swap", async () => {
    const rows = [media("m1", 0), media("m2", 1), media("m3", 2)];
    reorderMedia.mockResolvedValue(detail([rows[1], rows[0], rows[2]]));
    renderGallery({ media: rows, slotsRemaining: 9 });

    const forward = screen.getByRole("button", { name: "הזזת תמונה 1 קדימה" });
    forward.focus();
    fireEvent.click(forward);

    await waitFor(() => expect(reorderMedia).toHaveBeenCalledWith("d1", ["m2", "m1", "m3"]));
    // m1 is now second — focus followed the photo, not the index.
    await waitFor(() =>
      expect(document.activeElement).toHaveAttribute("aria-label", "הזזת תמונה 2 קדימה"),
    );
    expect(screen.getByRole("status")).toHaveTextContent("התמונה הועברה למקום 2 מתוך 3");
  });

  it("moves focus to the sibling when the button it used becomes disabled", async () => {
    const rows = [media("m1", 0), media("m2", 1)];
    reorderMedia.mockResolvedValue(detail([rows[1], rows[0]]));
    renderGallery({ media: rows, slotsRemaining: 10 });

    const forward = screen.getByRole("button", { name: "הזזת תמונה 1 קדימה" });
    forward.focus();
    fireEvent.click(forward);

    // m1 is now last, so its ↓ is disabled — focus must land on its ↑ sibling
    // rather than dropping to <body>.
    await waitFor(() =>
      expect(document.activeElement).toHaveAttribute("aria-label", "הזזת תמונה 2 אחורה"),
    );
  });

  it("disables the first item's back button and the last item's forward button", () => {
    renderGallery({ media: [media("m1", 0), media("m2", 1)], slotsRemaining: 10 });
    expect(screen.getByRole("button", { name: "הזזת תמונה 1 אחורה" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "הזזת תמונה 2 קדימה" })).toBeDisabled();
  });
});

describe("MediaGallery signed-URL expiry", () => {
  it("refetches the dress exactly once per mount, however many images fail", async () => {
    getDress.mockResolvedValue(detail([media("m1", 0), media("m2", 1)]));
    const { onDetail } = renderGallery({ media: [media("m1", 0), media("m2", 1)], slotsRemaining: 10 });

    const images = screen.getAllByRole("img");
    fireEvent.error(images[0]);
    fireEvent.error(images[1]);

    await waitFor(() => expect(onDetail).toHaveBeenCalledTimes(1));
    expect(getDress).toHaveBeenCalledTimes(1);
    expect(getDress).toHaveBeenCalledWith("d1");
  });

  it("names gallery images by dress and ordinal", () => {
    renderGallery({ media: [media("m1", 0), media("m2", 1)], slotsRemaining: 10 });
    expect(screen.getByAltText("עלמה — תמונה 1")).toBeInTheDocument();
    expect(screen.getByAltText("עלמה — תמונה 2")).toBeInTheDocument();
  });

  it("appends the ordinal to every per-item control without replacing its visible label", () => {
    renderGallery({ media: [media("m1", 0), media("m2", 1)], slotsRemaining: 10 });
    // WCAG 2.5.3: the accessible name must BEGIN with the visible text verbatim.
    expect(screen.getByRole("button", { name: "מחיקה — תמונה 2" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "קבעי כתמונה ראשית — תמונה 2" }),
    ).toBeInTheDocument();
    // Item 1 is the primary photo, so it carries the caption and no set-primary action.
    expect(screen.getByText("תמונה ראשית (מוצגת בקטלוג)")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "קבעי כתמונה ראשית — תמונה 1" }),
    ).toBeNull();
  });
});
