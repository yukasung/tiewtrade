import { accountText as t } from "../../accountMessages";
import { useTheme } from "../../context/ThemeContext";

/** Adapted from references/admin-template/src/components/common/ThemeToggleButton.tsx. */
export function ThemeToggleButton() {
  const { theme, toggleTheme } = useTheme();
  const next = theme === "light" ? t("darkTheme") : t("lightTheme");
  return <button type="button" onClick={toggleTheme} aria-label={next} title={next}
    className="account-theme-toggle relative flex h-11 w-11 items-center justify-center rounded-full border border-gray-200 bg-white text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700 dark:border-gray-800 dark:bg-gray-900 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-white">
    {theme === "light" ? <svg aria-hidden="true" width="20" height="20" viewBox="0 0 20 20" fill="none">
      <path d="M17.45 11.97A6.96 6.96 0 0 1 8.03 2.55 8.46 8.46 0 1 0 17.45 11.97Z"
        stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
    </svg> : <svg aria-hidden="true" width="20" height="20" viewBox="0 0 20 20" fill="none">
      <circle cx="10" cy="10" r="3.2" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M10 1.75v1.5M10 16.75v1.5M1.75 10h1.5M16.75 10h1.5M4.17 4.17l1.06 1.06M14.77 14.77l1.06 1.06M15.83 4.17l-1.06 1.06M5.23 14.77l-1.06 1.06"
        stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>}
  </button>;
}
