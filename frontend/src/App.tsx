import { type JSX } from "react";

import { AuthPanel } from "./AuthPanel";
import "./styles/admin-theme.css";

/** Application shell with account/auth presentation. */
export function App(): JSX.Element {
  return (
    <main className="app-theme">
      <AuthPanel />
    </main>
  );
}
