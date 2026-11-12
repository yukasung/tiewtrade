# Compact Paper / Spot / Futures header — Local checkpoint

วันที่: 2026-11-12 (Asia/Bangkok)
สถานะ: **Ready for Code Review — รอ review code/owner acceptance/required CI**
อ้างอิง: [Approved amendment](../compact-market-navigation-amendment.md),
[validation](../validation.md), [candidate ก่อนหน้า](settings-status-checkpoint.md)
Branch `feature/responsive-top-navigation` จากmain `afb2adb`; ยังไม่commit/push
Frontend fingerprint `f572103a7d24`; private per-file manifest/runner/config/images
อยู่ `frontend/test-results/navigation-runtime/` ไม่ใช้baseSHAแทนimplementationcommit

## Implementation

- Menu labels Paper→`/paper/trade`, Spot→`/live/trade` เดิมทั้งth/en; Futuresเป็น
  shared Button disabled/aria-disabled/titleแปลได้ ไม่มีhref/onClick/route/API
  ไม่พัฒนาFutures engineและไม่เปลี่ยนLive unavailable/financial/authorization gates
- ลบbrand mode badge/import/calculationในAccountHeader คงTradingWorkspace Badge
  PAPER/LIVEเดิมและactive links. Headerสูง64pxdesktop/56pxcompactแบบborder-box
  primary controls/icon buttonsยังมีclick targets>=44px และ Settingsขวาสุด
- ResizeObserverเผยแพร่measured heightที่workspace root พร้อมcleanupค่าเดิม;
  header/menu/Settings/trade barใช้propertyเดียวกัน ไม่เพิ่มglobalpersistentstate
- Sticky trade barอยู่ใต้global headerและเหนือchart/form/orders scroll containers
  ใช้overflow:clipที่workspaceเพื่อรักษาขอบและไม่สร้างscroll ancestorที่กักsticky
  ไม่มีการเปลี่ยนDOM/props/financial stateของฟอร์มหรือTradingWorkspace

## Verification

- Vitest7ไฟล์ **102Passed (4.46s)**: AccountLayout/AccountNavigation/AccountSession/
  KillSwitchControls/TopNavigation/PaperTradePage/CompactMarketNavigation
  รวมlabel/route/current/disabled Futures,modeBadgeในworkspace,formdraftผ่านmenu/resize,
  financial/key/owner/recovery/storage assertionsเดิม
- `npm run typecheck`, `npm run build`: Passed; full ESLintรอบแรกพบเฉพาะtestใหม่ใช้
  bare localStorage เปลี่ยนเป็นwindow.localStorageตามpatternเดิม แล้วscoped ESLintผ่าน
  typecheck/buildหลังsticky CSSปรับเพิ่มผ่าน; warningbundle>500kBเดิมยังมี
- Browserรอบแรก **12Passed (36.5s)**: 6width375/768/1024/1279/1280/1440 ×th/en×light/dark,
  geometry/colors/48screenshots,brandไม่มีmodebadge,header64/56,Settingsขวาสุด,
  Futuresdisabledไม่มีhrefและTabข้าม,menu/focus/dialog/unknownretry/storagewarnings
- เพิ่มproofจอเตี้ยและตรวจsticky CSS adapter: trade-only **4Passed (10.6s)**
  Paper/Spotทั้ง375×900,1024×900,1440×900และ1024×480; รวม **13distinct browser cases Passed**
  ทุกmodeBadgeยังเห็นขณะscroll,menuไม่replaceformnode,nohorizontaloverflow
  และไม่มีfinancial POSTจากการnavigate/scroll/เปิดSettings
- ใช้real authenticated fixture+STOP/status/empty public catalog fixtures; tradepages
  แสดงexisting unavailable guardsตามข้อมูลที่ยังไม่พร้อม ไม่ใช้UIproofแทนfinancial
  backend/concurrency correctness และไม่ส่งคำสั่ง owner/Live orders
- เก็บbrowserรอบแรกใน`market-round1-results`,trade rerunใน`results` โดยคงประวัติเดิม
  ไม่มีfailed browser candidateในamendmentนี้; ESLintfailureข้างต้นคงตามประวัติจริง

## Cleanup และรายการค้าง

Fixture DBใหม่ `tiewtrade_e2e_navigation_market_20261112`,bootstrap/migration0066เดิม;
API8018/Vite5188,workers1/retries0/timeout/assertionsเดิม หลังจบปิดtestserversและลบ
เฉพาะfixtureDBแล้ว ไม่หยุดcontainers/flushRedis/เปลี่ยนฐานเจ้าของหรือเริ่มfinancialworkers
Local5173รับsourcebranchนี้ผ่านHMR รีเฟรช `http://127.0.0.1:5173/paper/trade`

NAV-V26–28 Passed(local); V29 Partial(localPassed/requiredCINotRun).
Owner visual acceptance,review/refactorและrequiredCIยังค้าง; F17FullValidationไม่เปลี่ยน
ขั้นถัดไป: แจ้งReady for Code Review และรอ `review code`; ไม่Gitpublicationเอง
Reviewerควรเน้นmode-cue sticky/scroll/stacking,disabled FuturesและLive gatesเดิม
