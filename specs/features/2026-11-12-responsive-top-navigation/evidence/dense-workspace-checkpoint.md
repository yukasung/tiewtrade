# Borderless header and dense chart workspace — Local checkpoint

วันที่: 2026-11-12 (Asia/Bangkok)
สถานะ: **Ready for Code Review — รอ review code/owner acceptance/required CI**
อ้างอิง: [Approved amendment](../dense-trading-workspace-amendment.md),
[validation](../validation.md), [candidate ก่อนหน้า](compact-market-checkpoint.md)
Branch `feature/responsive-top-navigation`, main base `afb2adb`; ยังไม่commit/push.
Frontend fingerprint `9755979f42c4`; private per-file manifest/runner/config/screenshots/
traceอยู่ `frontend/test-results/navigation-runtime/`. Base SHAไม่ใช่implementationcommit.

## สิ่งที่เปลี่ยน

- Header theme/account/Settings/hamburgerไม่มีกรอบ/shadow/defaultbackground,
  glyph20px/targets>=44px; header64pxdesktop/56pxcompactและSettingsขวาสุดเดิม.
  คงtemplate hover/focus-visible/disabled states; stylesจำกัดheader controls.
- ลบBadgeหน้าคู่เทรด/importที่ไม่มีconsumerในTradingWorkspace. DesktopactivePaper
  หรือSpotพร้อมคำกำกับLiveและcompact triggerPaper/Liveแสดงโหมดจากrouteปัจจุบัน;
  ไม่มีbadgeข้างbrandและไม่เก็บmodeสำเนาในpersistentstate. Futuresdisabledเดิม.
- Tradeouterpadding4px/panelgap4px/toolbarและformpadding8px. คงform22.5rem;
  chart/ordersใช้สัดส่วน4:1พร้อมordersขั้นต่ำ10remและscroll. หน้าไม่มีordersใช้
  chartพื้นที่ที่เหลือ. Heightอิงviewport/measuredheader/insetแทนoffsetเก่า;
  shortdesktopมีminimum37remและbodyเลื่อนได้, stackedchartขั้นต่ำ420px.
- ตัดinnergutter/nestedchartborder; flexframe/canvasเติมchartcolumnจริง ใช้renderer
  autoSizeเดิม ไม่แก้renderer/data/viewport/financial/API/schema/session/authorization.
  Account/securityspacingไม่เปลี่ยน; ข้อยกเว้นtemplateอยู่ในamendmentที่อนุมัติ.

## ผลตรวจ

- Vitest **142distinct tests / 9 files Passed**: AccountLayout, AccountNavigation,
  AccountSession, KillSwitchControls, TopNavigation, PaperTradePage,
  CompactMarketNavigation, CandlestickChartPanel, chart-renderer.
  ชุด8ไฟล์128testsผ่าน5.02s; renderer14ผ่าน1.38s; หลังเพิ่มLiveข้อความกำกับ
  ตรวจCompactMarketNavigation6testsทดแทนผ่าน1.73s ไม่รวมซ้ำใน142.
  คงfinancial/key/owner/Paper–Live/recovery assertionsเดิม.
- `npm run lint`, `npm run typecheck`, `npm run build`: **Passed**.
  Buildล่าสุด1.64s; warningchunk>500kBยังมี ไม่เพิ่มdependency/refactorนอกงาน.
  หลังเพิ่มเฉพาะE2Eerrorproofตรวจlint/typesอีกครั้งผ่าน; productioncandidateไม่เปลี่ยน.
- Browser **14distinct cases Passed** เมื่อรวมผลที่ยังvalid: geometry6width
  375/768/1024/1279/1280/1440 ×th/en×light/dark; header64/56,defaulttransparent,
  border0/shadownone/icon20/targets44,Settingsขวาสุด,48navigation/Settingsภาพ.
  ครอบfocus/Tab/Escape/outside/inert/scrolllock,unknownSTOP/key/pending/resize,
  detailsdialog/session/routing/longstoragewarnings375×320และPaper/Livecueขณะscroll
  รวมshortviewport1024×480. Navigation/resizeไม่มีfinancialPOST.
- Realcharttestใช้guardedisolatedDBและcandlestick `browser_fixture.py seed` เดิม:
  realhistory/API/renderer/canvas. Paperwalletreadresponse/orderslistใช้snapshotfixture
  patternจากPaperTradePage testsเพื่อให้มีorderspanel ไม่ใช้UIfixtureรับรองเงินจริง.
  ตรวจ6widthว่าframe/canvas/renderertableตรงcolumnภายใน2px,stackedheight>=420,
  desktoporders>=160และchartใหญ่กว่าorders; inset4/gap4/padding8,nohorizontaloverflow,
  legend/axes/TradingView attributionยังอยู่. คู่เทรด/timeframe/canvasnodeและdraft123.45
  อยู่ครบหลังresize. Standalonechartgutter0และframeเติมพื้นที่เหมือนกัน.
- เพิ่ม504history/livefixturesตรวจtypederror/retryทั้งstandaloneและembedded375px;
  retrytarget>=44,frameไม่ทับretry/ล้นarea. SpotpageยังdisabledsubmitและแสดงLivecue.
  FinancialPOST0ตลอดcase ไม่คลิกownerSTOP/resume/submitหรือส่งLiveorder.
- ผลmockcomponentของchartselection/viewportเดิมยังผ่าน รวมfractionalviewportหลัง
  livedrawและkeyboardselection; ไม่อ้างDOMnodeidentityอย่างเดียวเป็นviewportproof.

## ประวัติรอบตรวจและ cleanup

- `dense-browser.log`: **13Passed/1Failed (1.0m)**. Caseใหม่รอorderspanelจน30sเพราะ
  registeredfixtureไม่มีPaperwallet; candles/canvaschecksก่อนหน้านั้นผ่าน. เก็บtrace/
  contextใน`dense-round1-results`,ไม่ลบ/เปลี่ยนfailureเป็นPassed.
- แก้เฉพาะtestreadfixtureให้มีwalletscopeตามpatternเดิม ไม่แก้production/timeout/
  ลดassertions. `dense-browser-round2.log`: **1Passed (9.0s)** เฉพาะcaseที่ล้ม.
- เติมช่องว่างembeddederrorlayout/Spotdisabledproofแล้วตรวจเฉพาะcaseนั้น:
  `dense-browser-final.log`: **1Passed (11.1s)**. ผล13casesแรกใช้ต่อเพราะไม่กระทบ;
  ห้ามนับcampaignattemptsเป็นdistinctcasesเพิ่ม.
- เก็บbaselineตลาดเดิมใน`market-round2-results`; fingerprintmanifestก่อนdenseสำรองไว้.
  TestDB `tiewtrade_e2e_navigation_dense_20261112` bootstrap/migration0066,
  API8018/Vite5188/workers1/retries0/timeoutเดิม. หลังจบปิดtestservers/ตรวจportsปิด
  และdropเฉพาะfixtureDBแล้ว ไม่flushRedis/หยุดcontainers/แก้ฐานเจ้าของ.
- LocalfrontendPID7260cwdเป็นbranchworktreeนี้; GETหน้าtradeตอบ200/HMRพร้อม:
  `http://127.0.0.1:5173/paper/trade`. Owner8000/5173ไม่ถูกหยุด.

## รายการค้างและขั้นถัดไป

NAV-V30–33 Passed(local); V34 Partial(localPassed/requiredCINotRun).
NAV-V27ถูกแทนด้วยV32; คงผลเก่าเป็นประวัติcandidate. Owner visualacceptance,
code review/findings/refactorและrequiredCIบนpublishedcandidateยังค้าง.
F17FullValidation/Release/dependencyสถานะเดิม ไม่มีfinancialworkloadใหม่ในงานนี้.

แจ้ง **Ready for Code Review** แล้วรอ `review code` ตามAGENTS; ยังไม่commit/push/
เปิดPR/merge. Reviewerควรเน้นmodecueแยกPaper–Live,sharedCSS/chartresize/errorlayout
และstableSTOPrequestidentityในSettings. Localproofไม่แทนrequiredCI.
