# F-18 M3 — publication, financial replay, stop recovery — 2026-10-26

สถานะ: In Progress — ยังไม่ Ready for Code Review ของ feature / production admission ยังปิด

## ขอบเขตที่เพิ่ม

- 0045 public immutable full-price frames, proof/watermark, EXCLUSIVE publisher fence
  ก่อน feed locks และ SHARED financial fence; protocol/admission switches default false
- 0046 cancellation-only wallet revision ไม่รอ publication/risk cursor
- 0047 immutable source revision ของ F14 facts และ boundary sequence สำหรับ replay
  ตาม holdings ที่ถูกต้องในอดีต ไม่ใช้ holdings ปัจจุบันกับ price ก่อน fill
- 0048 owner SELECT policy ของ projection columns ที่ F16 grant ไว้แล้ว; scan hints
  ไม่ให้ API อ่าน F14 event/activity tables หรือ ENGINE_SCAN อ่าน limit/book/amounts
- 0049 stop request + breach/latch/audit atomic, bounded enrollment/progress,
  immutable per-target effects และ F15 cancel requests ที่ retry key เดิม
- 0050 lifecycle/result DB-clock cutoffs ทำให้ enrollment หลายรอบไม่พลาด targets
  ที่เปลี่ยนสถานะหลัง stop; 0051 command DB-clock cutoff กับ stop scan hints
- 0052 fence ครอบคลุม unconfigured wallet ด้วย; capital-only lifecycle ยังใช้ได้
  และ compatible proven SELL ใช้ boundary ได้โดยไม่สร้างเพดานอัตโนมัติ
- transaction-bound boundaries สำหรับ fills/corrections/F14 initialization/episode reset/
  setting/reset; source ไม่ครบคง unavailable/replay_pending โดยไม่ rollback bounded SELL
- chronological bounded monitor, owner concurrency4, DB rescan/freshness expiry,
  persistent 5-minute price-pause state และ read-time source/price/cursor checks
- loss reset บันทึก baseline cutoff/historical price proof พร้อม audit/result;
  เปลี่ยนเพดาน drain old-limit frames ก่อน ไม่ล้าง latch และ stale scope ไม่สร้าง marker
- pure matcher รับ scoped risk context และประเมินหลังแต่ละ fill ใน batch;
  เมื่อ fill แรกชนเพดานไม่ fill BUY ที่เหลือ และ unavailable ไม่ใช้ BUY liquidity
- stop consumer ใช้ F15 cancel/checkpoint/reservation facts; old stop cuts ไม่ถูก
  ยกเลิกด้วย loss reset; snapshot counts กับ effects pagination แยกกันตาม R4

## หลักฐานที่วัดได้ (targeted correctness environment เดิม)

ใช้ PostgreSQL16 isolated localhost55458, runtime roles/RLS จริง, 2CPU/2GiB
ไม่ใช่ release workload baseline; ไม่มี Live API/credentials/orders, ไม่มี workload
หรือ diagnostic ซ้อน ใช้ wrapper เดิมสำหรับ DB tests และ uv สำหรับ static checks

| ชุดตรวจ | ผลและขอบเขต |
|---|---|
| risk price journal + F10 realtime storage | **13 passed in9.51s** — rollback, old writer/GUC spoof, SH/EX ordering และ existing lease behavior |
| financial boundaries + F14 storage | **17 passed in3.10s** — atomic rollback, nested marker, fence and deferred finalization |
| risk monitor initial replay | **3 passed in1.21s** — transient breach/recovery, pre-fill vs post-fill holdings และ bounded replay |
| risk persistence + F13 storage/recovery | **62 passed in14.62s** ก่อน follow-up ด้าน matcher/lifecycle; affected changes ต้องตรวจอีกครั้งตามด้านล่าง |
| risk monitor follow-up | **6 passed in2.77s** — authoritative reset, immediate disconnect read, episode baseline/latch preservation |
| risk + F15 executions/worker/initialization | **82 passed,1 failed in44.72s**; failure คือ legacy downgrade test inventory ไม่รู้จัก F18 guard; ไม่ถือ run นี้ผ่านทั้งหมด |
| stop/pagination + fixed downgrade + route inventory | **24 passed in3.40s** — bounded pages/watermark/owner/mode, F15 cancel and one release; route GET non-renewing |
| core risk + matching + new per-fill regression | **97 passed in0.84s** — includes stopping remaining fills in same batch, unavailable BUY and proven SELL |
| risk persistence + F16 bridge after policy/stop-cut changes | **46 passed in12.64s** |
| boundary/stop/downgrade follow-up | **9 passed in4.01s** — includes unconfigured old writer rejection and compatible SELL |
| targeted strict mypy | ผ่าน18/24 affected source/test files ตาม invocation; ต้องตรวจ final affected set อีกครั้ง |

คำสั่ง DB tests: `python3 /tmp/tiewtrade-f18-run.py uv run pytest <paths> -o addopts= -q`
คำสั่ง pure tests: `uv run pytest tests/core/test_risk_matching.py tests/core/test_paper_matching.py tests/core/test_risk_limits.py -o addopts= -q`
เวลาเป็น elapsed ที่เครื่องมือวัด ไม่อ้างรวมเวลาที่ไม่ได้จับ

Development failures ที่แก้: SQL numeric-domain parameter inference (explicit casts),
fixture decimal string scale (assert exact Money), API columns มี grant แต่ขาด owner
RLS policy (เพิ่มเฉพาะ policy ไม่เพิ่ม financial columns), source reader ใช้ narrow
readiness function เดิม, test scheduler claim cancel แบบเจาะ owner แทนพึ่ง backlog
ของ DB ร่วม และเพิ่ม guard/head inventory ให้ downgrade test เดิมโดยไม่ลด FORCE RLS assertion

## งานค้าง ณ checkpoint M3 (historical)

รายการด้านล่างเป็นสถานะตอนบันทึก M3; ดู [M4](m4-ui-composition.md) และ
[M5](m5-final-candidate.md) สำหรับหลักฐานที่ทำต่อ ไม่ตีความว่า runtimeปัจจุบันยังใช้ policy=None.

### ยังต้องทำ / ยังไม่รับรอง

- ตรวจ factory/intake/bridge/execution composition จริง รวม durable evaluation hints,
  price readiness ของ pair ที่กำลังสั่ง, queued/active race, corrections หลัง baseline,
  source gaps, alert/retry UI และ multi-owner scheduler cases
- consumer/pagination temporal cutoff และ HTTP endpoint tests ต้องเพิ่มตาม risks ใหม่
- main loop isolation/pool/compose/health ยังไม่ครบ; production API/engine policy ยัง None
- M4 UI/shared controls/generated contracts/browser production harness ยังไม่ทำ
- M5 Ready for Code Review/final review/full candidate gates ยังไม่ถึง
- full regression และ W1–W4 ยังไม่เริ่ม; รันทีละชุดเมื่อ final composition นิ่ง
- V21 Pending Full Validation; V22/23 dependencies เดิมยัง Pending Dependency
- ไม่มี commit/push/merge หรือ activation ใน production
