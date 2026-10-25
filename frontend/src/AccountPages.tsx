import type { ReactNode } from "react";
import { useAccountPage, type AccountPage } from "./accountNavigation";

export function AccountPages({ isPlatformAdmin, children }: { isPlatformAdmin?: boolean; children: (page: AccountPage) => ReactNode }) {
  return children(useAccountPage(isPlatformAdmin));
}
