# F18-R25 — Paper acceptance aligned with product service targets

สถานะ: Approved — เจ้าของสั่ง “เริ่มทำ” หลังข้อเสนอ R25 และคำอธิบาย trade-off วันที่ 2026-10-29
วันที่: 2026-10-29

## เป้าหมายและเหตุผล

เจ้าของต้องการพัฒนาระบบให้เสร็จเร็วขึ้นหลังทดลองหลายวัน และขอพิจารณาเกณฑ์
ที่ยืดหยุ่น/เหมาะสม. ข้อเสนอนี้เปลี่ยนความเร็วที่ Paper ยอมรับ ไม่ใช่เปลี่ยน
นิยามเงินที่ถูกต้อง. เป็นproductdecision ไม่ใช่Binance requirement หรือหลักฐาน
ว่าค่าใหม่ปลอดภัย/ผ่านแน่นอน. Runtimeปัจจุบันยังใช้เกณฑ์เดิมจนอนุมัติ.

Current:100activeowners×20orders,Paperprocessingp95<=500ms/p99<=1s,
ทุกreadyriskinput<=3s,target1s. R24ทดลองFailed3/746104inputs,max3.586173s;
financialoraclePassed,processingp95352ms,p99528ms,connections44→55.
NativeW1ก่อนR24ก็Failedสูงสุด4.103704s. R24/R24-Aย้อนกลับแล้ว;
ผลR24จึงไม่ใช่หลักฐานรับรองruntimeปัจจุบัน และเกณฑ์ใหม่ไม่ทำให้ผลเก่าPassed.

## ทางเลือก

| ทางเลือก | ผลต่อผู้ใช้/งาน | ข้อจำกัด |
|---|---|---|
| คงทุกinput<=3s | คงเวลาตอบสนองเดิม ต้องหาผู้ถือlockและแก้ให้ผ่าน | เวลาจบimplementationยังประเมินไม่ได้ ไม่เสนอให้ทดลองschedulerต่อแบบเดา |
| Paper service target+hard bound (แนะนำให้เจ้าของพิจารณา) | ยอมรับtail delayแบบจำกัด ลดการผูกการรับงานกับoutlierทุกตัว | จงใจยอมให้latch/เริ่มstopจากbackgroundmonitorช้าขึ้นได้ ต้องอนุมัติข้อแลกเปลี่ยน |

## A. Proposed Paper risk service contract

- ต่อแต่ละowner และทั้งrun: **อย่างน้อย99.9%ของreadyinputs commitผล/latch<=3s**.
  วัดตรงจากจำนวนinputsที่<=3sหารด้วยexpectedinputs ไม่ใช้percentileinterpolation.
- **ทุกreadyinputต้องcommitผล/latch<=5s**. Source-ready→durablecommitยังรวม
  queue,lock,compute,commitครบ. คง1sเป็นtargetรายงานแยก.
- ตัวเลข5s/99.9%เป็นข้อเสนอความต้องการบริการ ไม่อนุมานจากผล3.586sว่าเหมาะสม
  หรือครอบทุกกรณี. ข้อมูลที่มีไม่พิสูจน์ผลต่อการเทรดจริงหรือรับประกันpass.
- เก็บdistribution/maxและรายการ>3sทั้งหมด พร้อมowner/input/ready/ack;
  รายงานcount/rate>1s,>3s,>5sแยก. เกิน5sตัวเดียวหรือเกินquota3sของownerใดล้ม.
  อนุญาตไม่เกิน0.1%ต่อowner ไม่เปิดให้ค่ารวมซ่อนกระเป๋าที่ช้าซ้ำ.
- expectedinputs/unacknowledged/clockerrorsนับครบ; ขาดackหรือข้อมูลวัดผิดเป็นFailed.
  ไม่ตัดtail,ช่วงรอหรือinputsออก. คงapprovedfaultwindows/exceptionsเดิมเท่านั้น.
- ผลต่อผู้ใช้:ระหว่าง3–5sอาจยังไม่บันทึกbreach/latchและยังไม่เริ่มstopจากผลนั้น;
  ไม่สัญญาว่าความเสียหายจำกัดตามlimitได้หากราคากระโดดหรือexecutionล่าช้า.
  Hardboundนี้ไม่ใช่stopcompletiondeadline.
- Freshness/F10,fully-fencedfinancialchecksก่อนเปลี่ยนเงิน,transientbreach,
  durablelatch,authorization,duplicateprevention,Money/Quantity,balances/positions
  และstop/retrydeadlinesเดิมคงอยู่. **Liveยัง1s/PendingDependency** ไม่ใช้เกณฑ์นี้รับรอง.

## B. Proposed connection acceptance definition

โค้ดresource_samplerใช้countของdatabaseเป้าหมายถูกต้อง แต่connections_start
เป็นsampleแรกและendเป็นsampleสุดท้าย ก่อนstop/disposeworkers. ดังนั้นend<=start+2
ไม่แยกlazy-poolgrowthออกจากleak. ยังไม่พิสูจน์ว่า55connectionsเป็นปกติหรือleak.

เสนอแทนเฉพาะF18integratedconnection-growthgateด้วย:

1. ก่อนรันบันทึกpoolinventoryต่อprocess/role ได้แก่pool_size,max_overflow,
   workersและobserverconnectionsจริง. ตรึงconnectionbudgetจากinventoryและ
   PostgreSQLconnectionheadroomก่อนรู้ผล ห้ามตั้งbudgetเป็นpeakที่วัดได้ภายหลัง.
   ถ้าinventoryยังไม่ครบ ให้Pending ไม่ใช้เลข55/60เป็นเกณฑ์เดา.
2. ระหว่างรันcountทุกsampleต้องอยู่ในbudgetนั้น ไม่เพิ่มworkers/pools/ทรัพยากร
   เพื่อทำให้ผ่าน. เก็บstart/end/peakเป็นmetricsต่อไป และรายงานpooltimeouts/errors.
3. หลังdrain,stopworkersและdisposeทุกengineแล้ว ภายใน5sต้องไม่เหลือappclient
   connectionsของisolatedrunDB. Queryผู้ตรวจเองและobserverที่ระบุPIDไว้ล่วงหน้า
   แยกนับอย่างชัดเจน ไม่ยกเว้นทั้งroleเพื่อซ่อนconnectionที่ค้าง. ถ้ายังเหลือล้ม.
4. W3ยังตรวจmemory/resourceและprogressเดิม; connectionที่โตแต่ไม่เกินpoolไม่ใช่
   หลักฐานว่าระบบไม่มีleak. ต้องตรวจcheckout/returnและpendingtransactionsที่ค้าง
   เมื่อdrainให้ครบ. กฎเงินและresourcegatesอื่นไม่ผ่อนตามข้อเสนอนี้.

ขั้นpoolinventory/ตรวจcleanupใช้codeและหลักฐานเดิมก่อนเสนอruntimefix ไม่แก้
productionpoolตามข้อเสนอนี้. F15standaloneเดิมไม่เปลี่ยน.

## แผนหลังอนุมัติและเวลา

- แก้requirements NC-F18-05,plan,validationก่อนoracle:Papercontractใหม่และ
  connectiondefinition. เก็บทุกFailed/Partialเดิม. ไม่ฟื้นR24หรือปรับschedulerเพิ่ม.
- ใช้sla_summary/inputs/ack/everyowneroraclesเดิมและresource_samplerเดิม
  (`backend/tests/infra/risk_limits/profile_workload.py`,
  `backend/tests/infra/execution_market/profile_workload.py`); F18-specificverdict
  ใช้contractใหม่,F15verdictคงเดิม. เพิ่มเฉพาะbudgetinventory/cleanup evidenceที่ขาด.
- Boundarytests:exact3/5s,quotaต่อowner,missingack,clockerror,smallowner sample,
  faultwindows; connectionsbudget/knownobserver/cleanup/nonreturningconnections.
  ตรวจsafetyตามdiff/callers ไม่มีproductionfinancialruntimechangeที่วางไว้.
- เตรียมspec/oracleและtargetedchecksประมาณ15–30minเบื้องต้น ไม่รวมแก้บั๊กที่ยังไม่ทราบ;
  แจ้งประเมินใหม่ก่อนรันจริง. ไม่รันfullregressionซ้ำโดยไม่มีผลกระทบที่ต้องพิสูจน์.
- ใช้candidateเดิมที่ย้อนR24แล้ว ไม่เพิ่มdiagnosticperformance trialเพื่อหาpass.
  เมื่อreadinessและขั้นreviewที่ได้รับคำสั่งครบ จึงW1→W2→W3→W4ตามเดิม;
  W1–W3ช่วงวัดบังคับ45minบวกsetup/cleanup. แจ้งเวลารวมแต่ละชุดก่อนเริ่ม.
- Failureที่ล้มgateให้หยุดเก็บหลักฐาน ไม่รันซ้ำอัตโนมัติ. เกณฑ์ใหม่ไม่ได้อนุมัติ
  ให้เรียกPaperผ่านจากผลเก่า หรือF18CompletedขณะV22/V23ยังPendingDependency.

## Approval boundary

ต้องอนุมัติA(99.9%<=3sทุกowner,ทุกinput<=5s)และB(connectionbudget+cleanup)
ก่อนแก้requirements/plan/validationและoracles. การขอให้พิจารณาความยืดหยุ่นยัง
ไม่ใช่การเลือกตัวเลขเหล่านี้. เจ้าของอนุมัติด้วยคำสั่ง “เริ่มทำ” วันที่2026-10-29; การแก้spec/oracleตามขอบเขตA/Bอนุญาตแล้ว.


Owner approval2026-10-29 applies A/B above. Proceed with spec/oracle implementation; retain old failure evidence and all financial gates.
