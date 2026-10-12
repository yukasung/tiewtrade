import { type JSX, useEffect, useState } from "react";

import {
  completeSignIn,
  fetchIdentity,
  logIn,
  logOut,
  logOutEverywhere,
  type Me,
  primeCsrfToken,
  register,
} from "./auth";
import { TotpPanel } from "./TotpPanel";
import { AccountSession } from "./AccountSession";
import { RealtimePricePanel } from "./RealtimePricePanel";
import { CandlestickChartPanel } from "./CandlestickChartPanel";
import { TradingAccountPanel } from "./TradingAccountPanel";
import { AccountLayout } from "./layout/AccountLayout";
import { AccountPages } from "./AccountPages";
import { chartText } from "./chartMessages";
import { ApiKeyPanel } from "./ApiKeyPanel";

import { AuthLayout } from "./layout/AuthLayout";
import { Button } from "./components/ui/Button";
import { Input } from "./components/ui/Input";
import { Label } from "./components/ui/Label";
import { authText as t } from "./authMessages";

type Mode = "login" | "register";

/**
 * ฟอร์มเข้าสู่ระบบและสมัคร พร้อมสถานะว่าเข้าสู่ระบบอยู่หรือไม่ (F-05)
 *
 * Presentation adapted from TailAdmin; authentication and session flow stay unchanged.
 *
 * **ไม่เก็บรหัสผ่านไว้ที่ไหนเลยนอกจากช่องกรอก** และไม่เก็บโทเคน เพราะ cookie
 * ของ session เป็น httpOnly ซึ่งสคริปต์อ่านไม่ได้โดยเจตนา
 */
export function AuthPanel(): JSX.Element {
  const [identity, setIdentity] = useState<Me | null>(null);
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [refusal, setRefusal] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // **ขั้นที่สองของการเข้าสู่ระบบ** — จริงเมื่อหลังบ้านบอกว่ายังไม่จบ (F-06 RQ-5)
  const [secondStep, setSecondStep] = useState(false);
  const [code, setCode] = useState("");
  const [recoveryCode, setRecoveryCode] = useState("");
  const [codesLeft, setCodesLeft] = useState<number | null>(null);

  useEffect(() => {
    void primeCsrfToken()
      .then(fetchIdentity)
      .then(setIdentity)
      .catch(() => {
        setIdentity(null);
      });
  }, []);

  async function run(action: () => Promise<unknown>): Promise<void> {
    setBusy(true);
    setRefusal(null);
    try {
      await action();
      const found = await fetchIdentity();
      setIdentity(found);
      setPassword("");
      if (found !== null) {
        setSecondStep(false);
      }
      if (found === null) {
        // ออกจากระบบแล้ว cookie กัน CSRF ถูกลบไปด้วย — ต้องขอใบใหม่
        // มิฉะนั้นการเข้าสู่ระบบครั้งต่อไปจะถูกปฏิเสธจนกว่าผู้ใช้จะโหลดหน้าใหม่
        // (พบจาก e2e ไม่ใช่จากการอ่านโค้ด)
        await primeCsrfToken();
        // กลับไปโหมดเข้าสู่ระบบ เพราะคนที่เพิ่งออกจากระบบมีบัญชีอยู่แล้ว
        // ถ้าค้างไว้ที่โหมดสมัคร การกดครั้งถัดไปจะกลายเป็นการสมัครซ้ำ
        setMode("login");
      }
    } catch (cause: unknown) {
      setRefusal(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusy(false);
    }
  }

  async function endSession(action: () => Promise<unknown>): Promise<void> {
    setBusy(true);
    setRefusal(null);
    try {
      await action();
      // The logout response confirms termination. Unmount the account/cache
      // before any follow-up request, which may fail or remain pending.
      setIdentity(null);
      setMode("login");
      setEmail("");
      setPassword("");
      setSecondStep(false);
      setCode("");
      setRecoveryCode("");
      setCodesLeft(null);
      await primeCsrfToken();
    } catch (cause: unknown) {
      setRefusal(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusy(false);
    }
  }

  if (secondStep && identity === null) {
    return (
      <AuthLayout>
        <section data-testid="second-step" className="auth-form">
          <h1>{t("secondStep")}</h1>
          <p>{t("secondStepHelp")}</p>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void run(async () => {
                const done = await completeSignIn(
                  recoveryCode === "" ? { code } : { recoveryCode },
                );
                setCodesLeft(done.recovery_codes_left ?? null);
                setCode("");
                setRecoveryCode("");
              });
            }}
          >
            <Label htmlFor="second-step-code">{t("appCode")}</Label>
            <Input
              id="second-step-code"
              name="second-step-code"
              inputMode="numeric"
              autoComplete="one-time-code"
              value={code}
              onChange={(event) => {
                setCode(event.target.value);
              }}
            />
            <Label htmlFor="second-step-recovery">{t("recoveryCode")}</Label>
            <Input
              id="second-step-recovery"
              name="second-step-recovery"
              autoComplete="off"
              value={recoveryCode}
              onChange={(event) => {
                setRecoveryCode(event.target.value);
              }}
            />
            <Button
              type="submit"
              data-testid="submit-second-step"
              disabled={busy}
            >
              {t("confirm")}
            </Button>
          </form>
          {refusal !== null && (
            <p role="alert" data-testid="refusal">
              {refusal}
            </p>
          )}
        </section>
      </AuthLayout>
    );
  }

  if (identity !== null) {
    return (
      <AccountSession identity={identity} onExpired={() => setIdentity(null)}>
        <AccountPages>{page => <AccountLayout page={page}>
          <div data-testid="signed-in">
          {page === "account" && <section id="account-details">
            <h1>{t("accountHeading")}</h1>
            <p className="page-description">{t("accountHelp")}</p>
            <div className="account-details-panel">
              <p>
                {t("signedIn")}{" "}
                <span data-testid="user-id">{identity.user_id}</span>
              </p>
              {codesLeft !== null && (
                <p data-testid="codes-left">
                  {t("codesLeft", { count: codesLeft })}
                </p>
              )}
              <Button
                type="button"
                data-testid="log-out"
                disabled={busy}
                onClick={() => void endSession(logOut)}
              >
                {t("logout")}
              </Button>
              <Button
                type="button"
                data-testid="log-out-everywhere"
                disabled={busy}
                onClick={() => void endSession(logOutEverywhere)}
              >
                {t("logoutEverywhere")}
              </Button>
              {refusal !== null && (
                <p role="alert" data-testid="refusal">
                  {refusal}
                </p>
              )}
            </div>
          </section>}
            {page === "security" && <TotpPanel
              identity={identity}
              onChanged={async () => {
                const found = await fetchIdentity();
                setIdentity((current) =>
                  current?.user_id === identity.user_id ? found : current,
                );
              }}
            />}
            {page === "api-keys" && <ApiKeyPanel identity={identity} />}
            {page === "trading-account" && <TradingAccountPanel identity={identity} />}
            {page === "prices" && <RealtimePricePanel />}
            {page === "chart" && (import.meta.env.VITE_CHART_ENABLED === "1"
              ? <CandlestickChartPanel userId={identity.user_id}/>
              : <p role="status">{chartText("errors.CHART_DISABLED")}</p>)}
          </div>
        </AccountLayout>}</AccountPages>
      </AccountSession>
    );
  }

  return (
    <AuthLayout>
      <section data-testid="signed-out" className="auth-form">
        <h1>{t(mode === "login" ? "login" : "register")}</h1>
        <p className="auth-description">
          {t(mode === "login" ? "loginHelp" : "registerHelp")}
        </p>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void run(async () => {
              if (mode === "register") {
                await register(email, password);
                return;
              }
              const started = await logIn(email, password);
              // **ขั้นแรกอาจยังไม่จบ** — ถ้ายังต้องยืนยันอีกขั้น อย่าถือว่าเข้าสู่ระบบแล้ว
              setSecondStep(started.second_step_required);
            });
          }}
        >
          <Label htmlFor="email">{t("email")}</Label>
          <Input
            id="email"
            name="email"
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(event) => {
              setEmail(event.target.value);
            }}
          />
          <Label htmlFor="password">{t("password")}</Label>
          <Input
            id="password"
            name="password"
            type="password"
            autoComplete={
              mode === "login" ? "current-password" : "new-password"
            }
            required
            value={password}
            onChange={(event) => {
              setPassword(event.target.value);
            }}
          />
          <Button type="submit" data-testid="submit" disabled={busy}>
            {t(mode === "login" ? "login" : "registerSubmit")}
          </Button>
        </form>
        <Button
          type="button"
          data-testid="switch-mode"
          onClick={() => {
            setMode(mode === "login" ? "register" : "login");
            setRefusal(null);
          }}
        >
          {t(mode === "login" ? "switchRegister" : "switchLogin")}
        </Button>
        {mode === "register" && (
          <p className="auth-warning" data-testid="recovery-warning">
            {t("passwordWarning")}
          </p>
        )}
        {refusal !== null && (
          <p role="alert" data-testid="refusal">
            {refusal}
          </p>
        )}
      </section>
    </AuthLayout>
  );
}
