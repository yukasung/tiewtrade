# Trading toolbar width and right panel alignment

สถานะ: **Approved — เจ้าของตอบ approve สำหรับ Requirements/Plan/Validation วันที่ 2026-11-13**
วันที่ 2026-11-13 Asia/Bangkok

## Requirements

เจ้าของขอให้แถบ BTC/USDT–Timeframe–รีเซ็ตกว้างตามฝั่งกราฟในภาพ Binance
และเลื่อน sidebar สั่งออเดอร์ด้านขวาขึ้นเพื่อเพิ่มพื้นที่ใช้งาน พร้อมเพิ่มขนาด header icons

- เมื่อใช้สองคอลัมน์ แถบคู่เทรดอยู่เฉพาะคอลัมน์กราฟ
- ฟอร์มสั่งออเดอร์เริ่มระดับเดียวกับแถบคู่เทรดใต้เมนูหลัก และใช้ความสูงถึงขอบล่าง workspace
- Timeframe และรีเซ็ตยังอยู่ต่อจาก BTC/USDT
- ไอคอนธีม/บัญชี/Settings และ hamburger ขนาด24pxตามตัวอย่างAppHeader/UserDropdownของtemplate

## Plan ที่อนุมัติ

ใช้ TradingWorkspace, shared CSS และ controls เดิม
เปลี่ยน grid areas ของสองคอลัมน์เป็น bar/form, chart/form, orders/form
กรณีไม่มี orders ใช้ bar/form และ chart/form
Form column กว้าง22.5rem ส่วน chart/orders ใช้สัดส่วน64:36หลังpair toolbarตามแผนปัจจุบัน
คง outer inset4px/panel gap4px และพื้นที่scrollภายในฟอร์ม

เพิ่ม glyph จาก20pxเป็น24pxใน shared header styles พร้อม targetอย่างน้อย44px
ใช้ขนาด24pxที่ปรากฏใน references/admin-template/src/layout/AppHeader.tsx
และ components/header/UserDropdown.tsx คงรูปแบบborderless/focus-visibleของfeature

Mobile/tabletที่ใช้stacked layoutจัดแถบควบคุม กราฟ และฟอร์มตามflowเดิม
Headerยังใช้64px/56pxตามbreakpointของfeature

## Validation ที่อนุมัติ

ทุกข้อเป็น Feature

- วัดbar/form topตรงกัน และbar/chart/ordersกว้างถึงขอบformพร้อมgap4pxบนสองคอลัมน์
- Formสูงถึงขอบworkspaceและscrollถึงcontrolsท้ายฟอร์มได้ ทั้งPaper/Spotและกรณีไม่มีorders
- ตรวจinlinecontrols,chartfill/axes/error,64:36และorders/historyheightหลังresize
- ตรวจglyph24px/targets44px,keyboard/focus,Settings/STOP pending/unknown/requestidentity
- Browser375/768/1024/1279/1280/1440และ2553×1240 พร้อมไทย/อังกฤษ/light/dark ไม่มีnavigationoverflow
- Targeted testsและfrontend lint/typecheck/build จากนั้น Ready for Code Review และรอreview code


## ทะเบียนเกณฑ์

| ID | ระยะ | เกณฑ์ | ผล |
|---|---|---|---|
| NAV-V42 | Feature | แถบคู่เทรดกว้างฝั่งกราฟ Formเริ่มระดับเดียวกับbarและสูงถึงขอบworkspaceในPaper/Live พร้อมscrollถึงปุ่มท้ายฟอร์มและchart/orders64:36 | Passed (local) |
| NAV-V43 | Feature | Header glyph24px,target44px,borderless/focus/disabled/menu/Settings/STOPถูกต้องทั้ง7width/สองภาษา/สองธีมตามส่วนที่กระทบ | Passed (local) |
| NAV-V44 | Feature ก่อนmerge | targeted/static/browserผ่าน และrequiredCIบนfinalcandidate | Partial — local Passed; required CI Not Run |

NAV-V30เรื่องglyph20pxเป็นประวัติcandidateเดิมและถูกแทนด้วยV43


## ผลล่าสุด

Implementation และlocal checksผ่านตาม [right panel checkpoint](evidence/right-panel-top-alignment-checkpoint.md)
NAV-V42/V43 Passed(local),V44 PartialรอrequiredCI
Ready for Code Review รอreview codeและowner acceptance


## ปรับระยะไอคอนตามคำสั่งเจ้าของ

เจ้าของขอให้ไอคอนด้านขวากระชับตามภาพBinance
Desktopเอาgap8pxภายในactionsและgap16pxก่อนSettingsออก ให้targets44pxเรียงติดกัน
Glyph24pxมีระยะกึ่งกลาง44pxเท่ากันทั้งสามปุ่ม ใช้marginของbrandรักษาระยะก่อนเมนูหลัก
ตรวจcomputed bounds ว่าtargetsไม่ทับกันและSettingsยังอยู่ขวาสุด พร้อมkeyboardและpopupเดิม
