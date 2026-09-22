# ADR-0013: การเพิกถอน Session และ WebSocket

- Status: **Accepted** (2026-09-22)
- Date: 2026-09-22
- Amends: [ADR-0007](0007-session-auth-and-totp.md)
- Related: FR-TEN-02, FR-ADM-05, FR-SEC

## Context
ADR-0007 อนุญาตให้ cache session ใน Redis แต่ก็สัญญาว่าเพิกถอนได้ทันที session ที่อยู่ใน cache อาจยังใช้ได้หลังถูกเพิกถอนใน Postgres และ WebSocket ที่เปิดอยู่ไม่ถูกตรวจซ้ำ

## Decision
1. **Postgres เป็นแหล่งเดียวที่ตัดสิน session** ใน MVP **ไม่ cache การตรวจ session** ใน Redis: ทุก HTTP request ตรวจกับ Postgres (ปริมาณตามเป้า NFR-16 รับได้)
2. **ถ้า Postgres ใช้ไม่ได้** ให้ปฏิเสธ request (fail-closed)
3. **เพิกถอน** (logout, ระงับบัญชี, เปลี่ยนรหัสผ่าน, Admin ระงับ, ลบบัญชี) = ตั้ง `revoked_at` ใน Postgres แล้ว publish event `session.revoked`
4. **WebSocket:** api ปิดการเชื่อมต่อทันทีเมื่อได้ event `session.revoked` และ**ตรวจ session ซ้ำกับ Postgres ทุก 60 วินาที** เป็น fallback เผื่อ event หาย — ช่วงเวลาที่ session ที่ถูกเพิกถอนยังรับข้อมูลได้จึงไม่เกิน 60 วินาที
5. **การกระทำที่อ่อนไหว** (ส่ง Order Live, จัดการ Credential, Admin, เปลี่ยน Plan) ตรวจ session และ 2FA กับ Postgres ทุกครั้ง WebSocket ใช้ส่งข้อมูลออกเท่านั้น ไม่รับคำสั่งเหล่านี้
6. ถ้าอนาคตต้องการ cache: TTL ไม่เกิน 30 วินาที, ลบ cache เมื่อได้ `session.revoked`, และการกระทำในข้อ 5 ยังตรวจ Postgres เสมอ

## Consequences
- ความหมายของ "เพิกถอนทันที" ชัดเจน: HTTP ทันที, WebSocket ทันทีหรือไม่เกิน 60 วินาที
- Postgres รับ query เพิ่มหนึ่งครั้งต่อ request
