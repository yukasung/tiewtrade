# Bounded VM policy boot smoke — Failed, cleanup recovered

วันที่: 2026-10-23 (Asia/Bangkok)

## ผลจริง

`tiewtrade-ci-proof` สร้างสำเร็จภายใต้บัญชี CI; effective config อยู่ใน
[boot journal](vm-policy-boot.json). Scoped host PF policy ติดก่อนเปิด VM.
Boot command ไม่สำเร็จ: Lima hostagent พยายาม SSH จากบัญชี CI ไป host loopback
แม้ config `ssh.overVsock=true`; เส้นทางนี้ถูก reserved-destination deny บล็อก.
ไม่แก้ด้วย broad localhost exception และไม่รันซ้ำ recipe เดิม.

อ่าน `ha.stderr.log` พร้อม `pfctl -a tiewtrade-ci-proof -vvsr` ระหว่างทำงาน:

```text
2026-10-23T23:35:05+07:00 executing ssh ... -p 53071 127.0.0.1
2026-10-23T23:35:13+07:00 ssh: connect to host 127.0.0.1 port 53071: Operation timed out
```

Excerpt ข้างต้นตัด argv ส่วน bootstrap ที่ไม่เกี่ยวออก; full hostagent log ยังอยู่ใน
private CI home. ไม่มี runner/token/checkout ใน VM นี้.

PF counters ตอน recovery: reserved TCP deny **403 packets/24,304 bytes**;
public TCP80 **24,948 packets/109,673,291 bytes**, TCP443 **452 packets/486,666 bytes**;
UDP DNS1.1.1.1 **48 packets/5,614 bytes**. เป็นหลักฐาน attribution/traffic ของ UID550
เท่านั้น ไม่พิสูจน์ package provisioning จบ, DNS contract, canary isolation หรือ ICMP coverage.
อ่าน raw counters ใน [recovery](vm-policy-recovery.json).

## Cleanup ที่พิสูจน์แล้ว

- หยุดเฉพาะ named proof VM ด้วย `limactl stop --force tiewtrade-ci-proof`.
- Supervisor เก็บ `failed/manual_reconciliation_required`: normal stop exit1 จึงไม่ถอน
  policy ก่อนยืนยัน stopped. เก็บ original journal ไว้ ไม่เปลี่ยน failure เป็น success.
- Recovery ตรวจ fixed VM **Stopped**, live root filter/NAT และ Apple child references
  ไม่มี foreign change, owned rules แปดรายการ scope UID550. จึงคืนเฉพาะ root references,
  flush เฉพาะ owned anchor rules และ release token ของ proof.
- ผลหลัง recovery: PF **Disabled**, states **0**, root filter/NAT/Apple references ตรงเดิม.
  ไม่ใช้ global disable/flush ไม่เขียน `/etc/pf.conf`. Empty inactive anchor name ยังคงอยู่.
- บัญชี disabled-login, stopped VM/image และ Lima ยังอยู่สำหรับ bounded proof ต่อ;
  ไม่ถือ NI-07 full account/home rollback ผ่าน. ไม่ลบ owner/development resources.

## งานค้าง / ไม่ใช่ acceptance

NI-04 **Failed**: control channel ภายใต้ policy ปัจจุบันใช้ไม่ได้. ต้องตรวจเส้นทางควบคุม
และออกแบบข้อยกเว้นที่แคบ/พิสูจน์ ownership ได้ตาม amendment §6 หรือ reject recipe;
ห้ามเปิด localhost/LAN แบบกว้าง. Guest/root/privileged-container bypass, controlled host/LAN
canaries, non-TCP/UDP coverage และ lifecycle/network transitions ยังไม่ครบ.
NC-52 ยังเปิด; ไม่ลงทะเบียน runner ไม่แก้ workflow/Billing ไม่ commit/push.

## Control-channel source review

ตรวจ pinned source Lima v2.2.1
[`startVsockForwarder`](https://github.com/lima-vm/lima/blob/v2.2.1/pkg/driver/vz/vsock_forwarder.go):
ฟังก์ชันเปิด TCP listener บน localhost แล้วส่งแต่ละ connection เข้า guest vsock.
ดังนั้น `overVsock=true` เปลี่ยน transport ช่วง host→guest แต่ไม่ได้ตัด host TCP listener;
log timeout ในรอบจริงตรงกับ implementation นี้ ไม่ใช่การตั้งค่าไม่ถูกนำไปใช้.

การ allow เฉพาะเลขพอร์ตเดิม 53071 ยังไม่ใช่ fix ที่พิสูจน์ปลอดภัย: เมื่อ forwarder
ปิดหรือ crash พอร์ตอาจถูก process อื่น bind ก่อน policy ถูกถอน. PF destination-port
rule ไม่ผูกกับเจ้าของ listener และ source UID550 ใช้ร่วมกันทั้ง control client และ
guest network proxy. จึงไม่เพิ่ม fixed-port exception โดยอาศัย preflight ownership
ครั้งเดียวหรือ polling; NI-06 ต้องครอบ listener lifetime/rebind ด้วย.

เงื่อนไขของ fix ถัดไป: ต้องมี control endpoint ที่ ownership/lifetime คงอยู่จนหยุด VM,
หรือแยก identity ของ control client ออกจาก guest proxy ด้วย runtime ที่รองรับ.
ต้องตรวจแนวทางนี้ก่อนเขียน allow rule และพิสูจน์ listener crash/rebind ด้วย canary;
หาก runtime ที่อนุมัติทำไม่ได้ ให้ใช้ทางออกใน network amendment ไม่ลด isolation.
