import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Modal } from "../components/Modal";
import { Button } from "../components/Button";

describe("Modal", () => {
  it("shows title and body when open", () => {
    render(
      <Modal open onClose={() => {}} title="העברה לארכיון">
        השמלה תוסתר מהקטלוג
      </Modal>,
    );
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("העברה לארכיון")).toBeInTheDocument();
    expect(screen.getByText("השמלה תוסתר מהקטלוג")).toBeInTheDocument();
  });

  it("Esc (cancel) dismisses without firing the confirm action", () => {
    const onClose = vi.fn();
    const onConfirm = vi.fn();
    render(
      <Modal
        open
        onClose={onClose}
        title="מחיקה"
        footer={<Button variant="danger" onClick={onConfirm}>מחיקה</Button>}
      >
        פעולה זו אינה הפיכה
      </Modal>,
    );
    fireEvent(screen.getByRole("dialog"), new Event("cancel", { cancelable: true }));
    expect(onClose).toHaveBeenCalledOnce();
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("fires the confirm action only when its button is pressed", () => {
    const onConfirm = vi.fn();
    render(
      <Modal open onClose={() => {}} title="מחיקה" footer={<Button variant="danger" onClick={onConfirm}>מחיקה</Button>}>
        פעולה זו אינה הפיכה
      </Modal>,
    );
    screen.getByRole("button", { name: "מחיקה" }).click();
    expect(onConfirm).toHaveBeenCalledOnce();
  });
});
