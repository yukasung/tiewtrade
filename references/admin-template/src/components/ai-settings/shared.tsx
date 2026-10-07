import { useEffect, useRef, useState, type ReactNode } from "react";
import { useLanguage } from "../../context/LanguageContext";
import { cn } from "../../utils";

export const inputClass =
  "dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30";

export const textareaClass =
  "dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 w-full resize-none rounded-lg border border-gray-300 bg-transparent px-4 py-3 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30";

export function SettingsPanel({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="mx-auto py-6 xl:max-w-[650px] xl:py-8.5">
      <h2 className="mb-6 border-b border-gray-200 pb-4 text-2xl font-semibold text-gray-900 dark:border-gray-800 dark:text-white/90">
        {title}
      </h2>
      <div className="space-y-6">{children}</div>
    </div>
  );
}

export function SettingsSection({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="space-y-4">
      <h3 className="mb-2 text-xs font-medium text-gray-500 uppercase dark:text-gray-400">
        {title}
      </h3>
      {children}
    </section>
  );
}

export function SettingsCard({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-2xl border border-gray-100 bg-white dark:border-gray-800 dark:bg-white/3 ${className}`}
    >
      {children}
    </div>
  );
}

export function FormRow({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col justify-between gap-2 border-b border-gray-100 px-5 py-4 sm:flex-row sm:items-center dark:border-gray-800">
      <label className="flex-1 text-sm font-medium text-gray-700 dark:text-white/90">
        {label}
      </label>
      <div className="flex-1">{children}</div>
    </div>
  );
}

export function Field({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium text-gray-800 dark:text-white/90">
        {label}
      </span>
      {children}
    </label>
  );
}

export function ActionRow({
  title,
  description,
  action,
  badge,
  leading,
  isLast = false,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  badge?: ReactNode;
  leading?: ReactNode;
  isLast?: boolean;
}) {
  return (
    <div
      className={`flex flex-col justify-between gap-4 px-5 py-4 sm:flex-row sm:items-center ${
        isLast ? "" : "border-b border-gray-100 dark:border-gray-800"
      }`}
    >
      <div className="flex items-center gap-3">
        {leading}
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <p className="mb-1 text-sm font-medium text-gray-800 dark:text-white/90">
              {title}
            </p>
            {badge}
          </div>
          {description && (
            <p className="text-xs text-gray-500 dark:text-gray-400">
              {description}
            </p>
          )}
        </div>
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

export function ToggleRow({
  title,
  description,
  defaultChecked = false,
  isLast = false,
}: {
  title: string;
  description?: string;
  defaultChecked?: boolean;
  isLast?: boolean;
}) {
  const [checked, setChecked] = useState(defaultChecked);

  return (
    <ActionRow
      title={title}
      description={description}
      action={
        <CompactSwitch
          checked={checked}
          onChange={() => setChecked((value) => !value)}
        />
      }
      isLast={isLast}
    />
  );
}

export function CompactSwitch({
  checked,
  onChange,
}: {
  checked: boolean;
  onChange: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onChange}
      className="flex cursor-pointer items-center select-none"
      aria-pressed={checked}
    >
      <span className="relative">
        <span
          className={`block h-5 w-9 rounded-full transition ${
            checked ? "bg-brand-500" : "bg-gray-200 dark:bg-white/10"
          }`}
        />
        <span
          className={`absolute start-0.5 top-0.5 h-4 w-4 rounded-full bg-white shadow-theme-sm transition duration-200 ease-linear ${
            checked ? "translate-x-full rtl:-translate-x-full" : "translate-x-0"
          }`}
        />
      </span>
    </button>
  );
}

export function SegmentedControl({
  options,
  value,
  onChange,
}: {
  options: string[];
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="inline-flex items-center rounded-lg bg-gray-100 p-1 dark:bg-gray-800">
      {options.map((option) => (
        <button
          key={option}
          type="button"
          onClick={() => onChange(option)}
          className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
            value === option
              ? "bg-white text-gray-800 shadow-xs dark:bg-gray-700 dark:text-white/90"
              : "text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300"
          }`}
        >
          {option}
        </button>
      ))}
    </div>
  );
}

export function SelectControl({
  value,
  onChange,
  options,
  size = "md",
  className,
}: {
  value: string;
  onChange: (value: string) => void;
  options: string[];
  size?: "sm" | "md";
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const selectRef = useRef<HTMLDivElement>(null);
  const selectedLabel = getSelectOptionLabel(value);

  useEffect(() => {
    if (!open) {
      return;
    }

    const handlePointerDown = (event: PointerEvent) => {
      if (!selectRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };

    document.addEventListener("pointerdown", handlePointerDown, true);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("pointerdown", handlePointerDown, true);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  return (
    <div
      ref={selectRef}
      className={cn(
        "relative w-fit shrink-0",
        size === "sm" ? "min-w-25" : "min-w-44",
        className,
      )}
    >
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className={cn(
          "flex w-full items-center justify-between gap-2 rounded-lg border border-gray-300 bg-white ps-3.5 pe-3 text-sm text-gray-700 shadow-xs hover:bg-gray-50 focus:border-brand-300 focus:ring-3 focus:ring-brand-500/10 focus:outline-hidden dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700",
          size === "sm" ? "h-9 py-2" : "h-10 py-2",
        )}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span className="truncate">{selectedLabel}</span>
        <svg
          className={`size-5 shrink-0 text-gray-500 transition-transform dark:text-gray-400 ${
            open ? "rotate-180" : ""
          }`}
          viewBox="0 0 20 20"
          fill="none"
          aria-hidden="true"
        >
          <path
            d="M4.792 8.021 10 13.23l5.208-5.208"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>

      {open && (
        <div
          className="absolute start-0 top-full z-50 mt-1 w-full space-y-px rounded-xl bg-white p-1.5 shadow-lg sm:start-auto sm:end-0 dark:bg-gray-800"
          role="listbox"
        >
          {options.map((option) => {
            const selected = value === option;

            return (
              <button
                key={option}
                type="button"
                onClick={() => {
                  onChange(option);
                  setOpen(false);
                }}
                className={`flex w-full items-center truncate rounded-lg px-2 py-2 text-start text-sm font-medium text-gray-700 dark:text-gray-300 ${
                  selected
                    ? "bg-gray-100 dark:bg-white/10"
                    : "hover:bg-gray-50 dark:hover:bg-white/5"
                }`}
                role="option"
                aria-selected={selected}
              >
                {getSelectOptionLabel(option)}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

function getSelectOptionLabel(option: string) {
  return option === "Provider" ? "All" : option;
}

export function RangeControl({
  value,
  onChange,
  min = 0,
  max = 100,
  unit = "%",
}: {
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  unit?: string;
}) {
  const { dir } = useLanguage();
  const isRtl = dir === "rtl";
  const percentage = Math.min(
    100,
    Math.max(0, ((value - min) / (max - min || 1)) * 100),
  );

  return (
    <div className="flex items-center gap-3 sm:min-w-[220px]">
      <input
        type="range"
        min={min}
        max={max}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="ai-settings-range w-full"
        style={{
          background: isRtl
            ? `linear-gradient(to left, #465fff 0%, #465fff ${percentage}%, var(--range-bg, #e5e7eb) ${percentage}%, var(--range-bg, #e5e7eb) 100%)`
            : `linear-gradient(to right, #465fff 0%, #465fff ${percentage}%, var(--range-bg, #e5e7eb) ${percentage}%, var(--range-bg, #e5e7eb) 100%)`,
        }}
      />
      <span className="w-10 shrink-0 text-end text-sm text-gray-700 dark:text-gray-400">
        {value}
        {unit}
      </span>
    </div>
  );
}

export function PrimaryButton({ children }: { children: ReactNode }) {
  return (
    <button
      type="button"
      className="inline-flex h-9 items-center justify-center gap-2 rounded-lg bg-brand-500 px-4 py-2 text-sm font-medium text-white shadow-theme-xs transition hover:bg-brand-600"
    >
      {children}
    </button>
  );
}

export function SecondaryButton({
  children,
  icon,
}: {
  children: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <button
      type="button"
      className="inline-flex h-9 w-full cursor-pointer items-center justify-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3.5 py-2 text-sm font-medium text-gray-700 shadow-xs hover:bg-gray-100 sm:w-auto dark:border-gray-700 dark:bg-transparent dark:text-gray-300 dark:hover:bg-white/5"
    >
      {icon}
      {children}
    </button>
  );
}

export function DangerButton({
  children,
  icon,
}: {
  children: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <button
      type="button"
      className="inline-flex h-9 w-full cursor-pointer items-center justify-center gap-1.5 rounded-lg border border-red-400 px-3.5 py-2 text-sm font-medium text-red-500 transition-all hover:bg-red-50 sm:w-auto dark:border-red-500/30 dark:hover:bg-red-500/10"
    >
      {icon}
      {children}
    </button>
  );
}

export function MetaLine({ items }: { items: string[] }) {
  return (
    <p className="text-xs text-gray-500 dark:text-gray-400">
      {items.map((item, index) => (
        <span key={item}>
          {index > 0 && (
            <span className="mx-1.5 inline-block size-1 rounded-full bg-gray-400 align-middle" />
          )}
          {item}
        </span>
      ))}
    </p>
  );
}

export function ModelAvatar({
  label,
  provider,
  image,
  darkImage,
}: {
  label: string;
  provider: string;
  image?: string;
  darkImage?: string;
}) {
  const colorClass =
    provider === "OpenAI"
      ? "bg-gray-900 text-white dark:bg-white dark:text-gray-900"
      : provider === "Google"
        ? "bg-blue-100 text-blue-600 dark:bg-blue-500/15 dark:text-blue-300"
        : provider === "Anthropic"
          ? "bg-orange-100 text-orange-600 dark:bg-orange-500/15 dark:text-orange-300"
          : "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300";

  return (
    <span
      className={`inline-flex size-6 items-center justify-center rounded-full text-[10px] font-semibold ${image ? "" : colorClass}`}
    >
      {image ? (
        <>
          <img
            src={image}
            alt={label}
            className={`size-5 ${darkImage ? "dark:hidden" : ""}`}
          />
          {darkImage && (
            <img
              src={darkImage}
              alt={label}
              className="hidden size-5 dark:block"
            />
          )}
        </>
      ) : (
        label
      )}
    </span>
  );
}

export function AppAvatar({
  label,
  image,
  darkImage,
}: {
  label: string;
  image?: string;
  darkImage?: string;
}) {
  return (
    <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-gray-100 text-xs font-semibold text-gray-700 dark:bg-gray-800 dark:text-gray-300">
      {image ? (
        <>
          <img
            src={image}
            alt={label}
            className={`size-5 ${darkImage ? "dark:hidden" : ""}`}
          />
          {darkImage && (
            <img
              src={darkImage}
              alt={label}
              className="hidden size-5 dark:block"
            />
          )}
        </>
      ) : (
        label
      )}
    </div>
  );
}
