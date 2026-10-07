"use client";

import type React from "react";
import { createContext, useState, useContext, useEffect } from "react";

type ThemeMode = "light" | "dark" | "auto";
type ActiveTheme = "light" | "dark";

type ThemeContextType = {
  theme: ActiveTheme;
  selectedTheme: ThemeMode;
  setTheme: (theme: ThemeMode) => void;
  toggleTheme: () => void;
};

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [selectedTheme, setSelectedThemeState] = useState<ThemeMode>("light");
  const [theme, setThemeState] = useState<ActiveTheme>("light");
  const [isInitialized, setIsInitialized] = useState(false);

  useEffect(() => {
    // This code will only run on the client side
    const savedTheme = localStorage.getItem("theme") as ThemeMode | null;
    const initialTheme = savedTheme || "light";

    setSelectedThemeState(initialTheme);
    setIsInitialized(true);
  }, []);

  useEffect(() => {
    if (!isInitialized) return;

    localStorage.setItem("theme", selectedTheme);

    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");

    const handleChange = () => {
      if (selectedTheme === "auto") {
        setThemeState(mediaQuery.matches ? "dark" : "light");
      } else {
        setThemeState(selectedTheme);
      }
    };

    handleChange();

    if (selectedTheme === "auto") {
      mediaQuery.addEventListener("change", handleChange);
      return () => mediaQuery.removeEventListener("change", handleChange);
    }
  }, [selectedTheme, isInitialized]);

  useEffect(() => {
    if (!isInitialized) return;
    if (theme === "dark") {
      document.documentElement.classList.add("dark");
      document.documentElement.setAttribute("data-color-scheme", "dark");
    } else {
      document.documentElement.classList.remove("dark");
      document.documentElement.setAttribute("data-color-scheme", "light");
    }
  }, [theme, isInitialized]);

  const setTheme = (newTheme: ThemeMode) => {
    setSelectedThemeState(newTheme);
  };

  const toggleTheme = () => {
    setSelectedThemeState((prev) => {
      const resolved = prev === "auto"
        ? (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")
        : prev;
      return resolved === "light" ? "dark" : "light";
    });
  };

  return (
    <ThemeContext.Provider value={{ theme, selectedTheme, setTheme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
};

export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (context === undefined) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return context;
};
