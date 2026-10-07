import { type ReactNode, useRef, useState } from "react";
import AiSidebarHistory from "../../../components/ai/AiSidebarHistory";
import { useClickOutside } from "../../../hooks/useClickOutside";
import { FlashIcon, MicrophoneIcon, PaperClipIcon } from "../../../icons";
import GeneratorTopBar from "../../../components/ai/GeneratorTopbar";
import Tooltip from "../../../components/ui/tooltip/Tooltip";

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

const GEMINI_ICON = (
  <img src="./images/model/gemini.svg" width="18" height="18" alt="Gemini" />
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
  { label: "Gemini 2.5 Pro", icon: GEMINI_ICON },
  { label: "Gemini Flash", icon: GEMINI_ICON },
];

// ─────────────────────────────────────────────────────────────────────────────

interface GeneratorLayoutProps {
  children: ReactNode;
}

export default function CodeGeneratorWrapper({
  children,
}: GeneratorLayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [modelOpen, setModelOpen] = useState(false);
  const [modelSelected, setModelSelected] = useState("Claude Sonnet 4.6");
  const modelDropdownRef = useRef<HTMLDivElement>(null);
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
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
          >
            <path
              d="M4 6L20 6M4 18L20 18M4 12L20 12"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
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
                <Tooltip content="Attachment" placement="top" variant="light">
                  <label className="flex size-9 cursor-pointer items-center justify-center gap-1.5 rounded-lg border border-gray-200 text-sm text-gray-500 dark:hover:bg-gray-900 hover:text-gray-700 dark:border-gray-700 dark:text-gray-400 dark:hover:text-gray-300">
                    <input type="file" className="sr-only" />
                    <PaperClipIcon className="size-5" />
                  </label>
                </Tooltip>

                <div className="flex items-center gap-2">
                  {/* Model dropdown */}
                  <div className="relative" ref={modelDropdownRef}>
                    <button
                      onClick={() => setModelOpen((prev) => !prev)}
                      aria-expanded={modelOpen}
                      className="flex items-center gap-1.5 px-2.5 py-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-900 text-sm text-gray-700 dark:text-gray-400"
                    >
                      {currentModel?.icon}
                      <span>{modelSelected}</span>
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        width="18"
                        height="18"
                        viewBox="0 0 18 18"
                        fill="none"
                        className={`transition-transform duration-150${modelOpen ? " rotate-180" : ""}`}
                      >
                        <path
                          d="M4.3125 7.21875L9 11.9063L13.6875 7.21875"
                          stroke="currentColor"
                          strokeWidth="1.5"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
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
