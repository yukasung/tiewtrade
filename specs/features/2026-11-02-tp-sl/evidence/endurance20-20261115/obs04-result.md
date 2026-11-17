# OBS-04 — refactor and one scheduled-load diagnostic

สถานะ: Diagnostic Complete / workload Passed — ไม่เกิด sampler timeout ซ้ำใน5นาที
วันที่: 2026-11-16

## Refactor / validation

รวมcleanup negative testsสองฟังก์ชันเป็นตาราง5casesเดียว คงexception identity,
cleanupครบและnotesไม่เผยprivateข้อความ. Runtimeไม่เปลี่ยน.
7affected tests(M1สอง/M2ห้า)และRuff/format/mypyPassed; reuse165realPG/regressionsจากM1–M2.
CoordinatorreuseOBS03โดยhelper ASTเหมือนเดิม เปลี่ยนownednames/receipts/flag/config
เฉพาะOBS04. Pin source/config/migrations/copiedrunnerก่อนpreflightและsource unchangedหลังจบ.

## One approved campaign

[Summary](obs04-result-summary.json). Raw `validation-artifacts/f17-obs04-smoke-20261116/`.
Preflight7/7Passedก่อนfixture. Total458.000s (7m38s), measured300.001s,
final-tail0.570s;20owners/400baselineorders/600offered-admitted-completed/0rejected,
240fills/120cancels/120replays/120cycles. Bookinputs3000/3000.
Global invariants/resource/poolcontractPassed; transactionp95=102.457ms/p99=149.190ms.
ผลเหล่านี้เป็นdiagnosticมีobserveroverhead ไม่ใช้แทนperformance/enduranceacceptance.

Scheduled samplerครบ10/10 RETURNED, taskcompleted/joined; offsets15..285sจริง,
startlatenessสูงสุด1.190ms. Cold firstรวมspans64.446ms; reused9captures5.963–14.305ms.
Activityfirst/max22.964ms/median1.948ms; checkoutfirst32.685ms/reusedต่ำกว่าfirst.
ทุกช่วงรวมdriver/network/scheduling; sessionexitไม่ใช่servercommitล้วน.
Natural monitor0triggers/0errors;3057publicationsRETURNED. ไม่อ้างfixturePID/tickเป็นpublisherstall.
ไม่มีหลักฐานจากรอบนี้ว่าปัญหาหลัง32นาทีของW3ถูกแก้ หรือcollectorไม่อาจtimeoutอีก.

## Cleanup / stop

Independent audit: DBabsent/0connections/0locks, ownedRedisabsent,
20workerPIDreceiptsไม่ทำงานแล้ว. ไม่หยุดบริการอื่น/force drop.
คงW3OBS01Incompleteและผลก่อนหน้าทั้งหมด; fullW3financial/rebuild/Releaseยังค้าง,
F17ไม่Completed. หนึ่งcampaignที่อนุมัติใช้แล้ว หยุด/report ไม่มี4h/Git/CI/merge.
ขั้นถัดไปควรจัดทำแผนเก็บtimingในช่วงยาวที่ครอบคลุมหลังworkerrestartของW3
เพื่อแยกเหตุการณ์สะสม/ช่วงrestartจากbaseline5นาที ไม่รันSMOKEเดิมซ้ำโดยไม่มีสมมติฐานใหม่.
ต้องอนุมัติขอบเขตรอบถัดไปก่อนทดลองตามจุดหยุดOBS04; ยังไม่เริ่มรอบเพิ่ม.
