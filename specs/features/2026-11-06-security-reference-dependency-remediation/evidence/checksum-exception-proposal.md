# Secret checksum false-positive proposal — NC-SEC-REF-02

สถานะ: **Approved — เจ้าของเลือกอนุมัติ exact exception และทำต่อ 2026-11-06**
วันที่: 2026-11-06
PR: https://github.com/yukasung/tiewtrade/pull/54
Head: `8ccc9e72077f80a8ab3fdcbc1634407c8f559a19`
Base: `74ca1f4bc8118f119d9bdd96381c061b961650ee`
Tested merge: `65d78b324958f6d0ae3d37feaa39d60f4f259394`

## สาเหตุที่ CI blocked

[Security run 42172965768](https://github.com/yukasung/tiewtrade/actions/runs/42172965768)
policy/dependency/CodeQL ทั้งสาม languages ผ่าน แต่ secrets job และ aggregate gate fail.
Safe summary มี blocked 1 / excepted 92 / coverage 233 commits; configuration digest
`fe5e8d743e9e67e350c8969acd9292e24a9165e57a65bd5c90a48633d91419ad`.
ไม่เผยแพร่ matched content/raw Gitleaks reports.

| Field | Exact occurrence |
|---|---|
| kind / rule | secret / generic-api-key |
| identity | d84148a55a1db82c511520b0a40131229292c3c7c1fadf8d00f66a6cbbefe8b0 |
| originating commit | 8ccc9e72077f80a8ab3fdcbc1634407c8f559a19 |
| evidence file | specs/features/2026-11-06-security-reference-dependency-remediation/evidence/feature-candidate.json |
| lines | 37–37 |
| classification ที่เสนอ | false_positive — SHA256 ของ public source file ไม่ใช่ credential |

## หลักฐานตรวจแยกจาก scanner

บรรทัดดังกล่าวเก็บ SHA256 ของ `tools/security/secrets.py` ใน baseline fingerprint map.
คำนวณ hash จาก current source และ `git show 8ccc9e7:tools/security/secrets.py` แล้ว
ตรงกับค่าที่บันทึกทั้งคู่. Source file นี้อยู่ใน public repo และไม่เปลี่ยนใน PR.
ไม่มี API key/password/token ถูกใช้ใน fingerprint calculation หรือข้อมูล record นี้.
ไม่จำเป็นต้อง rotate/revoke credential เพราะค่าที่ตรวจเป็น content digest ของไฟล์.

ตรวจซ้ำด้วย Python 3.12 จาก worktree:

```python
from pathlib import Path
import hashlib, json, subprocess
p = Path('specs/features/2026-11-06-security-reference-dependency-remediation/evidence/feature-candidate.json')
expected = json.loads(p.read_text())['baseline_identity']['baseline_sha256']['tools/security/secrets.py']
assert hashlib.sha256(Path('tools/security/secrets.py').read_bytes()).hexdigest() == expected
source = subprocess.check_output(['git', 'show', '8ccc9e72077f80a8ab3fdcbc1634407c8f559a19:tools/security/secrets.py'])
assert hashlib.sha256(source).hexdigest() == expected
```

## ข้อเสนอที่แนะนำ — exact false-positive exception หนึ่งรายการ

อนุมัติ amendment ก่อน implementation:

1. Requirements RR-6 และขอบเขต: อนุญาตเพิ่มเฉพาะ secret false-positive identity
   ข้างต้นใน `.github/security/exceptions.json`; คง approved 92 entries เดิม, High/
   Critical/unknown blocking, dependency targets ทั้ง 5 และห้าม dependency exceptions.
   ไม่เปลี่ยน scanner rules/config/pins/workflows หรือสร้าง broad path/content ignore.
2. Plan: เพิ่มไฟล์ exception registry ใน allowlist พร้อม reason/owner approval/evidence
   ตาม existing schema. ไม่แก้/ลบ occurrence เพื่อกลบ historical finding ไม่ rewrite Git
   history หรือ force push. ตรวจ parser/policy contracts ที่เกี่ยวข้อง และ rerun Security
   บน candidate ใหม่ด้วย config digest ใหม่หลัง commit/push ที่เจ้าของอนุญาตแล้ว.
3. Validation RV-01/08: policy registry เปลี่ยนได้เฉพาะ identity นี้; RV-09 ต้องผ่าน fresh
   secrets/aggregate/required CI บน final head/base. Re-evaluate full-template scan ภายใต้
   policy digest ใหม่; reuse install/build/browser proofs เพราะ lock/source/harness ไม่เปลี่ยน.
   RV-10 ยัง pending post-merge และ native alert readback ตามเดิม.
4. ปิด NC-SEC-REF-02 ด้วยคำอนุมัติแล้วแก้ requirements/plan/validation ก่อน registry.
   หากพบ identity อื่นต้องเสนอแยก ไม่ให้การอนุมัตินี้ขยายไปเอง.

Proposed entry ด้านล่างเป็นข้อเสนอ ยังไม่เพิ่มลง registry; approval text จะอ้างคำตอบ
เจ้าของที่เกิดขึ้นจริงเท่านั้น:

```json
{
  "kind": "secret",
  "identity": "d84148a55a1db82c511520b0a40131229292c3c7c1fadf8d00f66a6cbbefe8b0",
  "resolution": "false_positive",
  "reason": "Verified SHA256 fingerprint of public tools/security/secrets.py source, not a credential.",
  "approval": "PENDING OWNER APPROVAL — NC-SEC-REF-02",
  "evidence": "specs/features/2026-11-06-security-reference-dependency-remediation/evidence/checksum-exception-proposal.md"
}
```

ผลกระทบ: เพิ่ม exception แบบผูก exact occurrence/commit/blob ตามระบบเดิมหนึ่งรายการ;
ไม่ได้ยกเว้น secrets ใหม่จริงหรือ occurrence ใหม่. ต้นทุนคือ Security CI ต้องรันใหม่
เพราะ configuration digest เปลี่ยน. หลักฐาน failed run นี้คงตามจริง ไม่ rerun เพื่อหวังผ่าน.

## ทางเลือก

- **อนุมัติ exact exception และ amendment (แนะนำ):** รักษา full-history scanner และ
  ความตรวจสอบย้อนหลัง แล้วตรวจ final candidate ใหม่.
- **ไม่เพิ่ม exception:** คง PR Blocked; ลบบรรทัดใน current tree อย่างเดียวไม่ลบ
  historical occurrence. ทางเปลี่ยนประวัติ/เปลี่ยน branch ต้องเสนอและขออนุมัติแยก.

## จุดหยุดและขั้นถัดไป

ต้องรอตัดสินเพราะ approved RR-6 คง exceptions เดิม และ security policy กำหนดให้
เจ้าของอนุมัติแต่ละ identity. AGENTS.md ระบุให้หยุดเมื่อเปลี่ยนข้อกำหนดที่อนุมัติแล้ว.
ระหว่างรอ ติดตาม original push/PR CI เดิมจนจบต่อได้; ยังไม่แก้ registry/commit/push
amendment/merge PR นี้. ผล CI ภายหลังจะรายงานพร้อม run URLs และ SHA ใน PR body.

## Owner decision

2026-11-06 เจ้าของเลือก **อนุมัติ exact exception และทำต่อ (แนะนำ)** ในคำถาม
NC-SEC-REF-02 ที่ระบุ identity ด้านบนและการขยาย requirements/plan/validation.
ข้อความ PENDING ใน proposed entry เป็น proposal history เท่านั้น; registry entry
จริงต้องอ้างคำอนุมัตินี้. ข้อจำกัด exact identity/no broad ignore และขั้นตรวจรับคงเดิม.
