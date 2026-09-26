import type { components } from "./api-types";

/**
 * ชนิดของข้อมูลที่ /health คืนมา
 *
 * มาจากไฟล์ที่สร้างจากสัญญา API ของหลังบ้าน (P-9)
 * ห้ามเขียนชนิดนี้เอง และห้ามใช้ any — ถ้าหลังบ้านเปลี่ยนสัญญา
 * ด่านตรวจชนิดข้อมูลของหน้าบ้านต้องแดง (P-10, V-16)
 */
export type Health = components["schemas"]["Health"];

export async function fetchHealth(): Promise<Health> {
  const response = await fetch("/api/health");
  if (!response.ok) {
    throw new Error(`เรียก /health ไม่สำเร็จ: ${String(response.status)}`);
  }
  return (await response.json()) as Health;
}
