import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export type Theme = "light" | "dark";
type ThemeContextValue = { theme: Theme; toggleTheme: () => void };

const storageKey = "theme";
const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

/** Adapted from references/admin-template/src/context/ThemeContext.tsx. */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(() => {
    try { return window.localStorage.getItem(storageKey) === "dark" ? "dark" : "light"; }
    catch { return "light"; }
  });

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    document.documentElement.dataset.colorScheme = theme;
    // Preference persistence is optional; the shell and safety controls must render.
    try { window.localStorage.setItem(storageKey, theme); } catch { /* Keep this mount's theme. */ }
    window.dispatchEvent(new CustomEvent("tiewtrade-theme-change", { detail: theme }));
  }, [theme]);

  return <ThemeContext.Provider value={{ theme, toggleTheme: () => setTheme(value =>
    value === "light" ? "dark" : "light") }}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("useTheme must be used within ThemeProvider");
  return context;
}
