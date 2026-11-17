# OBS-03 M1 — lag cancellation race fix

สถานะ: Fixed / affected checks Passed; รอ owner refactor
[Plan](../../observer-short-load-plan.md) / [Summary](obs03-m1-fix-summary.json)

Normal lag shutdown ใช้ stop Event ไม่ใช่ cancel ดังนั้น task cancellation เป็น evidence
loss เสมอ ไม่ใช้ stop flag ตอน callback มายกเว้น เพิ่ม lag_task_completed แยกจาก joined
report ตรวจ terminal failure โดยตรงได้แม้ callback ยังไม่ทำงาน และ flush ต้องมี completed=True
คง primary exception และ default observer/W3 behavior เดิม ไม่เปลี่ยน SQL/timeout/เงิน

เพิ่ม5cases: cancelก่อนtaskเริ่ม/ก่อนclose/ให้callbackมาก่อนclose, reportก่อนcallback,
และ missing completion metadata; normalclose testยืนยัน completeจริงและNO_TRIGGERได้
170affected tests Passed รวม realPG/blocker/rollback/cancellation/default/receipt/IO paths
23.5485sรวมsetup/cleanup; Ruff/format/mypy3files/whitespacePassed
Independent proof: DB absent,0connections/0locks
Raw: validation-artifacts/f17-obs03-m1-tests-20261116/
ไม่ rerun campaign/4h/Git/CI ไม่มีแก้เกรดเดิม F17ยังPending

ขั้นถัดไป: รอ owner refactor the code ตาม AGENTS ก่อน affected validation และ
เตรียม pinned coordinator/preflight/หนึ่งSMOKEตามแผนที่อนุมัติแล้ว
