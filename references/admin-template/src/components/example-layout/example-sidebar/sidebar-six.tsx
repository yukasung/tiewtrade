import { useSidebar } from "@/context/SidebarContext";
import {
  BellAltIcon,
  BoxCubeIcon,
  CalendarAltIcon,
  ChartAltIcon,
  DashboardAltIcon,
  EmailAltIcon,
  HeadphoneAltIcon,
  InboxAltIcon,
  IntegrationAltIcon,
  ProfileAltIcon,
  SettingsAltIcon,
} from "@/icons";
import { cn } from "@/utils";
import { useState } from "react";

type NavItemType = {
  id: string;
  label: string;
  icon: React.ReactNode;
};

const navItems: NavItemType[] = [
  { id: "dashboard", label: "Dashboard", icon: <DashboardAltIcon /> },
  { id: "calendar", label: "Calendar", icon: <CalendarAltIcon /> },
  { id: "profiles", label: "Profiles", icon: <ProfileAltIcon /> },
  { id: "settings", label: "Settings", icon: <SettingsAltIcon /> },
  { id: "design", label: "Design Engineering", icon: <BellAltIcon /> },
  { id: "email", label: "Email", icon: <EmailAltIcon /> },
  { id: "inbox", label: "Inbox", icon: <InboxAltIcon /> },
  { id: "support", label: "Customer Support", icon: <HeadphoneAltIcon /> },
  { id: "analytics", label: "Analytics", icon: <ChartAltIcon /> },
  { id: "integrations", label: "Integrations", icon: <IntegrationAltIcon /> },
  { id: "components", label: "Components", icon: <BoxCubeIcon /> },
];

type NavItemProps = {
  item: NavItemType;
  isActive: boolean;
  onClick: () => void;
};

function NavItem({ item, isActive, onClick }: NavItemProps) {
  return (
    <div className="group relative">
      <button
        onClick={onClick}
        className={cn(
          "nav-icon-item",
          isActive ? "nav-icon-item-active" : "nav-icon-item-inactive",
        )}
        aria-label={item.label}
      >
        <span className="[&_svg]:size-5">{item.icon}</span>
      </button>
      <span className="pointer-events-none absolute start-full top-1/2 z-50 ms-3 -translate-y-1/2 rounded-lg bg-gray-800 px-3 py-1.5 text-sm whitespace-nowrap text-white opacity-0 shadow-lg transition-opacity group-hover:opacity-100">
        {item.label}
      </span>
    </div>
  );
}

export default function SidebarSix() {
  const { isExpanded, isMobileOpen } = useSidebar();
  const [activeNav, setActiveNav] = useState("dashboard");

  // Desktop: use isExpanded to slide in/out
  // Mobile: use isMobileOpen to slide in/out
  const isVisible = isMobileOpen || isExpanded;

  return (
    <aside
      className={cn(
        "fixed start-0 top-16 z-9999 flex h-screen flex-col items-center bg-gray-50 pt-7 pb-5 transition-all duration-300 xl:sticky xl:top-0 dark:bg-gray-900",
        isVisible
          ? "w-[92px] translate-x-0 border-e border-gray-200 dark:border-gray-800"
          : "w-0 -translate-x-full overflow-hidden border-none rtl:translate-x-full",
      )}
    >
      {/* Logo */}
      <a
        href="#"
        className="mb-8 flex size-8 shrink-0 items-center justify-center rounded-xl bg-brand-500 xl:mb-16"
      >
        <img src="./images/logo/logo-icon.svg" alt="Logo" className="h-8 w-8" />
      </a>

      {/* Nav Icons */}
      <nav className="flex flex-1 flex-col items-center gap-1">
        {navItems.map((item) => (
          <NavItem
            key={item.id}
            item={item}
            isActive={activeNav === item.id}
            onClick={() => setActiveNav(item.id)}
          />
        ))}
      </nav>
    </aside>
  );
}
