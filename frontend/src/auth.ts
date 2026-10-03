import type { components } from "./api-types";

/**
 * ชนิดข้อมูลของเส้นทางยืนยันตัวตน (F-05)
 *
 * มาจากไฟล์ที่สร้างจากสัญญา API ของหลังบ้าน (P-9) ห้ามเขียนชนิดเหล่านี้เอง
 */
export type Identity = components["schemas"]["Identity"];
export type SessionsEnded = components["schemas"]["SessionsEnded"];

const CSRF_COOKIE = "tiewtrade_csrf";
const CSRF_HEADER = "X-CSRF-Token";

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
  return found === undefined ? "" : decodeURIComponent(found.slice(CSRF_COOKIE.length + 1));
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

async function send<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", [CSRF_HEADER]: csrfToken() },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(await refusalOf(response));
  }
  return (await response.json()) as T;
}

/** สมัครบัญชีใหม่ */
export async function register(email: string, password: string): Promise<Identity> {
  return send<Identity>("/auth/register", { email, password });
}

/** เข้าสู่ระบบ */
export async function logIn(email: string, password: string): Promise<Identity> {
  return send<Identity>("/auth/login", { email, password });
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
export async function fetchIdentity(): Promise<Identity | null> {
  const response = await fetch("/api/auth/me", { credentials: "same-origin" });
  if (response.status === 401) {
    return null;
  }
  if (!response.ok) {
    throw new Error(await refusalOf(response));
  }
  return (await response.json()) as Identity;
}
