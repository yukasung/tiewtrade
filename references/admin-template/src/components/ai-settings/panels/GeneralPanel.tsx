import { useTheme } from "@/context/ThemeContext";
import React, { useState } from "react";
import { MoonIcon, SunIcon, SystemIcon } from "../../../icons";
import {
  ActionRow,
  SelectControl,
  SettingsCard,
  SettingsPanel,
  SettingsSection,
  ToggleRow,
} from "../shared";

export function GeneralPanel() {
  const { selectedTheme, setTheme } = useTheme();
  const [language, setLanguage] = useState("English");
  const [timeZone, setTimeZone] = useState("UTC");

  const themeOptions: {
    value: "light" | "dark" | "auto";
    label: string;
    icon: React.ReactNode;
  }[] = [
    {
      value: "light",
      label: "Light",
      icon: <SunIcon className="size-5" />,
    },
    {
      value: "dark",
      label: "Dark",
      icon: <MoonIcon className="size-5" />,
    },
    {
      value: "auto",
      label: "Auto",
      icon: <SystemIcon className="size-5" />,
    },
  ];

  return (
    <SettingsPanel title="General">
      <SettingsSection title="Preference">
        <SettingsCard>
          <ActionRow
            title="Theme"
            description="Select your default theme"
            action={
              <div className="flex items-center gap-2">
                {themeOptions.map(({ value, label, icon }) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setTheme(value)}
                    className={`flex flex-col items-center gap-1.5 rounded-lg border px-8 py-2.5 text-xs font-medium text-gray-800 transition dark:text-gray-300 ${
                      selectedTheme === value
                        ? "border-gray-200 bg-gray-100 dark:border-gray-700 dark:bg-gray-800"
                        : "border-gray-100 hover:bg-gray-50 dark:border-gray-800 dark:hover:bg-white/5"
                    }`}
                  >
                    {icon}
                    {label}
                  </button>
                ))}
              </div>
            }
          />
          <ActionRow
            title="Language"
            action={
              <SelectControl
                size="sm"
                value={language}
                onChange={setLanguage}
                options={["English", "Spanish", "French", "German", "Japanese"]}
              />
            }
          />
          <ActionRow
            title="Time"
            action={
              <SelectControl
                value={timeZone}
                onChange={setTimeZone}
                options={[
                  "UTC",
                  "Pacific (PST)",
                  "Eastern (EST)",
                  "Central Europe (CET)",
                ]}
                size="sm"
              />
            }
            isLast
          />
        </SettingsCard>
      </SettingsSection>

      <SettingsSection title="Notification">
        <SettingsCard>
          <ToggleRow
            title="Activity & updates"
            description="Stay informed about activity and team mentions"
          />
          <ToggleRow
            title="Responses"
            description="Get notified when AI responds to requests"
            defaultChecked
          />
          <ToggleRow
            title="Product updates"
            description="Recent updates at a glance."
            isLast
          />
        </SettingsCard>
      </SettingsSection>
    </SettingsPanel>
  );
}
