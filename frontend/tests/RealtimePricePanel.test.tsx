import { act, cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { realtimePriceI18n } from "../src/realtimePriceMessages";
import { onlineManager } from "@tanstack/react-query";
import { AccountSession } from "../src/AccountSession";
import { RealtimePricePanel } from "../src/RealtimePricePanel";
import { snapshot } from "./priceFixture";
class Socket {
    static all: Socket[] = [];
    onopen: (() => void) | null = null;
    onclose: ((event: {
        code: number;
    }) => void) | null = null;
    onerror: (() => void) | null = null;
    onmessage: ((event: {
        data: string;
    }) => void) | null = null;
    close = vi.fn();
    constructor() { Socket.all.push(this); }
    push(body = snapshot()) { this.onmessage?.({ data: JSON.stringify(body) }); }
}
afterEach(() => { cleanup(); onlineManager.setOnline(true); vi.unstubAllGlobals(); vi.useRealTimers(); Socket.all = []; });
function mount(onExpired = vi.fn(), get: Promise<Response> = Promise.resolve(new Response(JSON.stringify(snapshot())))) {
    vi.stubGlobal("WebSocket", Socket);
    vi.stubGlobal("fetch", vi.fn(() => get));
    return render(<AccountSession identity={{ user_id: "one", totp_enabled: false }} onExpired={onExpired}><RealtimePricePanel /></AccountSession>);
}
it("reports readiness only at server reference, preserves exact decimals and trade time", async () => {
    mount();
    await screen.findAllByText("พร้อม ณ เวลาที่ตรวจ");
    expect(screen.getAllByText("12.34000000 USDT")).toHaveLength(5);
    expect(document.querySelectorAll("time[datetime]").length).toBe(6);
});
it("late GET cannot overwrite stream and offline warns without changing snapshot", async () => {
    let resolve!: (value: Response) => void;
    mount(vi.fn(), new Promise(r => { resolve = r; }));
    await act(() => Promise.resolve(Socket.all[0]!.push(snapshot("2", "2026-10-07T00:00:02Z"))));
    await act(() => Promise.resolve(resolve(new Response(JSON.stringify(snapshot())))));
    void act(() => window.dispatchEvent(new Event("offline")));
    expect(screen.getByText(/การเชื่อมต่อขาด/)).toBeTruthy();
    expect(screen.getAllByText("พร้อม ณ เวลาที่ตรวจ")).toHaveLength(5);
    expect(Socket.all[0]!.close).toHaveBeenCalled();
});
it("reconnect awaits full snapshot and rejects callbacks from old transport", async () => {
    vi.useFakeTimers();
    mount();
    await act(() => Promise.resolve());
    const old = Socket.all[0]!;
    act(() => old.onclose?.({ code: 1006 }));
    void act(() => vi.advanceTimersByTime(2000));
    const next = Socket.all.at(-1)!;
    act(() => next.onopen?.());
    expect(screen.getByText(/รอสถานะใหม่/)).toBeTruthy();
    act(() => old.push(snapshot("99", "2026-10-07T00:00:09Z")));
    expect(screen.getByText(/รอสถานะใหม่/)).toBeTruthy();
    act(() => next.push(snapshot("2", "2026-10-07T00:00:02Z")));
    expect(screen.queryByText(/รอสถานะใหม่/)).toBeNull();
});
it("session 4401 uses existing expiry flow and cleanup closes socket", async () => {
    const expired = vi.fn();
    const view = mount(expired);
    await act(() => Promise.resolve());
    await act(() => Promise.resolve(Socket.all[0]!.onclose?.({ code: 4401 })));
    expect(expired).toHaveBeenCalledOnce();
    view.unmount();
    expect(Socket.all[0]!.close).toHaveBeenCalled();
});
it("observed resume invalidates transport; wall clock alone does not certify readiness", async () => {
    mount();
    await screen.findAllByText("พร้อม ณ เวลาที่ตรวจ");
    const old = Socket.all[0]!;
    void act(() => window.dispatchEvent(new Event("pageshow")));
    expect(screen.getByText(/รอสถานะใหม่/)).toBeTruthy();
    expect(old.close).toHaveBeenCalled();
});
it("heartbeat detection warns immediately and does not infer a market outage", async () => {
    vi.useFakeTimers();
    mount();
    await act(() => Promise.resolve());
    void act(() => Socket.all[0]!.push());
    void act(() => vi.advanceTimersByTime(3001));
    expect(screen.getByText(/การเชื่อมต่อขาด/)).toBeTruthy();
    expect(screen.queryByText(/ครบ 60 วินาที/)).toBeNull();
    expect(screen.getAllByText("พร้อม ณ เวลาที่ตรวจ")).toHaveLength(5);
});
it("market alert remains visible beside delivery failure and is not cleared by opening", async () => {
    mount();
    await act(() => Promise.resolve());
    const body = snapshot("2", "2026-10-07T00:00:02Z");
    body.rows[0]!.alert_due = true;
    void act(() => Socket.all[0]!.push(body));
    void act(() => Socket.all[0]!.onclose?.({ code: 1006 }));
    expect(screen.getByText(/ครบ 60 วินาที/)).toBeTruthy();
    expect(screen.getByText(/การเชื่อมต่อขาด/)).toBeTruthy();
});
it("identity replacement prevents late old socket and GET callbacks entering new cache", async () => {
    let release!: (response: Response) => void;
    const view = mount(vi.fn(), new Promise(r => { release = r; }));
    const old = Socket.all[0]!;
    view.rerender(<AccountSession identity={{ user_id: "two", totp_enabled: false }}><RealtimePricePanel /></AccountSession>);
    void act(() => old.push(snapshot("99", "2026-10-07T00:00:09Z")));
    expect(screen.queryByText("12.34000000 USDT")).toBeNull();
    await act(() => Promise.resolve(release(new Response(JSON.stringify(snapshot())))));
    expect(old.close).toHaveBeenCalled();
});
it("a late failed GET cannot demote a valid newer socket delivery",async()=>{
 let reject!: (error:Error)=>void;
 mount(vi.fn(),new Promise((_resolve,r)=>{reject=r;}));
 void act(()=>Socket.all[0]!.push());
 await act(()=>Promise.resolve(reject(new Error("unsafe raw error"))));
 expect(screen.getByRole("status").textContent).toBe("เชื่อมต่อการส่งข้อมูลแล้ว");
});
it("invalid schema warns and preserves last valid snapshot",async()=>{
 mount(); await screen.findAllByText("พร้อม ณ เวลาที่ตรวจ");
 void act(()=>Socket.all[0]!.onmessage?.({data:'{"schema_version":9,"secret":"never-render"}'}));
 expect(screen.getByText(/การเชื่อมต่อขาด/)).toBeTruthy();
 expect(screen.getAllByText("12.34000000 USDT")).toHaveLength(5);
 expect(screen.queryByText(/never-render/)).toBeNull();
});

it("English snapshot labels and reference timestamps remain observational across silent wall-clock jumps",async()=>{
 await realtimePriceI18n.changeLanguage("en");
 try {
  mount(); await screen.findAllByText("Ready at last check");
  const reference=document.querySelector("time")!.getAttribute("datetime");
  vi.spyOn(Date,"now").mockReturnValue(0);
  expect(document.querySelector("time")!.getAttribute("datetime")).toBe(reference);
  expect(screen.getAllByText("Ready at last check")).toHaveLength(5);
 } finally {vi.restoreAllMocks();await realtimePriceI18n.changeLanguage("th");}
});

it.each([
    ["READY", "ราคาผ่านเกณฑ์ ณ เวลาที่ตรวจ", "Price passed checks at the server check time"],
    ["STALE", "ราคาเกินอายุที่กำหนด", "Price exceeded the maximum age"],
    ["RECOVERING", "ยังยืนยันความพร้อมของราคาไม่ได้", "Price readiness is not yet confirmed"],
    ["MISSING", "ยังไม่มีราคาซื้อขาย", "No trade price is available"],
    ["VENUE_PROTOCOL", "ข้อมูลจากตลาดไม่เป็นไปตามรูปแบบที่กำหนด", "Exchange data did not match the expected protocol"],
    ["VENUE_RATE_LIMITED", "ตลาดจำกัดอัตราการเรียกใช้งาน", "Exchange rate limit reached"],
    ["VENUE_UNAVAILABLE", "ตลาดไม่พร้อมให้บริการ", "Exchange is unavailable"],
    ["VENUE_REJECTED", "ตลาดปฏิเสธคำขอรับข้อมูล", "Exchange rejected the market data request"],
    ["SUBSCRIPTION_ACK_TIMEOUT", "ตลาดไม่ยืนยันการสมัครรับข้อมูลภายในเวลาที่กำหนด", "Exchange subscription acknowledgement timed out"],
    ["ORDER_UNCONFIRMED", "ยังยืนยันลำดับข้อมูลซื้อขายไม่ได้", "Trade data ordering is not confirmed"],
    ["DELIVERY_UNAVAILABLE", "การส่งข้อมูลราคาไม่พร้อมใช้งาน", "Price delivery is unavailable"],
    ["FUTURE_REASON", "ไม่ทราบเหตุผลจาก server", "Unknown server reason"],
].flatMap(([code, th, en]) => [{ code, locale: "th", expected: th }, { code, locale: "en", expected: en }]))(
    "translates $code into $locale without exposing raw reason codes", async ({ code, locale, expected }) => {
        await realtimePriceI18n.changeLanguage(locale);
        try {
            const body = snapshot();
            body.rows[0]!.reason = code!;
            mount(vi.fn(), Promise.resolve(new Response(JSON.stringify(body))));
            const row = await screen.findByTestId("price-BTC");
            expect(within(row).getByText(expected!)).toBeTruthy();
            expect(screen.queryByText(code!)).toBeNull();
        } finally { await realtimePriceI18n.changeLanguage("th"); }
    },
);
