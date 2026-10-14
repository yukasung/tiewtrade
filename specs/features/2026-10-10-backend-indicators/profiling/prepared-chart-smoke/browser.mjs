// Explicit local smoke only; uses the isolated capacity fixture account.
import { createRequire } from 'node:module';
import { writeFileSync } from 'node:fs';
import { performance } from 'node:perf_hooks';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
const require = createRequire(new URL('../../../../../frontend/package.json', import.meta.url));
const { chromium } = require('playwright');
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
await page.addInitScript(() => {
  window.smokeResponses = [];
  const original = window.fetch;
  window.fetch = async (...args) => {
    const start = performance.now();
    const response = await original(...args);
    if (String(args[0]).includes('/chart/history') && response.ok) {
      response.clone().json().then(body => window.smokeResponses.push({
        start, end: performance.now(), body,
      })).catch(() => {});
    }
    return response;
  };
});
const errors = [], results = [];
const http = [];
page.on('response', response => {
  if (response.url().includes('/api/')) http.push({ path: new URL(response.url()).pathname, status: response.status() });
});
page.on('pageerror', error => errors.push(error.message));
try {
  await page.goto('http://localhost:5174/');
  await page.locator('input[type=email]').fill(process.env.SMOKE_EMAIL);
  await page.locator('input[type=password]').fill('capacity fixture password only');
  const chart = page.getByTestId('candlestick-chart');
  async function measure(label, timeframe, action) {
    console.log('start', label);
    const start = performance.now();
    const pageStart = await page.evaluate(() => performance.now());
    let requestMs;
    const observer = request => {
      if (request.url().includes('/chart/history') && request.url().includes(`timeframe=${timeframe}`)) {
        requestMs ??= performance.now() - start;
      }
    };
    page.on('request', observer);
    try {
      await action();
      await page.waitForFunction(({ timeframe, pageStart }) => window.smokeResponses.some(r =>
        r.start >= pageStart && r.body.timeframe === timeframe), { timeframe, pageStart }, { timeout: 45000, polling: 50 });
      const captured = await page.evaluate(({ timeframe, pageStart }) => window.smokeResponses.find(r =>
        r.start >= pageStart && r.body.timeframe === timeframe), { timeframe, pageStart });
      const body = captured.body;
      const bodyMs = captured.end - pageStart;
      console.log('body', label, body.candles?.length);
      const point = body.rows.at(-1), candle = body.candles.at(-1);
      await page.waitForFunction(({ close, ema }) => {
        const selection = document.querySelector('.chart-selection');
        const values = [...(selection?.querySelectorAll('dd') ?? [])].map(e => e.textContent.replaceAll(',', ''));
        return values.some(v => v.includes(close)) && (ema == null || values.some(v => v.includes(ema)));
      }, { close: candle.close, ema: point.values.ema20.value }, { timeout: 10000, polling: 100 });
      console.log('values', label);
      await page.waitForTimeout(100);
      const displayMs = performance.now() - start;
      const pixels = await chart.locator('canvas').evaluateAll(canvases => canvases.reduce((sum, canvas) => {
        const context = canvas.getContext('2d');
        if (!context) return sum;
        const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
        for (let i = 0; i < pixels.length; i += 4) {
          const r = pixels[i], g = pixels[i+1], b = pixels[i+2], a = pixels[i+3];
          if (a && ((g > r * 1.4 && g > b * 1.1) || (r > g * 1.4 && r > b * 1.2))) sum++;
        }
        return sum;
      }, 0));
      if (!pixels || body.timeframe !== timeframe || !body.generation_id) throw new Error('CHART_DATA_OR_PAINT_MISMATCH');
      console.log('pixels', label, pixels);
      results.push({ label, timeframe, requestMs, bodyMs, displayMs, candlePixels: pixels,
        generation: body.generation_id, candles: body.candles.length, rows: body.rows.length,
        lastOpen: candle.open_at, close: candle.close, ema20: point.values.ema20.value });
      await page.screenshot({ path: new URL(`${label}.png`, import.meta.url).pathname.replace(/^\/(\w:)/, '$1'), timeout: 10000 });
    } finally { page.off('request', observer); }
  }
  await measure('initial-1h', '1h', () => page.getByTestId('submit').click());
  if (process.env.SMOKE_SOURCE_UPDATE === '1') {
    const before = await page.evaluate(() => performance.now());
    const request = page.waitForRequest(r => r.url().includes('/chart/history') && r.url().includes('timeframe=5m'));
    await chart.locator('select').nth(1).selectOption('5m');
    await request;
    const sql = "BEGIN; SELECT begin_indicator_source_write(); UPDATE market_candles SET close=CASE WHEN close=100.335 THEN 100.345 ELSE 100.335 END,fetch_started_at=clock_timestamp(),last_checked_at=clock_timestamp(),observed_at=clock_timestamp() WHERE source='primary_spot' AND base='BTC' AND quote='USDT' AND timeframe='5m' AND open_at=(SELECT max(open_at) FROM market_candles WHERE base='BTC' AND timeframe='5m' AND open_at<clock_timestamp()-interval '20 minutes'); COMMIT;";
    await promisify(execFile)('docker', ['exec', '-e', 'PGPASSWORD=dev_market_data', 'tiewtrade-f11-capacity-postgres',
      'psql', '-h', '127.0.0.1', '-U', 'tiewtrade_market_data', '-d', 'tiewtrade', '-v', 'ON_ERROR_STOP=1', '-c', sql]);
    await page.waitForFunction(before => window.smokeResponses.some(r => r.start >= before && r.body.timeframe === '5m'), before, { timeout: 10000, polling: 100 });
    const captured = await page.evaluate(before => window.smokeResponses.find(r => r.start >= before && r.body.timeframe === '5m'), before);
    const proof = await page.evaluate(async proof => {
      const csrf = document.cookie.split('; ').find(c => c.startsWith('tiewtrade_csrf=')).split('=').slice(1).join('=');
      const response = await fetch('/api/market-data/chart/verify', { method: 'POST', headers: {
        'Content-Type': 'application/json', 'X-CSRF-Token': decodeURIComponent(csrf),
      }, body: JSON.stringify({ display_proof: proof }) });
      return { http: response.status, body: await response.json() };
    }, captured.body.display_proof);
    results.push({ label: 'source-proof', ...proof });
    if (proof.http !== 200 || !['CHANGED', 'UNVERIFIABLE'].includes(proof.body.status)) throw new Error('SOURCE_PROOF_NOT_INVALIDATED');
    await page.waitForFunction(() => ![...document.querySelectorAll('.chart-selection dt')].some(e => e.textContent === 'EMA20'), null, { timeout: 20000, polling: 100 });
    results.push({ label: 'source-update', proofStatus: proof.body.status, indicatorsHidden: true,
      note: 'Write triggered after request start; completion ordering is not a transaction barrier test.' });
  } else {
  await measure('switch-1m', '1m', () => chart.locator('select').nth(1).selectOption('1m'));
  await measure('return-1h', '1h', () => chart.locator('select').nth(1).selectOption('1h'));
  await measure('rapid-final-1m', '1m', async () => {
    await chart.locator('select').nth(1).selectOption('5m');
    await chart.locator('select').nth(1).selectOption('1m');
  });
  }
} catch (error) {
  errors.push(error.message);
  errors.push((await page.locator('body').innerText()).slice(-1800));
  process.exitCode = 1;
} finally {
  writeFileSync(new URL(process.env.SMOKE_SOURCE_UPDATE === '1' ? 'source-update-results.json' : 'browser-results.json', import.meta.url), JSON.stringify({ results, errors, http }, null, 2));
  console.log(JSON.stringify({ results, errors }));
  await browser.close();
}
