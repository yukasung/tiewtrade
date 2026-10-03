import { type JSX, useEffect, useState } from "react";

import { fetchHealth, type Health } from "./api";
import { AuthPanel } from "./AuthPanel";

/**
 * หน้าเดียวของระบบตอนนี้ — สถานะเซิร์ฟเวอร์ (F-01) และการยืนยันตัวตน (F-05)
 *
 * ยังไม่ใช่หน้าจอจริง ไม่มีเมนู ไม่มีระบบแปลภาษา ไม่มี component กลาง
 * งานหน้าจอจริงเริ่มที่ F-12 และการสลับภาษาที่ F-30
 */
export function App(): JSX.Element {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchHealth()
      .then(setHealth)
      .catch((cause: unknown) => {
        setError(cause instanceof Error ? cause.message : String(cause));
      });
  }, []);

  return (
    <main>
      <h1>TiewTrade</h1>
      <p>ยังไม่มีความสามารถด้านการเทรด</p>
      <AuthPanel />
      {error !== null && <p data-testid="error">ผิดพลาด: {error}</p>}
      {health !== null && (
        <dl data-testid="health">
          <dt>สถานะ</dt>
          <dd data-testid="status">{health.status}</dd>
          <dt>เวลาของเซิร์ฟเวอร์</dt>
          <dd data-testid="server-time">{health.server_time}</dd>
          <dt>รุ่น</dt>
          <dd data-testid="version">{health.version}</dd>
        </dl>
      )}
    </main>
  );
}
