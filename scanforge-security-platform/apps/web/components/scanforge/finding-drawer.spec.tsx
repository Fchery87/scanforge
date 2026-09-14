import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { FindingDrawer } from "./finding-drawer";

const FINDING = {
  id: "f1",
  title: "SQL Injection in login handler",
  severity: "critical",
  status: "open",
  description: "Unsanitized user input passed directly to query.",
  category: "vulnerability",
  canonical_fingerprint: "abc123",
  primary_scanner: "semgrep",
  instances: [],
  events: [],
  references: [],
};

describe("FindingDrawer", () => {
  it("renders nothing when finding is null", () => {
    const { container } = render(
      <FindingDrawer finding={null} onClose={vi.fn()} onResolve={vi.fn()} onSuppress={vi.fn()} />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders the finding title when finding is provided", () => {
    render(
      <FindingDrawer finding={FINDING} onClose={vi.fn()} onResolve={vi.fn()} onSuppress={vi.fn()} />
    );
    expect(screen.getByText("SQL Injection in login handler")).toBeInTheDocument();
  });

  it("calls onClose when backdrop is clicked", async () => {
    const onClose = vi.fn();
    render(
      <FindingDrawer finding={FINDING} onClose={onClose} onResolve={vi.fn()} onSuppress={vi.fn()} />
    );
    const backdrop = document.querySelector(".fixed.inset-0.z-40") as HTMLElement;
    await userEvent.click(backdrop);
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("exposes dialog semantics with an accessible name and a labelled close control", () => {
    render(
      <FindingDrawer finding={FINDING} onClose={vi.fn()} onResolve={vi.fn()} onSuppress={vi.fn()} />
    );
    const dialog = screen.getByRole("dialog", { name: "SQL Injection in login handler" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(screen.getByRole("button", { name: "Close finding details" })).toBeInTheDocument();
  });

  it("hides the backdrop from assistive technology", () => {
    render(
      <FindingDrawer finding={FINDING} onClose={vi.fn()} onResolve={vi.fn()} onSuppress={vi.fn()} />
    );
    const backdrop = document.querySelector(".fixed.inset-0.z-40") as HTMLElement;
    expect(backdrop).toHaveAttribute("aria-hidden", "true");
  });

  it("closes on Escape", async () => {
    const onClose = vi.fn();
    render(
      <FindingDrawer finding={FINDING} onClose={onClose} onResolve={vi.fn()} onSuppress={vi.fn()} />
    );
    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("moves focus into the drawer on open and restores it on close", () => {
    const trigger = document.createElement("button");
    trigger.textContent = "Open finding";
    document.body.appendChild(trigger);
    trigger.focus();

    const view = render(
      <FindingDrawer finding={FINDING} onClose={vi.fn()} onResolve={vi.fn()} onSuppress={vi.fn()} />
    );
    expect(screen.getByRole("dialog")).toHaveFocus();

    view.rerender(
      <FindingDrawer finding={null} onClose={vi.fn()} onResolve={vi.fn()} onSuppress={vi.fn()} />
    );
    expect(trigger).toHaveFocus();
    trigger.remove();
  });

  it("does not trap keyboard users when other keys are pressed", async () => {
    const onClose = vi.fn();
    render(
      <FindingDrawer finding={FINDING} onClose={onClose} onResolve={vi.fn()} onSuppress={vi.fn()} />
    );
    await userEvent.keyboard("{Tab}");
    expect(onClose).not.toHaveBeenCalled();
  });
});
