import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "../src/App";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("App", () => {
  it("แสดงข้อมูลที่ได้จาก /health ไม่ใช่ข้อความที่ฝังไว้ในโค้ด", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              status: "ok",
              server_time: "2026-09-27T12:00:00Z",
              version: "0.1.0",
            }),
        }),
      ),
    );

    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId("status").textContent).toBe("ok");
    });
    expect(screen.getAllByRole("main")).toHaveLength(1);
    expect(screen.getByTestId("health").closest("footer")).not.toBeNull();
    expect(screen.getByTestId("server-time").textContent).toBe("2026-09-27T12:00:00Z");
    expect(screen.getByTestId("version").textContent).toBe("0.1.0");
  });

  it("แสดงข้อผิดพลาดเมื่อเรียก /health ไม่สำเร็จ", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ ok: false, status: 503 })));

    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId("error").textContent).toContain("503");
    });
  });
});
