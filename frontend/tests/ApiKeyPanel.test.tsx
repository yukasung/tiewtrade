import { QueryClient } from "@tanstack/react-query";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AccountSession } from "../src/AccountSession";
import { ApiKeyPanel } from "../src/ApiKeyPanel";
import { TradingAccountPanel } from "../src/TradingAccountPanel";
import { retryApiKey } from "../src/apiKeys";
import type { components } from "../src/api-types";

type KeyView = components["schemas"]["KeyView"];
const IDENTITY = { user_id: "user-one", totp_enabled: true };
const KEY = "PUBLIC-KEY-MUST-NOT-STAY";
const SECRET = "SECRET-MUST-NOT-STAY";

const mutations = [
  { action: "add", message: "เพิ่ม key แล้ว กำลังรอตรวจ" },
  { action: "retry", message: "ส่งคำขอตรวจใหม่แล้ว" },
  { action: "delete", message: "ลบ key แล้ว" },
] as const;

function mutateKey(action: typeof mutations[number]["action"]): void {
  if (action === "add") {
    fill();
    fireEvent.click(screen.getByRole("button", { name: "เพิ่ม key" }));
  } else if (action === "retry") {
    fireEvent.click(screen.getByRole("button", { name: "ลองใหม่" }));
  } else {
    fireEvent.click(screen.getByRole("button", { name: "ลบ key" }));
    fireEvent.click(screen.getByRole("button", { name: "ยืนยันลบ" }));
  }
}

it.each(mutations.flatMap((mutation) =>
  ["api-keys", "trading-account"].map((failedQuery) => ({ ...mutation, failedQuery })),
))("$action suppresses success feedback when $failedQuery refetch fails", async ({ action, message, failedQuery }) => {
  let changed = false;
  let fail = true;
  const fetcher = vi.fn((url: string, init?: RequestInit) => {
    if (init?.method === "POST" || init?.method === "DELETE") {
      changed = true;
      return Promise.resolve(response({ id: "key-one", status: "PENDING" },
        action === "delete" ? 204 : action === "retry" ? 202 : 201));
    }
    if (changed && fail && url.endsWith(failedQuery)) {
      return Promise.reject(new Error(SECRET));
    }
    const rows = changed ? action === "delete" ? [] : [row("PENDING")] :
      action === "add" ? [] : [row("UNVERIFIABLE")];
    return Promise.resolve(response(url.endsWith("api-keys") ? rows : {
      use: null, key: rows[0] ?? null, may_trade: false, may_change_use: false,
    }));
  });
  vi.stubGlobal("fetch", fetcher);
  render(
    <AccountSession identity={IDENTITY}>
      <ApiKeyPanel identity={IDENTITY} />
      <TradingAccountPanel identity={IDENTITY} />
    </AccountSession>,
  );
  await screen.findByText("ยังไม่ได้เลือกประเภทการใช้งาน");
  mutateKey(action);
  await waitFor(() => expect(changed).toBe(true));
  await screen.findAllByRole("alert");
  expect(screen.queryByText(message)).toBeNull();
  expect(document.body.textContent).not.toContain(SECRET);
  if (action === "add") assertCleared();
  expect(fetcher.mock.calls.filter(([, init]) => init?.method === "POST" || init?.method === "DELETE")).toHaveLength(1);
  fail = false;
  fireEvent.click(screen.getByRole("button", { name: "ดึงรายการใหม่" }));
  await waitFor(() => expect(screen.queryAllByRole("alert")).toHaveLength(0));
  expect(fetcher.mock.calls.filter(([, init]) => init?.method === "POST" || init?.method === "DELETE")).toHaveLength(1);
});

it.each(mutations)("$action waits for a delayed account refetch before showing success", async ({ action, message }) => {
  let changed = false;
  let finish!: (value: Response) => void;
  const rows = () => changed ? action === "delete" ? [] : [row("PENDING")] :
    action === "add" ? [] : [row("UNVERIFIABLE")];
  vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => {
    if (init?.method === "POST" || init?.method === "DELETE") {
      changed = true;
      return Promise.resolve(response({ id: "key-one", status: "PENDING" },
        action === "delete" ? 204 : action === "retry" ? 202 : 201));
    }
    if (changed && url.endsWith("trading-account")) {
      return new Promise<Response>((resolve) => { finish = resolve; });
    }
    return Promise.resolve(response(url.endsWith("api-keys") ? rows() : {
      use: null, key: rows()[0] ?? null, may_trade: false, may_change_use: false,
    }));
  }));
  render(
    <AccountSession identity={IDENTITY}>
      <ApiKeyPanel identity={IDENTITY} />
      <TradingAccountPanel identity={IDENTITY} />
    </AccountSession>,
  );
  await screen.findByText("ยังไม่ได้เลือกประเภทการใช้งาน");
  mutateKey(action);
  await waitFor(() => expect(finish).toBeTypeOf("function"));
  expect(screen.queryByText(message)).toBeNull();
  await act(async () => {
    finish(response({ use: null, key: rows()[0] ?? null, may_trade: false, may_change_use: false }));
    await Promise.resolve();
  });
  await screen.findByText(message);
});

function row(status: string, extra: Partial<KeyView> = {}): KeyView {
  return {
    id: "key-one",
    label: "กระเป๋าหลัก",
    public_tail: "ABCD",
    status,
    created_at: "2026-10-06T10:00:00Z",
    may_retry: status === "UNVERIFIABLE",
    ...extra,
  };
}

function response(
  body: unknown,
  status = 200,
  headers: HeadersInit = {},
): Response {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers,
  });
}

function mount(
  rows: KeyView[] = [],
  post?: (init: RequestInit) => Promise<Response>,
) {
  const fetcher = vi.fn((url: string, init?: RequestInit) => {
    if (init?.method === "POST" && url === "/api/api-keys") {
      return (
        post?.(init) ??
        Promise.resolve(response({ id: "new-key", status: "PENDING" }, 201))
      );
    }
    if ((init?.method ?? "GET") === "GET" && url === "/api/api-keys") {
      return Promise.resolve(response(rows));
    }
    if (init?.method === "DELETE") return Promise.resolve(response(null, 204));
    if (url.endsWith("/retry"))
      return Promise.resolve(
        response({ id: "key-one", status: "UNVERIFIABLE" }, 202),
      );
    throw new Error(`Unexpected request: ${url}`);
  });
  vi.stubGlobal("fetch", fetcher);
  render(
    <AccountSession identity={IDENTITY}>
      <ApiKeyPanel identity={IDENTITY} />
    </AccountSession>,
  );
  return fetcher;
}

function fill(): void {
  fireEvent.change(screen.getByLabelText("ชื่อ key"), {
    target: { value: "ใหม่" },
  });
  fireEvent.change(screen.getByLabelText("API key", { selector: "input" }), {
    target: { value: KEY },
  });
  fireEvent.change(screen.getByLabelText("API secret"), {
    target: { value: SECRET },
  });
  fireEvent.change(screen.getByLabelText("รหัส TOTP สำหรับเพิ่ม key"), {
    target: { value: "123456" },
  });
}

function assertCleared(): void {
  for (const label of ["API key", "API secret", "รหัส TOTP สำหรับเพิ่ม key"]) {
    const input = screen.queryByLabelText<HTMLInputElement>(label, {
      selector: "input",
    });
    expect(input?.value ?? "").toBe("");
  }
  expect(window.localStorage.length).toBe(0);
  expect(window.sessionStorage.length).toBe(0);
}

beforeEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  document.cookie = "tiewtrade_csrf=csrf-test; path=/";
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("หน้าจัดการ API key", () => {
  it("Retry-After แบบ HTTP-date ผ่าน adapter เป็นเวลา UTC ที่ตรงกัน", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          response({ detail: SECRET }, 429, {
            "Retry-After": "Wed, 07 Oct 2026 12:00:00 GMT",
          }),
        ),
      ),
    );
    await expect(retryApiKey("key-one")).rejects.toMatchObject({
      status: 429,
      retryAt: "2026-10-07T12:00:00.000Z",
      message: "API_KEY_REQUEST_FAILED",
    });
  });
  it("การปฏิเสธที่ไม่ทราบสาเหตุบอกให้ลองเองโดยไม่สัญญาว่าจะตรวจอัตโนมัติ", async () => {
    mount([row("UNVERIFIABLE", { failure_code: "VENUE_REJECTED" })]);
    await screen.findByText(/ระงับการตรวจอัตโนมัติ/);
    expect(screen.queryByText(/ระบบจะตรวจใหม่อัตโนมัติ/)).toBeNull();
    expect(
      screen.getByRole<HTMLButtonElement>("button", { name: "ลองใหม่" })
        .disabled,
    ).toBe(false);
  });
  it("แสดงคำเตือนถาวรและอธิบายการใช้รหัส TOTP ชุดใหม่", async () => {
    mount();
    expect(screen.getByRole("heading", { name: "API key" })).toBeTruthy();
    expect(screen.getByText(/Enable Spot Trading/)).toBeTruthy();
    expect(screen.getByText(/whitelist/)).toBeTruthy();
    expect(screen.getByText(/รหัสสำรองใช้แทนไม่ได้/)).toBeTruthy();
    expect(screen.getByText(/รอรหัสชุดใหม่/)).toBeTruthy();
    await screen.findByText(/ยังไม่มี API key/);
  });

  it("ส่ง CSRF/TOTP และล้างค่าทันทีโดยไม่ใส่ secret ใน mutation cache", async () => {
    const cache = vi.spyOn(QueryClient.prototype, "getMutationCache");
    let complete!: (answer: Response) => void;
    const fetcher = mount(
      [],
      () =>
        new Promise<Response>((resolve) => {
          complete = resolve;
        }),
    );
    await screen.findByText(/ยังไม่มี API key/);
    fill();
    fireEvent.click(screen.getByRole("button", { name: "เพิ่ม key" }));
    await waitFor(() => expect(complete).toBeTypeOf("function"));
    assertCleared();
    const sent = fetcher.mock.calls.find(
      ([, init]) => init?.method === "POST",
    )?.[1];
    expect(sent?.headers).toMatchObject({
      "X-CSRF-Token": "csrf-test",
      "X-TiewTrade-TOTP": "123456",
    });
    if (typeof sent?.body !== "string") throw new Error("คำขอไม่มี JSON body");
    expect(JSON.parse(sent.body)).toEqual({
      label: "ใหม่",
      key: KEY,
      secret: SECRET,
    });
    const states = cache.mock.results.flatMap((result) => {
      if (result.type !== "return") return [];
      const returned = result.value;
      return returned.getAll().map((entry) => entry.state);
    });
    expect(JSON.stringify(states)).not.toContain(SECRET);
    expect(JSON.stringify(states)).not.toContain(KEY);
    await act(async () => {
      complete(response({ id: "new-key", status: "PENDING" }, 201));
      await Promise.resolve();
    });
    await screen.findByText(/เพิ่ม key แล้ว/);
  });

  it.each([403, 409, 422, 500])(
    "คำตอบ %s ไม่เติม secret กลับและไม่แสดงรายละเอียดดิบ",
    async (status) => {
      mount([], () => Promise.resolve(response({ detail: SECRET }, status)));
      await screen.findByText(/ยังไม่มี API key/);
      fill();
      fireEvent.click(screen.getByRole("button", { name: "เพิ่ม key" }));
      await screen.findByRole("alert");
      assertCleared();
      expect(document.body.textContent).not.toContain(SECRET);
    },
  );

  it("เน็ตมีปัญหาก็ล้าง secret และบอกว่าต้องตรวจรายการก่อนเพิ่มซ้ำ", async () => {
    mount([], () => Promise.reject(new Error(SECRET)));
    await screen.findByText(/ยังไม่มี API key/);
    fill();
    fireEvent.click(screen.getByRole("button", { name: "เพิ่ม key" }));
    await screen.findByRole("alert");
    assertCleared();
    expect(document.body.textContent).not.toContain(SECRET);
    expect(screen.getByText(/ตรวจรายการก่อนเพิ่มซ้ำ/)).toBeTruthy();
  });

  it("แยกสี่สถานะและไม่ให้ลองใหม่เมื่อ server สั่งรอ", async () => {
    const fetcher = mount([
      row("PENDING", { id: "pending", label: "หนึ่ง" }),
      row("ACTIVE", { id: "active", label: "สอง" }),
      row("REJECTED", { id: "rejected", label: "สาม" }),
      row("UNVERIFIABLE", {
        may_retry: false,
        not_before: "2099-01-01T00:00:00Z",
      }),
    ]);
    for (const status of [
      "กำลังตรวจ",
      "ใช้งานได้",
      "ตรวจไม่ผ่าน",
      "ตรวจไม่ได้ ลองใหม่ได้",
    ]) {
      await screen.findByText(status);
    }
    expect(screen.getAllByText(/ABCD/)).toHaveLength(4);
    const retry = screen.getByRole<HTMLButtonElement>("button", {
      name: /ลองใหม่/,
    });
    expect(retry.disabled).toBe(true);
    fireEvent.click(retry);
    expect(fetcher.mock.calls.some(([url]) => url.endsWith("/retry"))).toBe(
      false,
    );
  });

  it("ลองใหม่ไม่ส่ง TOTP และลบได้เมื่อยืนยันเท่านั้น", async () => {
    const fetcher = mount([row("UNVERIFIABLE")]);
    fireEvent.click(await screen.findByRole("button", { name: "ลองใหม่" }));
    await screen.findByText(/ส่งคำขอตรวจใหม่แล้ว/);
    const retry = fetcher.mock.calls.find(([url]) =>
      url.endsWith("/retry"),
    )?.[1];
    expect(retry?.headers).toMatchObject({ "X-CSRF-Token": "csrf-test" });
    expect(retry?.headers).not.toHaveProperty("X-TiewTrade-TOTP");
    fireEvent.click(screen.getByRole("button", { name: "ลบ key" }));
    const confirmation = screen.getByRole("group", { name: "ยืนยันการลบ key" });
    expect(
      fetcher.mock.calls.some(([, init]) => init?.method === "DELETE"),
    ).toBe(false);
    fireEvent.click(
      within(confirmation).getByRole("button", { name: "ยืนยันลบ" }),
    );
    await screen.findByText(/ลบ key แล้ว/);
    expect(
      fetcher.mock.calls.some(([, init]) => init?.method === "DELETE"),
    ).toBe(true);
  });

  it("บอกทางไปเปิด TOTP และไม่แสดงฟอร์มเพิ่ม key เมื่อยังไม่เปิด", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(response([]))),
    );
    render(
      <AccountSession identity={{ ...IDENTITY, totp_enabled: false }}>
        <ApiKeyPanel identity={{ ...IDENTITY, totp_enabled: false }} />
      </AccountSession>,
    );
    expect(screen.queryByLabelText("API secret")).toBeNull();
    expect(
      screen
        .getByRole("link", { name: /เปิดการยืนยันสองชั้น/ })
        .getAttribute("href"),
    ).toBe("/security");
  });

  it("poll เปลี่ยนสถานะเองและหยุดเมื่อออกจากหน้าจอ", async () => {
    vi.useFakeTimers();
    let calls = 0;
    const fetcher = vi.fn(() =>
      Promise.resolve(response([row(calls++ === 0 ? "PENDING" : "ACTIVE")])),
    );
    vi.stubGlobal("fetch", fetcher);
    const view = render(
      <AccountSession identity={IDENTITY}>
        <ApiKeyPanel identity={IDENTITY} />
      </AccountSession>,
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(screen.getByText("กำลังตรวจ")).toBeTruthy();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(screen.getByText("ใช้งานได้")).toBeTruthy();
    view.unmount();
    const before = calls;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10000);
    });
    expect(calls).toBe(before);
  });

  it("401 ไม่แสดงรายการที่ค้างจากบัญชีเดิม", async () => {
    mount([], () => Promise.resolve(response({ detail: SECRET }, 401)));
    await screen.findByText(/ยังไม่มี API key/);
    fill();
    fireEvent.click(screen.getByRole("button", { name: "เพิ่ม key" }));
    await screen.findByRole("alert");
    expect(screen.getByText(/เข้าสู่ระบบใหม่/)).toBeTruthy();
    assertCleared();
  });

  it("429 แสดงเวลาจาก Retry-After และไม่ส่งคำขอซ้ำอัตโนมัติ", async () => {
    const fetcher = mount([], () =>
      Promise.resolve(
        response({ detail: SECRET }, 429, { "Retry-After": "60" }),
      ),
    );
    await screen.findByText(/ยังไม่มี API key/);
    fill();
    fireEvent.click(screen.getByRole("button", { name: "เพิ่ม key" }));
    await screen.findByText(/ลองได้อีกครั้งหลัง/);
    assertCleared();
    expect(
      fetcher.mock.calls.filter(([, init]) => init?.method === "POST"),
    ).toHaveLength(1);
  });

  it("แสดงว่าข้อมูลเก่าเมื่อดึงใหม่ล้มเหลวและปิดปุ่มลองใหม่", async () => {
    let fail = false;
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        fail
          ? Promise.reject(new Error(SECRET))
          : Promise.resolve(response([row("UNVERIFIABLE")])),
      ),
    );
    render(
      <AccountSession identity={IDENTITY}>
        <ApiKeyPanel identity={IDENTITY} />
      </AccountSession>,
    );
    await screen.findByText("ตรวจไม่ได้ ลองใหม่ได้");
    fail = true;
    fireEvent.click(screen.getByRole("button", { name: "ดึงรายการใหม่" }));
    await screen.findByText(/รายการที่แสดงอาจไม่ตรง/);
    expect(
      screen.getByRole<HTMLButtonElement>("button", { name: "ลองใหม่" })
        .disabled,
    ).toBe(true);
    expect(document.body.textContent).not.toContain(SECRET);
  });

  it("คำตอบที่มาช้าของบัญชีเก่าไม่โผล่ในบัญชีใหม่", async () => {
    let oldAnswer!: (answer: Response) => void;
    let calls = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        calls++ === 0
          ? new Promise<Response>((resolve) => {
              oldAnswer = resolve;
            })
          : Promise.resolve(response([row("ACTIVE", { label: "บัญชีใหม่" })])),
      ),
    );
    const view = render(
      <AccountSession identity={IDENTITY}>
        <ApiKeyPanel identity={IDENTITY} />
      </AccountSession>,
    );
    await waitFor(() => expect(oldAnswer).toBeTypeOf("function"));
    view.rerender(
      <AccountSession identity={{ ...IDENTITY, user_id: "user-two" }}>
        <ApiKeyPanel identity={{ ...IDENTITY, user_id: "user-two" }} />
      </AccountSession>,
    );
    await screen.findByText("บัญชีใหม่", { exact: false });
    await act(async () => {
      oldAnswer(response([row("ACTIVE", { label: "บัญชีเก่า" })]));
      await Promise.resolve();
    });
    expect(screen.queryByText("บัญชีเก่า", { exact: false })).toBeNull();
    expect(screen.getByText("บัญชีใหม่", { exact: false })).toBeTruthy();
  });

  it("คำยืนยันลบที่เปิดไว้ไม่ส่งคำขอเมื่อรายการกลายเป็นข้อมูลเก่า", async () => {
    let fail = false;
    const fetcher = vi.fn((url: string, init?: RequestInit) =>
      init?.method === "DELETE"
        ? Promise.resolve(response(null, 204))
        : fail
          ? Promise.reject(new Error("offline"))
          : Promise.resolve(response([row("ACTIVE")])),
    );
    vi.stubGlobal("fetch", fetcher);
    render(
      <AccountSession identity={IDENTITY}>
        <ApiKeyPanel identity={IDENTITY} />
      </AccountSession>,
    );
    fireEvent.click(await screen.findByRole("button", { name: "ลบ key" }));
    fail = true;
    fireEvent.click(screen.getByRole("button", { name: "ดึงรายการใหม่" }));
    await screen.findByText(/รายการที่แสดงอาจไม่ตรง/);
    const confirm = screen.getByRole<HTMLButtonElement>("button", {
      name: "ยืนยันลบ",
    });
    expect(confirm.disabled).toBe(true);
    fireEvent.click(confirm);
    expect(
      fetcher.mock.calls.some(([, init]) => init?.method === "DELETE"),
    ).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "ยกเลิก" }));
    expect(screen.queryByRole("group", { name: "ยืนยันการลบ key" })).toBeNull();
  });

  it.each(["-1", "999999999999999999999999"])(
    "Retry-After ผิดรูป %s ไม่ทำให้เสียสถานะ 429",
    async (header) => {
      mount([], () =>
        Promise.resolve(response({}, 429, { "Retry-After": header })),
      );
      await screen.findByText(/ยังไม่มี API key/);
      fill();
      fireEvent.click(screen.getByRole("button", { name: "เพิ่ม key" }));
      await screen.findByText(/คำขอถูกจำกัด กรุณารอ/);
      assertCleared();
    },
  );
});
it.each(["PENDING", "ACTIVE", "REJECTED", "UNVERIFIABLE"])(
  "one stored %s key blocks adding another",
  async (status) => {
    mount([row(status)]);
    await screen.findByRole("button", { name: "ลบ key" });
    expect(
      screen.getByText(
        "เก็บ API key ได้หนึ่งชุดต่อบัญชี ต้องลบชุดเดิมก่อนเพิ่มใหม่",
      ),
    ).toBeTruthy();
    expect(
      screen.getByRole<HTMLButtonElement>("button", { name: "เพิ่ม key" })
        .disabled,
    ).toBe(true);
  },
);
