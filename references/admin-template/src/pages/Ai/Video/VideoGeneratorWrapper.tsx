import { type ReactNode, useRef, useState } from "react";
import AiSidebarHistory from "../../../components/ai/AiSidebarHistory";
import Tooltip from "../../../components/ui/tooltip/Tooltip";
import { useClickOutside } from "../../../hooks/useClickOutside";
import {
  AspectIcon,
  ChevronDownIcon,
  ChevronLeftIcon,
  ClockIcon,
  DiamondIcon,
  FlashIcon,
  HorizontalSlideIcon,
  MenuIcon,
  MicrophoneIcon,
  Mute,
  PaperClipIcon,
  Sound,
  StackIcon,
} from "../../../icons";
import GeneratorTopBar from "../../../components/ai/GeneratorTopbar";

// ─── Style helpers ─────────────────────────────────────────────────────────────

const MENU_ITEM_BASE =
  "flex w-full items-center gap-2 rounded-lg px-1.5 py-2 text-sm hover:bg-gray-100 hover:text-gray-900 dark:hover:bg-gray-800 dark:hover:text-white";

const menuItemClass = (active: boolean) =>
  `${MENU_ITEM_BASE} ${active ? "bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-white" : "text-gray-700 dark:text-gray-400"}`;

// ─── Model icon fragments (reused in trigger + list) ──────────────────────────

const GOOGLE_ICON = (
  <img src="./images/model/google.svg" width="18" height="18" alt="Google" />
);

const KLING_ICON = (
  <img src="./images/model/kling.svg" width="18" height="18" alt="Kling" />
);

const SEEDREAM_ICON = (
  <img
    src="./images/model/seedream.svg"
    width="18"
    height="18"
    alt="Seedream"
  />
);

const RUNWAY_ICON = (
  <>
    <img
      src="./images/model/runway.svg"
      width="18"
      height="18"
      className="block dark:hidden"
      alt="Runway"
    />
    <img
      src="./images/model/runway-dark.svg"
      width="18"
      height="18"
      className="hidden dark:block"
      alt="Runway"
    />
  </>
);

const GROK_VIDEO_ICON = (
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

const QWEN_ICON = (
  <img src="./images/model/qwen.svg" width="18" height="18" alt="Wen" />
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
  { label: "Google Veo 3.1", icon: GOOGLE_ICON },
  { label: "Kling 3.0 Pro", icon: KLING_ICON },
  { label: "Seedream 1.5", icon: SEEDREAM_ICON },
  { label: "Runway 4.5", icon: RUNWAY_ICON },
  { label: "xAI Grok Video", icon: GROK_VIDEO_ICON },
  { label: "Wen 2.6", icon: QWEN_ICON },
];

// ─────────────────────────────────────────────────────────────────────────────

const aspectRatios = [
  {
    value: "16:9",
    icon: (
      <svg
        className="shrink-0"
        xmlns="http://www.w3.org/2000/svg"
        width="18"
        height="18"
        viewBox="0 0 18 18"
        fill="none"
      >
        <path
          d="M14.25 5.25H3.75C2.92157 5.25 2.25 5.92157 2.25 6.75V11.25C2.25 12.0784 2.92157 12.75 3.75 12.75H14.25C15.0784 12.75 15.75 12.0784 15.75 11.25V6.75C15.75 5.92157 15.0784 5.25 14.25 5.25Z"
          stroke="currentColor"
          strokeWidth="1.3"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    ),
  },
  {
    value: "4:3",
    icon: (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="18"
        height="18"
        viewBox="0 0 18 18"
        fill="none"
      >
        <path
          d="M13.5 4.5H4.5C3.67157 4.5 3 5.17157 3 6V12C3 12.8284 3.67157 13.5 4.5 13.5H13.5C14.3284 13.5 15 12.8284 15 12V6C15 5.17157 14.3284 4.5 13.5 4.5Z"
          stroke="currentColor"
          strokeWidth="1.3"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    ),
  },
  {
    value: "1:1",
    icon: (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="18"
        height="18"
        viewBox="0 0 18 18"
        fill="none"
      >
        <path
          d="M12.75 3.75H5.25C4.42157 3.75 3.75 4.42157 3.75 5.25V12.75C3.75 13.5784 4.42157 14.25 5.25 14.25H12.75C13.5784 14.25 14.25 13.5784 14.25 12.75V5.25C14.25 4.42157 13.5784 3.75 12.75 3.75Z"
          stroke="currentColor"
          strokeWidth="1.3"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    ),
  },
  {
    value: "3:4",
    icon: (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="18"
        height="18"
        viewBox="0 0 18 18"
        fill="none"
      >
        <path
          d="M13.5001 13.5L13.5001 4.5C13.5001 3.67157 12.8285 3 12.0001 3L6.00012 3C5.17169 3 4.50012 3.67157 4.50012 4.5L4.50012 13.5C4.50012 14.3284 5.17169 15 6.00012 15L12.0001 15C12.8285 15 13.5001 14.3284 13.5001 13.5Z"
          stroke="currentColor"
          strokeWidth="1.3"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    ),
  },
  {
    value: "9:16",
    icon: (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="18"
        height="18"
        viewBox="0 0 18 18"
        fill="none"
      >
        <path
          d="M12.75 14.249L12.75 3.74902C12.75 2.9206 12.0784 2.24902 11.25 2.24902L6.75 2.24902C5.92157 2.24902 5.25 2.9206 5.25 3.74902L5.25 14.249C5.25 15.0775 5.92157 15.749 6.75 15.749L11.25 15.749C12.0784 15.749 12.75 15.0775 12.75 14.249Z"
          stroke="currentColor"
          strokeWidth="1.3"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    ),
  },
];

const variants = ["1", "2", "3", "4"];

const resolutions = ["2K", "4K", "8K", "16K"];

// ─── SubMenu ──────────────────────────────────────────────────────────────────

interface SubMenuProps {
  title: string;
  children: ReactNode;
  onBack: () => void;
}

function SubMenu({ title, children, onBack }: SubMenuProps) {
  return (
    <div>
      <div className="flex items-center gap-1.5 border-b border-gray-100 px-2 py-2 dark:border-gray-800">
        <button
          onClick={onBack}
          className="flex items-center justify-center rounded-lg p-1.5 text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-gray-800"
        >
          <ChevronLeftIcon className="size-4 rtl:rotate-180" />
        </button>
        <span className="text-sm font-medium text-gray-800 dark:text-white">
          {title}
        </span>
      </div>
      <div className="space-y-0.5 p-1.5">{children}</div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────

interface GeneratorLayoutProps {
  children: ReactNode;
}

export default function ImageGeneratorWrapper({
  children,
}: GeneratorLayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [modelOpen, setModelOpen] = useState(false);
  const [modelSelected, setModelSelected] = useState("Google Veo 3.1");
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState("3:4");
  const [variantOpen, setVariantOpen] = useState(false);
  const [variantSelected, setVariantSelected] = useState("1");
  const [resolutionOpen, setResolutionOpen] = useState(false);
  const [resolutionSelected, setResolutionSelected] = useState("2K");
  const [durationOpen, setDurationOpen] = useState(false);
  const [durationSelected, setDurationSelected] = useState("30s");
  const [audioOn, setAudioOn] = useState(true);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [activeMenu, setActiveMenu] = useState<
    "aspect-ratio" | "variants" | "resolution" | "duration" | null
  >(null);
  const modelDropdownRef = useRef<HTMLDivElement>(null);
  const aspectRatioRef = useRef<HTMLDivElement>(null);
  const variantDropdownRef = useRef<HTMLDivElement>(null);
  const resolutionDropdownRef = useRef<HTMLDivElement>(null);
  const durationDropdownRef = useRef<HTMLDivElement>(null);
  const mobileMenuRef = useRef<HTMLDivElement>(null);
  useClickOutside(modelDropdownRef, () => setModelOpen(false));
  useClickOutside(aspectRatioRef, () => setOpen(false));
  useClickOutside(variantDropdownRef, () => setVariantOpen(false));
  useClickOutside(resolutionDropdownRef, () => setResolutionOpen(false));
  useClickOutside(durationDropdownRef, () => setDurationOpen(false));
  useClickOutside(mobileMenuRef, () => {
    setMobileMenuOpen(false);
    setActiveMenu(null);
  });

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
          <MenuIcon className="size-5" />
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
                <div className="flex items-center gap-2">
                  <Tooltip content="Attachment" placement="top" variant="light">
                    <label className="flex size-9 cursor-pointer dark:hover:bg-gray-900  items-center justify-center gap-1.5 rounded-lg border border-gray-200 text-sm text-gray-500 hover:text-gray-700 dark:border-gray-700 dark:text-gray-400 dark:hover:text-gray-300">
                      <input type="file" className="sr-only" />
                      <PaperClipIcon className="size-5" />
                    </label>
                  </Tooltip>
                  {/* Mobile Menu */}
                  <div
                    ref={mobileMenuRef}
                    className="relative block sm:hidden"
                    onKeyDown={(e) => {
                      if (e.key === "Escape") {
                        setMobileMenuOpen(false);
                        setActiveMenu(null);
                      }
                    }}
                  >
                    <button
                      type="button"
                      onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                      className="flex size-9 cursor-pointer items-center dark:hover:bg-gray-900  justify-center gap-1.5 rounded-lg border border-gray-200 text-sm text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:hover:text-gray-300"
                    >
                      <HorizontalSlideIcon className="size-5" />
                    </button>

                    {mobileMenuOpen && (
                      <div className="shadow-theme-md absolute bottom-full start-0 mb-2 w-56 overflow-hidden rounded-2xl bg-white p-1.5 dark:bg-gray-900">
                        {/* Main Menu */}
                        {activeMenu === null && (
                          <div>
                            <button
                              onClick={() => setActiveMenu("aspect-ratio")}
                              className="flex w-full items-center  justify-between gap-2 rounded-lg px-3.5 py-3 text-gray-800 hover:bg-gray-100 dark:text-white/90 dark:hover:bg-gray-800"
                            >
                              <div className="flex items-center gap-2.5">
                                <AspectIcon className="size-4.5" />
                                <span className="text-sm font-medium">
                                  Aspect Ratio
                                </span>
                              </div>
                              <div className="flex items-center gap-1">
                                <span className="text-sm">{selected}</span>
                                <svg
                                  className="rtl:rotate-180"
                                  xmlns="http://www.w3.org/2000/svg"
                                  width="16"
                                  height="16"
                                  viewBox="0 0 16 16"
                                  fill="none"
                                >
                                  <path
                                    d="M5.91669 12.1663L10.0834 7.99967L5.91669 3.83301"
                                    stroke="currentColor"
                                    strokeWidth="1.5"
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                  />
                                </svg>
                              </div>
                            </button>

                            <button
                              onClick={() => setActiveMenu("variants")}
                              className="flex w-full items-center justify-between gap-2 rounded-lg px-3.5 py-3 text-gray-800 hover:bg-gray-100 dark:text-white/90 dark:hover:bg-gray-800"
                            >
                              <div className="flex items-center gap-2.5">
                                <StackIcon className="size-4.5" />
                                <span className="text-sm font-medium">
                                  Variants
                                </span>
                              </div>
                              <div className="flex items-center gap-1">
                                <span className="text-sm">
                                  {variantSelected}
                                </span>
                                <svg
                                  className="rtl:rotate-180"
                                  xmlns="http://www.w3.org/2000/svg"
                                  width="16"
                                  height="16"
                                  viewBox="0 0 16 16"
                                  fill="none"
                                >
                                  <path
                                    d="M5.91669 12.1663L10.0834 7.99967L5.91669 3.83301"
                                    stroke="currentColor"
                                    strokeWidth="1.5"
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                  />
                                </svg>
                              </div>
                            </button>

                            <button
                              onClick={() => setActiveMenu("resolution")}
                              className="flex w-full items-center justify-between gap-2 rounded-lg px-3.5 py-3 text-gray-800 hover:bg-gray-100 dark:text-white/90 dark:hover:bg-gray-800"
                            >
                              <div className="flex items-center gap-2.5">
                                <DiamondIcon className="size-4.5" />
                                <span className="text-sm font-medium">
                                  Resolution
                                </span>
                              </div>
                              <div className="flex items-center gap-1">
                                <span className="text-sm">
                                  {resolutionSelected}
                                </span>
                                <svg
                                  className="rtl:rotate-180"
                                  xmlns="http://www.w3.org/2000/svg"
                                  width="16"
                                  height="16"
                                  viewBox="0 0 16 16"
                                  fill="none"
                                >
                                  <path
                                    d="M5.91669 12.1663L10.0834 7.99967L5.91669 3.83301"
                                    stroke="currentColor"
                                    strokeWidth="1.5"
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                  />
                                </svg>
                              </div>
                            </button>

                            {/* Duration */}
                            <button
                              onClick={() => setActiveMenu("duration")}
                              className="flex w-full items-center justify-between gap-2 rounded-lg px-3.5 py-3 text-gray-800 hover:bg-gray-100 dark:text-white/90  dark:hover:bg-gray-800"
                            >
                              <div className="flex items-center gap-2.5">
                                <ClockIcon className="size-4" />
                                <span className="text-sm font-medium">
                                  Duration
                                </span>
                              </div>
                              <div className="flex items-center gap-1">
                                <span className="text-sm">
                                  {durationSelected}
                                </span>
                                <svg
                                  className="rtl:rotate-180"
                                  xmlns="http://www.w3.org/2000/svg"
                                  width="16"
                                  height="16"
                                  viewBox="0 0 16 16"
                                  fill="none"
                                >
                                  <path
                                    d="M5.91669 12.1663L10.0834 7.99967L5.91669 3.83301"
                                    stroke="currentColor"
                                    strokeWidth="1.5"
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                  />
                                </svg>
                              </div>
                            </button>

                            {/* Audio toggle */}
                            <div className="flex w-full items-center justify-between gap-2 rounded-lg px-3.5 py-3">
                              <div className="flex items-center gap-2.5 text-gray-800 dark:text-white/90">
                                <Sound className="size-4" />
                                <span className="text-sm font-medium">
                                  Audio
                                </span>
                              </div>
                              <label className="relative inline-flex cursor-pointer items-center">
                                <input
                                  type="checkbox"
                                  checked={audioOn}
                                  onChange={() => setAudioOn(!audioOn)}
                                  className="sr-only peer"
                                />
                                <div className="peer h-6 w-11 rounded-full bg-gray-200 after:absolute after:start-[2px] after:top-[2px] after:h-5 after:w-5 after:rounded-full after:bg-white after:transition-all after:content-[''] peer-checked:bg-brand-500 peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full dark:bg-gray-700" />
                              </label>
                            </div>
                          </div>
                        )}

                        {/* Aspect Ratio Submenu */}
                        {activeMenu === "aspect-ratio" && (
                          <SubMenu
                            title="Aspect Ratio"
                            onBack={() => setActiveMenu(null)}
                          >
                            {aspectRatios.map((item) => (
                              <button
                                key={item.value}
                                onClick={() => {
                                  setSelected(item.value);
                                  setMobileMenuOpen(false);
                                  setActiveMenu(null);
                                }}
                                className={`flex w-full items-center gap-2 rounded-lg px-2 py-2 text-sm hover:bg-gray-100 hover:text-gray-900 dark:hover:bg-gray-800 dark:hover:text-white ${
                                  selected === item.value
                                    ? "bg-gray-100 text-gray-900 dark:bg-gray-800 dark:text-white"
                                    : "text-gray-700 dark:text-gray-400"
                                }`}
                              >
                                {item.icon}
                                {item.value}
                              </button>
                            ))}
                          </SubMenu>
                        )}

                        {/* Variants Submenu */}
                        {activeMenu === "variants" && (
                          <SubMenu
                            title="Variants"
                            onBack={() => setActiveMenu(null)}
                          >
                            {variants.map((item) => (
                              <button
                                key={item}
                                onClick={() => {
                                  setVariantSelected(item);
                                  setMobileMenuOpen(false);
                                  setActiveMenu(null);
                                }}
                                className={`flex w-full items-center gap-2 rounded-lg px-2 py-2 text-sm hover:bg-gray-100 hover:text-gray-900 dark:hover:bg-gray-800 dark:hover:text-white ${
                                  variantSelected === item
                                    ? "bg-gray-100 text-gray-900 dark:bg-gray-800 dark:text-white"
                                    : "text-gray-700 dark:text-gray-400"
                                }`}
                              >
                                {item}
                              </button>
                            ))}
                          </SubMenu>
                        )}

                        {/* Duration Submenu */}
                        {activeMenu === "duration" && (
                          <SubMenu
                            title="Duration"
                            onBack={() => setActiveMenu(null)}
                          >
                            {["5s", "10s", "15s", "30s"].map((dur) => (
                              <button
                                key={dur}
                                onClick={() => {
                                  setDurationSelected(dur);
                                  setMobileMenuOpen(false);
                                  setActiveMenu(null);
                                }}
                                className={`flex w-full items-center gap-2 rounded-lg px-2 py-2 text-sm hover:bg-gray-100 hover:text-gray-900 dark:hover:bg-gray-800 dark:hover:text-white ${
                                  durationSelected === dur
                                    ? "bg-gray-100 text-gray-900 dark:bg-gray-800 dark:text-white"
                                    : "text-gray-700 dark:text-gray-400"
                                }`}
                              >
                                {dur}
                              </button>
                            ))}
                          </SubMenu>
                        )}

                        {/* Resolution Submenu */}
                        {activeMenu === "resolution" && (
                          <SubMenu
                            title="Resolution"
                            onBack={() => setActiveMenu(null)}
                          >
                            {resolutions.map((item) => (
                              <button
                                key={item}
                                onClick={() => {
                                  setResolutionSelected(item);
                                  setMobileMenuOpen(false);
                                  setActiveMenu(null);
                                }}
                                className={`flex w-full items-center gap-2 rounded-lg px-2 py-2 text-sm hover:bg-gray-100 hover:text-gray-900 dark:hover:bg-gray-800 dark:hover:text-white ${
                                  resolutionSelected === item
                                    ? "bg-gray-100 text-gray-900 dark:bg-gray-800 dark:text-white"
                                    : "text-gray-700 dark:text-gray-400"
                                }`}
                              >
                                {item}
                              </button>
                            ))}
                          </SubMenu>
                        )}
                      </div>
                    )}
                  </div>
                  <div className="hidden gap-2 sm:flex">
                    <div className="relative" ref={aspectRatioRef}>
                      <Tooltip content="Aspect" placement="top" variant="light">
                        <button
                          type="button"
                          onClick={() => setOpen(!open)}
                          aria-expanded={open}
                          className="flex cursor-pointer items-center dark:hover:bg-gray-900  h-9 justify-center gap-1.5 rounded-lg border border-gray-200 py-2 pe-3 ps-2.5 text-sm text-gray-500 hover:text-gray-700 dark:border-gray-700 dark:text-gray-400 dark:hover:text-gray-300"
                        >
                          <AspectIcon className="size-5" />
                          <span>{selected}</span>
                        </button>
                      </Tooltip>

                      {open && (
                        <ul className="shadow-theme-md absolute bottom-full start-0 mb-2 min-w-[106px] space-y-0.5 rounded-xl bg-white p-1.5 dark:bg-gray-900">
                          {aspectRatios.map((item) => (
                            <li key={item.value}>
                              <button
                                type="button"
                                onClick={() => {
                                  setSelected(item.value);
                                  setOpen(false);
                                }}
                                className={`flex w-full items-center gap-2 rounded-lg px-1.5 py-2 text-sm transition-colors hover:bg-gray-100 hover:text-gray-900 dark:hover:bg-gray-800 dark:hover:text-white ${
                                  selected === item.value
                                    ? "bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-white"
                                    : "text-gray-700 dark:text-gray-400"
                                }`}
                                role="menuitem"
                              >
                                {item.icon}
                                {item.value}
                              </button>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                    <div ref={variantDropdownRef} className="relative">
                      <Tooltip
                        content="Variant"
                        placement="top"
                        variant="light"
                      >
                        <button
                          type="button"
                          onClick={() => setVariantOpen(!variantOpen)}
                          aria-expanded={variantOpen}
                          className="flex cursor-pointer items-center dark:hover:bg-gray-900  h-9 justify-center gap-1.5 rounded-lg border border-gray-200 py-2 pe-3 ps-2.5 text-sm text-gray-500 hover:text-gray-700 dark:border-gray-700 dark:text-gray-400 dark:hover:text-gray-300"
                        >
                          <StackIcon className="size-5" />
                          <span>{variantSelected}</span>
                        </button>
                      </Tooltip>

                      {variantOpen && (
                        <ul className="shadow-theme-md absolute bottom-full start-0 mb-2 min-w-[74px] space-y-0.5 rounded-xl bg-white p-1.5 dark:bg-gray-900">
                          {variants.map((variant) => (
                            <li key={variant}>
                              <button
                                type="button"
                                onClick={() => {
                                  setVariantSelected(variant);
                                  setVariantOpen(false);
                                }}
                                className={`flex w-full items-center gap-2 rounded-lg px-1.5 py-2 text-sm transition-colors hover:bg-gray-100 hover:text-gray-900 dark:hover:bg-gray-800 dark:hover:text-white ${
                                  variantSelected === variant
                                    ? "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-white"
                                    : "text-gray-700 dark:text-gray-400"
                                }`}
                                role="menuitem"
                              >
                                {variant}
                              </button>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                    <div ref={resolutionDropdownRef} className="relative">
                      <Tooltip
                        content="Resolution"
                        placement="top"
                        variant="light"
                      >
                        <button
                          type="button"
                          onClick={() => setResolutionOpen(!resolutionOpen)}
                          aria-expanded={resolutionOpen}
                          className="flex cursor-pointer h-9 dark:hover:bg-gray-900  items-center justify-center gap-1.5 rounded-lg border border-gray-200 py-2 pe-3 ps-2.5 text-sm text-gray-500 hover:text-gray-700 dark:border-gray-700 dark:text-gray-400 dark:hover:text-gray-300"
                        >
                          <DiamondIcon className="size-5" />
                          <span>{resolutionSelected}</span>
                        </button>
                      </Tooltip>

                      {resolutionOpen && (
                        <ul className="shadow-theme-md absolute bottom-full start-0 mb-2 min-w-[86px] space-y-0.5 rounded-xl bg-white p-1.5 dark:bg-gray-900">
                          {resolutions.map((resolution) => (
                            <li key={resolution}>
                              <button
                                type="button"
                                onClick={() => {
                                  setResolutionSelected(resolution);
                                  setResolutionOpen(false);
                                }}
                                className={`flex w-full items-center gap-2 rounded-lg px-1.5 py-2 text-sm transition-colors hover:bg-gray-100 hover:text-gray-900 dark:hover:bg-gray-800 dark:hover:text-white ${
                                  resolutionSelected === resolution
                                    ? "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-white"
                                    : "text-gray-700 dark:text-gray-400"
                                }`}
                                role="menuitem"
                              >
                                {resolution}
                              </button>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                    {/* Duration Dropdown */}
                    <div className="relative" ref={durationDropdownRef}>
                      <Tooltip
                        content="Duration"
                        placement="top"
                        variant="light"
                      >
                        <button
                          type="button"
                          onClick={() => setDurationOpen(!durationOpen)}
                          aria-expanded={durationOpen}
                          className="flex cursor-pointer h-9 dark:hover:bg-gray-900  items-center justify-center gap-1.5 rounded-lg border border-gray-200 py-2 pe-3 ps-2.5 text-sm text-gray-500 hover:text-gray-700 dark:border-gray-700 dark:text-gray-400 dark:hover:text-gray-300"
                        >
                          <ClockIcon className="size-5" />
                          <span>{durationSelected}</span>
                        </button>
                      </Tooltip>
                      {durationOpen && (
                        <ul
                          role="menu"
                          className="shadow-theme-md absolute bottom-full start-0 mb-2 min-w-[86px] space-y-0.5 rounded-xl bg-white p-1.5 dark:bg-gray-900"
                        >
                          {["5s", "10s", "15s", "30s"].map((dur) => (
                            <li key={dur}>
                              <button
                                onClick={() => {
                                  setDurationSelected(dur);
                                  setDurationOpen(false);
                                }}
                                className={`flex w-full items-center gap-2 rounded-lg px-1.5 py-2 text-sm hover:bg-gray-100 hover:text-gray-900 dark:hover:bg-gray-800 dark:hover:text-white ${
                                  durationSelected === dur
                                    ? "bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-white"
                                    : "text-gray-700 dark:text-gray-400"
                                }`}
                                role="menuitem"
                              >
                                {dur}
                              </button>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                    {/* Audio Toggle */}
                    <Tooltip
                      content={audioOn ? "Mute Audio" : "Enable Audio"}
                      placement="top"
                      variant="light"
                    >
                      <button
                        type="button"
                        onClick={() => setAudioOn(!audioOn)}
                        className={`flex cursor-pointer h-9 items-center dark:hover:bg-gray-900  justify-center gap-1.5 rounded-lg border py-2 pe-3 ps-2.5 text-sm hover:text-gray-700 dark:hover:text-gray-300 ${
                          audioOn
                            ? "border-gray-200 text-gray-700 dark:border-gray-700 dark:text-gray-300"
                            : "border-gray-200 text-gray-400 dark:border-gray-700 dark:text-gray-600"
                        }`}
                      >
                        {audioOn ? (
                          <Sound className="size-5" />
                        ) : (
                          <Mute className="size-5" />
                        )}
                        <span>{audioOn ? "Audio" : "Muted"}</span>
                      </button>
                    </Tooltip>
                  </div>
                </div>

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
                      <ChevronDownIcon
                        className={`size-4.5 transition-transform duration-150${modelOpen ? " rotate-180" : ""}`}
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
