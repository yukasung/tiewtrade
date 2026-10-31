# F18-UI — ล้าง Local Recovery ที่หมดอายุอัตโนมัติ — Plan Amendment

สถานะ: **Approved — เจ้าของตอบ “approve stale recovery plan and validation” วันที่ 2026-10-30**
วันที่: 2026-10-30
อ้างอิง: [Requirements](stale-recovery-auto-clear-requirements-amendment.md) **Approved 2026-10-30**

## แผน

1. เพิ่ม exact-key `discard` operation แบบ additiveใน `useDurableAttempt` โดยใช้
   journal clearที่ตรวจ expected keyเดิม; ไม่เปลี่ยน send/finishของ callersอื่น.
2. ใน `RiskLimitPanel` ตรวจพร้อมกันว่า:
   - มี pending attempt,
   - lookup errorเป็น `RISK_REQUEST_NOT_FOUND`,
   - snapshotพร้อมและ identity `revision:wallet:episode` ต่างจาก expected identity.
3. เมื่อครบ ให้ discard local attempt, sync draftจาก authoritative snapshot, ล้าง dirty/
   forced-stale/receipt state และไม่ POSTหรือสร้าง UUID.
4. กรณี identityตรง, network/storage error, request/authorization/resultพบ หรือ errorอื่น
   คง recoveryเดิมและ fail closed.
5. ไม่เปลี่ยนข้อความ visible, API/schema/backend, Money, TOTP, latch/resetหรือ Live.

## Tests

- stale+not-foundปลดล็อก inputด้วยค่าปัจจุบันโดย POST/UUIDเป็นศูนย์.
- not-foundแต่ identityตรงไม่ล้างและ exact-key Saveยังทำงาน.
- network error, AUTHORIZATION_ONLY, REQUEST_PENDING, APPLIED/REJECTEDไม่ถูกล้าง.
- owner/mode/key mismatchไม่ล้างข้าม scope.
- รัน `RiskLimitPanel`, shared durable-attempt callers, account/session tests,
  lint, typecheckและ build; rebuild frontend container.

ประมาณเวลา **20–30 นาที**. ไม่รัน backend workloadหรือ W1–W4.

## Needs Clarification

ไม่มี.
