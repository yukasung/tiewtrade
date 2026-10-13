import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { AccountLayout } from "../src/layout/AccountLayout";
import { Button } from "../src/components/ui/Button";
import { Input } from "../src/components/ui/Input";
import { Label } from "../src/components/ui/Label";
import { Select } from "../src/components/ui/Select";
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it("lets the chart page use the full workspace width", () => {
  const { container } = render(<AccountLayout page="chart"><p>chart</p></AccountLayout>);
  expect(container.querySelector(".account-content-chart")).toBeTruthy();
});
it("keeps the standard content width on other module pages", () => {
  const { container } = render(<AccountLayout page="account"><p>account</p></AccountLayout>);
  expect(container.querySelector(".account-content-chart")).toBeNull();
});
it("toggles the desktop icon rail without hiding the current module", () => {
  vi.stubGlobal("innerWidth", 1440);
  const { container } = render(<AccountLayout><p>current module</p></AccountLayout>);
  const trigger = screen.getByRole("button", { name: "เปิดเมนูบัญชี" });
  expect(trigger.getAttribute("aria-expanded")).toBe("true");
  fireEvent.click(trigger);
  expect(trigger.getAttribute("aria-expanded")).toBe("false");
  expect(container.querySelector(".sidebar-collapsed")).toBeTruthy();
  expect(screen.getByText("current module")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "ปิดเมนูบัญชี" })).toBeNull();
  fireEvent.click(trigger);
  expect(container.querySelector(".sidebar-collapsed")).toBeNull();
});
it("removes the mobile backdrop when resizing into desktop layout", () => {
  vi.stubGlobal("innerWidth", 375);
  render(<AccountLayout><p>current module</p></AccountLayout>);
  const trigger = screen.getByRole("button", { name: "เปิดเมนูบัญชี" });
  fireEvent.click(trigger);
  expect(screen.getByRole("button", { name: "ปิดเมนูบัญชี" })).toBeTruthy();
  vi.stubGlobal("innerWidth", 1440);
  fireEvent(window, new Event("resize"));
  expect(screen.queryByRole("button", { name: "ปิดเมนูบัญชี" })).toBeNull();
  expect(trigger.getAttribute("aria-expanded")).toBe("true");
});
it("keeps one main landmark when embedded in the page main", () => {
  render(
    <main>
      <AccountLayout>
        <p>account content</p>
      </AccountLayout>
    </main>,
  );
  expect(screen.getAllByRole("main")).toHaveLength(1);
  expect(screen.getByRole("main").textContent).toContain("account content");
});
it("closes navigation with Escape and backdrop and restores trigger focus", () => {
  render(
    <AccountLayout>
      <p>content</p>
    </AccountLayout>,
  );
  const trigger = screen.getByRole("button", { name: "เปิดเมนูบัญชี" });
  fireEvent.click(trigger);
  expect(trigger.getAttribute("aria-expanded")).toBe("true");
  fireEvent.keyDown(document, { key: "Escape" });
  expect(trigger.getAttribute("aria-expanded")).toBe("false");
  expect(document.activeElement).toBe(trigger);
  fireEvent.click(trigger);
  fireEvent.click(screen.getByRole("button", { name: "ปิดเมนูบัญชี" }));
  expect(trigger.getAttribute("aria-expanded")).toBe("false");
});
it("preserves native form props and explicit button types", () => {
  const submit = vi.fn((event: React.FormEvent) => event.preventDefault());
  render(
    <form onSubmit={submit}>
      <Label htmlFor="native">Native</Label>
      <Input
        id="native"
        name="native"
        required
        aria-invalid="true"
        aria-describedby="help"
      />
      <Select aria-label="Choice" name="choice" defaultValue="x">
        <option value="x">X</option>
      </Select>
      <Button>Cancel</Button>
      <Button type="submit">Save</Button>
    </form>,
  );
  expect(screen.getByLabelText("Native").getAttribute("aria-describedby")).toBe(
    "help",
  );
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(submit).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText("Native"), {
    target: { value: "value" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(submit).toHaveBeenCalledOnce();
});
