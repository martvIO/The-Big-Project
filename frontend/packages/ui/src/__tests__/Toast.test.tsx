import { fireEvent, render, screen, waitForElementToBeRemoved } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ToastProvider } from "../components/Toast";
import { useToast } from "../components/toast-context";

function Harness() {
  const toast = useToast();
  return (
    <>
      <button onClick={() => toast({ message: "נשמר בהצלחה", variant: "success" })}>ok</button>
      <button onClick={() => toast({ message: "שמירה נכשלה", variant: "error" })}>err</button>
    </>
  );
}

describe("Toast", () => {
  it("success uses role=status, error uses role=alert", () => {
    render(
      <ToastProvider autoDismissMs={10_000}>
        <Harness />
      </ToastProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "ok" }));
    expect(screen.getByRole("status")).toHaveTextContent("נשמר בהצלחה");
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("shows one toast at a time — a new one replaces the current", () => {
    render(
      <ToastProvider autoDismissMs={10_000}>
        <Harness />
      </ToastProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "ok" }));
    fireEvent.click(screen.getByRole("button", { name: "err" }));
    expect(screen.queryByRole("status")).toBeNull();
    expect(screen.getByRole("alert")).toHaveTextContent("שמירה נכשלה");
  });

  it("auto-dismisses", async () => {
    render(
      <ToastProvider autoDismissMs={30}>
        <Harness />
      </ToastProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "ok" }));
    await waitForElementToBeRemoved(() => screen.queryByRole("status"));
  });

  it("throws when used outside a ToastProvider", () => {
    expect(() => render(<Harness />)).toThrow(/ToastProvider/);
  });
});
