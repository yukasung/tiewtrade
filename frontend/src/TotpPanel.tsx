import QRCode from "qrcode";
import { type JSX, useEffect, useState } from "react";

import {
  confirmTotpSetup,
  disableTotp,
  type Me,
  reissueRecoveryCodes,
  startTotpReplacement,
  startTotpSetup,
} from "./auth";

/**
 * จัดการการยืนยันสองชั้น (F-06)
 *
 * ยังไม่ใช่หน้าจอจริงของผลิตภัณฑ์ — งานหน้าจอเริ่มที่ F-12 และการสลับภาษาที่ F-30
 * ที่นี่มีเท่าที่ทำให้ผู้ใช้เปิด ปิด ผูกเครื่องใหม่ และขอรหัสสำรองใหม่ได้จริง
 *
 * **ไม่เก็บ secret, รหัส หรือรหัสสำรองไว้ที่ไหนเลยนอกจาก state ของหน้าจอ**
 * ไม่ลง `localStorage` ไม่ลง cookie เพราะรหัสสำรองคือทางเข้าบัญชีอีกทางหนึ่ง
 */
export function TotpPanel({
  identity,
  onChanged,
}: {
  identity: Me;
  onChanged: () => Promise<void>;
}): JSX.Element {
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [uri, setUri] = useState<string | null>(null);
  const [qr, setQr] = useState<string | null>(null);
  const [codes, setCodes] = useState<string[] | null>(null);
  const [refusal, setRefusal] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // **สร้าง QR ในเบราว์เซอร์** — secret ไม่ถูกส่งออกไปไหนเพื่อทำภาพ
  //
  // ถ้าสร้างไม่สำเร็จก็ไม่เป็นไร เพราะข้อความของ URI ยังอยู่และกรอกด้วยมือได้
  // — ภาพที่หายไปไม่ควรทำให้ตั้งค่า TOTP ไม่ได้เลย
  //
  // **แต่การกลืนข้อผิดพลาดแบบนี้ซ่อนของพังได้** จึงมีเทสต์ e2e ที่ยืนยันว่า QR
  // ขึ้นจริงบนเบราว์เซอร์ — ไม่ใช่แค่มีโค้ดที่สร้างมัน (พบตอนทำ: ภาพไม่ขึ้นแล้วเงียบ)
  useEffect(() => {
    if (uri === null) {
      setQr(null);
      return;
    }
    let current = true;
    void QRCode.toDataURL(uri, { errorCorrectionLevel: "M", margin: 4, width: 320 })
      .then((image) => {
        if (current) {
          setQr(image);
        }
      })
      .catch(() => {
        if (current) {
          setQr(null);
        }
      });
    return () => {
      current = false;
    };
  }, [uri]);

  async function run(action: () => Promise<void>): Promise<void> {
    setBusy(true);
    setRefusal(null);
    try {
      await action();
    } catch (cause: unknown) {
      setRefusal(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusy(false);
    }
  }

  const enrolling = uri !== null;

  return (
    <section data-testid="totp-panel">
      <h3>การยืนยันสองชั้น</h3>
      <p data-testid="totp-state">{identity.totp_enabled ? "เปิดอยู่" : "ปิดอยู่"}</p>

      {codes !== null && (
        <div data-testid="recovery-codes">
          <p>
            <strong>เก็บรหัสสำรองชุดนี้ไว้ — แสดงครั้งเดียว</strong> เหลือ {codes.length} ใบ
          </p>
          <ul>
            {codes.map((one) => (
              <li key={one}>{one}</li>
            ))}
          </ul>
          <p>
            ใช้ได้ใบละครั้ง และ<strong> ถ้าหมดแล้วเสียเครื่องด้วย จะเข้าบัญชีไม่ได้เลย</strong>
          </p>
        </div>
      )}

      {enrolling && (
        <div data-testid="enrollment">
          <p>สแกนภาพนี้ด้วยแอปยืนยันตัวตน แล้วกรอกรหัสที่แอปแสดงเพื่อยืนยัน</p>
          {qr !== null && (
            <img
              data-testid="otpauth-qr"
              src={qr}
              width={320}
              height={320}
              alt="รหัส QR สำหรับเพิ่มบัญชีนี้ในแอปยืนยันตัวตน — ถ้าสแกนไม่ได้ ใช้ข้อความข้างล่างแทน"
            />
          )}
          <p>สแกนไม่ได้ก็กรอกค่านี้ในแอปด้วยมือได้ (เลือก &ldquo;ใส่รหัสด้วยตนเอง&rdquo;)</p>
          <code data-testid="otpauth-uri">{uri}</code>
          <label htmlFor="totp-code">รหัสจากแอป</label>
          <input
            id="totp-code"
            name="totp-code"
            inputMode="numeric"
            autoComplete="one-time-code"
            value={code}
            onChange={(event) => {
              setCode(event.target.value);
            }}
          />
          <button
            type="button"
            data-testid="confirm-totp"
            disabled={busy}
            onClick={() =>
              void run(async () => {
                const enabled = await confirmTotpSetup(code);
                setCodes(enabled.recovery_codes);
                setUri(null);
                setCode("");
                setPassword("");
                await onChanged();
              })
            }
          >
            ยืนยันและเปิดใช้
          </button>
        </div>
      )}

      {!enrolling && (
        <form
          onSubmit={(event) => {
            event.preventDefault();
          }}
        >
          <label htmlFor="totp-password">รหัสผ่านปัจจุบัน</label>
          <input
            id="totp-password"
            name="totp-password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => {
              setPassword(event.target.value);
            }}
          />
          {identity.totp_enabled && (
            <>
              <label htmlFor="totp-current">รหัสจากแอปปัจจุบัน</label>
              <input
                id="totp-current"
                name="totp-current"
                inputMode="numeric"
                autoComplete="one-time-code"
                value={code}
                onChange={(event) => {
                  setCode(event.target.value);
                }}
              />
            </>
          )}

          {!identity.totp_enabled && (
            <button
              type="button"
              data-testid="start-totp"
              disabled={busy}
              onClick={() =>
                void run(async () => {
                  const started = await startTotpSetup(password);
                  setUri(started.otpauth_uri);
                  setCodes(null);
                })
              }
            >
              เปิดใช้การยืนยันสองชั้น
            </button>
          )}

          {identity.totp_enabled && (
            <>
              <button
                type="button"
                data-testid="replace-totp"
                disabled={busy}
                onClick={() =>
                  void run(async () => {
                    const started = await startTotpReplacement(
                      password,
                      code === "" ? undefined : code,
                    );
                    setUri(started.otpauth_uri);
                    setCodes(null);
                    setCode("");
                  })
                }
              >
                ผูกเครื่องใหม่
              </button>
              <button
                type="button"
                data-testid="reissue-codes"
                disabled={busy}
                onClick={() =>
                  void run(async () => {
                    const issued = await reissueRecoveryCodes(password, code);
                    setCodes(issued.recovery_codes);
                    setCode("");
                    setPassword("");
                  })
                }
              >
                ขอรหัสสำรองชุดใหม่
              </button>
              <button
                type="button"
                data-testid="disable-totp"
                disabled={busy}
                onClick={() =>
                  void run(async () => {
                    await disableTotp(password, code === "" ? undefined : code);
                    setCode("");
                    setPassword("");
                    setCodes(null);
                    await onChanged();
                  })
                }
              >
                ปิดการยืนยันสองชั้น
              </button>
            </>
          )}
        </form>
      )}

      {refusal !== null && <p data-testid="totp-refusal">{refusal}</p>}
    </section>
  );
}
