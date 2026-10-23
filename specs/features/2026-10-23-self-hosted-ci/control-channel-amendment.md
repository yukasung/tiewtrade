# Control channel — proposed bounded proof

สถานะ: **Retired (2026-10-24)** — ไม่ใช้แนวทาง self-hosted ต่อ; ดู [closure checkpoint](evidence/closure-checkpoint.md).
เนื้อหาและผลตรวจด้านล่างเป็นประวัติ ไม่ใช่คำสั่งให้ทำต่อหรือผล validation ผ่าน.

ประวัติการอนุมัติ: **Approved สำหรับ bounded proof** — เจ้าของสั่ง `approve` วันที่ 2026-10-23;
ยังไม่อนุมัติ runner activation หรือถือว่า isolation ผ่าน
วันที่: 2026-10-23

## หลักฐานและข้อเสนอ

Pinned Lima 2.2.1 `pkg/sshutil/sshutil.go` รองรับ environment `SSH` สำหรับเลือก
SSH executable/arguments. จึงมี extension point ที่ใช้ได้โดยไม่ fork runtime.
`cmd/limactl/tunnel.go` ใช้ SSH localhost connection เดิม จึงไม่แก้ bootstrap failure.

เสนอใช้ OpenSSH ProxyCommand ต่อผ่าน local Unix socket ไปยัง broker ที่เปิดด้วย
native administrator authorization. Broker เป็น process แยกจาก UID550 และเปิดเฉพาะ
connection ไป SSH endpoint ของ proof VM ตาม trusted manifest. PF ของ guest proxy
ยัง deny host/LAN ทั้งหมด; ไม่เพิ่ม exception สำหรับ UID550 ไปยัง host TCP port.

นี่เป็นการเพิ่ม privileged control component จากแผนเดิม ต้องอนุมัติขอบเขตนี้ก่อน
implementation ไม่ถือว่า SSH override เพียงอย่างเดียวพิสูจน์ security boundary แล้ว.

## ข้อบังคับของ proof

- Root-owned broker/config; ไม่รับ arbitrary command, destination หรือ path จาก guest,
  workflow หรือ SSH argv. ใช้ fixed instance identity และ manifest ที่ตรวจแล้วเท่านั้น.
- Unix socket อยู่ใน private host directory ไม่มี mount เข้า guest; ตรวจ peer identity.
  ไม่มี sudo grant, setuid executable หรือ persistent service.
- SSH client ยังคงเป็น non-admin; broker ทำเฉพาะ byte transport. ไม่รัน SSH command
  หรือประมวลผล guest output ด้วยสิทธิ์ root. ไม่ส่ง owner keys/agent/env เข้า VM.
- ต้องแก้ endpoint rebind ด้วย authenticated guest identity ที่ตรึงจาก trusted bootstrap
  และ fail closed; ownership polling หรือเลขพอร์ตอย่างเดียวไม่พอ. ห้ามใช้ Lima default
  StrictHostKeyChecking=no เป็นหลักฐานว่าป้องกัน endpoint substitution ได้.
- ก่อน boot ต้องทบทวนวิธีสร้าง/ส่ง trusted guest host public key โดยไม่ใช้ network TOFU
  และไม่ expose private key. หากทำผ่าน approved image/runtime ไม่ได้ให้หยุด recipe นี้.
- ทดสอบ broker unavailable/crash, listener replacement, invalid peer/manifest,
  guest root/privileged-container access และ cleanup ก่อนเปิด runner.
- Broker ที่พิสูจน์ผ่านยังไม่ปิด NI-01..07: protocol coverage, LAN canaries และ network
  lifecycle ต้องครบตาม network-isolation-amendment.md.

## ผลกระทบและเกณฑ์หยุด

ไม่มี application/trading/workflow changes หรือค่า cloud เพิ่ม. เพิ่ม trusted host code
และภาระตรวจ privileged IPC; ถ้า owner ไม่ต้องการความซับซ้อนนี้ ให้ยุติ Mac runner recipe
และใช้ Linux host แยกที่มีอยู่ หรือ local validation ตามทางออกเดิม.

แหล่งอ้างอิง:
- https://github.com/lima-vm/lima/blob/v2.2.1/pkg/sshutil/sshutil.go
- https://github.com/lima-vm/lima/blob/v2.2.1/cmd/limactl/tunnel.go

## Bootstrap implementation decision

ตรวจ `pkg/cidata/cidata.TEMPLATE.d/user-data` และ installed template รุ่น 2.2.1 แล้ว:
`provision.mode: boot` ถูกฝังลง cloud-init bootcmd ก่อน system provisioning.
ใช้ช่องนี้ติดตั้ง host key เฉพาะ instance ลงชื่อไฟล์ที่ไม่ใช่ default host-key paths
เพื่อไม่ให้ขั้น default key regeneration ลบ key ที่ตรึงไว้. ต้องตรวจ ordering จริงบน guest
ก่อนถือว่าผ่าน; source review อย่างเดียวไม่ใช่ boot acceptance.

สร้าง key ใน private runtime directory บน host, ส่งเข้า generated runtime template
ที่ permission จำกัด; ห้ามเขียน private key ลง repository/log/evidence. Public key เท่านั้น
อยู่ใน known_hosts ที่ trusted supervisor ควบคุม. SSH wrapper ต้องบังคับ
StrictHostKeyChecking=yes, HostKeyAlias เฉพาะ instance, UserKnownHostsFile ที่ตรึงไว้,
GlobalKnownHostsFile=/dev/null และ NoHostAuthenticationForLocalhost=no ก่อน arguments
ที่ Lima เติมมา. ทดสอบด้วย OpenSSH effective configuration ว่าค่าของ Lima override ไม่ได้.

## Implementation checkpoint

เพิ่ม `control_bootstrap.py` สร้าง per-instance Ed25519 identity และ generated template
ใน directory ใหม่ mode0700; template/known_hosts mode0600, ไม่ overwrite existing identity.
Private key ไม่อยู่ใน repo/evidence. `control_ssh.py` ตรึง SSH authentication options
ก่อน Lima arguments; ตรวจ effective configuration ด้วย OpenSSH บน macOS จริงแล้ว.

`control_broker.py` มี kernel peer-identity check ด้วย macOS getpeereid และ byte relay
ที่จำกัด buffer/write/idle timeout, รองรับ half-close. Peer ที่ไม่ใช่ UID550 ถูกปฏิเสธ
ก่อนเปิด host connection; ไม่มี client-supplied destination protocol.
นี่เป็น transport primitives ยังไม่ใช่ deployed broker หรือ supervisor ที่เสร็จแล้ว.

Focused tests **40 passed**, Ruff และ mypy **7 files** ผ่าน; รวม key/public-pin correspondence,
private permissions/no overwrite, unauthorized peer rejection และ duplex/half-close.
งานค้าง: root-owned socket/listener lifecycle, supervisor integration, bootstrap ordering
บน VM จริง, forged-key/listener replacement/crash และ NI gates เดิม. ไม่ถือ tests เหล่านี้
แทน VM acceptance; runner ยังไม่เปิด และไม่ต้องขออนุมัติขอบเขต broker ซ้ำ.

### Supervisor integration / first actual run

เพิ่ม bounded listener, executable SSH wrapper และ `control_proof.py` ใช้ PF lifecycle
เดิม. Evidence ตัด provisioning scripts ออกเพื่อไม่ให้ bootstrap private material หลุด;
regression ทดสอบ secret canary แล้ว. Tests 40 ผ่าน, lint/types 8 files ผ่านก่อนรัน.

รอบจริง `evidence/control-policy-boot.json` **Failed**: hostagent bootstrap ยังเรียก
`/usr/bin/ssh` โดยตรง แม้กำหนด `SSH`. ตรวจ pinned hostagent source พบว่าตัวเลือก
SSHExe ใช้สร้าง options แต่ SSHConfig ของ bootstrap ไม่ได้ส่ง executable นี้ต่อ.
หยุด named VM แล้วและ cleanup คืน owned PF rules/reference สำเร็จ; PF Disabled,
snapshot หลัง cleanup มี states 5 รายการ เก็บไว้ตามจริง ไม่ global flush.
Supervisor จบแล้วและคืน template เดิม; private runtime คงอยู่สำหรับตรวจ/เก็บแบบจำกัดสิทธิ์.

แก้ executable discovery ให้ root-owned `bin/ssh` อยู่หน้าสุดใน PATH ของ subprocess
CI เท่านั้น พร้อม SSH override ชี้ไฟล์เดียวกัน; wrapper เรียก `/usr/bin/ssh` แบบ absolute
จึงไม่ recurse. ยังไม่ได้รัน attempt 2: ต้องตรวจและ archive private runtime เดิมแบบ
recoverable ก่อนสร้างใหม่; original failed evidence ต้องคงอยู่. ไม่อ้างว่า bootstrap
หรือ key-substitution/crash acceptance ผ่านจากการแก้ code นี้.

Attempt 2 preflight (2026-10-24): archived attempt-1 runtime recoverably to
`/private/var/run/tiewtrade-ci-proof-attempt-1` after confirming VM Stopped and no broker
socket. New attempt stopped before PF mutation/VM start because one existing PF state
remained. Read-only inspection showed TCP CLOSING:ESTABLISHED to Ubuntu HTTP, age
00:04:24 and expiry 00:11:54 at observation. No state deletion or global flush performed.
New prepared runtime remains at the original runtime path; supervisor closed broker
and restored VM template. Before retry, wait for states=0 and archive this prepared
runtime to a separate unique path; do not overwrite either retained identity/evidence.
Added an early state guard before preparing further runtime/key material.

### Attempt 2 execution — 2026-10-24

`resume_control_proof.py` waited for states=0 without deleting states, confirmed VM Stopped,
archived prepared runtime to `tiewtrade-ci-proof-attempt-2-preflight`, then ran attempt 2.
`control-policy-boot-2.json` is **Failed**, cleanup succeeded: VM stopped, owned policy
and reference removed, PF Disabled; one HTTP state remained. Private runtime retained,
broker endpoint closed, VM template restored.

Hostagent now invokes `/private/var/run/tiewtrade-ci-proof/bin/ssh`: executable selection
is corrected. Initial proxy closed immediately. Controlled diagnostic `SHELL=/bin/sh`
reached ProxyCommand and local SSH version, then banner exchange timed out after 8 seconds.
Added this process-only shell setting; account login remains disabled. TCP deny counters
were zero, so evidence does not establish the hypothesis that PF dropped broker replies.
No firewall allowance was added. Next: add sanitized broker stage/error counts and resolve
banner exchange before host-key/crash/rebind/NI acceptance. Runner remains inactive.
Wait-helper guards passed in the focused suite: **42 tests passed**; prior lint/types passed.
