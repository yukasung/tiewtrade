# ADR-0007: Session Authentication + TOTP 2FA

- Status: **Accepted** (2026-09-22)
- Date: 2026-09-22
- Related: FR-TEN-02, FR-TEN-04, FR-LIVE-08, FR-ADM-01

## Decision
- Server-side session เก็บใน Postgres (cache ใน Redis ได้) ส่งด้วย cookie แบบ httpOnly / Secure / SameSite + CSRF token
- Password hash ด้วย argon2
- TOTP 2FA: บังคับสำหรับ User ที่เปิด Live และ Platform Admin
- เพิกถอน session ได้ทันที (ระงับบัญชี, เปลี่ยนรหัสผ่าน)

## Consequences
- เพิกถอนสิทธิ์ได้ทันทีต่างจาก JWT อายุยาว
- ใช้ได้ดีกับ SPA ที่อยู่ domain เดียวกับ api ผ่าน reverse proxy
