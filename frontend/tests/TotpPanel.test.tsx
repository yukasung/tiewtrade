import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthPanel } from "../src/AuthPanel";

beforeEach(() => { window.history.replaceState(null, "", "/security"); });

afterEach(() => {
  vi.unstubAllGlobals();
  document.cookie = "tiewtrade_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
});

const USER = "a4f0e1d2-0000-4000-8000-000000000001";

/** หลังบ้านจำลองที่ตอบตามเส้นทาง — ไม่ใช่ตอบเหมือนกันหมด */
function serverThat(routes: Record<string, () => Response>): ReturnType<typeof vi.fn> {
  return vi.fn((input: string, init?: RequestInit) => {
    const key = `${init?.method ?? "GET"} ${input}`;
    const handler = routes[key];
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

describe("การยืนยันสองชั้นบนหน้าเว็บ", () => {
  it("บอกว่าปิดอยู่เมื่อบัญชียังไม่เปิดใช้", async () => {
    vi.stubGlobal(
      "fetch",
      serverThat({
        "GET /api/auth/csrf": () => jsonResponse({ csrf_token: "t" }),
        "GET /api/auth/me": () => jsonResponse({ user_id: USER, totp_enabled: false }),
      }),
    );

    render(<AuthPanel />);

    await waitFor(() => {
      expect(screen.getByTestId("totp-state").textContent).toBe("ปิดอยู่");
    });
    expect(screen.getByTestId("start-totp").className).toContain("account-button");
  });

  it("แสดง QR และข้อความให้สแกน แล้วแสดงรหัสสำรองหลังยืนยัน", async () => {
    let enabled = false;
    vi.stubGlobal(
      "fetch",
      serverThat({
        "GET /api/auth/csrf": () => jsonResponse({ csrf_token: "t" }),
        "GET /api/auth/me": () => jsonResponse({ user_id: USER, totp_enabled: enabled }),
        "POST /api/auth/totp/setup": () =>
          jsonResponse({ otpauth_uri: "otpauth://totp/TiewTrade%3Aa%40b.co?secret=AAAA" }),
        "POST /api/auth/totp/confirm": () => {
          enabled = true;
          return jsonResponse({ recovery_codes: ["AAAA-1", "BBBB-2"], ended: 1 });
        },
      }),
    );

    render(<AuthPanel />);
    await waitFor(() => {
      expect(screen.getByTestId("start-totp").className).toContain("account-button");
    });

    fireEvent.click(screen.getByTestId("start-totp"));
    await waitFor(() => {
      expect(screen.getByTestId("otpauth-uri").textContent).toContain("otpauth://totp/");
    });

    // **ต้องมีทั้ง QR และข้อความ** — สแกนไม่ได้ก็ต้องกรอกด้วยมือได้ (plan หัวข้อ 9)
    await waitFor(() => {
      expect(screen.getByTestId("otpauth-qr").getAttribute("src")).toMatch(
        /^data:image\/png;base64,/,
      );
    });
    expect(screen.getByTestId("otpauth-qr").getAttribute("alt")).toContain("ข้อความข้างล่าง");

    fireEvent.change(screen.getByLabelText("รหัสจากแอป"), { target: { value: "123456" } });
    fireEvent.click(screen.getByTestId("confirm-totp"));

    await waitFor(() => {
      expect(screen.getByTestId("recovery-codes").textContent).toContain("AAAA-1");
    });
    // **คำเตือนต้องบอกผลที่ตามมาจริง** ไม่ใช่แค่ว่า "เก็บไว้ให้ดี"
    expect(screen.getByTestId("recovery-codes").textContent).toContain("เข้าบัญชีไม่ได้เลย");
    expect(screen.getByTestId("totp-state").textContent).toBe("เปิดอยู่");
  });

  it("ขอรหัสจากแอปเป็นขั้นที่สองหลังกรอกรหัสผ่านถูก", async () => {
    let signedIn = false;
    vi.stubGlobal(
      "fetch",
      serverThat({
        "GET /api/auth/csrf": () => jsonResponse({ csrf_token: "t" }),
        "GET /api/auth/me": () =>
          signedIn
            ? jsonResponse({ user_id: USER, totp_enabled: true })
            : jsonResponse({ detail: "ต้องเข้าสู่ระบบก่อน" }, 401),
        "POST /api/auth/login": () =>
          jsonResponse({ user_id: USER, second_step_required: true }),
        "POST /api/auth/totp/login": () => {
          signedIn = true;
          return jsonResponse({ user_id: USER, recovery_codes_left: null });
        },
      }),
    );

    render(<AuthPanel />);
    await waitFor(() => {
      expect(screen.getByTestId("signed-out")).toBeTruthy();
    });

    fireEvent.change(screen.getByLabelText("อีเมล"), { target: { value: "a@b.co" } });
    fireEvent.change(screen.getByLabelText("รหัสผ่าน"), {
      target: { value: "รหัสผ่านที่ยาวพอใช้งานจริง" },
    });
    fireEvent.click(screen.getByTestId("submit"));

    // **ยังไม่ถือว่าเข้าสู่ระบบ** — หน้าจอต้องขอขั้นที่สอง ไม่ใช่แสดงว่าเข้าแล้ว
    await waitFor(() => {
      expect(screen.getByTestId("second-step")).toBeTruthy();
    });
    expect(screen.queryByTestId("signed-in")).toBeNull();

    fireEvent.change(screen.getByLabelText("รหัสจากแอป"), { target: { value: "123456" } });
    fireEvent.click(screen.getByTestId("submit-second-step"));

    await waitFor(() => {
      expect(screen.getByTestId("signed-in")).toBeTruthy();
    });
  });

  it("บอกจำนวนรหัสสำรองที่เหลือเมื่อเข้าสู่ระบบด้วยรหัสสำรอง", async () => {
    window.history.replaceState(null, "", "/account");
    let signedIn = false;
    vi.stubGlobal(
      "fetch",
      serverThat({
        "GET /api/auth/csrf": () => jsonResponse({ csrf_token: "t" }),
        "GET /api/auth/me": () =>
          signedIn
            ? jsonResponse({ user_id: USER, totp_enabled: true })
            : jsonResponse({ detail: "ต้องเข้าสู่ระบบก่อน" }, 401),
        "POST /api/auth/login": () =>
          jsonResponse({ user_id: USER, second_step_required: true }),
        "POST /api/auth/totp/login": () => {
          signedIn = true;
          return jsonResponse({ user_id: USER, recovery_codes_left: 3 });
        },
      }),
    );

    render(<AuthPanel />);
    await waitFor(() => {
      expect(screen.getByTestId("signed-out")).toBeTruthy();
    });
    fireEvent.change(screen.getByLabelText("อีเมล"), { target: { value: "a@b.co" } });
    fireEvent.change(screen.getByLabelText("รหัสผ่าน"), {
      target: { value: "รหัสผ่านที่ยาวพอใช้งานจริง" },
    });
    fireEvent.click(screen.getByTestId("submit"));
    await waitFor(() => {
      expect(screen.getByTestId("second-step")).toBeTruthy();
    });

    fireEvent.change(screen.getByLabelText("หรือรหัสสำรอง"), { target: { value: "AAAA-1" } });
    fireEvent.click(screen.getByTestId("submit-second-step"));

    await waitFor(() => {
      expect(screen.getByTestId("codes-left").textContent).toContain("3");
    });
  });

  it("แสดงข้อความที่หลังบ้านส่งมาเมื่อรหัสไม่ผ่าน", async () => {
    vi.stubGlobal(
      "fetch",
      serverThat({
        "GET /api/auth/csrf": () => jsonResponse({ csrf_token: "t" }),
        "GET /api/auth/me": () => jsonResponse({ detail: "ต้องเข้าสู่ระบบก่อน" }, 401),
        "POST /api/auth/login": () =>
          jsonResponse({ user_id: USER, second_step_required: true }),
        "POST /api/auth/totp/login": () =>
          jsonResponse({ detail: "รหัสยืนยันไม่ถูกต้อง" }, 403),
      }),
    );

    render(<AuthPanel />);
    await waitFor(() => {
      expect(screen.getByTestId("signed-out")).toBeTruthy();
    });
    fireEvent.change(screen.getByLabelText("อีเมล"), { target: { value: "a@b.co" } });
    fireEvent.change(screen.getByLabelText("รหัสผ่าน"), {
      target: { value: "รหัสผ่านที่ยาวพอใช้งานจริง" },
    });
    fireEvent.click(screen.getByTestId("submit"));
    await waitFor(() => {
      expect(screen.getByTestId("second-step")).toBeTruthy();
    });

    fireEvent.change(screen.getByLabelText("รหัสจากแอป"), { target: { value: "000000" } });
    fireEvent.click(screen.getByTestId("submit-second-step"));

    await waitFor(() => {
      expect(screen.getByTestId("refusal").textContent).toContain("รหัสยืนยันไม่ถูกต้อง");
    });
    // **ยังอยู่ที่ขั้นที่สอง** — ลองใหม่ได้โดยไม่ต้องกรอกรหัสผ่านอีก (V-24.1)
    expect(screen.getByTestId("second-step")).toBeTruthy();
  });
});
