import { type JSX, useEffect, useState } from "react";

import {
  fetchIdentity,
  type Identity,
  logIn,
  logOut,
  logOutEverywhere,
  primeCsrfToken,
  register,
} from "./auth";

type Mode = "login" | "register";

/**
 * ฟอร์มเข้าสู่ระบบและสมัคร พร้อมสถานะว่าเข้าสู่ระบบอยู่หรือไม่ (F-05)
 *
 * ยังไม่ใช่หน้าจอจริงของผลิตภัณฑ์ — งานหน้าจอเริ่มที่ F-12 และการสลับภาษาที่ F-30
 * ที่นี่มีเท่าที่ทำให้ผู้ใช้สมัคร เข้าสู่ระบบ และออกจากระบบได้จริง
 *
 * **ไม่เก็บรหัสผ่านไว้ที่ไหนเลยนอกจากช่องกรอก** และไม่เก็บโทเคน เพราะ cookie
 * ของ session เป็น httpOnly ซึ่งสคริปต์อ่านไม่ได้โดยเจตนา
 */
export function AuthPanel(): JSX.Element {
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [refusal, setRefusal] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void primeCsrfToken().then(fetchIdentity).then(setIdentity).catch(() => {
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

  if (identity !== null) {
    return (
      <section data-testid="signed-in">
        <p>
          เข้าสู่ระบบแล้ว: <span data-testid="user-id">{identity.user_id}</span>
        </p>
        <button
          type="button"
          data-testid="log-out"
          disabled={busy}
          onClick={() => void run(logOut)}
        >
          ออกจากระบบ
        </button>
        <button
          type="button"
          data-testid="log-out-everywhere"
          disabled={busy}
          onClick={() => void run(logOutEverywhere)}
        >
          ออกจากระบบทุกเครื่อง
        </button>
        {refusal !== null && <p data-testid="refusal">{refusal}</p>}
      </section>
    );
  }

  return (
    <section data-testid="signed-out">
      <h2>{mode === "login" ? "เข้าสู่ระบบ" : "สมัครใช้งาน"}</h2>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void run(() => (mode === "login" ? logIn(email, password) : register(email, password)));
        }}
      >
        <label htmlFor="email">อีเมล</label>
        <input
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
        <label htmlFor="password">รหัสผ่าน</label>
        <input
          id="password"
          name="password"
          type="password"
          autoComplete={mode === "login" ? "current-password" : "new-password"}
          required
          value={password}
          onChange={(event) => {
            setPassword(event.target.value);
          }}
        />
        <button type="submit" data-testid="submit" disabled={busy}>
          {mode === "login" ? "เข้าสู่ระบบ" : "สมัคร"}
        </button>
      </form>
      <button
        type="button"
        data-testid="switch-mode"
        onClick={() => {
          setMode(mode === "login" ? "register" : "login");
          setRefusal(null);
        }}
      >
        {mode === "login" ? "ยังไม่มีบัญชี — สมัครใช้งาน" : "มีบัญชีแล้ว — เข้าสู่ระบบ"}
      </button>
      {mode === "register" && (
        <p data-testid="recovery-warning">
          รหัสผ่านต้องยาวอย่างน้อย 15 ตัวอักษร และ
          <strong> ระบบยังไม่มีทางกู้รหัสผ่าน</strong> ถ้าลืมจะเข้าบัญชีไม่ได้
        </p>
      )}
      {refusal !== null && <p data-testid="refusal">{refusal}</p>}
    </section>
  );
}
