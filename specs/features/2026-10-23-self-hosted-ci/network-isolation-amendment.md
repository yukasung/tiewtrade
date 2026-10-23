# NC-52 — Host-enforced CI network sandbox — Design amendment

สถานะ: **Retired (2026-10-24)** — ไม่ใช้แนวทาง self-hosted ต่อ; ดู [closure checkpoint](evidence/closure-checkpoint.md).
เนื้อหาและผลตรวจด้านล่างเป็นประวัติ ไม่ใช่คำสั่งให้ทำต่อหรือผล validation ผ่าน.

ประวัติการอนุมัติ: **Approved สำหรับ bounded proof** — เจ้าของสั่ง `อนุมัติ` หลังได้รับคำอธิบาย
เรื่องสร้างบัญชี CI และทดลอง PF แบบจำกัดขอบเขตพร้อม rollback วันที่ 2026-10-23.
ยังไม่อนุมัติ runner activation และยังไม่ถือว่า isolation ผ่าน
วันที่: 2026-10-23
อ้างอิง: [requirements CI-02/07/08](requirements.md), [plan §2](plan.md), [validation](validation.md)

## ข้อสรุปจากการออกแบบ

เสนอพิสูจน์ **dedicated non-admin macOS identity + PF anchor เฉพาะ CI identity**
ควบคู่กับ Lima user-mode networking. ยังไม่ถือเป็น verified isolation recipe.
เลือกเป็น bounded proof ก่อน implementation/activation ไม่ใช่สัญญาว่าต้องฝืนใช้วิธีนี้.
หากพิสูจน์ packet attribution/protocol coverage/loopback ไม่ครบ ต้องหยุด ไม่ลด CI-02.
ไม่ใช้ guest firewall, runner label หรือปิด mounts เป็น network boundary แทน.

ไม่เลือก sandbox-exec เป็น security boundary หลัก: Apple ระบุ custom sandbox API/profile
ไม่รองรับ third-party development และ deprecated; ไม่สร้าง custom NetworkExtension หรือ
fork Lima เพื่อหลีกเลี่ยงข้อจำกัดในงานนี้. ยังไม่ซื้อเครื่อง/cloud หรือเพิ่ม paid quota.

## หลักฐานที่ตรวจแล้ว — read-only เท่านั้น

- เครื่องมี `/usr/bin/sandbox-exec` แต่การมี binary ไม่ได้พิสูจน์ isolation.
- `/etc/pf.conf` บนเครื่องมี Apple anchors; ห้ามใช้/เขียน namespace `com.apple/*`
  เป็นพื้นที่ของเรา. ยังไม่ได้อ่าน live PF state ด้วยสิทธิ์ root หรือโหลด rules.
- Local macOS `pf.conf(5)` ระบุว่า user match อ้าง effective UID ของ socket;
  forwarded traffic อาจเป็น unknown และ attribution ครอบเฉพาะ TCP/UDP.
- คู่มือเดียวกันระบุ `set skip on lo0` ทำให้ PF ไม่ตรวจ traffic บน interface นั้น;
  ต้องตรวจ live configuration ไม่ใช่อ่าน `/etc/pf.conf` อย่างเดียว.
- `pfctl(8)` เตือน root ruleset reload อาจ flush rules ที่ระบบเติมไว้;
  ใช้ PF reference token ของเราเองได้ผ่าน `-E`/`-X`, ไม่ใช้ global disable/flush.
- [Lima 2.2.1 gvproxy](https://raw.githubusercontent.com/lima-vm/lima/v2.2.1/pkg/networks/usernet/gvproxy.go)
  แสดง gateway NAT ไป host loopback. จึงต้องทดสอบ destination จริงหลัง proxy/NAT
  และ attribution ของ host sockets ไม่ใช่ตรวจ guest route เพียงอย่างเดียว.

## แบบที่เสนอสำหรับ bounded proof

1. **Identity:** สร้าง local non-admin account เฉพาะ CI ชื่อที่ตรวจว่าไม่ชนแล้ว เช่น
   `tiewtrade_ci`; home/private runtime directory แยก, ไม่มี password login/remote login,
   sudo/admin groups, host keychain credentials, SSH agent หรือ owner repo mount.
   Lima hostagent/network helper ทุก process ต้องรันเป็น identity นี้ ไม่ใช่ owner/root.
   Owner-side trusted launcher ยังเก็บ GitHub credential และส่งเฉพาะ registration token
   ชั่วคราวหลัง isolation gate ผ่าน; bounded proof ไม่ลงทะเบียน runner.
2. **Rule scope:** ใช้ anchor ของเรา เช่น `tiewtrade-ci` พร้อม validated numeric UID;
   helper แบบ root-owned รับเฉพาะ operation/manifest ที่กำหนด ไม่รับ arbitrary path,
   shell/rules text จาก workflow. ไม่แก้ Apple anchors/default policy หรือฆ่า global states.
   ต้อง review placement ที่ไม่ถูก quick-pass/skip rule ก่อนหน้าข้ามได้ก่อนโหลด.
3. **Egress policy:** deny guest→host addresses, loopback, RFC1918/CGNAT/link-local,
   multicast/reserved และ directly-connected networks รวม host/LAN ที่ใช้ public IP.
   เสนอเริ่มด้วย IPv4 public TCP 80/443 และ TCP/UDP DNS เฉพาะ resolver ที่เลือกไว้;
   IPv6/ICMP/other protocols ต้อง deny หรือพิสูจน์ว่าไม่มี proxy/forward path ออกได้.
   ห้ามนับ PF UID TCP/UDP rules เป็นหลักฐานว่า deny ICMP/IPv6 แล้ว.
4. **Dynamic networks:** capture host/interface/routes/DNS fingerprint ก่อน VM start;
   ไม่อนุญาต VPN/network change ระหว่าง proof. เมื่อ fingerprint เปลี่ยนให้หยุด VM
   ก่อนเริ่มงานใหม่และยืนยัน policy ใหม่ ไม่เติม subnet ระหว่างรันแบบ fail-open.
5. **Order:** validate live PF/rule ownership/UID → syntax check ไม่โหลด → review diff
   ของ system files → owner-authorized scoped install → เปิด PF reference ของเรา →
   ทำ canary proof → ปิด VM → ถอนเฉพาะ owned resources/reference. ต้องมี rollback พร้อมก่อน install.
   ไม่เปิด VM ที่รับ workflow ระหว่าง rule reload; ถอน policy ได้หลังหยุด VM แล้วเท่านั้น.
   ไม่อ้าง continuous protection จาก polling อย่างเดียว: guest ต้องถอด host policy ไม่ได้
   และ proxy/helper failure ต้องไม่เพิ่มทางออกอื่น. Host administrator/root เป็น trusted
   boundary; การฝืนปิด PF จาก root ภายนอกไม่อยู่ในคำรับรองและทำให้หลักฐานรอบนั้นใช้ไม่ได้.
6. **Control channel:** การให้ host ควบคุม VM ผ่าน loopback SSH ต้องแคบกว่าการให้ guest
   ต่อ host services. ต้องตรวจว่า reply/control sockets ไม่ต้องเปิดกว้างจนยกเว้น host loopback
   ทั้งหมด; ถ้าต้องทำเช่นนั้นให้ reject recipe ไม่ขยาย allow rules.

## OS changes ที่ต้องอนุมัติก่อนทำจริง

- สร้าง account/home ของ CI และ runtime directory ของ identity นี้.
- อาจเพิ่ม anchor hook เฉพาะ CI ใน `/etc/pf.conf`, root-owned anchor/helper และ
  ใช้ PF enable reference; ไม่ reload main ruleset หากยังพิสูจน์ preservation ไม่ได้.
- รอบออกแบบไม่ได้แก้ OS; เจ้าของอนุมัติ account/firewall mutations ที่จำกัดตาม
  bounded proof นี้แล้วภายหลัง. ต้องผ่าน read-only preflight/syntax/review/rollback
  ตามลำดับก่อน mutation และยังต้องยืนยัน OS administrator privileges เมื่อระบบร้องขอ.
- ต้องทำ backup/hash ของไฟล์ที่จะเปลี่ยนและบันทึกทรัพยากรที่สร้างก่อน mutation;
  rollback คืนเฉพาะ diff/anchor/token ของเรา ไม่ overwrite concurrent system changes.
  ไม่ลบบัญชี/home ที่มีอยู่แล้ว ไม่ลบ evidence และไม่แก้ owner Git credentials.

## Validation ส่วนเพิ่ม — ทุกข้อ Not Run

| # | สิ่งที่ต้องพิสูจน์ก่อน activation |
|---|---|
| NI-01 | Live PF options/skip/anchors/rule order และ socket effective UID ตรงแบบ; default user-mode เท่านั้น ไม่มี vzNAT/bridge/user-v2/helper อื่นเป็นทางออก |
| NI-02 | ใช้ synthetic canary listeners ไม่ใช้ dev DB: host loopback IPv4/IPv6, host LAN IP และ controlled private/LAN target. Host owner ต่อ canary ได้ก่อน/หลัง แต่ guest ต่อไม่ได้; มี PF counter/capture ประกอบ ไม่ถือ timeout อย่างเดียวเป็นหลักฐาน |
| NI-03 | Guest root และ Docker container แบบ privileged ลองเปลี่ยน routes/DNS/iptables, direct IP, IPv4-mapped IPv6, ICMP/UDP/other protocol และ proxy gateway แล้วไม่ bypass. ไม่ probe อุปกรณ์ LAN ของคนอื่น; unknown/unobservable path ถือว่าไม่ผ่าน |
| NI-04 | Public HTTPS/DNS/package download/SSH control/service containers ยังทำงาน; ไม่ต้องเปิด broad localhost/LAN exception หรือ host Docker socket |
| NI-05 | Owner browser/Git/Docker/dev canary และ unrelated PF anchors/states ไม่เปลี่ยน; filtering ไม่กระทบ UID อื่น. Root-originated helper/socket ไม่เป็นทางหลุด |
| NI-06 | Guest root ถอด host policy ไม่ได้; proxy/helper crash, sleep/resume/cancel และ network/VPN transition ที่รองรับต้องไม่เปิดช่องเข้าถึง host/LAN. การถอน anchor/PF reference โดย helper ต้องเกิดหลังหยุด VM เท่านั้น; external administrator rule changes ทำให้ run ไม่ได้รับการรับรอง. ถ้า lifecycle บังคับลำดับนี้ไม่ได้ให้ reject |
| NI-07 | Rollback ถอนเฉพาะ owned rule/reference/helper/account ที่สร้างใน proofตามอนุมัติและเก็บ evidence; ไม่ flush rules/states/disable PF ของระบบหรือผู้ใช้อื่น |

## Gate / ทางออกเมื่อ proof ไม่ผ่าน

NC-52 ยังเปิดอยู่จน recipe ได้รับอนุมัติและมีหลักฐาน NI-01..07 ครบ.
อนุมัติเอกสารนี้ได้เพียงให้ทำ bounded proof ไม่ให้ถือว่า isolation ผ่านหรือเปิด runner จริง.
หาก PF/user-mode model บังคับ policy ไม่ครบ ให้หยุดและเลือก Linux host ที่แยกจริง
เมื่อเจ้าของมีอยู่ หรือพัฒนาด้วย local validation ระหว่างรอ free Actions allowance;
ไม่เปลี่ยน Failed GitHub CI เป็น Passed. ไม่เสนอซื้อบริการหรือเปิด repo เป็น Public.

## แหล่งอ้างอิง

- Local macOS 15.6.1: `pf.conf(5)`, `pfctl(8)`, `/etc/pf.conf` — อ่านอย่างเดียว 2026-10-23.
- [Apple Developer Technical Support](https://developer.apple.com/forums/thread/661939):
  custom sandbox profiles ไม่ใช่ supported third-party API.
- [Lima user-mode network](https://lima-vm.io/docs/config/network/user/) และ pinned source ข้างต้น.

## Bounded-proof checkpoint — เริ่มหลังอนุมัติ

- Read-only preflight: owner UID 501 อยู่กลุ่ม admin; `tiewtrade_ci` ยังไม่มี.
- `sudo -n -l` ต้องยืนยันรหัสผ่าน และเรียก pfctl แบบไม่ยกระดับอ่าน `/dev/pf` ไม่ได้.
  ใช้ native macOS administrator dialog สำหรับการอ่าน PF status/rules/interfaces เท่านั้น;
  ไม่ขอรหัสผ่านในแชต ไม่เพิ่ม NOPASSWD และยังไม่สร้างบัญชี/โหลด rules.
- NI-01..07 ยังคง Not Run จนมีหลักฐานจริง. การอนุมัติ bounded proof ไม่ปิด NC-52.

### Host identity probe checkpoint — Partial ไม่ใช่ guest isolation ผ่าน

- เพิ่ม `.ci/self-hosted/pf_probe.py` และ focused safety tests ใน
  `backend/tests/gates/test_pf_probe.py`; default mode อ่านอย่างเดียว.
  Mutating mode ต้องเป็น root, UID ว่าง, PF Disabled/states=0, default root config
  และ root anchors ที่รู้จัก. ไม่สร้าง account/home/VM หรือรับ network target จาก CLI.
- ใช้ native macOS authorization สำหรับ synthetic TCP localhost listeners เท่านั้น;
  UID 550 ไม่มี account record และใช้เฉพาะ child process ที่ drop privileges.
  ตรึง numeric UID จึงไม่ได้เปลี่ยน owner identity หรือระบบ login.
- ผลจริงใน [raw evidence](evidence/pf-identity-probe.json): ก่อน filter ทั้ง UID ทดลอง
  และ owner ต่อ canary ได้; เมื่อ enable กฎ scoped UID ทดลองต่อ IPv4/IPv6 ไม่ได้
  แต่ owner ต่อได้ทั้งสอง. PF TCP counter แสดง 11 packets/724 bytes; UDP counter 0
  จึง **ยังไม่อ้าง UDP/proxy/ICMP/guest-root isolation ผ่าน**.
- โหลดเฉพาะ temporary root anchor reference กับ owned child rules; ไม่เขียน `/etc/pf.conf`,
  ไม่ load/flush Apple child anchors, ไม่ flush global states และไม่ disable PF ของคนอื่น.
  คืน root filter/NAT rules ตรงก่อนเริ่ม, Apple references ตรงเดิม, release เฉพาะ PF token
  ของเรา แล้ว PF กลับ Disabled และ states=0.
- Kernel ยังแสดงชื่อ `tiewtrade-ci-proof` แบบว่างแม้ล้าง owned rules และโหลด scoped
  empty ruleset แล้ว; ไม่มี filter/NAT rule หรือ root attachment ใช้งานอยู่.
  เก็บข้อสังเกตนี้ตรงไปตรงมา ไม่ใช้ global flush/reboot เพื่อลบเพียงชื่อ anchor.
  ไม่ถือว่ารายการ NI-07 ครบจาก cleanup เฉพาะ host probe นี้.
- Diagnostic ก่อน mutation: รอบแรก helper ตีความ warning ปกติของ pfctl -f เป็น error;
  รอบถัดไป syntax-only guard จับ staged anchor insertion ที่ไปโดน normalization/translation
  prefixes. ทั้งสองหยุดก่อน load; แก้ warning handling/whole-line placement และเพิ่ม
  regressions ก่อนรอบจริงผ่าน. ไม่ลด PF safety preconditions.
- ผลสุดท้าย focused tests **18 passed**, Ruff/format และ scoped mypy **2 files** ผ่าน.
  ยังไม่ commit/push, ติดตั้ง Lima, สร้างบัญชี CI, แก้ workflows หรือลงทะเบียน runner.
  ขั้นถัดไปยังต้องทดสอบ guest/proxy attribution, UDP/ICMP/IPv6 bypass, host/LAN/private
  targets, lifecycle และ rollback บน VM ตาม NI-01..07 ก่อนปิด NC-52/activation.

### VM provisioning checkpoint — ต่อจาก host-only probe

- ติดตั้ง Lima **2.2.1** เท่านั้น ไม่อัปเกรด packages อื่น. ใช้ Apple VZ บน macOS
  15.6.1/arm64; resource budget 4 vCPU/4 GiB/60 GiB ตามแผน.
- Image: Ubuntu 24.04 ARM64 `release-20260926`, SHA256
  `1d6bffe64b848468ac97f821d369a4846d983de1800ccf6b5ec8853e85cefc55`;
  ตรวจจาก official SHA256SUMS และตรึงใน `.ci/self-hosted/lima-proof.yaml`.
  `limactl validate` ผ่าน และ `create` จบจริงภายใต้ UID 550.
- บัญชี `tiewtrade_ci` สร้างตาม manifest: UID 550, non-admin, disabled login,
  shell `/usr/bin/false`, home mode 0700. ไม่แตะ owner account/Git credentials.
  macOS ปฏิเสธการเขียน protected GeneratedUID และการเขียน UniqueID เดิมซ้ำใน
  initial/recovery attempts; หยุดก่อนสร้าง VM, ปรับ helper ให้กำหนด UID/GID ครั้งเดียว
  และอ่าน GUID ที่ระบบสร้าง. Recovery ตรวจ GUID ตรง partial record ก่อนทำต่อ;
  บัญชีสุดท้ายตรวจผ่าน ไม่เปิด password login หรือเพิ่ม NOPASSWD.
- Effective config จาก `limactl list --json`: ไม่มี mounts/network เสริม,
  ปิด host key/agent/X11 forwarding, SSH over vsock, port forwards ignored,
  hostResolver/proxy propagation/containerd ปิด. VM ยังไม่มี runner หรือ checkout.
- `.ci/self-hosted/vm_policy_probe.py` ใช้ฟังก์ชัน inspect/staging/PF เดิมซ้ำ;
  scoped TCP/UDP policy ปิด reserved/host-onlink prefixes ก่อน public IPv4 HTTP(S)
  และ DNS เฉพาะ 1.1.1.1. ไม่อ้างว่า UID rules บังคับ ICMP/other protocols ได้.
  Policy ต้องติดก่อน boot; ต้องยืนยัน stopped ก่อนถอน rules/reference และเมื่อ stop
  ล้มเหลวต้องคง policy/journal เพื่อ reconcile ไม่ fail-open.
- Focused helper tests **33 passed**, Ruff/format และ mypy **4 files** ผ่าน.
  Tests ไม่ใช้ PF/Directory Services/network จริง; รวม public-onlink ordering,
  boundary config rejection และ stop failure ที่ต้องไม่ถอน policy.
  การตรวจนี้ไม่เปลี่ยน application inputs จึงไม่รัน financial/full workload ซ้ำ.
- Boot smoke เก็บ progress/result/cleanup ใน [journal](evidence/vm-policy-boot.json).
  ขั้นนี้ไม่ใช่ guest canary, privileged Docker bypass หรือ lifecycle acceptance;
  NI-02/03/06 ยังขาด, NC-52 ยังเปิด และไม่อนุญาต runner activation.
- ผล boot smoke รอบนี้ **Failed ที่ NI-04/control channel**: hostagent ยังใช้
  `127.0.0.1:53071` แม้ `overVsock=true`; ไม่เปิด broad loopback exception.
  หยุด VM และ reconcile owned policy สำเร็จแล้วตาม [diagnostic](evidence/vm-policy-diagnostic.md).
  PF กลับ Disabled/states=0, root/Apple references เดิม; เก็บ stopped VM/account ไว้
  สำหรับ bounded proof ต่อ ไม่ถือ full NI-07 ผ่าน. Tests หลังเพิ่ม recovery guards
  **36 passed**, Ruff/format และ mypy 4 files ผ่าน. ต้องตรวจ control-channel recipe
  ที่แคบและพิสูจน์ได้ก่อน boot รอบใหม่ ไม่ rerun failure เดิมโดยไม่มีการเปลี่ยนที่เกี่ยวข้อง.
