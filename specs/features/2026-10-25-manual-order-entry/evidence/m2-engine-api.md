# M2 — Engine/API checkpoint

วันที่: 2026-10-25 · branch `feat/f16-manual-order-entry` · uncommitted working tree

## Implementation

- API เพิ่ม authenticated Paper snapshot/list/detail, strict NEW/CANCEL inbox admission,
  joined intake→command→order reads, same-key recovery และ unresolved discovery ทุก episode.
  แยก throttle NEW/CANCEL (20 tokens, refill 1/sec); replay ไม่เสีย quota ซ้ำ.
- Migration 0042 จำกัด engine ให้ SELECT account use ของ owner เท่านั้น, ให้ API อ่าน
  public execution readiness และเพิ่ม buckets; downgrade ปฏิเสธหากมี manual history.
- Bridge ใช้ shared wallet advisory lock + lease/token/revision fencing; transfer/result/audit
  และ F-15 command commit พร้อมกัน. รักษา admitted catalog revision เดิม; remove→re-add
  ไม่ทำให้ BUY กลับมาทำงาน. Reset ไม่ข้ามช่วง inbox→F-15 queue.
- Core manual policy ใช้ authoritative held/reserved กับ Money/Quantity, bounded SELL
  ลดความเสี่ยงได้ตาม account-use rule; bridge และ NEW execution recheck policy.
- Snapshot ใช้ repeatable read, เงิน/ปริมาณเป็น exact strings; unavailable เป็น null.
  Detail/list มี original/filled/remaining/reserved และ failure code จาก command.
- Production API และ worker คง policy=None; NEW ตอบ 503 ก่อนสร้าง executable request.
  Policy ที่ยอมรับคำสั่งมีเฉพาะ dependency injection ใน tests. ไม่มี Live executor/API-key path.
- OpenAPI และ frontend generated API types อัปเดตตาม generator; ยังไม่มี order UI ใน M2.

## Checks และผลจริง

Environment: isolated compose project `tiewtrade-f16`, PostgreSQL localhost:55432;
Redis สำหรับ API TestClient แยก localhost:56379. ใช้ roles จริงตาม README ผ่าน wrapper
`/tmp/tiewtrade-f16-run.py`; ไม่บันทึก secrets. ไม่มี Live order/network execution.

| Check | Result |
|---|---|
| `pytest tests/core/test_manual_trading.py tests/core/test_paper_matching.py tests/infra/manual_orders tests/infra/execution_market tests/infra/paper_wallet tests/api/test_manual_order_routes.py tests/api/test_route_policy.py tests/api/test_route_classification.py tests/gates/test_paper_isolation.py tests/services/api/test_manual_order_models.py -x` | **210 passed**, หยุดที่ legacy renewing-route allowlist: 1 failed / 76.62s; failure แก้ตามแถวถัดไป ไม่อ้างว่าคำสั่งนี้ผ่านทั้งชุด |
| Follow-up: overspend inbox regression + `test_route_policy.py test_route_classification.py test_paper_isolation.py test_manual_order_models.py` | **51 passed / 2.68s**; ครอบคลุมส่วนท้ายที่คำสั่งแรกยังไม่รันและ allowlists ที่แก้ |
| Policy หายระหว่าง transfer→execution | **1 passed** ในรอบ 1 passed/1 failed / 1.28s; อีก failure เป็น overspend test ที่เดิมคาดว่ามีสอง owner claims พร้อมกันได้ แก้ให้ตรวจ claim ที่ไม่สำเร็จแล้ว retry หลัง owner writer จบ ตาม protocol เดิม; overspend ผ่านในสองรอบถัดมา |
| Final follow-up: `test_market_order_crossing_levels_links_every_fill_once` สอง paths + inbox overspend | **3 passed / 2.83s**. Inbox และ internal baseline ใช้ 1100 USDT ได้ 10.5 BTC เงินเหลือ 8900, links=2; competing LIMIT reservations รวม 9000 จาก cash10000, อีก command reject `ORDER_INSUFFICIENT_FUNDS` |
| Crash/process kill ก่อน/หลัง bridge COMMIT + real TCP commit-ack loss | ทั้ง 3 tests อยู่ใน regression 210 passed; same request/command identity, rollback/replay ไม่สร้าง financial effect ซ้ำ |
| Ruff changed backend source/migrations/tests | Passed; final edited tests ตรวจซ้ำผ่าน |
| Strict mypy | Passed — 495 source files หลังแก้ final parity/concurrency tests |
| Import-linter | Passed — 7 contracts kept, 0 broken; 259 files |
| `npm run gen:api` + `npm run typecheck` | Passed; Node22 runtime, generated contract ตรง OpenAPI ปัจจุบัน |
| `git diff --check` | Passed |

ผล M1 ที่ dependencies ไม่เปลี่ยนยังใช้ต่อ. ไม่บวกรวมจำนวน tests ข้างบนเพราะมีส่วนซ้ำกัน.
Final follow-up เปลี่ยนเฉพาะ tests; backend runtime code เหมือน regression 210 passed.
คำสั่งแรกมี Starlette TestClient/httpx deprecation warning เดิม ไม่ใช่ financial failure.

Legacy migration test ปรับให้รู้จัก exact safety guards ของ revisions0040–0042 และตรวจ
version/RLS เดิมต่อ. Route tests ตรึง POST NEW/CANCEL เป็น explicit user actions ที่ต่ออายุ
session และตรึง CANCEL เป็น risk reducing; GET polling ไม่ต่ออายุ session.

เวลาข้างบนเป็น pytest elapsed ที่วัดจริง. ไม่ได้วัดช่วงอ่าน/เขียน/review แยกครบ;
ไม่แต่งเวลารวมและไม่รวมเวลาที่รันขนานกัน. Logs ของรอบหลัก/follow-up/parity อยู่ใน
`/tmp/f16-m2-{regression,followup,parity}.log` เฉพาะ environment นี้.

## Validation coverage และงานค้าง

- V-3/7/8/9/10: เพิ่ม bridge transfer, catalog continuity, audit rollback, claim replacement,
  reset barrier, subprocess crash และ commit-ack loss; UI journal/reload ยังรอ M3.
- V-6: core PAPER/LIVE policy parity (ไม่มี Live execution), BOT/unselected opening rejected,
  bounded-vs-oversized SELL และ missing policy ผ่าน; production policy integration รอ F-18.
- V-11: API owner-bound views, downstream rejection แม้ไม่มี order row และ exact
  reserved/available หลัง LIMIT/cancel ผ่าน; browser render/discovery recovery ยังรอ M3.
- V-12: multi-level MARKET financial outcome ผ่านทั้ง inbox และ internal F-15 baseline;
  overspend/concurrency และ cancel release ผ่าน. Existing partial/expiry/correction/recovery
  safety suite ผ่านใน regression; full browser variants ยังรอ M3.
- V-13: API input/CSRF/ownership/routing/throttle/Retry-After/replay/error sanitization,
  OpenAPI generation และ frontend typecheck ผ่านในขอบเขต backend.
- V-5/17: isolation gate และ production policy=None/readiness/503/no row ผ่าน;
  Live page/disabled UI/polling/lifecycle ยังรอ M3.
- V-1/2/3/4/5/6/7/8/9/10/11/12/13/17 รวมยัง **Partial** จนหลักฐานที่เกี่ยวข้องครบ.
  V-14/15/16 ยัง **Not Run**. ไม่ยก targeted checks เป็น candidate/full acceptance.
- M3: shared form, Paper/Live URLs, owner-bound query/cache/journal/discovery, i18n,
  template/accessibility/component/browser tests.
- M4: แจ้ง Ready for Code Review เมื่อ implementation ครบ feature, review/fix findings,
  final candidate full regression/build/static/generated/required CI ตามมาตรฐาน.
- V-18 **Pending Dependency — F-18**; V-20 **Pending Full Validation** release checkpoint.
- ยังไม่ commit/push/merge, ไม่ Completed และยังไม่พร้อม merge.
