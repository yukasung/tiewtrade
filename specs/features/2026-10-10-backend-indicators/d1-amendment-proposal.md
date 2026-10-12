# F-11 — ข้อเสนอปรับ R2-D1 สำหรับ first release

สถานะ: **Approved** — เจ้าของยืนยัน first-release baseline และอนุมัติเกณฑ์แทนด้วยคำสั่ง “approve” เมื่อ2026-10-11
วันที่: 2026-10-11

## ปัญหาและเงื่อนไขการใช้ข้อเสนอนี้

R2-D1เดิมต้องใช้ legacy F-11 full-scan binary ที่มี v1decoderเดิม แต่ artifacts
ที่ตรวจพบมีเพียง pre-F-11/F-09 และ compatible/prepared snapshots.
Git HEADก่อนbranchนี้คือF-10ที่mergeแล้ว ไม่มีF-11 releaseในประวัติที่ตรวจ.
ข้อเสนอนี้ใช้ได้เมื่อเจ้าของยืนยันว่า **ไม่เคยdeploy F-11 full-scan รุ่นเดิมให้ผู้ใช้**
และไม่มีoldF-11replica/tokenที่ต้องรองรับนอกinventoryที่ตรวจ
ถ้ามีdeploymentดังกล่าว ต้องหาartifactจริงและใช้R2-D1เดิม

## เกณฑ์แทนที่เสนอ

1. ใช้ immutable pre-F-11 API/F-09 imageจริงบนexpanded schema ก่อน strict proof;
   ตรวจ health/auth/F-09 read/write/cleanupเดิมทำงาน และindicatorrouteยังไม่มี
2. รัน compatibleF-11สองprocess/imagesจริงในLEGACY: v1page1/continuation
   A→B→Aและหลังrestartตรงfullscanreference/digest; ไม่ใช้decoderstub
3. ก่อนstagegateไม่มีv2issuanceหรือbuilderclaim; oldF-09cleanup365วันต้องอยู่ได้
   เฉพาะก่อนstrictproof และ inventoryที่ขาด/offline/restartoldimageบล็อกactivation
4. ผ่านdrain/verifiedstopก่อนproofinstall แล้ว restartเฉพาะcompatibleimages;
   ใช้D2..D7เดิมต่อโดยไม่ผ่อนcursor/proof/key/grace/fencing/resourcecriteria
5. บันทึกimageIDs, schema/mode/epoch, routing/HTTP/claimtrace และnegativecontrols
   ร่วมกับคำยืนยัน first-release ของเจ้าของในevidence bundle

## ข้อจำกัดที่ยอมรับเมื่ออนุมัติ

ไม่รับรอง mixed paging กับoldF-11binaryที่ไม่เคยdeploy และไม่มีartifactให้ทดสอบ.
หลักฐานจะรับรองfirstreleaseจากpre-F-11ระบบและcompatibilityของv1ในreplicasที่ส่งมอบ.
ไม่เปลี่ยนD1เป็นPassedก่อนรันเกณฑ์แทน ไม่ใช้ผลนี้เปิดPREPAREDหรือปิดC/D gatesอื่น

การอนุมัติมีผลให้ปรับ requirements/plan/validation/performance-plan-v2 และrunbook
ให้ระบุแทนR2-D1เดิมก่อนลงมือharness; ขณะนี้D1ยังPendingจนรันเกณฑ์แทนครบ ไม่ถือว่าapprovalเป็นผลPassed
