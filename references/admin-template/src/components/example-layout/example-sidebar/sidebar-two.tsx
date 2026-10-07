import { useSidebar } from "@/context/SidebarContext";
import {
  BellAltIcon,
  BoltIcon,
  ChartAltIcon,
  ChevronDownIcon,
  CubeAltIcon,
  DashboardAltIcon,
  HeadphoneAltIcon,
  HorizontaLDots,
  ProfileAltIcon,
  SettingsAltIcon,
} from "@/icons";
import { cn } from "@/utils";
import { useEffect, useState } from "react";

type SubItem = { id: string; label: string };

type NavItem = {
  id: string;
  label: string;
  icon?: React.ReactNode;
  children?: SubItem[];
};

type NavGroup = {
  group: string;
  items: NavItem[];
};

const navGroups: NavGroup[] = [
  {
    group: "General",
    items: [
      {
        id: "Dashboard",
        label: "Dashboard",
        icon: <DashboardAltIcon />,
        children: [
          { id: "inventoryManagement", label: "Inventory Management" },
          { id: "productDevelopment", label: "Product Development" },
          { id: "finance", label: "Finance" },
          { id: "humanResources", label: "Human Resources" },
          { id: "supplyChain", label: "Supply Chain" },
        ],
      },
      { id: "profile", label: "Public Profiles", icon: <ProfileAltIcon /> },
      { id: "settings", label: "Settings", icon: <SettingsAltIcon /> },
      { id: "notifications", label: "Notifications", icon: <BellAltIcon /> },
      { id: "analytics", label: "User Analytics", icon: <ChartAltIcon /> },
    ],
  },
  {
    group: "Projects",
    items: [
      {
        id: "designEngineering",
        label: "Design Engineering",
        icon: <BoltIcon />,
      },
      { id: "marketing", label: "Sales & Marketing", icon: <ChartAltIcon /> },
      { id: "saas", label: "SaaS", icon: <CubeAltIcon /> },
      {
        id: "customerSupport",
        label: "Customer Support",
        icon: <HeadphoneAltIcon />,
      },
    ],
  },
  {
    group: "API Reference",
    items: [
      { id: "fileConventions", label: "File Conventions" },
      { id: "versionControl", label: "Version Control" },
      { id: "fileOrganization", label: "File Organization" },
      { id: "backupProcedures", label: "Backup Procedures" },
    ],
  },
];

export default function SidebarTwo() {
  const { isExpanded, isMobileOpen, isHovered, setIsHovered, setIsMobileOpen } =
    useSidebar();
  const [selected, setSelected] = useState("Dashboard");
  const [openDropdown, setOpenDropdown] = useState<string | null>("Dashboard");

  const showContent = isExpanded || isHovered || isMobileOpen;

  // Auto-expand / collapse dropdown based on sidebar visibility
  useEffect(() => {
    if (!showContent) {
      setOpenDropdown(null);
    } else {
      // Re-open Dashboard by default when sidebar becomes visible
      setOpenDropdown("Dashboard");
    }
  }, [showContent]);

  // Auto-close sidebar on mobile (if needed)
  useEffect(() => {
    // Close mobile sidebar on navigation
    if (isMobileOpen) {
      setIsMobileOpen(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected]);

  return (
    <aside
      className={cn(
        "fixed start-0 top-0 z-9999 flex h-screen flex-col overflow-y-auto border-e border-gray-200 bg-gray-50 px-5 transition-all duration-300 ease-in-out xl:translate-x-0 xl:rtl:translate-x-0 dark:border-gray-800 dark:bg-gray-900",
        isMobileOpen
          ? "translate-x-0"
          : "-translate-x-full rtl:translate-x-full",
        isExpanded || isMobileOpen
          ? "w-[290px]"
          : isHovered
            ? "w-[290px]"
            : "w-[90px]",
      )}
      onMouseEnter={() => !isExpanded && setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* SIDEBAR HEADER */}
      <div
        className={cn(
          "sidebar-header flex items-center gap-2 pt-8 pb-7",
          !showContent ? "xl:justify-center" : "justify-between",
        )}
      >
        <a href="#">
          {showContent ? (
            <>
              <img
                className="dark:hidden"
                src="./images/logo/logo.svg"
                alt="Logo"
              />
              <img
                className="hidden dark:block"
                src="./images/logo/logo-dark.svg"
                alt="Logo"
              />
            </>
          ) : (
            <img src="./images/logo/logo-icon.svg" alt="Logo" />
          )}
        </a>
      </div>
      {/* /SIDEBAR HEADER */}

      {/* Sidebar Menu */}
      <div className="no-scrollbar flex flex-col overflow-y-auto duration-300 ease-linear">
        <nav>
          {navGroups.map((group) => (
            <div key={group.group}>
              <h3 className="mb-3 text-xs leading-[20px] text-gray-500 dark:text-gray-400">
                {showContent ? (
                  <span className="ms-3">{group.group}</span>
                ) : (
                  <HorizontaLDots className="mx-auto size-6" />
                )}
              </h3>

              <ul className="mb-7 flex flex-col gap-1">
                {group.items.map((item) => {
                  const isActive = selected === item.id;
                  const isOpen = openDropdown === item.id;
                  return (
                    <li key={item.id}>
                      <a
                        href="#"
                        onClick={(e) => {
                          e.preventDefault();
                          setSelected(item.id);
                          if (item.children) {
                            setOpenDropdown(isOpen ? null : item.id);
                          }
                        }}
                        className={cn(
                          "group flex items-center gap-2 rounded-full px-3 py-2 text-sm font-normal",
                          isActive
                            ? "bg-gray-100 dark:bg-gray-800"
                            : "bg-transparent hover:bg-gray-100 dark:hover:bg-gray-800",
                        )}
                      >
                        <span
                          className={`shrink-0 [&_svg]:size-5 ${
                            isActive
                              ? "text-gray-800 dark:text-white/90"
                              : "text-gray-500 group-hover:text-gray-800 dark:text-gray-400 dark:group-hover:text-white/90"
                          }`}
                        >
                          {item.icon}
                        </span>
                        {showContent && (
                          <span
                            className={`menu-item-text ${
                              isActive
                                ? "text-gray-800 dark:text-white/90"
                                : "text-gray-500 group-hover:text-gray-800 dark:text-gray-400 dark:group-hover:text-white/90"
                            }`}
                          >
                            {item.label}
                          </span>
                        )}
                        {item.children && showContent && (
                          <ChevronDownIcon
                            className={cn(
                              "ms-auto h-5 w-5 transition-transform duration-200",
                              isOpen
                                ? "rotate-180 dark:text-white/90"
                                : "text-gray-500 group-hover:text-gray-800 dark:group-hover:text-white/90",
                            )}
                          />
                        )}
                      </a>

                      {/* Accordion dropdown */}
                      {item.children && (
                        <div
                          className={cn(
                            "menu-accordion",
                            isOpen && showContent && "open",
                            !showContent && "hidden",
                          )}
                        >
                          <div>
                            <ul className="menu-dropdown ms-9 mt-3 flex flex-col space-y-2 border-s border-gray-200 ps-5 dark:border-gray-800">
                              {item.children.map((child) => (
                                <li key={child.id}>
                                  <a
                                    href="#"
                                    onClick={(e) => {
                                      e.preventDefault();
                                      setSelected(child.id);
                                    }}
                                    className={cn(
                                      "text-sm hover:text-gray-800 dark:hover:text-white/90",
                                      selected === child.id
                                        ? "text-gray-800 dark:text-white/90"
                                        : "text-gray-500 dark:text-gray-400",
                                    )}
                                  >
                                    {child.label}
                                  </a>
                                </li>
                              ))}
                            </ul>
                          </div>
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>
      </div>
      {/* /Sidebar Menu */}
    </aside>
  );
}
