import { useSidebar } from "@/context/SidebarContext";
import { cn } from "@/utils";
import { useEffect, useRef, useState } from "react";

const versions = ["v1.0.1", "v2.0.8-alpha", "V3.0.9-beta1"];

const navSections = [
  {
    id: "GetStarted",
    label: "Get Started",
    items: [
      { id: "QuickStart", label: "Quick Start" },
      { id: "InstallationGuide", label: "Installation Guide" },
      { id: "Tutorials", label: "Tutorials" },
      { id: "Configuration", label: "Configuration" },
      { id: "BestPractices", label: "Best Practices" },
      { id: "FAQ", label: "FAQ" },
    ],
  },
  {
    id: "DeveloperFeatures",
    label: "Developer Features",
    items: [
      { id: "Plugins", label: "Plugins" },
      { id: "CustomHooks", label: "Custom Hooks" },
      { id: "StateManagement", label: "State Management" },
      { id: "PerformanceTips", label: "Performance Tips" },
    ],
  },
  {
    id: "SDKDocumentation",
    label: "SDK Documentation",
    items: [
      { id: "SDKGettingStarted", label: "Getting Started" },
      { id: "SDKAuthentication", label: "Authentication" },
      { id: "ErrorHandling", label: "Error Handling" },
      { id: "RateLimits", label: "Rate Limits" },
    ],
  },
  {
    id: "APIReference",
    label: "API Reference",
    items: [
      { id: "RESTAPI", label: "REST API" },
      { id: "GraphQL", label: "GraphQL" },
      { id: "Webhooks", label: "Webhooks" },
      { id: "SDKMethods", label: "SDK Methods" },
    ],
  },
  {
    id: "IntegrationGuides",
    label: "Integration Guides",
    items: [
      { id: "OAuthSetup", label: "OAuth Setup" },
      { id: "ThirdPartyServices", label: "Third-party Services" },
      { id: "DatabaseIntegration", label: "Database Integration" },
    ],
  },
  {
    id: "TutorialsSection",
    label: "Tutorials",
    items: [
      { id: "BuildingDashboard", label: "Building a Dashboard" },
      { id: "CRUDOperations", label: "CRUD Operations" },
      { id: "AuthFlow", label: "Authentication Flow" },
    ],
  },
  {
    id: "ReleaseNotes",
    label: "Release Notes",
    items: [
      { id: "v200", label: "v2.0.0" },
      { id: "v150", label: "v1.5.0" },
      { id: "v100", label: "v1.0.0" },
    ],
  },
];

export default function SidebarFour() {
  const { isExpanded, isMobileOpen } = useSidebar();
  const isVisible = isExpanded || isMobileOpen;
  const [versionOpen, setVersionOpen] = useState(false);
  const [activeVersion, setActiveVersion] = useState("v2.0.8-alpha");
  const [selected, setSelected] = useState("InstallationGuide");
  const [openSection, setOpenSection] = useState("GetStarted");

  const versionDropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        versionDropdownRef.current &&
        !versionDropdownRef.current.contains(e.target as Node)
      ) {
        setVersionOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <aside
      className={cn(
        "sidebar fixed start-0 top-16 z-9999 flex h-screen flex-col bg-gray-50 transition-all duration-300 lg:top-19 xl:sticky xl:top-0 dark:bg-gray-900",
        isVisible
          ? "w-[290px] translate-x-0 border-e border-gray-200 dark:border-gray-800"
          : "w-0 -translate-x-full overflow-hidden border-none rtl:translate-x-full",
      )}
    >
      {/* SIDEBAR HEADER */}
      <div className="px-5 pt-5 pb-7">
        <div
          ref={versionDropdownRef}
          className="relative flex items-center justify-between gap-2.5"
        >
          <div className="flex items-center gap-3">
            <a href="index.html" className="shrink-0">
              <img
                src="./images/logo/logo-icon.svg"
                alt="Logo"
                className="h-8 w-8"
              />
            </a>
            <div>
              <span className="text-sm font-normal text-gray-800 dark:text-white/90">
                TailAdmin Docs
              </span>
              <span className="flex items-center gap-1 rounded text-xs font-normal text-gray-500 dark:text-gray-400">
                {activeVersion}
              </span>
            </div>
          </div>

          <div className="ms-auto">
            <button
              onClick={() => setVersionOpen(!versionOpen)}
              className="inline-flex size-5 items-center justify-center rounded-md border border-gray-200 text-gray-800 dark:border-gray-800 dark:text-gray-400"
            >
              <svg
                width="16"
                height="16"
                viewBox="0 0 16 16"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d="M12.1668 6.24235L8.00016 2.07568L3.8335 6.24235M3.8335 9.75736L8.00016 13.924L12.1668 9.75736"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
          </div>

          {/* Version Dropdown */}
          {versionOpen && (
            <div className="absolute inset-x-0 top-full z-50 mt-2 overflow-hidden rounded-lg bg-white p-1.5 shadow-lg dark:border-gray-700 dark:bg-gray-800">
              {versions.map((version) => (
                <button
                  key={version}
                  onClick={() => {
                    setActiveVersion(version);
                    setVersionOpen(false);
                  }}
                  className={cn(
                    "flex w-full items-center justify-between rounded-lg px-3 py-2 text-sm font-normal text-gray-700 hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-gray-700",
                    activeVersion === version && "bg-gray-100 dark:bg-gray-700",
                  )}
                >
                  <span>{version}</span>
                  {activeVersion === version && (
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      width="16"
                      height="16"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      className="text-gray-700 dark:text-gray-300"
                    >
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
      {/* SIDEBAR HEADER */}

      {/* SEARCH */}
      <div className="px-5 pb-5">
        <div className="relative">
          <span className="pointer-events-none absolute start-3 top-1/2 -translate-y-1/2 text-gray-400">
            <svg
              width="18"
              height="18"
              viewBox="0 0 18 18"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M12.944 12.945L15.9366 15.9376M14.8125 8.43695C14.8125 11.9569 11.9583 14.8104 8.4375 14.8104C4.91669 14.8104 2.0625 11.9569 2.0625 8.43695C2.0625 4.91698 4.91669 2.06348 8.4375 2.06348C11.9583 2.06348 14.8125 4.91698 14.8125 8.43695Z"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </span>
          <input
            type="text"
            placeholder="Search the docs"
            className="dark:bg-dark-900 h-9 w-full rounded-lg border border-gray-200 bg-transparent py-2.5 ps-9 pe-3 text-sm text-gray-800 shadow-theme-xs placeholder:text-gray-400 focus:border-brand-300 focus:ring-3 focus:ring-brand-500/10 focus:outline-hidden dark:border-gray-800 dark:bg-white/3 dark:text-white/90 dark:placeholder:text-white/30 dark:focus:border-brand-800"
          />
        </div>
      </div>
      {/* SEARCH */}

      {/* NAV */}
      <div className="no-scrollbar flex flex-col overflow-y-auto px-5 pb-10">
        <nav className="space-y-1">
          {navSections.map((section) => (
            <div key={section.id}>
              <button
                onClick={() =>
                  setOpenSection(openSection === section.id ? "" : section.id)
                }
                className={cn(
                  "flex w-full items-center justify-between rounded-lg px-3 py-1.5 text-sm font-normal text-gray-800 dark:text-white/90",
                  openSection === section.id
                    ? "bg-gray-100 dark:bg-gray-800"
                    : "hover:bg-gray-100 dark:hover:bg-gray-800",
                )}
              >
                {section.label}
                <svg
                  className={`transition-transform duration-200 ${
                    openSection === section.id ? "rotate-180" : ""
                  }`}
                  width="16"
                  height="16"
                  viewBox="0 0 16 16"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    d="M3.8335 5.9165L8.00016 10.0832L12.1668 5.9165"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </button>

              <div
                className={cn(
                  "menu-accordion",
                  openSection === section.id && "open",
                )}
              >
                <div>
                  <ul className="flex flex-col gap-3 px-5 py-2">
                    {section.items.map((item) => (
                      <li key={item.id}>
                        <a
                          href="#"
                          onClick={(e) => {
                            e.preventDefault();
                            setSelected(item.id);
                          }}
                          className={cn(
                            "text-sm",
                            selected === item.id
                              ? "text-brand-500"
                              : "text-gray-500 hover:text-brand-500 dark:text-gray-400 dark:hover:text-brand-400",
                          )}
                        >
                          {item.label}
                        </a>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          ))}
        </nav>
      </div>
      {/* NAV */}
    </aside>
  );
}
