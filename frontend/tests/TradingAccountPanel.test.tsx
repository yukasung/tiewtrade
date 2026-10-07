import {
  act,
  within,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { AccountSession } from "../src/AccountSession";
import { TradingAccountPanel } from "../src/TradingAccountPanel";
import { ApiKeyPanel } from "../src/ApiKeyPanel";
const identity = { user_id: "user-one", totp_enabled: true };
const key = {
  id: "key-one",
  label: "Primary",
  public_tail: "ABCD",
  status: "ACTIVE",
  created_at: "2026-10-07T00:00:00Z",
  may_retry: false,
};
const account = { use: null, key, may_trade: false, may_change_use: false };
function answer(body: unknown, status = 200) {
  return new Response(status === 204 ? null : JSON.stringify(body), { status });
}
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});
function mount(
  handler: (url: string, init?: RequestInit) => Promise<Response>,
) {
  document.cookie = "tiewtrade_csrf=csrf-test";
  const fetcher = vi.fn(handler);
  vi.stubGlobal("fetch", fetcher);
  render(
    <AccountSession identity={identity}>
      <TradingAccountPanel identity={identity} />
    </AccountSession>,
  );
  return fetcher;
}
function select(use = "MANUAL", code = "123456") {
  fireEvent.change(screen.getByLabelText("ประเภทการใช้งานบัญชี"), {
    target: { value: use },
  });
  fireEvent.change(screen.getByLabelText("รหัส TOTP สำหรับเลือกประเภท"), {
    target: { value: code },
  });
  fireEvent.click(screen.getByRole("button", { name: "เลือกประเภทการใช้งาน" }));
}
it("initial choice is empty and needs explicit selection with fresh TOTP", async () => {
  mount(() => Promise.resolve(answer(account)));
  await screen.findByText("ยังไม่ได้เลือกประเภทการใช้งาน");
  expect(
    screen.getByLabelText<HTMLSelectElement>("ประเภทการใช้งานบัญชี").value,
  ).toBe("");
  expect(
    screen.getByRole<HTMLButtonElement>("button", {
      name: "เลือกประเภทการใช้งาน",
    }).disabled,
  ).toBe(true);
  expect(screen.getByText("บัญชีนี้ยังใช้เทรดไม่ได้")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "เริ่มบอท" })).toBeNull();
  expect(screen.queryByLabelText("API secret")).toBeNull();
});
it.each(["MANUAL", "BOT"])(
  "selects %s with CSRF/TOTP and refetches server choice",
  async (use) => {
    let selected = false;
    const fetcher = mount((_url, init) => {
      if (init?.method === "POST") {
        selected = true;
        return Promise.resolve(answer({ ...account, use }, 201));
      }
      return Promise.resolve(
        answer({ ...account, use: selected ? use : null }),
      );
    });
    await screen.findByText("ยังไม่ได้เลือกประเภทการใช้งาน");
    select(use);
    await screen.findByText("เลือกประเภทการใช้งานแล้ว");
    await screen.findByText(use === "BOT" ? "บอท" : "เทรดมือ", { exact: true });
    expect(screen.queryByLabelText("รหัส TOTP สำหรับเลือกประเภท")).toBeNull();
    const request = fetcher.mock.calls.find(
      ([, init]) => init?.method === "POST",
    )?.[1];
    expect(request?.headers).toMatchObject({
      "X-CSRF-Token": "csrf-test",
      "X-TiewTrade-TOTP": "123456",
    });
    expect(
      JSON.parse(typeof request?.body === "string" ? request.body : "{}"),
    ).toEqual({ use });
    expect(
      screen.getByRole<HTMLButtonElement>("button", { name: "เปลี่ยนประเภท" })
        .disabled,
    ).toBe(true);
  },
);
it.each([
  null,
  { ...key, status: "PENDING" },
  { ...key, status: "REJECTED" },
  { ...key, status: "UNVERIFIABLE" },
])("cannot select without ACTIVE sole key %j", async (sole) => {
  mount(() => Promise.resolve(answer({ ...account, key: sole })));
  await screen.findByText("ยังไม่ได้เลือกประเภทการใช้งาน");
  expect(
    screen.queryByRole("button", { name: "เลือกประเภทการใช้งาน" }),
  ).toBeNull();
  expect(screen.getByText(/เพิ่ม API key แล้วรอผลตรวจ/)).toBeTruthy();
});
it("uncertain POST clears code, does not retry and keeps choice unconfirmed", async () => {
  const fetcher = mount((_url, init) =>
    init?.method === "POST"
      ? Promise.reject(new Error("RAW-SECRET"))
      : Promise.resolve(answer(account)),
  );
  await screen.findByText("ยังไม่ได้เลือกประเภทการใช้งาน");
  select();
  await screen.findByText(/ยังยืนยันผลคำขอไม่ได้/);
  expect(document.body.textContent).not.toContain("RAW-SECRET");
  expect(
    screen.getByLabelText<HTMLInputElement>("รหัส TOTP สำหรับเลือกประเภท")
      .value,
  ).toBe("");
  expect(
    fetcher.mock.calls.filter(([, init]) => init?.method === "POST"),
  ).toHaveLength(1);
  expect(screen.getByText("ยังไม่ได้เลือกประเภทการใช้งาน")).toBeTruthy();
});
it.each([
  [
    "TRADING_ACCOUNT_KEY_UNAVAILABLE",
    409,
    "API key ยังไม่พร้อม ดึงข้อมูลล่าสุดก่อนลองอีกครั้ง",
  ],
  [
    "TRADING_ACCOUNT_ACTIVITY_UNKNOWN",
    409,
    "ยังเปลี่ยนประเภทไม่ได้ เพราะยังไม่มีหลักฐานสถานะบอท ออเดอร์ และ position ครบ",
  ],
  ["RAW-SECRET", 403, "ยืนยัน TOTP ไม่ผ่าน หากใช้รหัสเดิมแล้วให้รอรหัสชุดใหม่"],
])("sanitizes and explains %s", async (detail, status, message) => {
  mount((_url, init) =>
    Promise.resolve(
      init?.method === "POST" ? answer({ detail }, status) : answer(account),
    ),
  );
  await screen.findByText("ยังไม่ได้เลือกประเภทการใช้งาน");
  select();
  await screen.findByText(message);
  expect(
    screen.getByLabelText<HTMLInputElement>("รหัส TOTP สำหรับเลือกประเภท")
      .value,
  ).toBe("");
  expect(document.body.textContent).not.toContain("RAW-SECRET");
});
it("loading/read failure does not invent an empty or disconnected account", async () => {
  let resolve!: (response: Response) => void;
  mount(
    () =>
      new Promise<Response>((done) => {
        resolve = done;
      }),
  );
  expect(screen.getByText("กำลังดึงข้อมูลบัญชี…")).toBeTruthy();
  expect(screen.queryByText("ยังไม่เชื่อมต่อ")).toBeNull();
  resolve(answer({ detail: "RAW-SECRET" }, 503));
  await screen.findByRole("alert");
  expect(screen.queryByText("ยังไม่ได้เลือกประเภทการใช้งาน")).toBeNull();
  expect(document.body.textContent).not.toContain("RAW-SECRET");
});
it("existing selection persists when sole key is deleted and both panels refetch", async () => {
  let deleted = false;
  const fetcher = vi.fn((url: string, init?: RequestInit) => {
    if (init?.method === "DELETE") {
      deleted = true;
      return Promise.resolve(answer(null, 204));
    }
    return Promise.resolve(
      answer(
        url.endsWith("api-keys")
          ? deleted
            ? []
            : [key]
          : { ...account, use: "BOT", key: deleted ? null : key },
      ),
    );
  });
  vi.stubGlobal("fetch", fetcher);
  render(
    <AccountSession identity={identity}>
      <ApiKeyPanel identity={identity} />
      <TradingAccountPanel identity={identity} />
    </AccountSession>,
  );
  await screen.findByText("บอท", { exact: true });
  fireEvent.click(screen.getByRole("button", { name: "ลบ key" }));
  fireEvent.click(screen.getByRole("button", { name: "ยืนยันลบ" }));
  await screen.findByText("ยังไม่เชื่อมต่อ");
  await screen.findByText(/ยังไม่มี API key/);
  expect(screen.getByText("บอท", { exact: true })).toBeTruthy();
  expect(screen.getByText("บัญชีนี้ยังใช้เทรดไม่ได้")).toBeTruthy();
});
it("DELETE followed by summary refetch failure clearly marks retained old data stale", async () => {
  let deleted = false;
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (init?.method === "DELETE") {
        deleted = true;
        return Promise.resolve(answer(null, 204));
      }
      if (url.endsWith("trading-account") && deleted)
        return Promise.reject(new Error("RAW-SECRET"));
      return Promise.resolve(
        answer(
          url.endsWith("api-keys")
            ? deleted
              ? []
              : [key]
            : { ...account, use: "MANUAL" },
        ),
      );
    }),
  );
  render(
    <AccountSession identity={identity}>
      <ApiKeyPanel identity={identity} />
      <TradingAccountPanel identity={identity} />
    </AccountSession>,
  );
  await screen.findByText("เทรดมือ", { exact: true });
  fireEvent.click(screen.getByRole("button", { name: "ลบ key" }));
  fireEvent.click(screen.getByRole("button", { name: "ยืนยันลบ" }));
  await screen.findByText(/ยังไม่มี API key/);
  await within(screen.getByTestId("trading-account-panel")).findByRole("alert");
  await within(screen.getByTestId("api-key-panel")).findByRole("alert");
  expect(screen.queryByText("ลบ key แล้ว")).toBeNull();
  expect(screen.queryByText("ยังไม่เชื่อมต่อ")).toBeNull();
  expect(screen.getByText("เทรดมือ", { exact: true })).toBeTruthy();
  expect(document.body.textContent).not.toContain("RAW-SECRET");
});
it("TOTP never enters mutation variables/query keys and mutation cache clears after settle", async () => {
  const { useQueryClient } = await import("@tanstack/react-query");
  let client: ReturnType<typeof useQueryClient> | undefined;
  function Capture() {
    client = useQueryClient();
    return null;
  }
  let resolve!: (response: Response) => void;
  vi.stubGlobal(
    "fetch",
    vi.fn((_url: string, init?: RequestInit) =>
      init?.method === "POST"
        ? new Promise<Response>((done) => {
            resolve = done;
          })
        : Promise.resolve(answer(account)),
    ),
  );
  render(
    <AccountSession identity={identity}>
      <Capture />
      <TradingAccountPanel identity={identity} />
    </AccountSession>,
  );
  await screen.findByText("ยังไม่ได้เลือกประเภทการใช้งาน");
  select("BOT", "987654");
  await waitFor(() => expect(resolve).toBeTypeOf("function"));
  expect(
    client?.getMutationCache().getAll()[0]?.state.variables,
  ).toBeUndefined();
  expect(
    JSON.stringify(
      client
        ?.getQueryCache()
        .getAll()
        .map((query) => query.queryKey),
    ),
  ).not.toContain("987654");
  expect(
    screen.getByLabelText<HTMLInputElement>("รหัส TOTP สำหรับเลือกประเภท")
      .value,
  ).toBe("");
  resolve(answer({ detail: "RAW-SECRET-987654" }, 500));
  await screen.findByText(/ยังยืนยันผลคำขอไม่ได้/);
  await waitFor(() =>
    expect(client?.getMutationCache().getAll()).toHaveLength(0),
  );
});
it("late old-user POST success never changes new-user summary, cache or feedback", async () => {
  const { useQueryClient } = await import("@tanstack/react-query");
  const clients: ReturnType<typeof useQueryClient>[] = [];
  function Capture() {
    const client = useQueryClient();
    if (!clients.includes(client)) clients.push(client);
    return null;
  }
  let old = true;
  let complete!: (response: Response) => void;
  const newAccount = {
    ...account,
    key: { ...key, id: "new-key", label: "New account key" },
  };
  const fetcher = vi.fn((_url: string, init?: RequestInit) =>
    init?.method === "POST"
      ? new Promise<Response>((resolve) => {
          complete = resolve;
        })
      : Promise.resolve(answer(old ? account : newAccount)),
  );
  vi.stubGlobal("fetch", fetcher);
  const panels = (who: typeof identity) => (
    <AccountSession identity={who}>
      <Capture />
      <TradingAccountPanel identity={who} />
    </AccountSession>
  );
  const view = render(panels(identity));
  await screen.findByText("ยังไม่ได้เลือกประเภทการใช้งาน");
  select("BOT");
  await waitFor(() => expect(complete).toBeTypeOf("function"));
  const mutation = clients[0]?.getMutationCache().getAll()[0];
  old = false;
  view.rerender(panels({ ...identity, user_id: "new-user" }));
  await screen.findByText(/New account key/);
  const reads = fetcher.mock.calls.filter(
    ([, init]) => init?.method === "GET",
  ).length;
  complete(answer({ ...account, use: "BOT" }, 201));
  await waitFor(() => expect(mutation?.state.status).toBe("success"));
  expect(screen.queryByText("เลือกประเภทการใช้งานแล้ว")).toBeNull();
  expect(clients[1]?.getQueryData(["trading-account", "new-user"])).toEqual(
    newAccount,
  );
  expect(clients[1]?.getMutationCache().getAll()).toHaveLength(0);
  expect(
    fetcher.mock.calls.filter(([, init]) => init?.method === "GET"),
  ).toHaveLength(reads);
});
it("POST followed by failed summary refetch never reports a confirmed selected state", async () => {
  let selected = false;
  mount((_url, init) => {
    if (init?.method === "POST") {
      selected = true;
      return Promise.resolve(answer({ ...account, use: "BOT" }, 201));
    }
    return selected
      ? Promise.reject(new Error("RAW-REFETCH"))
      : Promise.resolve(answer(account));
  });
  await screen.findByText("ยังไม่ได้เลือกประเภทการใช้งาน");
  select("BOT");
  await screen.findByRole("alert");
  expect(screen.queryByText("เลือกประเภทการใช้งานแล้ว")).toBeNull();
  expect(
    screen.getByRole<HTMLButtonElement>("button", {
      name: "เลือกประเภทการใช้งาน",
    }).disabled,
  ).toBe(true);
  expect(document.body.textContent).not.toContain("RAW-REFETCH");
});
it("adding sole key refetches the account summary through the shared client", async () => {
  let added = false;
  const pending = { ...key, status: "PENDING" };
  const fetcher = vi.fn((url: string, init?: RequestInit) => {
    if (init?.method === "POST") {
      added = true;
      return Promise.resolve(answer({ id: key.id, status: "PENDING" }, 201));
    }
    return Promise.resolve(
      answer(
        url.endsWith("api-keys")
          ? added
            ? [pending]
            : []
          : { ...account, key: added ? pending : null },
      ),
    );
  });
  vi.stubGlobal("fetch", fetcher);
  render(
    <AccountSession identity={identity}>
      <ApiKeyPanel identity={identity} />
      <TradingAccountPanel identity={identity} />
    </AccountSession>,
  );
  const panel = screen.getByTestId("trading-account-panel");
  await within(panel).findByText("ยังไม่เชื่อมต่อ");
  fireEvent.change(screen.getByLabelText("ชื่อ key"), {
    target: { value: key.label },
  });
  fireEvent.change(document.querySelector("#api-key-key")!, {
    target: { value: "SYNTHETIC-KEY" },
  });
  fireEvent.change(screen.getByLabelText("API secret"), {
    target: { value: "SYNTHETIC-SECRET" },
  });
  fireEvent.change(screen.getByLabelText("รหัส TOTP สำหรับเพิ่ม key"), {
    target: { value: "123456" },
  });
  fireEvent.click(screen.getByRole("button", { name: "เพิ่ม key" }));
  await within(panel).findByText("กำลังตรวจ");
  expect(within(panel).queryByText("ยังไม่เชื่อมต่อ")).toBeNull();
  expect(
    fetcher.mock.calls.filter(([url]) => url.endsWith("trading-account"))
      .length,
  ).toBeGreaterThan(1);
});
it("retrying a key refetches its new status in the account panel", async () => {
  let retried = false;
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        retried = true;
        return Promise.resolve(answer({ id: key.id, status: "PENDING" }, 202));
      }
      const current = {
        ...key,
        status: retried ? "PENDING" : "UNVERIFIABLE",
        may_retry: !retried,
      };
      return Promise.resolve(
        answer(
          url.endsWith("api-keys") ? [current] : { ...account, key: current },
        ),
      );
    }),
  );
  render(
    <AccountSession identity={identity}>
      <ApiKeyPanel identity={identity} />
      <TradingAccountPanel identity={identity} />
    </AccountSession>,
  );
  const panel = screen.getByTestId("trading-account-panel");
  await within(panel).findByText("ตรวจไม่ได้ ลองใหม่ได้");
  fireEvent.click(screen.getByRole("button", { name: "ลองใหม่" }));
  await within(panel).findByText("กำลังตรวจ");
});
it("key polling updates the sole account summary when worker verification completes", async () => {
  vi.useFakeTimers();
  let verified = false;
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      const current = { ...key, status: verified ? "ACTIVE" : "PENDING" };
      return Promise.resolve(
        answer(
          url.endsWith("api-keys") ? [current] : { ...account, key: current },
        ),
      );
    }),
  );
  render(
    <AccountSession identity={identity}>
      <ApiKeyPanel identity={identity} />
      <TradingAccountPanel identity={identity} />
    </AccountSession>,
  );
  await act(async () => {
    await vi.advanceTimersByTimeAsync(100);
  });
  const panel = screen.getByTestId("trading-account-panel");
  expect(within(panel).getByText("กำลังตรวจ")).toBeTruthy();
  expect(within(panel).queryByLabelText("ประเภทการใช้งานบัญชี")).toBeNull();
  verified = true;
  await act(async () => {
    await vi.advanceTimersByTimeAsync(5000);
  });
  expect(within(panel).getByText("ใช้งานได้")).toBeTruthy();
  expect(
    within(panel).getByLabelText<HTMLSelectElement>("ประเภทการใช้งานบัญชี")
      .value,
  ).toBe("");
});
it("ACTIVE key without TOTP points to setup instead of showing selection fields", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve(answer(account))),
  );
  render(
    <AccountSession identity={{ ...identity, totp_enabled: false }}>
      <TradingAccountPanel identity={{ ...identity, totp_enabled: false }} />
    </AccountSession>,
  );
  await screen.findByRole("link", {
    name: "เปิด TOTP ก่อนเลือกประเภทการใช้งาน",
  });
  expect(screen.queryByLabelText("รหัส TOTP สำหรับเลือกประเภท")).toBeNull();
});
