/**
 * พิสูจน์ว่าด่านชนิดข้อมูลของหน้าบ้านจับได้เมื่อสัญญา API เปลี่ยน (P-10, V-16)
 *
 * **ตรวจ source จริงของหน้าบ้านภายใต้ tsconfig.json จริง** ไม่ใช่ไฟล์ทดสอบที่เขียนขึ้นเอง
 * (รีวิว 2026-09-27 ข้อ R-2) ถ้าตรวจไฟล์ที่เขียนขึ้นเอง เทสต์จะยังผ่าน
 * แม้ `src/api.ts` และ `App.tsx` เลิกใช้ชนิดที่สร้างจากสัญญา API แล้ว
 *
 * เกณฑ์ผ่านเข้มกว่าปกติเหมือนเทสต์ด่านฝั่งหลังบ้าน:
 * 1. ต้องแดงเพราะช่องที่หายไปจริง ไม่ใช่เพราะ tsc รันไม่ได้
 * 2. ต้องมีกรณีที่ถูกต้องคู่กัน ซึ่งผ่านภายใต้ชุดตั้งค่าเดียวกัน
 * 3. รันด้วย tsconfig และ source ชุดเดียวกับด่านจริง
 *
 * **แต่ละกรณีคัดลอกหน้าบ้านทั้งชุดแล้วเรียก `tsc` ในกระบวนการลูก** จึงใช้เวลาเป็นวินาที
 * ค่า timeout ปริยายของ vitest (5 วินาที) พอในเครื่องนักพัฒนาแต่ไม่พอบน runner ของ CI
 * ที่ cache ยังเย็น — ด่านที่แดงสุ่มแย่กว่าด่านที่ช้า เพราะมันสอนให้คนเลิกเชื่อสีแดง
 * จึงตั้ง timeout ให้ตรงกับงานที่มันทำจริง (แก้หลัง CI ของ F-33 แดงสองครั้งด้วยเหตุนี้)
 */

/** เวลาที่ให้กรณีที่ต้องคอมไพล์จริง — เผื่อ runner ที่ cache เย็น */
const COMPILE_TIMEOUT_MS = 60_000;

import { execFileSync } from "node:child_process";
import { cpSync, mkdtempSync, readFileSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const FRONTEND_ROOT = join(import.meta.dirname, "..", "..");
const REAL_OPENAPI = join(FRONTEND_ROOT, "..", "backend", "openapi.json");

/** ไฟล์และโฟลเดอร์ของหน้าบ้านจริงที่ต้องคัดลอกไปตรวจ */
const COPIED = [
  "tsconfig.json",
  "package.json",
  "eslint.config.js",
  "vite.config.ts",
  "vitest.config.ts",
  "playwright.config.ts",
  "src",
  "tests",
  "e2e",
];

interface Result {
  code: number;
  output: string;
}

function run(command: string, args: string[], cwd: string): Result {
  try {
    const output = execFileSync(command, args, { cwd, encoding: "utf8", stdio: "pipe" });
    return { code: 0, output };
  } catch (error: unknown) {
    const failure = error as { status?: number; stdout?: string; stderr?: string };
    return { code: failure.status ?? 1, output: `${failure.stdout ?? ""}${failure.stderr ?? ""}` };
  }
}

/**
 * คัดลอกหน้าบ้านจริงไปที่ชั่วคราว สร้างชนิดข้อมูลจากสัญญาที่ให้มา
 * แล้วรัน typecheck ด้วย tsconfig จริง
 */
function typecheckRealFrontendAgainst(schema: unknown): Result {
  const dir = mkdtempSync(join(tmpdir(), "tiewtrade-contract-"));

  for (const entry of COPIED) {
    cpSync(join(FRONTEND_ROOT, entry), join(dir, entry), { recursive: true });
  }
  // ใช้ node_modules ชุดเดียวกัน ไม่ติดตั้งใหม่ เพื่อให้เวอร์ชันเครื่องมือตรงกับด่านจริง
  symlinkSync(join(FRONTEND_ROOT, "node_modules"), join(dir, "node_modules"), "dir");

  writeFileSync(join(dir, "openapi.json"), JSON.stringify(schema));
  const generated = run(
    "npx",
    ["openapi-typescript", "openapi.json", "-o", join("src", "api-types.ts")],
    dir,
  );
  expect(generated.code, `สร้างชนิดข้อมูลไม่สำเร็จ:\n${generated.output}`).toBe(0);

  return run("npx", ["tsc", "--noEmit", "-p", "tsconfig.json"], dir);
}

describe("ด่านชนิดข้อมูลของหน้าบ้าน", () => {
  const realSchema = JSON.parse(readFileSync(REAL_OPENAPI, "utf8")) as {
    components: { schemas: { Health: { properties: Record<string, unknown> } } };
  };

  it(
    "ผ่านเมื่อสัญญา API ตรงกับที่โค้ดหน้าบ้านใช้",
    () => {
      const result = typecheckRealFrontendAgainst(realSchema);
      expect(result.code, `ควรผ่านแต่แดง:\n${result.output}`).toBe(0);
    },
    COMPILE_TIMEOUT_MS,
  );

  it(
    "แดงเมื่อหลังบ้านเปลี่ยนชื่อช่องที่หน้าบ้านใช้",
    () => {
      const changed = JSON.parse(JSON.stringify(realSchema)) as typeof realSchema;
      const properties = changed.components.schemas.Health.properties;
      properties["state"] = properties["status"];
      delete properties["status"];

      const result = typecheckRealFrontendAgainst(changed);
      expect(result.code, "ควรแดงเพราะช่อง status หายไป แต่ผ่าน").not.toBe(0);
      expect(result.output, `แดงแต่ไม่ใช่เพราะช่อง status:\n${result.output}`).toContain("status");
    },
    COMPILE_TIMEOUT_MS,
  );
});
