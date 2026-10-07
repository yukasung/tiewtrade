import { type JSX, useEffect, useState } from "react";

import { fetchHealth, type Health } from "./api";
import { AuthPanel } from "./AuthPanel";
import { authText as t } from "./authMessages";
import "./styles/admin-theme.css";

/** Application shell with account/auth presentation and live server health. */
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
    <main className="app-theme">
      <AuthPanel />
      <footer className="system-footer" aria-label={t("systemStatus")}>
        <p>{t("noTrading")}</p>
        {error !== null && (
          <p role="alert" data-testid="error">
            {t("error", { message: error })}
          </p>
        )}
        {health !== null && (
          <dl data-testid="health">
            <dt>{t("status")}</dt>
            <dd data-testid="status">{health.status}</dd>
            <dt>{t("serverTime")}</dt>
            <dd data-testid="server-time">{health.server_time}</dd>
            <dt>{t("version")}</dt>
            <dd data-testid="version">{health.version}</dd>
          </dl>
        )}
      </footer>
    </main>
  );
}
