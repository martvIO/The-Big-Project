import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "@boutique/ui";
import { FALLBACK_ERROR_MESSAGE } from "../api";
import { ShareButton } from "../components/ShareButton";
import i18n from "../i18n";

// Three branches ship here — native share, clipboard fallback, neither — and
// the share branch has two outcomes that must not be confused: the visitor
// closing the sheet (nothing failed) and the browser refusing the call
// (Chromium desktop's NotAllowedError), which leaves the visitor with no link
// unless the clipboard picks it up.

function stub(property: "share" | "clipboard", value: unknown) {
  Object.defineProperty(navigator, property, { value, configurable: true, writable: true });
}

// The toast fires a microtask after the click; findBy* would also work, but the
// "nothing happened" assertions need a flush they cannot express.
async function flush() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

let writeText: ReturnType<typeof vi.fn>;

beforeEach(() => {
  writeText = vi.fn(() => Promise.resolve());
  stub("clipboard", { writeText });
});

afterEach(() => {
  stub("share", undefined);
  stub("clipboard", undefined);
  vi.clearAllMocks();
});

function renderShare(title = "ורד") {
  render(
    <ToastProvider>
      <ShareButton title={title} />
    </ToastProvider>,
  );
  return screen.getByRole("button", { name: i18n.t("dress.share") });
}

describe("ShareButton — native share sheet", () => {
  it("hands the dress name and this URL to the platform, and copies nothing", async () => {
    const share = vi.fn(() => Promise.resolve());
    stub("share", share);

    fireEvent.click(renderShare());
    await flush();

    expect(share).toHaveBeenCalledWith({ title: "ורד", url: window.location.href });
    expect(writeText).not.toHaveBeenCalled();
    // A native sheet is its own confirmation — a toast on top of it is noise.
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("stays silent when the visitor dismisses the sheet", async () => {
    const abort = new Error("dismissed");
    abort.name = "AbortError";
    stub("share", vi.fn(() => Promise.reject(abort)));

    fireEvent.click(renderShare());
    await flush();

    // The visitor chose not to share. Copying the link behind their back and
    // announcing it would be answering a decision they already made.
    expect(writeText).not.toHaveBeenCalled();
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("falls back to the clipboard when the browser refuses the share", async () => {
    const refused = new Error("Must be handling a user gesture to perform a share request.");
    refused.name = "NotAllowedError";
    stub("share", vi.fn(() => Promise.reject(refused)));

    fireEvent.click(renderShare());

    // Chromium on desktop rejects like this when it does not count the click as
    // transient activation. Swallowing it leaves the visitor with no sheet, no
    // link and no message.
    expect(await screen.findByRole("status")).toHaveTextContent(i18n.t("dress.shareCopied"));
    expect(writeText).toHaveBeenCalledWith(window.location.href);
  });
});

describe("ShareButton — clipboard fallback", () => {
  it("copies the link and says so out loud when there is no share sheet", async () => {
    stub("share", undefined);

    fireEvent.click(renderShare());

    expect(writeText).toHaveBeenCalledWith(window.location.href);
    // role="status" — a silent clipboard write looks broken to a screen-reader
    // user, who gets no visual cue that anything happened.
    expect(await screen.findByRole("status")).toHaveTextContent(i18n.t("dress.shareCopied"));
  });

  it("reports a failed clipboard write instead of pretending it copied", async () => {
    stub("share", undefined);
    writeText.mockReturnValue(Promise.reject(new Error("denied")));

    fireEvent.click(renderShare());

    expect(await screen.findByRole("alert")).toHaveTextContent(FALLBACK_ERROR_MESSAGE);
  });

  it("explains itself when the platform offers neither share nor clipboard", async () => {
    stub("share", undefined);
    stub("clipboard", undefined);

    fireEvent.click(renderShare());

    // An insecure origin has no clipboard. The button must not go inert with no
    // explanation.
    expect(await screen.findByRole("alert")).toHaveTextContent(FALLBACK_ERROR_MESSAGE);
  });
});
