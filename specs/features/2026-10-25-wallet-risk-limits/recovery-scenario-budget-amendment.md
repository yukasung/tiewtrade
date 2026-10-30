# F18-R26 — Separate positive-cycle and recovery-scenario progress budgets

สถานะ: Approved — เจ้าของตอบ “approve” วันที่ 2026-10-29
วันที่: 2026-10-29

## ผลทบทวนเกณฑ์จากแหล่งจริง

F15validation§5/บรรทัด206–239 กำหนดcycle5คำสั่งและ60sเป็นharnessprogressbound
“ไม่ใช่ production order timeout”. F18profile_workload.Fixture.cycle เพิ่ม
breach_reset (breach/stop/recoveryprice/RESET/20sequentialNEWs),correctionและRESET
เข้าไปในcycleแรกของselectedowner. run_scheduled_cycles ยังครอบทั้งหมดด้วย60s.
F18plan:471อนุมัติชัดว่ารวมexistingF18scenarioใน60sด้วย จึงเป็นapprovedcontract
ที่กำลังเสนอปรับ ไม่ใช่หลักฐานว่าimplementationฝ่าฝืนแผนหรือF15timeoutไม่จำเป็น.

R25W1ล่าสุดbaseline2000ผ่าน แต่60sหมดที่selectedowner→breach_reset→new→request
รอAPIpool;มี370completed/46cycles. ParentAPIpeak15เต็มconfiguredcap.
ยังไม่รู้ว่ารายการNEWใดรอกี่วินาทีและแต่ละช่วงใช้เท่าไร. จึงไม่อาจรับรองว่า
เปลี่ยนงบเวลาอย่างเดียวจะแก้poolcontentionหรือทำให้ผ่าน.

## ทางเลือกและข้อเสนอ

| ทางเลือก | ผลต่อการพัฒนา/ผู้ใช้ | ข้อจำกัด |
|---|---|---|
| คง60sรวมทุกงาน | ต้องลดเวลารวมcaseใหญ่ให้<=60sภายใต้โหลดเดิม | ต้องระบุpoolholderและแก้ต่อ เวลาจบยังไม่ทราบ |
| แยกงบของbatchพิเศษ (เสนอ) | เกณฑ์ผูกกับภาระงาน5commandsกับreseed20รายการแยกกัน | ยอมให้recoverycaseรวมช้าขึ้น และยังต้องพิสูจน์load/ทุกdeadlineอื่น |
| เพิ่มdeadlineทุกcycle/ทุกrequest | ขยายการยอมรับเวลารอทั้งระบบ | ไม่แนะนำเพราะเกินปัญหาcaseเฉพาะและอาจกลบคำสั่งค้าง |

เสนอเฉพาะ F18 integrated profile:

1. ทุกcycleปกติยัง60s. First selectedowner cycle ยังคุมเวลาส่วนปกติทั้งหมด
   **<=60s เมื่อหักเฉพาะเวลาของbreach_resetที่ระบุไว้**. ห้ามหักเวลารอAPIpool/
   SQL/lockที่อยู่นอกphaseนี้ หรือหักfaultใหม่เอง.
2. เฉพาะphasebreach_resetครั้งเดียวต่อrun มีงบรวม **<=120s** เริ่มจากเปลี่ยน
   ราคาให้breachจนreseeding20รายการacceptedครบ. ภายในphaseยังใช้boundเดิม:
   latch/stopwait30s,recoveryprice10s,แต่ละrequest/mutation60sตามimplementationเดิม.
   ห้ามพัก/ต่อclockเมื่อAPIpoolbusy. บันทึกเวลาแต่ละstageและแต่ละreseedrequest.
3. First selectedcycleจึงมีouterguardสูงสุด180s (60+120) พร้อมตรวจnormalelapsed
   <=60sแยกจริง ไม่ใช่ให้180sกับfivecommandsได้ตามใจ. CorrectionและendRESET
   ยังอยู่ในnormalelapsedตามเดิม. Phaseล้ม,requestล้ม,หรือnormalส่วนเกินล้มทันที.
4. 120sเป็นข้อเสนองบวิศวกรรมสำหรับtestrecoverybatch ไม่ใช่BinanceSLAหรือค่าที่
   พิสูจน์ว่าปลอดภัย/จำเป็นจากข้อมูลปัจจุบัน และไม่ใช่productionorderexpiry.
   Ownerต้องยอมรับว่าการตรวจรับจะอนุญาตcaserestore20ordersนี้ถึง2นาที.
5. ไม่เปลี่ยนF15standalone/F16publiccontract;ไม่เพิ่มAPIpool/connections/workers/
   CPU/RAM; ไม่เปลี่ยนriskR25(99.9%<=3sต่อowner/ทุกinput<=5s),processing500ms/1s,
   publicationfreshness,stopcompletionboundsและfinancialfences/idempotency.

## รักษาความหมายของ workload

- ยังคง100owners×20baseline, source10Hz, commands10/100/10s และ600/300/1800s.
  ไม่ย้ายriskcaseไปทำตอนidle/ก่อนmeasurement ไม่พัก99ownerอื่นเพื่อช่วยselectedowner.
- ไม่เลื่อนdue timesของownerอื่น ไม่เอา20reseedไปนับแทนpositive5commands ไม่ลด
  expectedcounts/cycles. Selectedownerยังต้องทำcycleถัดไปตามscheduleและจบครบ.
- คงmeasurementduration/minimumsourcecadence/finalelapsed<=duration+60sและdrain60s
  เดิมทั้งหมด. หากcaseพิเศษทำให้ป้อนโหลด/จบงานไม่ทัน ยังFailed ไม่ขยายtailอีก.
- ทุกreadyinputรวมในriskoracle,lateinputs/unacknowledgedเก็บครบ; รายการพิเศษ
  ต้องมีstage/identity/timeหลักฐาน มิฉะนั้นไม่สามารถหักphaseelapsedได้.

## ขอบเขต implementation/test หลังอนุมัติ

แก้เฉพาะF18caseกับtest-harnesscallbackสำหรับbudget;reuseF15scheduler/positive
oraclesและเดิมFixture.breach_reset. F15default60sต้องคงเดิม ไม่มีproductionruntime
changeที่วางแผนไว้. ออกแบบbudgettrackingให้วัดเวลาจริงและรับcancellation;
ไม่ใช้การตัดlatencyในprocessing/riskmetricsเพราะแยกงบcycle.

Targeted testsพิสูจน์normal61sต้องfailแม้recoveryสั้น,recovery121sต้องfail,
caseหนึ่งเดียวรับbudgetเพิ่ม,ordinaryowners/defaultF15ยัง60s,ไม่มีworkloadpause/
counterdrop,stageerror/cancelไม่ทิ้งtask/connection. ใช้controllableclock/barriers
แทนunit-testนอน60–180s. ตรวจpool/querycontractsที่เปลี่ยนและstaticตามdiff.

ประมาณการเบื้องต้น15–30minสำหรับharness/targetedchecks ไม่รวมunknownbugs;
เมื่อผ่านให้รันnativeW1ครั้งเดียวประมาณ15–20minรวมsetup/analysisตามรอบก่อน.
ถ้ารายการเดี่ยวค้าง60sหรือW1ล้มเกณฑ์อื่น ต้องหยุดเก็บหลักฐาน ไม่เพิ่มdeadline
หรือรันซ้ำอัตโนมัติ. W2/W3/W4ยังเป็นด่านเดิมหลังW1ผ่าน ไม่ถือว่าทั้งF18ผ่านจาก
amendmentหรือผลเก่า. อาจยังต้องแก้APIpoolcontention;ไม่รับประกันผล/วันปิดงาน.

## Approval boundary

อนุมัติเฉพาะ120sสำหรับone recoveryphase,60snormalexclusiveและ180souterguard
พร้อมทุกเงื่อนไขข้างต้นก่อนแก้plan/validation/harness. คำสั่งทบทวนไม่ได้เลือก
ตัวเลขใหม่นี้แทนเจ้าของ. No runtime/tests/workload modified by this review.


Owner approved R26 before implementation on2026-10-29; old failures retained.


## Implementation/result — 2026-10-29

ApprovedR26implemented;targeted56/staticpassed. OneW1failedtheunchangedordinary
60sboundduringendRESET,selectedrecoverycancelledbeforeits120sbound. Preserve
R26asapprovedcontract,notarevertedexperiment;noacceptancepass/retryclaimed.
SeeM5forcounter/stageevidenceandunresolvedextraRESETloaddefinition.
