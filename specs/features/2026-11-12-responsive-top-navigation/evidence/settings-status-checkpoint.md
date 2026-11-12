# STOP status inside Settings — Local checkpoint

วันที่: 2026-11-12 (Asia/Bangkok)
สถานะ: **Ready for Code Review — รอ review code/owner acceptance/required CI**
อ้างอิง: [Approved amendment](../settings-status-amendment.md), [validation](../validation.md),
[หลักฐานก่อนย้ายสถานะ](stop-actions-checkpoint.md)
Branch `feature/responsive-top-navigation` จากmain `afb2adb`; ยังไม่commit/push
Frontend fingerprint `65d6c13cbb87`; per-file manifest/runner/config/private artifacts
อยู่ `frontend/test-results/navigation-runtime/` ไม่ใช้baseSHAแทนimplementation commit

## Implementation และขอบเขต

- StopControl status/warnings อยู่ในsectionPaper/LiveของSettingsร่วมกับactionsเดิม
  ปิดSettingsแล้วสถานะ/alertsไม่รับfocusหรือปรากฏนอกเมนู เปิดใหม่อ่านqueryล่าสุดได้
- ถอดreadouts wrapper/mode labelซ้ำและCSSที่ไม่มีconsumer; compactเหลือheaderแถวเดียว
  Settingsขวาสุด, popup/main menuยังใช้measured header heightและscrollเองเมื่อข้อความยาว
- StopControl hooks/query/mutation/recovery/attemptKey/owner keysไม่ถูกย้ายหรือสร้างซ้ำ
  StopSummaryModalอยู่นอกhidden surfaceและคืนfocusSettingsตามเดิม
- ไม่เปลี่ยนbackend/API/schema/session/financial/journal/resume/Live capability/
  dependencyหรือCIpolicy และไม่เพิ่มnotificationสำเนานอกเมนู

## หลักฐานและประวัติผล

- Vitest5ไฟล์เดิม **65Passed (2.42s)**; เพิ่มcase query updateขณะSettingsปิดและ
  ตรวจเปิดใหม่ด้วยreal QueryClient: TopNavigation **20Passed (2.02s)**
  รวม **66 distinct targeted cases Passed** บนsourceนี้
- รักษาassertionsเงิน/receipt/key/จำนวนPOST/owner switch/late recovery/Paper–Live
  และstorage fault6cases ปรับการเข้าถึงสถานะ/alertsให้เปิดSettingsตามUIที่อนุมัติ
- `npm run lint`, `npm run typecheck`, `npm run build`: **Passed**;
  scoped ESLint/typecheckหลังเพิ่มtestsผ่าน; buildมีwarningbundle>500kBเดิม
- Browser9casesรอบแรก: **8Passed/1Failed (30.8s)**. กรณีlong storage warningคาด
  error-700 แต่ shared `.app-theme [role="alert"]:not(.ui-alert)` กำหนดerror-600เดิม
  ตรวจเทียบtemplate/paletteแล้วแก้เฉพาะtest expectedเป็นrgb(217,45,32)
  ไม่เปลี่ยนproduction rule/timeout/assertionsเงินหรือเกณฑ์ให้ผ่าน
- Rerunเฉพาะcaseที่ล้ม: **1Passed (6.1s)**; รวม **9 distinct browser cases Passed**
  เก็บroundแรกใน`status-round1-results` และรอบทดแทนใน`results`; ไม่ลบผลFailed
- Browserครอบ375/768/1024/1279/1280/1440px ×th/en ×light/dark,48ภาพnavigation+
  Settings,computed geometry/color/hit tests; status/alertsไม่อยู่นอกเมนูเมื่อปิด,
  Settingsขวาสุด,tab/focus/menu/dialog/resize/unknown retryและkeyเดิมผ่าน
- Long warningที่375×320px:สองmodeอ่านได้จากpopupที่scrollเอง,สีerror600ตามshared
  style,hiddenเมื่อปิด,คืนfocusSettingsและไม่มีSTOP POSTจากการเปิด/ปิด
- Dedicated risk-limits E2Eปรับselectorให้เปิดSettingsก่อนอ่านstatus/alerts;
  คงbusinessassertionsเดิม ชุดเต็มยังรอrequiredCI ไม่ใช้UI fixturesแทนfinancial proof

## Environment, cleanup และรายการค้าง

Fixture DBใหม่ `tiewtrade_e2e_navigation_status_20261112`, migration0066เดิม;
API8018/Vite5188, workers1/retries0และtimeoutเดิม ใช้auth/sessionจริงบนfixture
กับinterceptedSTOP/statusเพื่อพิสูจน์UI ไม่มีfinancial worker/Live orders/คำสั่งใน
บัญชีเจ้าของ. หลังจบปิดserversทดสอบและลบเฉพาะfixtureDBแล้ว ไม่หยุดcontainersหรือflushRedis
Local5173ยังรับsourceจากbranchนี้ผ่านHMR รีเฟรช
`http://127.0.0.1:5173/paper/trade` เพื่อทดสอบด้วยมือได้

NAV-V22–24 Passed(local); V25 Partial(localPassed/requiredCINotRun).
V18–21ที่อ้างตำแหน่งstatusด้านนอกเป็นประวัติcandidateก่อนหน้าและถูกแทนแล้ว
Code review/refactor/owner visual acceptance/requiredCIยังค้าง; F17FullValidationไม่เปลี่ยน
ขั้นถัดไป: แจ้งReady for Code Review และรอ `review code`; ยังไม่Git publicationเอง
