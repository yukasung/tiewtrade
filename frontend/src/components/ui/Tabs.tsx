/** Adapted from references/admin-template/src/components/ui/tabs/TabWithUnderline.tsx. */
export function Tabs({ label, items, active }: { label: string; items: string[]; active: string }) {
  return <nav className="account-tabs -mb-px flex space-x-2 overflow-x-auto" role="tablist" aria-label={label}>
    {items.map(item => {
      const selected = item === active;
      return <button key={item} type="button" role="tab" aria-selected={selected} disabled
        className={`account-tab inline-flex items-center border-b-2 px-2.5 py-2 text-sm font-medium transition-colors duration-200 ease-in-out ${
          selected ? "border-brand-500 text-brand-500 dark:border-brand-400 dark:text-brand-400" :
            "border-transparent bg-transparent text-gray-500 dark:text-gray-400"
        }`}>{item}</button>;
    })}
  </nav>;
}
