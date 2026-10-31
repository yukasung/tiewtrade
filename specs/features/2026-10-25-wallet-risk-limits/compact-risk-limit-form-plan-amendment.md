# F18-UI — ฟอร์มเพดานขาดทุนแบบสั้น — Plan Amendment

สถานะ: **Approved — เจ้าของตอบ “approve plan and validation amendment” วันที่ 2026-10-30**
วันที่: 2026-10-30
อ้างอิง: [Requirements Amendment](compact-risk-limit-form-requirements-amendment.md)
**Approved 2026-10-30**

## 1. แนวทาง

ปรับเฉพาะ frontend composition ของ `RiskLimitPanel` จาก summary/actions หลายชั้นเป็น
controlled form หนึ่งช่อง. คง `useDurableAttempt`, journal, query keys, API paths,
TOTP header adapter, stop-effects reader และ server snapshot เดิมทั้งหมด.

ฟอร์มเลือก action จากค่าปัจจุบันโดยใช้ parser ข้อความทศนิยมแบบ pure ซึ่งแปลงเป็น
integer coefficient scale 18 ด้วย `BigInt`. ห้ามใช้ `Number`, floating point หรือ
คำนวณ Money ใน browser. Client parser มีไว้ควบคุม UX และ routing เท่านั้น; server
ยังสร้าง `Money` และเป็นผู้ตัดสิน authoritative validation.

## 2. ของเดิมที่จะใช้ซ้ำ

- `frontend/src/components/ui/{Input,Label,Button,Alert,Modal}.tsx` จาก admin template.
- `frontend/src/useDurableAttempt.ts` และ `riskLimitJournal.ts` สำหรับ durable recovery,
  exact intent/key และ no-duplicate protocol.
- `frontend/src/riskLimits.ts` สำหรับ snapshot/receipt/effects และ mutation paths เดิม.
- `RiskStopEffects` ใช้เฉพาะ contextual failure details; ไม่สร้าง stop reader ใหม่.
- `riskLimitMessages.ts` ใช้ i18n ไทย/อังกฤษเดิมและเพิ่มเฉพาะข้อความ form/draft/conflict.

## 3. State และ data flow

### 3.1 Amount parser

เพิ่ม pure helper ใกล้ risk client (แยกไฟล์เล็กเพื่อทดสอบโดยตรง) ที่:

- รับ plain decimal text เท่านั้น: optional leading `+`, digits และ decimal point;
  ไม่รับลบ, scientific notation, comma, NaN หรือ Infinity.
- ตัด whitespace รอบนอกและ leading zeros, ตัด trailing fractional zerosก่อนตรวจ scale.
- รับค่ามากกว่า 0, real decimal placesไม่เกิน18 และค่าน้อยกว่า `1E20` ให้ตรง Money
  storage contract. ศูนย์/เกินช่วง/เกิน scaleคืน invalid โดยไม่ปัด.
- คืน canonical text และ coefficient scale18 เป็น `bigint`; ใช้ coefficientเปรียบเทียบ
  กับ snapshot amount ที่ parseด้วย helperเดียวกัน.
- ไม่ export เป็น financial domain typeและไม่ใช้ทำยอด ขาดทุน หรือ PnL.

### 3.2 Draft identity

`RiskLimitPanel` เก็บ `draft`, `dirty` และ identity ของ snapshot ที่ draftเริ่มจาก
`revision + wallet_id + episode_id`:

- เมื่อ snapshot แรกมาถึงและยังไม่ dirty/ไม่มี durable attempt ให้เติม current amount.
- Polling อัปเดต draftได้เฉพาะเมื่อไม่ dirty.
- ถ้า identityเปลี่ยนขณะ dirty ให้ตั้ง `draftStale`; คงข้อความที่ผู้ใช้กรอก แสดง warning
  และปิดบันทึก. ปุ่ม contextual `ใช้ค่าล่าสุด` ล้าง draft/dirty แล้ว sync snapshotใหม่.
- หลัง terminal `APPLIED` ให้ invalidateเดิมและคง pending stateจน snapshot revision
  เท่ากับ `applied_revision`; จากนั้น sync authoritative amountและล้าง dirty.
- `REJECTED` คง draftไว้ให้แก้ ยกเว้น scope/revision conflict ซึ่งทำเครื่องหมาย stale
  และต้องรับ snapshotล่าสุดก่อนสร้าง keyใหม่.

### 3.3 Submit state machine

- Submit formด้วยปุ่มหรือ Enter; invalid/unchanged/blocked/staleไม่สร้าง UUIDหรือ journal.
- Snapshot amount `null` → `SET`; coefficientต่ำกว่า → `DECREASE`; สูงกว่า → `INCREASE`.
- `SET`/`DECREASE`: สร้าง intent/keyหนึ่งครั้ง เขียน journalก่อน POST แล้วส่งทันที.
- `INCREASE`: กดบันทึกแล้ว freeze canonical amount + snapshot identity/action ไว้ใน
  modal. ยังไม่สร้าง key/journalจนผู้ใช้ยืนยัน TOTP. หาก identityเปลี่ยนก่อนยืนยันให้
  ปิดทาง submitและกลับสู่ stale warning.
- TOTP อยู่ใน controlled fieldชั่วคราวและ `codeRef` เดิม; ล้างเมื่อ cancel, unmount
  หรือหลัง adapterอ่าน. ไม่เก็บใน intent, mutation cache, journal หรือ error.
- Reset ใช้ modal warning/actionเดิม แต่ triggerแสดงเฉพาะเมื่อ `latched=true`.
  การเพิ่มเพดานไม่เปิด resetหรือล้าง latch.

## 4. UI composition

- Card headerคงชื่อและ mode; bodyปกติมี status badgeหนึ่งตัว แล้ว formแนวนอนบน desktop
  และเรียงแนวตั้งบน mobile: Label/Input + `บันทึก`.
- Inputใช้ `type=text`, `inputMode=decimal`, `autoComplete=off`, maxLengthเดิม และ
  `aria-describedby` สำหรับ validation/status. ปุ่มบันทึกเป็น primaryเพียงปุ่มเดียว.
- ไม่ render summary grid, calculation disclosure, adjust-action modal หรือ
  more-actions disclosure.
- Loading/load error/source unavailable/pause/latch/stop problemแสดง Alertตามความจำเป็น.
  Readyปกติไม่เพิ่มคำอธิบายยาว.
- Latched alertมีปุ่ม reset contextual. หาก stopยังทำงานให้แสดงข้อความสั้น; แสดง
  `RiskStopEffects` ใน disclosureเฉพาะ `stop_alert_due`, failed count หรือ PROBLEMS.
- Pendingแสดงสถานะสั้นและ disable form. UNKNOWN/lookup errorแสดง `ตรวจสถานะ`;
  AUTHORIZATION_ONLY/retryใช้ exact attempt/keyเดิม. Request key/technical detail
  อยู่ใน disclosureเฉพาะตอนผลไม่แน่นอน ไม่ปรากฏในสถานะปกติ.
- Modal TOTP/resetใช้ shared focus trapและ return-focus refไปยังปุ่มที่เปิด modal.
- ลบ translation keysเฉพาะที่ไม่มี callerหลัง refactor; คง error/status keysจาก server.

## 5. ไฟล์และผลกระทบ

- `RiskLimitPanel.tsx`: form/draft/action/recovery compositionใหม่.
- `riskLimitMessages.ts`: label/save/validation/stale/TOTP/reset contextual copy.
- Pure amount helperใหม่และ unit tests; ไม่แก้ backend Money/API/schema.
- `RiskLimitPanel.test.tsx`, `TradingAccountPanel.test.tsx` และ session/recovery callers
  ที่ assertionเดิมผูกกับ UIเก่า.
- E2E risk-limitเฉพาะ selector/flowที่ได้รับผลกระทบ; ไม่รัน backend workload.

## 6. ความเสี่ยงและการควบคุม

| ความเสี่ยง | การควบคุม |
|---|---|
| เลือก INCREASE/DECREASE ผิดจากทศนิยม | pure bigint-scale parser + boundary/equivalent-text tests |
| Pollingทับค่าที่กำลังกรอก | dirty + snapshot identity + stale gate |
| เพิ่มเพดานข้าม TOTP | freeze actionก่อน modal; INCREASE pathเดียวเรียก `/increase` พร้อม header |
| ส่งซ้ำหลัง timeout/reload | reuse durable journal/key/receipt matchingเดิม |
| แสดงค่าที่ engineยังไม่ใช้ | ไม่ optimistic; รอ APPLIED + matching snapshot revision |
| ซ่อน stop failure | contextual alert/disclosureเมื่อ due/failed/PROBLEMS |
| UIใหม่กระทบ Live | scope-isolation testsและไม่เปลี่ยน Live activation |

## 7. Checkpoint และเวลา

1. Pure parser + form state tests: 10–15 นาที.
2. Component refactor + i18n: 20–30 นาที.
3. Targeted tests, lint, typecheck, build: 15–25 นาที.

รวมประมาณ **45–70 นาที** หากไม่พบ findingใหม่. งานนี้ไม่เปลี่ยน backend/runtimeจึงไม่
ทำให้ผล W1–W4, Money, order หรือ performanceหมดอายุ และไม่รัน workloadซ้ำ.

## 8. Needs Clarification

ไม่มีข้อที่บล็อก implementation หลัง plan/validationได้รับอนุมัติ.
