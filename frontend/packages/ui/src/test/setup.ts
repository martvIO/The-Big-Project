import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// RTL auto-cleanup hooks onto a global afterEach we don't expose (globals: false).
afterEach(() => {
  cleanup();
});

// jsdom implements <dialog> only partially; stub the modal methods so Modal
// tests exercise open/close/events. Real focus-trap behavior is a browser-QA
// concern (Phase 5), not a jsdom one.
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
