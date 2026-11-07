# Reference template dependency remediation — Requirements

สถานะ: **Approved — requirements และ scope amendments NC-SEC-REF-01/02 อนุมัติ 2026-11-06**
วันที่: 2026-11-06
Branch: `feature/security-reference-dependency-remediation`
ฐานเริ่มต้น: `74ca1f4bc8118f119d9bdd96381c061b961650ee`

## ทำไมต้องมี

หลัง merge Security CI ใน PR #48 ยังมี Dependabot High 5 alert records ใน
`references/admin-template/package-lock.json` ครอบคลุม 3 packages เดิม; full scan พบ High
เพิ่ม 3 records ในอีก 2 packages ที่มีใน baseline เดิม. เจ้าของอนุมัติ scope amendment
NC-SEC-REF-01 ให้แก้รวม 5 packages / 8 known High records ตามตารางด้านล่าง.
เจ้าของสั่ง `เริ่มทำ` งานแยกนี้หลังได้รับข้อเสนอให้จัดทำ requirements;
ยังไม่ใช่การอนุมัติเปลี่ยน dependencies หรือ implementation.

| Package | Locked version | Target version | High advisory / native alert |
|---|---|---|---|
| vite | 8.2.2 | 8.2.4 | GHSA-587h-7wmj-h5pm / #15 |
| source-map-js | 1.2.1 | 1.2.2 | GHSA-68fv-2mgg-jv7q / #13 |
| js-yaml | 4.1.1 | 4.3.2 | GHSA-2883-xcg3-v3hh / #9; GHSA-5p4m-2wfm-xmqj / #7; GHSA-52cp-r559-cp3m / #6 |
| brace-expansion | 5.0.9 | 5.0.11 | GHSA-6j4f-fj2g-mc7p; GHSA-qhr7-859c-m2p7 (additional scanner High) |
| zod | 4.5.4 | 4.6.6 | GHSA-mrhx-c7xc-m3w5 (additional scanner High) |

ตรวจ advisory metadata และ npm registry แบบ read-only วันที่ 2026-11-06:
targets มีเผยแพร่แล้วและอยู่นอก vulnerable ranges ของทั้ง 8 findings.
Vite เป็น direct dev dependency ช่วง `^8.2.2`; source-map-js เป็น transitive ของ
`@tailwindcss/node` และ `postcss` ช่วง `^1.2.1`; js-yaml เป็น transitive ของ
`cosmiconfig` ช่วง `^4.1.0`. Targets อยู่ใน ranges เดิม จึงเสนอคง manifest.
brace-expansion เป็น transitive ของ minimatch ช่วง `^5.0.8`; zod เป็น transitive
ของ eslint-plugin-react-hooks ช่วง `^3.25.0 || ^4.0.0`. Targets ทั้งหมดอยู่ใน ranges เดิม.
js-yaml และ zod เป็น minor updates ภายใน major 4 ต้องตรวจ compatibility ด้วย.

Template เป็นแหล่งอ้างอิง UI ตาม tech stack; application ไม่ import runtime จาก
`references/`. Template ใช้ React 19/Vite 8 ต่างจาก application React 18/Vite 6.
แม้เป็น reference/toolchain ก็ต้องแก้ vulnerable lock entries โดยรักษาต้นแบบ UI
และไม่ย้ายชุด dependencies ของ template เข้า application.

## ขอบเขต

- แก้ 5 package versions ข้างต้นใน template lockfile และ metadata ที่จำเป็นต่อ
  reproducible install โดยคง package ranges ที่รองรับ targets อยู่แล้ว.
- ตรวจ dependency graph เต็มของ template candidate และ compatibility ของ
  template install/build/dev/preview ตามผลกระทบ พร้อมรักษา application เดิม.
- ใช้ Security CI ที่ merge แล้วและหลักฐานเดิมที่ยัง valid; ขั้น plan ต้องระบุ
  วิธีสแกน template เพิ่มสำหรับงานนี้ เพราะ permanent application dependency gate
  ปัจจุบันตรวจเฉพาะ `backend/uv.lock` และ `frontend/package-lock.json`.

อนุญาต secret false-positive exception เพิ่มหนึ่ง exact identity ตาม NC-SEC-REF-02
ที่เจ้าของอนุมัติ; ไม่อนุญาต dependency exceptions หรือ broad scanner suppressions.

ไม่รวม broad dependency upgrade, React/Vite/Node major migration, UI/source refactor,
application dependencies, database/session/trading behavior, scanner policy/exception changes นอก exact identity ที่อนุมัติ
หรือ GitHub settings changes, การขยาย permanent CI scope, deployment หรือ Live Trading.
หากต้องแก้ source/helper เพื่อสร้างหลักฐาน ให้เสนอ path และเหตุผลใน plan เพื่ออนุมัติก่อน.

## ข้อกำหนด

| รหัส | ข้อกำหนด | ที่มา |
|---|---|---|
| RR-1 | เปลี่ยนทุก occurrence ของ 5 packages เป้าหมายใน template lockfile เป็น versions ตามตาราง; คง manifest ranges และ dependencies อื่นที่ไม่จำเป็นต้องเปลี่ยน หาก resolver ต้องเปลี่ยน package อื่น ให้แสดง dependency edge/reason และขออนุมัติ scope เพิ่มก่อนแก้ | advisory remediation; AGENTS.md ขอบเขตหนึ่งงาน |
| RR-2 | Candidate ต้องติดตั้งแบบ clean/frozen จาก lockfile ได้ด้วย Node 22 ที่ตรง engines ของ template/Vite และ npm version ที่บันทึกในหลักฐาน; integrity, resolved metadata, manifest และ dependency graph ต้องสอดคล้อง ไม่แก้ด้วย broad `npm audit fix` หรือ force upgrade | reproducibility; tech-stack.md |
| RR-3 | สแกน template candidate ทั้ง inventory รวม direct/dev/transitive/optional และ nested occurrences ไม่ใช้ diff-only scan หรือสถานะ alert บน main แทน; baseline มี 373 non-root package entries ให้บันทึกจำนวนจริงของ candidate และอธิบายความเปลี่ยนแปลง | Security CI dependency coverage; testing.md |
| RR-4 | Findings เป้าหมายทั้ง 8 ต้องไม่เหลือใน candidate scan; High/Critical หรือ unknown ที่ยังไม่จัดการเป็น blocker ต้องรายงานและขออนุมัติขอบเขตเมื่อเกินงานนี้ ห้าม suppress/dismiss/สร้าง exception เพื่อให้ผ่าน; บันทึก Medium/Low ตามจริง | Security CI RQ-6/7; security.md |
| RR-5 | Template ต้อง build และเปิด dev/preview ได้ โดยตรวจเส้นทาง UI ตัวแทนและ asset loading ตามผลกระทบใน plan; เปรียบเทียบ baseline เมื่อจำเป็นเพื่อแยกปัญหาเดิม ห้ามแก้ source/UI นอกขอบเขตเพื่อให้ dependency update ผ่าน หาก baseline หรือ candidate ล้มจนพิสูจน์ compatibility ไม่ได้ ให้คง blocker | frontend.md; testing.md §7 |
| RR-6 | คง reference layout/components/styles และ application source/lockfiles เดิม; ไม่เปลี่ยน runtime imports ให้พึ่ง `references/` ไม่ย้าย template dependencies เข้า application และไม่เปลี่ยน security gates/pins; คง 92 approved exceptions เดิมและเพิ่มเฉพาะ secret false-positive identity d84148a55a1db82c511520b0a40131229292c3c7c1fadf8d00f66a6cbbefe8b0 ตาม NC-SEC-REF-02 ที่เจ้าของอนุมัติ | tech-stack.md; frontend.md §2.1; Security CI plan |
| RR-7 | ไม่เปลี่ยน PostgreSQL sessions/persistence, migrations, transactions/locking/idempotency, เงิน/quantity, orders, balance/position, PnL, leverage/margin/liquidation หรือ Paper/Live isolation; validation ไม่ใช้ live credentials หรือส่ง Live orders | AGENTS.md; architecture.md; trading-safety.md |
| RR-8 | ก่อน merge ต้องผ่าน review, Feature validation และ required CI บน final candidate; หลักฐานต้องระบุ SHA, lock fingerprints, inventory, scanner/tool/environment versions และ run URLs แยก local จาก CI; ตรวจ native alerts หลัง merge โดยไม่ใช้การรอ refresh แทน candidate proof และไม่อ้างว่า scanner ครอบคลุมช่องโหว่ทุกชนิด | testing.md §6–7; AGENTS.md Git |

## กฎความปลอดภัยและสถาปัตยกรรม

ยึด [tech stack](../../tech-stack.md), [architecture](../../standards/architecture.md),
[frontend](../../standards/frontend.md), [security](../../standards/security.md),
[trading safety](../../standards/trading-safety.md) และ [testing](../../standards/testing.md).
ไม่มี session storage/infrastructure ใหม่และไม่มีผลต่อ stateless deployment.
เลือกระดับ validation ตาม dependency diff จริงในขั้น plan; ไม่เพิ่ม full regression
หรือทดสอบ exchange/ฐานข้อมูลที่ไม่มีส่วนได้รับผลกระทบเพียงเพื่อทำซ้ำขั้นตอน.

## ยังไม่ชัด / Dependencies / จุดหยุด

- **NC-SEC-REF-01 — Closed (2026-11-06):** เจ้าของตอบ approve ให้
  [scope amendment](evidence/scope-amendment-proposal.md) ขยาย requirements/plan/validation
  ครอบคลุม brace-expansion และ zod รวม 5 packages/8 known High; ไม่มี relevant
  Needs Clarification ค้าง. ผล temporary candidate เดิมเก็บไว้ตามจริง ต้องตรวจ candidate ใหม่.
- **NC-SEC-REF-02 — Closed (2026-11-06):** เจ้าของเลือกอนุมัติ exact exception
  และทำต่อ ตาม [ข้อเสนอ](evidence/checksum-exception-proposal.md); อนุญาตเพิ่มเฉพาะ
  public source checksum false-positive identity ข้างต้นและแก้ plan/validation ก่อน registry.
- หากพบ target ไม่เข้ากับ toolchain เดิม, ต้องแก้ source/UI, เปลี่ยน manifest range,
  package อื่น หรือ policy ให้หยุดเสนอ scope/requirements ใหม่ก่อน implementation ส่วนนั้น.
- Security CI PR #48 merge แล้ว; ขอบเขต application scan เดิมคงไว้.
  การตรวจ fork จริงก่อนรับ fork PR แรกและ Batch/Release ของ feature อื่นยังคงเดิม.
- Requirements ได้รับอนุมัติแล้ว; ขั้นถัดไปคือจัดทำ `plan.md` + `validation.md`
  และรออนุมัติเอกสารทั้งสอง ก่อนเปลี่ยน lockfile/โค้ด. Commit/push/merge ตามคำสั่งเจ้าของเท่านั้น.

## แหล่งอ้างอิง

- [ข้อมูลตรวจประกอบ requirements](evidence/requirements-research.json)
- [Security CI requirements](../2026-11-05-security-ci/requirements.md) และ [plan](../2026-11-05-security-ci/plan.md)
- [launch-editor / Vite advisory](https://github.com/vitejs/launch-editor/security/advisories/GHSA-587h-7wmj-h5pm)
- [source-map-js fix release](https://github.com/7rulnik/source-map-js/releases/tag/v1.2.2) และ [advisory](https://github.com/advisories/GHSA-68fv-2mgg-jv7q)
- [js-yaml empty merge advisory](https://github.com/nodeca/js-yaml/security/advisories/GHSA-2883-xcg3-v3hh)
- [js-yaml omap advisory](https://github.com/nodeca/js-yaml/security/advisories/GHSA-5p4m-2wfm-xmqj)
- [js-yaml merge-chain advisory](https://github.com/nodeca/js-yaml/security/advisories/GHSA-52cp-r559-cp3m)
- npm registry targets: [vite 8.2.4](https://registry.npmjs.org/vite/8.2.4), [source-map-js 1.2.2](https://registry.npmjs.org/source-map-js/1.2.2), [js-yaml 4.3.2](https://registry.npmjs.org/js-yaml/4.3.2)

## การเปลี่ยนแปลงหลังอนุมัติ

2026-11-06 เจ้าของตอบ approve ให้ [scope amendment NC-SEC-REF-01](evidence/scope-amendment-proposal.md)
เพิ่ม brace-expansion 5.0.11 และ zod 4.6.6 พร้อม caller/plugin compatibility probes
ก่อนทำ implementation ต่อ. ไม่เปลี่ยน security thresholds, exceptions หรือ permanent CI scope.

2026-11-06 เจ้าของอนุมัติ [NC-SEC-REF-02](evidence/checksum-exception-proposal.md)
ให้เพิ่ม exact secret false-positive exception หนึ่งรายการจาก 92 เป็น 93; คง
High/Critical/unknown blocking, dependency thresholds, scanner rules/pins และ workflow เดิม.
