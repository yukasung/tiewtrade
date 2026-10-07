import { cn } from "@/utils";
import { useState } from "react";

const versions = ["v1.0.1", "v2.0.8-alpha", "V3.0.9-beta1"];

type Section = "GetStarted" | "Components";

const getStartedItems = [
  { id: "Introduction", label: "Introduction" },
  { id: "QuickStart", label: "Quick Start" },
  { id: "FrameworkGuides", label: "Framework guides" },
  { id: "Usage", label: "Usage" },
  { id: "Javascript", label: "Javascript" },
  { id: "Accessibility", label: "Accessibility" },
  { id: "UpgradeGuide", label: "Upgrade Guide" },
  { id: "License", label: "License" },
];

const componentItems = [
  { id: "Accordion", label: "Accordion" },
  { id: "Alert", label: "Alert" },
  { id: "Avatar", label: "Avatar" },
  { id: "Badge", label: "Badge" },
  { id: "Button", label: "Button" },
  { id: "Card", label: "Card" },
  { id: "Carousel", label: "Carousel" },
  { id: "ChatBubble", label: "Chat Bubble" },
  { id: "Collapse", label: "Collapse" },
  { id: "Indicator", label: "Indicator" },
  { id: "ListGroup", label: "List Group" },
  { id: "Loading", label: "Loading" },
  { id: "Progress", label: "Progress" },
  { id: "RadialProgress", label: "Radial progress" },
  { id: "Skeleton", label: "Skeleton" },
  { id: "Stack", label: "Stack" },
];

type SidebarFiveProps = {
  sidebarToggle?: boolean;
  docsSidebarOpen?: boolean;
};

export default function SidebarFive({
  sidebarToggle = true,
  docsSidebarOpen = true,
}: SidebarFiveProps) {
  const [selected, setSelected] = useState("FrameworkGuides");
  const [activeVersion, setActiveVersion] = useState("v2.0.8-alpha");
  const [versionOpen, setVersionOpen] = useState(false);
  const [openSections, setOpenSections] = useState<Section[]>([
    "GetStarted",
    "Components",
  ]);

  const toggleSection = (section: Section) => {
    setOpenSections((prev) =>
      prev.includes(section)
        ? prev.filter((s) => s !== section)
        : [...prev, section],
    );
  };

  const isSectionOpen = (section: Section) => openSections.includes(section);

  return (
    <aside
      className={cn(
        "sidebar fixed start-0 top-16 z-9999 flex h-screen w-[290px] flex-col border-e border-gray-200 bg-gray-50 transition-all duration-300 lg:top-19 xl:sticky xl:top-0 xl:translate-x-0 xl:rtl:translate-x-0 dark:border-gray-800 dark:bg-gray-900",
        sidebarToggle
          ? "translate-x-0"
          : "-translate-x-full rtl:translate-x-full",
        !docsSidebarOpen &&
          "xl:w-0 xl:min-w-0 xl:overflow-hidden xl:border-e-0",
      )}
    >
      {/* SIDEBAR HEADER */}
      <div className="px-5 pt-5 pb-7">
        <div className="relative flex items-center justify-between gap-2.5">
          <div className="flex items-center gap-3">
            <a href="#" className="shrink-0">
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
              <span className="flex items-center gap-1 rounded text-xs font-medium text-gray-500 dark:text-gray-400">
                {activeVersion}
              </span>
            </div>
          </div>

          <div className="ms-auto">
            <button
              onClick={() => setVersionOpen((prev) => !prev)}
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
                    "mb-0.5 flex w-full items-center justify-between rounded-lg px-3 py-2 text-sm text-gray-800 dark:text-white/90",
                    activeVersion === version
                      ? "bg-gray-100 dark:bg-gray-700"
                      : "hover:bg-gray-100 dark:hover:bg-gray-700",
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
      {/* SIDEBAR HEADER END */}

      {/* NAV */}
      <div className="no-scrollbar flex flex-col overflow-y-auto pb-10">
        <nav>
          {/* Get Started */}
          <div>
            <button
              onClick={() => toggleSection("GetStarted")}
              className="flex w-full items-center justify-between px-5 py-3 text-sm font-normal text-gray-700 dark:text-gray-300"
            >
              Get Started
              <svg
                className={`text-gray-400 transition-transform duration-200 ${
                  isSectionOpen("GetStarted") ? "rotate-180" : ""
                }`}
                width="16"
                height="16"
                viewBox="0 0 16 16"
                fill="none"
              >
                <path
                  d="M3.83325 6.41675L7.99992 10.5834L12.1666 6.41675"
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
                isSectionOpen("GetStarted") && "open",
              )}
            >
              <div>
                <ul className="ms-5 flex flex-col gap-3 border-s border-gray-200 dark:border-gray-700">
                  {getStartedItems.map((item) => (
                    <li key={item.id}>
                      <a
                        href="#"
                        onClick={(e) => {
                          e.preventDefault();
                          setSelected(item.id);
                        }}
                        className={cn(
                          "docs-border-item",
                          selected === item.id
                            ? "docs-border-item-active"
                            : "docs-border-item-inactive",
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
          {/* Get Started End */}

          {/* Components */}
          <div>
            <button
              onClick={() => toggleSection("Components")}
              className="flex w-full items-center justify-between px-5 py-3 text-sm font-normal text-gray-700 dark:text-gray-300"
            >
              Components
              <svg
                className={`text-gray-400 transition-transform duration-200 ${
                  isSectionOpen("Components") ? "rotate-180" : ""
                }`}
                width="16"
                height="16"
                viewBox="0 0 16 16"
                fill="none"
              >
                <path
                  d="M3.83325 6.41675L7.99992 10.5834L12.1666 6.41675"
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
                isSectionOpen("Components") && "open",
              )}
            >
              <div>
                <ul className="ms-5 flex flex-col gap-3 border-s border-gray-200 dark:border-gray-700">
                  {componentItems.map((item) => (
                    <li key={item.id}>
                      <a
                        href="#"
                        onClick={(e) => {
                          e.preventDefault();
                          setSelected(item.id);
                        }}
                        className={cn(
                          "docs-border-item",
                          selected === item.id
                            ? "docs-border-item-active"
                            : "docs-border-item-inactive",
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
          {/* Components End */}
        </nav>
      </div>
      {/* NAV END */}
    </aside>
  );
}
