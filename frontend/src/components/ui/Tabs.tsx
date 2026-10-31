import { useId, useRef, type KeyboardEvent } from "react";

export type TabItem<T extends string = string> = { id: T; label: string };

/** Adapted from references/admin-template/src/components/ui/tabs/TabWithUnderline.tsx. */
export function Tabs<T extends string>({ label, items, active, onChange, disabled = false, id, controls }: {
  label: string;
  items: readonly TabItem<T>[];
  active: T;
  onChange?: (id: T) => void;
  disabled?: boolean;
  id?: string;
  controls?: string;
}) {
  const generatedId = useId();
  const tablistId = id ?? generatedId;
  const tabs = useRef<Array<HTMLButtonElement | null>>([]);
  const move = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    if (disabled || !onChange || !["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const next = event.key === "Home" ? 0 : event.key === "End" ? items.length - 1 :
      (index + (event.key === "ArrowRight" ? 1 : -1) + items.length) % items.length;
    const item = items[next];
    if (item === undefined) return;
    onChange(item.id);
    tabs.current[next]?.focus();
  };
  return <nav className="account-tabs -mb-px flex space-x-2 overflow-x-auto" role="tablist" aria-label={label}>
    {items.map((item, index) => {
      const selected = item.id === active;
      return <button key={item.id} id={`${tablistId}-${String(index)}`} ref={element => { tabs.current[index] = element; }}
        type="button" role="tab" aria-selected={selected} aria-controls={controls}
        tabIndex={selected ? 0 : -1} disabled={disabled || !onChange}
        onKeyDown={event => move(event, index)} onClick={() => onChange?.(item.id)}
        className={`account-tab inline-flex items-center border-b-2 px-2.5 py-2 text-sm font-medium transition-colors duration-200 ease-in-out ${
          selected ? "border-brand-500 text-brand-500 dark:border-brand-400 dark:text-brand-400" :
            "border-transparent bg-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
        }`}>{item.label}</button>;
    })}
  </nav>;
}
