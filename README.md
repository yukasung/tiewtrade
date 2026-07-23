# TiewTrade

TiewTrade เป็นบอตซื้อขายระยะ Internal Alpha ที่พัฒนาแบบ Paper-first ปัจจุบัน
โครงการนี้รองรับการ replay Paper Spot แบบกำหนดผลแน่นอนสำหรับ Candle ที่ปิดสมบูรณ์ของ
BTCUSDT ช่วงเวลา 5 นาที

CLI สำหรับ replay ไม่เชื่อมต่อ Binance และไม่ส่งคำสั่ง Live

## การติดตั้ง

สร้างสภาพแวดล้อมเสมือน แล้วติดตั้งโครงการพร้อมส่วนพึ่งพาสำหรับการพัฒนา:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"
```

## การตรวจซ้ำด้วย fixture

เรียกใช้ deterministic Paper Spot replay จาก root ของโครงการ:

```bash
PYTHONPATH=src .venv/bin/python -m tiewtrade.paper_replay_main \
  tests/fixtures/btcusdt_5m_tracer.csv \
  --available-capital 1000 \
  --trading-capital-ratio 0.6 \
  --max-entries 4
```

ผลลัพธ์ JSON ที่คงที่คือ:

```json
{"accepted_candles":40,"closed_baskets":1,"current_entries":0,"realized_pnl":"13.84062222"}
```

## การตรวจสอบ

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q
.venv/bin/python -m ruff check src tests
.venv/bin/python -m ruff format --check src tests
.venv/bin/python -m mypy src
git diff --check
```
