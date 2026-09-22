# ADR-0012: รูปแบบการเข้ารหัส API Secret ที่ใช้ได้ทั้ง VM และ Cloud KMS

- Status: **Accepted** (2026-09-22)
- Date: 2026-09-22
- Supersedes: ส่วน "sealed box" ของ [ADR-0005](0005-live-execution-gateway-and-credentials.md)
- Related: FR-SEC-01/02/09, NFR-25

## Context
ADR-0005 ใช้ libsodium sealed box (X25519 + XSalsa20-Poly1305) แล้วระบุว่าย้ายไป Cloud KMS asymmetric decrypt ได้ด้วยการเปลี่ยน config แต่ Cloud KMS asymmetric decryption รองรับ RSA-OAEP ไม่รองรับ sealed box จึงย้ายด้วย config อย่างเดียวไม่ได้

## Decision
1. **อัลกอริทึม:** Browser เข้ารหัส API Secret ด้วย **RSA-OAEP (SHA-256) ขนาด 4096 บิต** ผ่าน WebCrypto โดยตรง (Secret ของ Binance สั้น อยู่ในขนาดที่ RSA-OAEP 4096 เข้ารหัสได้) เป็นรูปแบบที่ Cloud KMS `RSA_DECRYPT_OAEP_4096_SHA256` ถอดได้
2. **ที่เก็บ private key:** VM ใช้ไฟล์ PEM ที่ mount เข้า container execution เท่านั้น; GCP ใช้ Cloud KMS asymmetric key ที่ให้สิทธิ์ decrypt เฉพาะ service account ของ execution
3. **Ciphertext มีเวอร์ชัน:** เก็บ `format_version` (เริ่มที่ 1 = RSA-OAEP-4096-SHA256) และ `encryption_key_id` (key และเวอร์ชันที่ใช้) คู่กับ ciphertext
4. **การย้ายหรือเปลี่ยน key (rewrap):** job ภายใน execution ถอดรหัสด้วย key เดิม แล้วเข้ารหัสใหม่ด้วย public key ใหม่ (เช่น ของ Cloud KMS) ทีละ credential และอัปเดต `encryption_key_id`; plaintext อยู่ในหน่วยความจำของ execution เท่านั้น
5. **หลังถอดรหัส** Secret อยู่ในหน่วยความจำของ execution เท่านั้น ไม่เขียนลง disk หรือ log และล้างทันทีเมื่อ Credential ถูกลบ (FR-SEC-09)

## Consequences
- ย้ายไป Cloud KMS ได้ด้วย rewrap job โดยไม่ต้องให้ผู้ใช้ใส่ Key ใหม่
- ไม่ต้องใช้ library เข้ารหัสเพิ่มใน browser (ใช้ WebCrypto ที่มีอยู่)
- ต้องจัดการ public key หลายเวอร์ชันระหว่างช่วง rotation
