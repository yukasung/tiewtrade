import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AuthPanel } from "../src/AuthPanel";

afterEach(() => {
  vi.unstubAllGlobals();
  document.cookie =
    "tiewtrade_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
});

/** หลังบ้านจำลองที่ตอบตามเส้นทาง — ไม่ใช่ตอบเหมือนกันหมด */
function serverThat(
  routes: Record<string, () => Response>,
): ReturnType<typeof vi.fn> {
  return vi.fn((input: string, init?: RequestInit) => {
    const key = `${init?.method ?? "GET"} ${input}`;
    const handler =
      routes[key] ??
      (key === "GET /api/api-keys"
        ? () => jsonResponse([])
        : key === "GET /api/trading-account"
          ? () =>
              jsonResponse({
                use: null,
                key: null,
                may_trade: false,
                may_change_use: false,
              })
          : undefined);
    if (handler === undefined) {
      throw new Error(`เทสต์ไม่ได้เตรียมคำตอบของ ${key}`);
    }
    return Promise.resolve(handler());
  });
}

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status < 400,
    status,
    json: () => Promise.resolve(body),
  } as unknown as Response;
}

describe("AuthPanel", () => {
  it("แสดงฟอร์มเข้าสู่ระบบเมื่อยังไม่ได้เข้าสู่ระบบ", async () => {
    vi.stubGlobal(
      "fetch",
      serverThat({
        "GET /api/auth/csrf": () => jsonResponse({ csrf_token: "t" }),
        "GET /api/auth/me": () =>
          jsonResponse({ detail: "ต้องเข้าสู่ระบบก่อน" }, 401),
      }),
    );

    window.history.replaceState(null, "", "/account");
    render(<AuthPanel />);

    await waitFor(() => {
      expect(screen.getByTestId("signed-out")).toBeTruthy();
    });
    expect(screen.queryByTestId("signed-in")).toBeNull();
    expect(screen.getByTestId("signed-out").closest(".auth-layout")).not.toBeNull();
    expect(screen.getByTestId("submit").className).toContain("account-button");
  });

  it("แสดงรหัสผู้ใช้เมื่อเข้าสู่ระบบแล้ว", async () => {
    vi.stubGlobal(
      "fetch",
      serverThat({
        "GET /api/auth/csrf": () => jsonResponse({ csrf_token: "t" }),
        "GET /api/auth/me": () =>
          jsonResponse({ user_id: "a4f0e1d2-0000-4000-8000-000000000001" }),
      }),
    );

    window.history.replaceState(null, "", "/account");
    render(<AuthPanel />);

    await waitFor(() => {
      expect(screen.getByTestId("user-id").textContent).toBe(
        "a4f0e1d2-0000-4000-8000-000000000001",
      );
    });
  });

  it("บอกเหตุผลที่หลังบ้านปฏิเสธ ไม่ใช่ข้อความที่เขียนไว้เอง", async () => {
    let signedIn = false;
    vi.stubGlobal(
      "fetch",
      serverThat({
        "GET /api/auth/csrf": () => jsonResponse({ csrf_token: "t" }),
        "GET /api/auth/me": () =>
          signedIn
            ? jsonResponse({ user_id: "x" })
            : jsonResponse({ detail: "ต้องเข้าสู่ระบบก่อน" }, 401),
        "POST /api/auth/login": () =>
          jsonResponse({ detail: "อีเมลหรือรหัสผ่านไม่ถูกต้อง" }, 401),
      }),
    );

    window.history.replaceState(null, "", "/account");
    render(<AuthPanel />);
    await waitFor(() => {
      expect(screen.getByTestId("signed-out")).toBeTruthy();
    });

    fireEvent.change(screen.getByLabelText("อีเมล"), {
      target: { value: "someone@example.com" },
    });
    fireEvent.change(screen.getByLabelText("รหัสผ่าน"), {
      target: { value: "รหัสผ่านที่ยาวพอใช้งาน" },
    });
    fireEvent.click(screen.getByTestId("submit"));

    await waitFor(() => {
      expect(screen.getByTestId("refusal").textContent).toBe(
        "อีเมลหรือรหัสผ่านไม่ถูกต้อง",
      );
    });
    expect(signedIn).toBe(false);
  });

  it("เตือนว่ากู้รหัสผ่านไม่ได้ ก่อนผู้ใช้สมัคร", async () => {
    vi.stubGlobal(
      "fetch",
      serverThat({
        "GET /api/auth/csrf": () => jsonResponse({ csrf_token: "t" }),
        "GET /api/auth/me": () =>
          jsonResponse({ detail: "ต้องเข้าสู่ระบบก่อน" }, 401),
      }),
    );

    window.history.replaceState(null, "", "/account");
    render(<AuthPanel />);
    await waitFor(() => {
      expect(screen.getByTestId("signed-out")).toBeTruthy();
    });

    fireEvent.click(screen.getByTestId("switch-mode"));

    const warning = screen.getByTestId("recovery-warning").textContent ?? "";
    expect(warning).toContain("ยังไม่มีทางกู้รหัสผ่าน");
    expect(warning).toContain("15");
  });

  it("ขอโทเคนกัน CSRF ใบใหม่และกลับไปโหมดเข้าสู่ระบบหลังออกจากระบบ", async () => {
    let signedIn = true;
    const primes: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((input: string, init?: RequestInit) => {
        const key = `${init?.method ?? "GET"} ${input}`;
        if (key === "GET /api/auth/csrf") {
          primes.push(key);
          return Promise.resolve(jsonResponse({ csrf_token: "t" }));
        }
        if (key === "GET /api/auth/me") {
          return Promise.resolve(
            signedIn
              ? jsonResponse({ user_id: "x" })
              : jsonResponse({ detail: "ต้องเข้าสู่ระบบก่อน" }, 401),
          );
        }
        if (key === "POST /api/auth/logout") {
          signedIn = false;
          return Promise.resolve(jsonResponse({ ended: 1 }));
        }
        throw new Error(`เทสต์ไม่ได้เตรียมคำตอบของ ${key}`);
      }),
    );

    window.history.replaceState(null, "", "/account");
    render(<AuthPanel />);
    await waitFor(() => {
      expect(screen.getByTestId("signed-in")).toBeTruthy();
    });

    fireEvent.click(screen.getByTestId("log-out"));

    await waitFor(() => {
      expect(screen.getByTestId("signed-out")).toBeTruthy();
    });
    // ใบเดิมถูกลบไปพร้อม session — ถ้าไม่ขอใบใหม่ การเข้าสู่ระบบครั้งต่อไปจะถูกปฏิเสธ
    expect(primes.length).toBe(2);
    // และต้องอยู่โหมดเข้าสู่ระบบ ไม่ใช่โหมดสมัคร ซึ่งจะกลายเป็นการสมัครซ้ำ
    expect(screen.getByRole("heading", { name: "เข้าสู่ระบบ" })).toBeTruthy();
  });
});
