import type { ReactNode } from "react";
import { useAccountPage, type AccountPage } from "./accountNavigation";

export function AccountPages({ children }: { children: (page: AccountPage) => ReactNode }) {
  return children(useAccountPage());
}
