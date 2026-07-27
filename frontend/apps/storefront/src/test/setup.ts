import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// RTL auto-cleanup hooks onto global afterEach, which we don't expose
// (globals: false) — register it explicitly.
afterEach(() => {
  cleanup();
});

// jsdom implements <dialog> only partially; stub the modal methods so the
// @boutique/ui Modal (native <dialog>) behind the booking CTA works in tests.
// Real focus-trap behavior is a browser-QA concern.
const dialogProto = globalThis.HTMLDialogElement?.prototype;
if (dialogProto && typeof dialogProto.showModal !== "function") {
  dialogProto.showModal = function showModal(this: HTMLDialogElement) {
    this.open = true;
  };
  dialogProto.show = function show(this: HTMLDialogElement) {
    this.open = true;
  };
  dialogProto.close = function close(this: HTMLDialogElement, returnValue?: string) {
    this.open = false;
    if (returnValue !== undefined) this.returnValue = returnValue;
    this.dispatchEvent(new Event("close"));
  };
}
