# Bounded E2E network diagnostics

สถานะ: **Approved — เจ้าของสั่ง PLEASE IMPLEMENT THIS PLAN 2026-11-11**

## เหตุผลและขอบเขต

Candidate 754edcc เปลี่ยน Azure mirror เป็น Ubuntu archive สำเร็จ แต่ยังล้มจาก DNS
ก่อนเริ่ม browser tests; required checks ผ่าน 6/7. เก็บ failures และหลักฐานเดิมต่อ.
เพิ่ม diagnostic เพื่อแยก DNS, HTTPS และ proxy ระหว่าง user กับ sudo ก่อนทดลองแก้ต่อ.
ไม่เปลี่ยน resolver, mirror, proxy/network policy หรือใช้ Playwright image ใน amendment นี้.

## Implementation และ reuse

- ใช้ branch/PR #67 เดิม และ standard-library unittest/tempfile/subprocess patterns
  ใน `.github/tests/test_e2e_apt.py`; ใช้ worker/verdict และ required names เดิม.
- เพิ่ม `.github/scripts/diagnose_e2e_network.py` หลัง mirror preparation และก่อนคำสั่ง
  Playwright เดิมใน `.github/workflows/ci.yml`; step timeout-minutes: 2.
- Helper ใช้ monotonic budget 100s; แต่ละ child command timeout ไม่เกิน 8s และมี
  coreutils timeout ภายใน sudo สำหรับ DNS/curl เพื่อไม่ทิ้ง privileged child ที่ค้าง.
  DNS limit 5s, curl total limit 6s; ไม่มี retry หรือการติดตั้งเครื่องมือเพิ่ม.
- ตรวจ getent ahosts ของ azure.archive.ubuntu.com, archive.ubuntu.com,
  security.ubuntu.com และ packages.microsoft.com ทั้ง user และ sudo -n.
  ตรวจ HTTPS HEAD ของ https://archive.ubuntu.com/ubuntu/ และ
  https://packages.microsoft.com/ ทั้งสองบริบท. ใช้ curl --disable เพื่อตัด curlrc,
  HTTPS-only redirects, TLS verification เดิม, no retry, ไม่แสดง headers/body/raw errors.
- Metadata ของแต่ละบริบท: nameserver เฉพาะ IP ที่ parse ได้, presence booleans ของ
  proxy env ที่ระบุชื่อไว้ล่วงหน้า และ APT proxy directives; ไม่พิมพ์ค่า directive/env.
  Runner image อ่านเฉพาะ ImageOS/ImageVersion ใน user context. ไม่ dump config/environment.
- stdout เป็น JSON report ที่ใช้ชื่อ domain/context/status คงที่, HTTP status และ sanitized
  metadata; แยก DNS กับ HTTPS results. ไม่ใช้ DNS failure อย่างเดียวเป็น gate เพราะ proxy
  อาจ resolve hostname แทนได้. เก็บผลของทุก probe แม้ probe ก่อนหน้าล้ม.
- Continue ได้เมื่อ sudo Ubuntu archive HTTPS สำเร็จเท่านั้น และ diagnostic harness
  เก็บหลักฐานได้ครบ (เครื่องมือ/metadata ใช้ไม่ได้หรือ budget หมดเป็น operational failure).
  DNS failure หรือ control endpoint failure ที่เก็บผลได้ครบยังเป็นหลักฐาน ไม่ใช่ test success.
  Unknown/invalid response ไม่ถือว่าสำเร็จ. หาก fail ให้หยุดก่อน Playwright install.
- Root metadata ใช้ sudo -n รัน helper เดียวกันด้วย --metadata-only; validate schema
  ของ captured JSON ก่อนรายงาน. ไม่พิมพ์ subprocess stdout/stderr หรือ exception ตรง ๆ.

## Validation ระดับ Feature

V-22: tests ครอบคลุม DNS/HTTPS failure, proxy DNS, TLS/HTTP errors, timeout/budget,
missing tools, user/sudo ต่างกัน, metadata malformed และ secret redaction.
V-23: worker wiring/order/2-minute cap, baseline inventory, Ruff/strict mypy/actionlint
และ existing policy tests ผ่าน. คำสั่ง runtime/test เดิมไม่เปลี่ยน.
V-24: หลัง Ready for Code Review → review code → refactor decision ตาม AGENTS.md
รวม source/spec/evidence อัปเดต PR ครั้งเดียวตาม Git authorization เดิม. ติดตาม CI จนจบ;
runtime CI ประมาณ 20–30 นาที ไม่ใช่รับรองว่าทั้ง run ใช้เวลาเพียง 2 นาที.
ต้องมี report จาก runner จริง พร้อม SHA/run URL; report ไม่เท่ากับ E2E Passed.
Required checks ต้อง 7/7 ก่อน merge และยังรอคำสั่ง merge; main/manual ยัง Pending.

หลังได้หลักฐานให้ระบุสิ่งที่พิสูจน์ได้และข้อมูลที่ขาด เสนอ amendment วิธีแก้ตามผลก่อน
ทดลองเพิ่มเติม ห้ามเลือก resolver/proxy/image ใหม่เองหรือ rerun แบบเดิมอัตโนมัติ.

อ้างอิง: [GitHub networking troubleshooting](https://docs.github.com/en/actions/how-tos/troubleshoot-workflows#networking-troubleshooting-suggestions).
