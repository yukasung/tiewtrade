# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: candlestick-chart.spec.ts >> live snapshots recover after disconnect without indicator reads
- Location: e2e/candlestick-chart.spec.ts:245:1

# Error details

```
Error: expect(received).toBe(expected) // Object.is equality

Expected: true
Received: false

Call Log:
- Timeout 5000ms exceeded while waiting on the predicate
```

# Page snapshot

```yaml
- main [ref=e3]:
  - generic [ref=e4]:
    - navigation "จัดการบัญชี" [ref=e5]:
      - strong [ref=e6]: TiewTrade
      - link "กราฟแท่งเทียน" [ref=e7] [cursor=pointer]:
        - /url: /chart
      - link "เทรด Paper" [ref=e10] [cursor=pointer]:
        - /url: /paper/trade
      - link "เทรด Live" [ref=e13] [cursor=pointer]:
        - /url: /live/trade
      - link "บัญชี" [ref=e16] [cursor=pointer]:
        - /url: /account
      - link "TOTP / 2FA" [ref=e19] [cursor=pointer]:
        - /url: /security
      - link "API key" [ref=e22] [cursor=pointer]:
        - /url: /api-keys
      - link "บัญชีเทรด" [ref=e25] [cursor=pointer]:
        - /url: /trading-account
    - generic [ref=e28]:
      - generic [ref=e29]:
        - button "เปิดเมนูบัญชี" [expanded] [ref=e30]
        - strong [ref=e32]: TiewTrade
        - generic [ref=e33]: จัดการบัญชี
        - generic "Kill switch" [ref=e34]:
          - generic [ref=e35]:
            - button "หยุดบอท Paper" [ref=e36]
            - status [ref=e37]: —
          - generic [ref=e38]:
            - button "หยุดบอท Live" [ref=e39]
            - status [ref=e40]: —
        - button "เปลี่ยนเป็นโหมดมืด" [ref=e41]
      - region "กราฟแท่งเทียน" [ref=e46]:
        - generic [ref=e47]:
          - generic [ref=e48]:
            - strong [ref=e49]: BTC/USDT
            - generic [ref=e50]: Binance TH Spot
          - generic [ref=e51]:
            - combobox "คู่เทรด" [ref=e54]:
              - option "BTC/USDT" [selected]
              - option "ETH/USDT"
            - combobox "Timeframe" [ref=e57]:
              - option "1m"
              - option "5m"
              - option "15m"
              - option "1h" [selected]
              - option "4h"
              - option "1d"
              - option "1w"
              - option "1M"
            - button "รีเซ็ตกราฟ" [ref=e58]
        - generic [ref=e59]:
          - alert [ref=e60]: อ่านข้อมูลสดไม่ทันเวลาที่กำหนด
          - button "ลองใหม่" [ref=e61]
          - generic [ref=e62]:
            - generic:
              - generic:
                - strong: BTC/USDT
                - generic: · 1h · Binance TH Spot
              - generic:
                - time: 7 พ.ย. 2569 20 นาฬิกา 00 นาที 00 วินาที GMT+7
                - generic: ·
                - generic: ยังไม่มีหลักฐานยืนยัน CLOSED
              - generic:
                - generic:
                  - text: O
                  - generic: 100.000000000000000001 USDT
                - generic:
                  - text: H
                  - generic: 101 USDT
                - generic:
                  - text: L
                  - generic: 99 USDT
                - generic:
                  - text: C
                  - generic: 100.75 USDT
                - generic:
                  - text: V
                  - generic: 1 BTC
            - table [ref=e65]:
              - row [ref=e66]:
                - cell
                - cell [ref=e67]:
                  - link "Charting by TradingView" [ref=e71] [cursor=pointer]:
                    - /url: https://www.tradingview.com/?utm_medium=lwc-link&utm_campaign=lwc-chart&utm_source=localhost/chart
                - cell [ref=e76]
              - row [ref=e80]:
                - cell
                - cell [ref=e81]
                - cell [ref=e85]
        - complementary [ref=e88]:
          - generic [ref=e89]:
            - heading "คำสั่งซื้อขาย" [level=3] [ref=e90]
            - generic [ref=e91]: ยังไม่เปิดใช้งาน
          - tablist "ฝั่งคำสั่ง" [ref=e92]:
            - tab "ซื้อ" [disabled] [selected] [ref=e93]
            - tab "ขาย" [disabled] [ref=e94]
          - generic [ref=e95]:
            - generic [ref=e96]: ประเภทคำสั่ง
            - combobox "ประเภทคำสั่ง" [disabled] [ref=e98]:
              - option "Limit" [selected]
            - generic [ref=e99]: ราคา
            - textbox "ราคา" [disabled] [ref=e100]:
              - /placeholder: USDT
            - generic [ref=e101]: จำนวน
            - textbox "จำนวน" [disabled] [ref=e102]:
              - /placeholder: BTC
            - generic [ref=e103]: ยอดรวม
            - textbox "ยอดรวม" [disabled] [ref=e104]:
              - /placeholder: USDT
          - button "ยังไม่เปิดใช้งาน" [disabled] [ref=e105]
          - paragraph [ref=e106]: พื้นที่นี้เตรียมไว้สำหรับงานส่งออเดอร์ในอนาคต และยังไม่รับข้อมูลหรือส่งคำสั่งซื้อขาย
        - region [ref=e107]:
          - generic [ref=e108]:
            - heading "รายการซื้อขาย" [level=3] [ref=e109]
            - tablist "ประเภทประวัติ" [ref=e110]:
              - tab "ออเดอร์ที่เปิดอยู่" [disabled] [selected] [ref=e111]
              - tab "ประวัติออเดอร์" [disabled] [ref=e112]
              - tab "ประวัติการเทรด" [disabled] [ref=e113]
          - table [ref=e115]:
            - rowgroup [ref=e116]:
              - row [ref=e117]:
                - columnheader "วันเวลา" [ref=e118]
                - columnheader "คู่เทรด" [ref=e119]
                - columnheader "ฝั่ง" [ref=e120]
                - columnheader "ราคา" [ref=e121]
                - columnheader "จำนวน" [ref=e122]
                - columnheader "สถานะ" [ref=e123]
            - rowgroup [ref=e124]:
              - row [ref=e125]:
                - cell "ยังไม่มีข้อมูลออเดอร์หรือการเทรดจากระบบ" [ref=e126]
```

# Test source

```ts
  1   | import { execFileSync, spawn } from "node:child_process";
  2   | import { mkdtempSync, writeFileSync, rmSync } from "node:fs";
  3   | import { tmpdir } from "node:os";
  4   | import { join } from "node:path";
  5   | import { randomUUID } from "node:crypto";
  6   | import { setTimeout, clearTimeout } from "node:timers";
  7   | import { expect, test, type Page } from "@playwright/test";
  8   | import { backendPython, e2eEnvironment } from "./helpers/environment";
  9   | import { PASSWORD } from "./helpers/totp";
  10  |
  11  | function fixture(action: string): void {
  12  |   execFileSync(backendPython,
  13  |     ["-X", "utf8", "../specs/features/2026-10-12-candlestick-chart/evidence/browser_fixture.py", action],
  14  |     { cwd: "../backend", env: e2eEnvironment(), stdio: "pipe" });
  15  | }
  16  |
  17  | async function registerAccount(page: Page): Promise<string> {
  18  |   const email = `chart-${randomUUID()}@example.com`;
  19  |   await page.goto("/");
  20  |   await page.getByTestId("switch-mode").click();
  21  |   await page.getByLabel("อีเมล").fill(email);
  22  |   await page.getByLabel("รหัสผ่าน", { exact: true }).fill(PASSWORD);
  23  |   await page.getByTestId("submit").click();
  24  |   await expect(page.getByTestId("candlestick-chart")).toBeVisible();
  25  |   return email;
  26  | }
  27  |
  28  | async function expectLiveStatus(page: Page, expected: string[]) {
  29  |   await expect.poll(async () => {
  30  |     const response = await page.request.get(
  31  |       "/api/market-data/chart/live?base=BTC&quote=USDT&timeframe=1h",
  32  |     );
  33  |     const body = await response.json() as { status?: string; detail?: string; reason?: string };
  34  |     if (process.env.CHART_E2E_DIAGNOSTICS === "1") {
  35  |       process.stdout.write(JSON.stringify({ probe: "live-status", http: response.status(),
  36  |         status: body.status, detail: body.detail, reason: body.reason }) + "\n");
  37  |     }
  38  |     if (response.status() !== 200) return false;
  39  |     return body.status !== undefined && expected.includes(body.status);
> 40  |   }).toBe(true);
      |      ^ Error: expect(received).toBe(expected) // Object.is equality
  41  | }
  42  |
  43  | function producer(script: string) {
  44  |   const directory = mkdtempSync(join(tmpdir(), "tiewtrade-chart-"));
  45  |   const control = join(directory, "control");
  46  |   const mode = (value: string) => writeFileSync(control, value);
  47  |   mode("healthy");
  48  |   const worker = spawn(backendPython,
  49  |     ["-B", script, "--control-file", control], { cwd: "../backend", env: e2eEnvironment(), stdio: "ignore" });
  50  |   const exited = new Promise<void>((resolve, reject) => {
  51  |     worker.once("exit", () => resolve());
  52  |     worker.once("error", () => reject(new Error("F12_BROWSER_PRODUCER_FAILED")));
  53  |   });
  54  |   let stopped = false;
  55  |   const stop = async () => {
  56  |     if (stopped) return;
  57  |     stopped = true;
  58  |     mode("stop");
  59  |     const timer = setTimeout(() => { worker.kill(); }, 3000);
  60  |     await exited;
  61  |     clearTimeout(timer);
  62  |     rmSync(directory, { recursive: true });
  63  |   };
  64  |   return { mode, stop };
  65  | }
  66  |
  67  | test.beforeEach(({ page }) => {
  68  |   fixture("seed");
  69  |   if (process.env.CHART_E2E_DIAGNOSTICS === "1") {
  70  |     page.on("pageerror", error => process.stdout.write(`browser_error: ${error.name}: ${error.message}\n`));
  71  |     page.on("response", response => {
  72  |       const path = new URL(response.url()).pathname;
  73  |       if (!path.includes("/market-data/chart/") && !path.includes("/market-data/candles")) return;
  74  |       void response.json().then((body: { detail?: string; status?: string; accepted?: boolean;
  75  |         refresh?: { required: boolean }; rows?: unknown[] }) => {
  76  |         process.stdout.write(JSON.stringify({ path, http: response.status(), detail: body.detail,
  77  |           status: body.status, accepted: body.accepted, refresh: body.refresh?.required,
  78  |           rows: body.rows?.length }) + "\n");
  79  |       }).catch(() => undefined);
  80  |     });
  81  |   }
  82  | });
  83  |
  84  | test("actual chart panes, exact values and keyboard selection", async ({ page }) => {
  85  |   const errors: string[] = [];
  86  |   const requests: string[] = [];
  87  |   page.on("pageerror", error => errors.push(error.message));
  88  |   page.on("request", request => requests.push(request.url()));
  89  |   page.on("response", response => {
  90  |     if (response.url().includes("/market-data/chart/history") && response.status() !== 200) {
  91  |       void response.json().then((body: { detail?: string }) => {
  92  |         process.stdout.write(`chart history refusal: ${response.status()} ${body.detail ?? "UNKNOWN"}\n`);
  93  |       }).catch(() => undefined);
  94  |     }
  95  |   });
  96  |   await registerAccount(page);
  97  |   const chart = page.getByTestId("candlestick-chart");
  98  |   await expect(chart).toBeVisible();
  99  |   await expect(chart.getByText("100.000000000000000001 USDT", { exact: true })).toBeVisible({ timeout: 60_000 });
  100 |   await expect(chart.locator("canvas").first()).toBeVisible();
  101 |   await expect(chart.getByRole("button", { name: "รีเซ็ตกราฟ" })).toBeEnabled();
  102 |   await expect(chart.getByLabel("MACD_LINE", { exact: true })).toHaveCount(0);
  103 |   for (const name of ["EMA20", "EMA50", "EMA200", "RSI14", "ATR14"]) {
  104 |     await expect(chart.getByText(name, { exact: true })).toHaveCount(0);
  105 |   }
  106 |   await expect(chart.getByRole("combobox", { name: "ภาษา", exact: true })).toHaveCount(0);
  107 |   await expect(chart.getByRole("heading", { name: "กราฟแท่งเทียน" })).toHaveCount(0);
  108 |   for (const width of [375, 768, 1440]) {
  109 |     await page.setViewportSize({ width, height: 1000 });
  110 |     await expect(chart.locator("canvas").first()).toBeVisible();
  111 |     await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= globalThis.innerWidth)).toBe(true);
  112 |   }
  113 |   const pair = chart.getByRole("combobox", { name: "คู่เทรด", exact: true });
  114 |   const pairStyle = await pair.evaluate(element => {
  115 |     const style = globalThis.getComputedStyle(element);
  116 |     return {
  117 |       appearance: style.appearance,
  118 |       borderColor: style.borderColor,
  119 |       borderRadius: style.borderRadius,
  120 |       height: style.height,
  121 |     };
  122 |   });
  123 |   expect(pairStyle).toEqual({
  124 |     appearance: "none",
  125 |     borderColor: "rgb(208, 213, 221)",
  126 |     borderRadius: "8px",
  127 |     height: "44px",
  128 |   });
  129 |   await pair.focus();
  130 |   await expect(pair).toHaveCSS("border-color", "rgb(156, 185, 255)");
  131 |   const disabled = chart.getByRole("button", { name: "ยังไม่เปิดใช้งาน", exact: true });
  132 |   await expect(disabled).toBeDisabled();
  133 |   await expect(disabled).toHaveCSS("cursor", "not-allowed");
  134 |   await expect(disabled).toHaveCSS("opacity", "0.5");
  135 |   await expect(disabled).toHaveCSS("border-radius", "8px");
  136 |   await expect(chart.getByRole("link", { name: "Charting by TradingView", exact: true })).toBeVisible();
  137 |   await page.screenshot({ path: "../specs/features/2026-10-12-candlestick-chart/evidence/chart-browser.png", fullPage: true });
  138 |   expect(errors).toEqual([]);
  139 |   expect(requests.some(url => /binance|\/(?:orders|trading-account\/use|indicators)(?:[/?#]|$)/i.test(url))).toBe(false);
  140 | });
```
