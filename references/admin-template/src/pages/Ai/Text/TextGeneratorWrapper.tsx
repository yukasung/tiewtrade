import { type ReactNode, useRef, useState } from "react";
import AiSidebarHistory from "../../../components/ai/AiSidebarHistory";
import { useClickOutside } from "../../../hooks/useClickOutside";
import {
  ChevronDownIcon,
  CloseIcon,
  FlashIcon,
  GlobeIcon,
  MenuIcon,
  MicrophoneIcon,
  PlusIcon,
  TelescopeIcon,
  UploadIcon,
} from "../../../icons";
import GeneratorTopBar from "../../../components/ai/GeneratorTopbar";

// ─── Style helpers ─────────────────────────────────────────────────────────────

const MENU_ITEM_BASE =
  "flex w-full items-center gap-2 rounded-lg px-1.5 py-2 text-sm hover:bg-gray-100 hover:text-gray-900 dark:hover:bg-gray-800 dark:hover:text-white";

const menuItemClass = (active: boolean) =>
  `${MENU_ITEM_BASE} ${active ? "bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-white" : "text-gray-700 dark:text-gray-400"}`;

// ─── Model icon fragments (reused in trigger + list) ──────────────────────────

const GPT_ICON = (
  <>
    <img
      src="./images/model/gpt-light.svg"
      width="18"
      height="18"
      className="block dark:hidden"
      alt="gpt"
    />
    <img
      src="./images/model/gpt-dark.svg"
      width="18"
      height="18"
      className="hidden dark:block"
      alt="gpt"
    />
  </>
);

const CLAUDE_ICON = (
  <img src="./images/model/claude.svg" width="18" height="18" alt="claude" />
);

const GROK_ICON = (
  <>
    <img
      src="./images/model/grok-light.svg"
      width="18"
      height="18"
      className="block dark:hidden"
      alt="grok"
    />
    <img
      src="./images/model/grok-dark.svg"
      width="18"
      height="18"
      className="hidden dark:block"
      alt="grok"
    />
  </>
);

// ─── Data ──────────────────────────────────────────────────────────────────────

interface ModelOption {
  label: string;
  icon: ReactNode;
  badge?: ReactNode;
}

const MODEL_OPTIONS: ModelOption[] = [
  {
    label: "Auto",
    icon: <FlashIcon className="size-[18px] shrink-0" />,
  },
  {
    label: "GPT 4.5",
    icon: GPT_ICON,
    badge: (
      <span className="bg-success-50 dark:bg-success-500/10 dark:text-success-500 text-success-600 inline-flex h-5 items-center justify-center rounded-full px-2 text-xs">
        New
      </span>
    ),
  },
  { label: "GPT 5.5", icon: GPT_ICON },
  { label: "Claude Sonnet 4.5", icon: CLAUDE_ICON },
  { label: "Claude Sonnet 4.6", icon: CLAUDE_ICON },
  { label: "Grok 3.0", icon: GROK_ICON },
  { label: "Grok 2.0", icon: GROK_ICON },
];

const SEARCH_OPTIONS = [
  { label: "Web Search", icon: <GlobeIcon className="size-[18px] shrink-0" /> },
  {
    label: "Deep Search",
    icon: <TelescopeIcon className="size-[18px] shrink-0" />,
  },
];

const CHIP_ICONS: Record<string, ReactNode> = {
  "Upload File": <UploadIcon className="size-5 shrink-0 group-hover:hidden" />,
  "Web Search": <GlobeIcon className="size-5 shrink-0 group-hover:hidden" />,
  "Deep Search": (
    <TelescopeIcon className="size-5 shrink-0 group-hover:hidden" />
  ),
};

// ─────────────────────────────────────────────────────────────────────────────

interface GeneratorLayoutProps {
  children: ReactNode;
}

export default function GeneratorWrapper({ children }: GeneratorLayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [selected, setSelected] = useState("");
  const [modelOpen, setModelOpen] = useState(false);
  const [modelSelected, setModelSelected] = useState("Claude Sonnet 4.6");
  const dropdownRef = useRef<HTMLDivElement>(null);
  const modelDropdownRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  useClickOutside(dropdownRef, () => setDropdownOpen(false));
  useClickOutside(modelDropdownRef, () => setModelOpen(false));

  const currentModel = MODEL_OPTIONS.find((m) => m.label === modelSelected);

  return (
    <div className="relative h-[calc(100vh-134px)] xl:h-[calc(100vh-76px)] px-4 xl:flex xl:px-0">
      <div className="my-6 flex items-center justify-between rounded-2xl border border-gray-200 bg-white p-3 xl:hidden dark:border-gray-800 dark:bg-gray-900">
        <h4 className="ps-2 text-lg font-medium text-gray-800 dark:text-white/90">
          Chats History
        </h4>
        <button
          onClick={() => setSidebarOpen(true)}
          className="inline-flex h-11 w-11 items-center justify-center rounded-lg border border-gray-300 text-gray-700 dark:border-gray-700 dark:text-gray-400"
        >
          <MenuIcon className="size-6" />
        </button>
      </div>

      <div className="flex-1 xl:pb-10">
        <GeneratorTopBar />
        <div className="relative mx-auto items-center max-w-[720px]">
          {children}
          <div className="fixed bottom-5 lg:bottom-10 left-1/2 z-20 w-full -translate-x-1/2 transform px-4 sm:px-6 lg:px-8">
            <div className="mx-auto w-full max-w-[720px] rounded-2xl border border-gray-200 bg-white p-3 shadow-xs dark:border-gray-700 dark:bg-white/5">
              <textarea
                placeholder="Type your prompt here..."
                className="h-20 w-full resize-none border-none bg-transparent p-2 font-normal text-gray-800 outline-none placeholder:text-gray-400 focus:ring-0 dark:text-white"
              />

              <div className="flex items-center justify-between pt-2">
                <div className="flex items-center gap-1">
                  {/* + Dropdown */}
                  <div className="relative" ref={dropdownRef}>
                    <button
                      onClick={() => setDropdownOpen((prev) => !prev)}
                      className="flex size-9 items-center   justify-center gap-1.5 rounded-lg border border-gray-100 text-sm text-gray-700 hover:bg-gray-100  hover:text-gray-800 dark:border-gray-700 dark:text-gray-400 dark:hover:bg-gray-900 dark:hover:text-gray-300"
                    >
                      <PlusIcon className="size-5" />
                    </button>
                    {dropdownOpen && (
                      <ul
                        role="menu"
                        className="absolute bottom-full start-0 mb-2 min-w-[200px] space-y-0.5 rounded-xl bg-white p-1.5 shadow-md dark:bg-gray-900"
                      >
                        <li>
                          <input
                            type="file"
                            ref={fileInputRef}
                            className="hidden"
                          />
                          <button
                            onClick={() => {
                              fileInputRef.current?.click();
                              setDropdownOpen(false);
                            }}
                            className={menuItemClass(false)}
                            role="menuitem"
                          >
                            <UploadIcon className="size-[18px] shrink-0" />
                            Upload File
                          </button>
                        </li>
                        <hr className="my-1 border-gray-200 dark:border-white/10" />
                        {SEARCH_OPTIONS.map(({ label, icon }) => (
                          <li key={label}>
                            <button
                              onClick={() => {
                                setSelected(label);
                                setDropdownOpen(false);
                              }}
                              className={menuItemClass(selected === label)}
                              role="menuitem"
                            >
                              {icon}
                              {label}
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>

                  {/* After-select chip */}
                  {selected !== "" && (
                    <button
                      onClick={() => setSelected("")}
                      className="text-brand-500 group hover:bg-brand-500/10 flex h-9 items-center gap-2 rounded-lg px-2.5 py-2 text-sm font-medium"
                    >
                      <CloseIcon className="bg-brand-500/20 hidden size-5 shrink-0 rounded-full group-hover:block" />
                      {CHIP_ICONS[selected]}
                      <span className="hidden sm:inline">{selected}</span>
                    </button>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  {/* Model dropdown */}
                  <div className="relative" ref={modelDropdownRef}>
                    <button
                      onClick={() => setModelOpen((prev) => !prev)}
                      aria-expanded={modelOpen}
                      className="flex items-center dark:hover:bg-gray-900 h-9 gap-1.5 px-2.5 py-2 rounded-lg hover:bg-gray-100 text-sm text-gray-700 dark:text-gray-400"
                    >
                      {currentModel?.icon}
                      <span>{modelSelected}</span>
                      <ChevronDownIcon
                        className={`transition-transform duration-150${modelOpen ? " rotate-180" : ""}`}
                      />
                    </button>
                    {modelOpen && (
                      <ul
                        role="menu"
                        className="absolute end-0 bottom-full mb-2 min-w-[220px] space-y-0.5 rounded-xl bg-white p-1.5 shadow-md dark:bg-gray-900"
                      >
                        {MODEL_OPTIONS.map(({ label, icon, badge }) => (
                          <li key={label}>
                            <button
                              onClick={() => {
                                setModelSelected(label);
                                setModelOpen(false);
                              }}
                              className={menuItemClass(modelSelected === label)}
                              role="menuitem"
                            >
                              {icon}
                              {label}
                              {badge}
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>

                  {/* Send Button */}
                  <button className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-gray-900 text-white transition hover:bg-gray-800 dark:bg-white/90 dark:text-gray-800 dark:hover:bg-gray-900 dark:hover:text-white/90">
                    <MicrophoneIcon className="size-5" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <AiSidebarHistory
        isSidebarOpen={sidebarOpen}
        onCloseSidebar={() => setSidebarOpen(false)}
      />
    </div>
  );
}
