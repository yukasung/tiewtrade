import { Button } from "./components/ui/Button";
import { Input } from "./components/ui/Input";
import { Label } from "./components/ui/Label";
import { authText as t } from "./authMessages";

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
 * TailAdmin presentation for the existing setup/replacement/recovery flow.
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
    void QRCode.toDataURL(uri, {
      errorCorrectionLevel: "M",
      margin: 4,
      width: 320,
    })
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
    <section id="totp-panel" data-testid="totp-panel" className="totp-panel">
      <h2>{t("totpHeading")}</h2>
      <p data-testid="totp-state">
        {t(identity.totp_enabled ? "enabled" : "disabled")}
      </p>

      {codes !== null && (
        <div data-testid="recovery-codes">
          <p>
            <strong>{t("saveCodes")}</strong>{" "}
            {t("remaining", { count: codes.length })}
          </p>
          <ul>
            {codes.map((one) => (
              <li key={one}>{one}</li>
            ))}
          </ul>
          <p>{t("codesWarning")}</p>
        </div>
      )}

      {enrolling && (
        <div data-testid="enrollment">
          <p>{t("scanHelp")}</p>
          {qr !== null && (
            <img
              data-testid="otpauth-qr"
              src={qr}
              width={320}
              height={320}
              alt={t("qrAlt")}
            />
          )}
          <p>{t("manualHelp")}</p>
          <code data-testid="otpauth-uri">{uri}</code>
          <Label htmlFor="totp-code">{t("appCode")}</Label>
          <Input
            id="totp-code"
            name="totp-code"
            inputMode="numeric"
            autoComplete="one-time-code"
            value={code}
            onChange={(event) => {
              setCode(event.target.value);
            }}
          />
          <Button
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
            {t("enableConfirm")}
          </Button>
        </div>
      )}

      {!enrolling && (
        <form
          onSubmit={(event) => {
            event.preventDefault();
          }}
        >
          <Label htmlFor="totp-password">{t("currentPassword")}</Label>
          <Input
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
              <Label htmlFor="totp-current">{t("currentCode")}</Label>
              <Input
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
            <Button
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
              {t("enableTotp")}
            </Button>
          )}

          {identity.totp_enabled && (
            <>
              <Button
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
                {t("replaceTotp")}
              </Button>
              <Button
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
                {t("reissueCodes")}
              </Button>
              <Button
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
                {t("disableTotp")}
              </Button>
            </>
          )}
        </form>
      )}

      {refusal !== null && (
        <p role="alert" data-testid="totp-refusal">
          {refusal}
        </p>
      )}
    </section>
  );
}
