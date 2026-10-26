import type { components } from "./api-types";

/**
 * ชนิดข้อมูลของเส้นทางยืนยันตัวตน (F-05)
 *
 * มาจากไฟล์ที่สร้างจากสัญญา API ของหลังบ้าน (P-9) ห้ามเขียนชนิดเหล่านี้เอง
 */
export type Identity = components["schemas"]["Identity"];
type MeContract = components["schemas"]["Me"];
/** Optional only for a rolling frontend/backend deployment; the current API always emits it. */
export type Me = Omit<MeContract, "platform_role"> & {
  platform_role?: MeContract["platform_role"];
};
export type SessionsEnded = components["schemas"]["SessionsEnded"];
export type SignInStarted = components["schemas"]["SignInStarted"];
export type SignedIn = components["schemas"]["SignedIn"];
export type Enrollment = components["schemas"]["Enrollment"];
export type Enabled = components["schemas"]["Enabled"];
export type CodesIssued = components["schemas"]["CodesIssued"];
export type Disabled = components["schemas"]["Disabled"];

const CSRF_COOKIE = "tiewtrade_csrf";
const CSRF_HEADER = "X-CSRF-Token";

/** header ที่พารหัสยืนยันปัจจัยที่สองของคำขอนั้น (F-06) */
const TOTP_HEADER = "X-TiewTrade-TOTP";

/**
 * โทเคนกัน CSRF จาก cookie ที่หลังบ้านตั้งไว้
 *
 * cookie ใบนี้ **ไม่ใช่** httpOnly โดยเจตนา เพราะหน้าเว็บต้องอ่านไปใส่ header
 * ส่วน cookie ของ session เป็น httpOnly จึงอ่านจากที่นี่ไม่ได้ ซึ่งเป็นสิ่งที่ต้องการ
 */
function csrfToken(): string {
  const found = document.cookie
    .split("; ")
    .find((entry) => entry.startsWith(`${CSRF_COOKIE}=`));
  return found === undefined
    ? ""
    : decodeURIComponent(found.slice(CSRF_COOKIE.length + 1));
}

/** ข้อความผิดพลาดที่หลังบ้านส่งมา — ไม่เดาแทน และไม่แปลเอง */
async function refusalOf(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") {
      return body.detail;
    }
  } catch {
    // คำตอบที่ไม่ใช่ JSON — ใช้สถานะแทน
  }
  return `คำขอไม่สำเร็จ (${String(response.status)})`;
}

/** ขอโทเคนกัน CSRF ก่อนส่งคำขอที่เปลี่ยนสถานะครั้งแรก */
export async function primeCsrfToken(): Promise<void> {
  await fetch("/api/auth/csrf", { credentials: "same-origin" });
}

export class ApiRequestError extends Error {
  readonly retryAt: string | null;

  constructor(
    message: string,
    readonly status: number,
    retryAfter: string | null = null,
  ) {
    super(message);
    const source = retryAfter?.trim() ?? "";
    const moment = /^\d+$/.test(source)
      ? Date.now() + Number(source) * 1000
      : /^(?:[A-Za-z]{3}, |\d{4}-\d{2}-\d{2}T)/.test(source)
        ? Date.parse(source)
        : NaN;
    const date = new Date(moment);
    this.retryAt = Number.isFinite(date.getTime()) ? date.toISOString() : null;
  }
}

/** ตัวส่งที่ใช้ร่วมกัน — cookie/CSRF/TOTP อยู่ที่เดียว ไม่บันทึก payload */
export async function send<T>(
  path: string,
  body: unknown,
  code?: string,
  method: "POST" | "GET" | "DELETE" = "POST",
  signal?: AbortSignal,
  additionalHeaders?: Readonly<Record<string, string>>,
): Promise<T> {
  const headers: Record<string, string> =
    method === "GET"
      ? {}
      : {
          "Content-Type": "application/json",
          [CSRF_HEADER]: csrfToken(),
        };
  if (code !== undefined) {
    headers[TOTP_HEADER] = code;
  }
  Object.assign(headers, additionalHeaders);
  const response = await fetch(`/api${path}`, {
    method,
    credentials: "same-origin",
    headers,
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    ...(signal === undefined ? {} : { signal }),
  });
  if (!response.ok) {
    throw new ApiRequestError(
      await refusalOf(response),
      response.status,
      response.headers?.get("Retry-After") ?? null,
    );
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/** สมัครบัญชีใหม่ */
export async function register(
  email: string,
  password: string,
): Promise<Identity> {
  return send<Identity>("/auth/register", { email, password });
}

/**
 * ขั้นแรกของการเข้าสู่ระบบ
 *
 * **ยังไม่แน่ว่าเข้าสู่ระบบแล้ว** — ผู้ใช้ที่เปิดการยืนยันสองชั้นจะได้
 * `second_step_required` เป็นจริง และต้องเรียก `completeSignIn` ต่อ (F-06 RQ-5)
 */
export async function logIn(
  email: string,
  password: string,
): Promise<SignInStarted> {
  return send<SignInStarted>("/auth/login", { email, password });
}

/** ขั้นที่สองของการเข้าสู่ระบบ — รหัสจากแอป หรือรหัสสำรองหนึ่งใบ */
export async function completeSignIn(input: {
  code?: string;
  recoveryCode?: string;
}): Promise<SignedIn> {
  return send<SignedIn>("/auth/totp/login", {
    code: input.code ?? null,
    recovery_code: input.recoveryCode ?? null,
  });
}

/** เริ่มตั้งค่าการยืนยันสองชั้น — ต้องกรอกรหัสผ่านปัจจุบัน */
export async function startTotpSetup(password: string): Promise<Enrollment> {
  return send<Enrollment>("/auth/totp/setup", { password });
}

/** ยืนยันรหัสจากแอปแล้วเปิดใช้ — คืนรหัสสำรองชุดใหม่ */
export async function confirmTotpSetup(code: string): Promise<Enabled> {
  return send<Enabled>("/auth/totp/confirm", { code });
}

/** เริ่มผูกเครื่องใหม่ — ต้องยืนยันปัจจัยที่สองของคำขอนี้ */
export async function startTotpReplacement(
  password: string,
  code?: string,
): Promise<Enrollment> {
  return send<Enrollment>("/auth/totp/replace", { password }, code);
}

/** ปิดการยืนยันสองชั้น */
export async function disableTotp(
  password: string,
  code?: string,
): Promise<Disabled> {
  return send<Disabled>("/auth/totp/disable", { password }, code);
}

/** ขอรหัสสำรองชุดใหม่ — ชุดเก่าใช้ไม่ได้ทันที */
export async function reissueRecoveryCodes(
  password: string,
  code: string,
): Promise<CodesIssued> {
  return send<CodesIssued>("/auth/totp/recovery-codes", { password }, code);
}

/** ออกจากระบบเครื่องนี้ */
export async function logOut(): Promise<SessionsEnded> {
  return send<SessionsEnded>("/auth/logout", {});
}

/** ออกจากระบบทุกเครื่อง */
export async function logOutEverywhere(): Promise<SessionsEnded> {
  return send<SessionsEnded>("/auth/logout-all", {});
}

/**
 * ตัวตนของผู้ใช้ปัจจุบัน — `null` เมื่อยังไม่ได้เข้าสู่ระบบ
 *
 * ถือว่า `401` คือ "ยังไม่เข้าสู่ระบบ" ไม่ใช่ข้อผิดพลาด เพราะเป็นสภาพปกติของหน้าแรก
 */
export async function fetchIdentity(): Promise<Me | null> {
  const response = await fetch("/api/auth/me", { credentials: "same-origin" });
  if (response.status === 401) {
    return null;
  }
  if (!response.ok) {
    throw new Error(await refusalOf(response));
  }
  return (await response.json()) as Me;
}
