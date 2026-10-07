import { useState } from "react";
import { ChatIcon, DocsIcon, PlusAltIcon, TrashBinIcon } from "../../../icons";
import {
  DangerButton,
  SettingsCard,
  SettingsPanel,
  SettingsSection,
  ToggleRow,
} from "../shared";

const importOptions = [
  { id: "add-memory", label: "Add Memory", icon: DocsIcon },
  { id: "import-chats", label: "Import Chats", icon: ChatIcon },
  { id: "create-folder", label: "Create Folder", icon: PlusAltIcon },
];

export function MemoryPanel() {
  const [selectedImport, setSelectedImport] = useState("add-memory");

  return (
    <SettingsPanel title="Memory">
      <SettingsSection title="Memory">
        <SettingsCard>
          <ToggleRow
            title="Enable memory"
            description="Allow the assistant to recall past context"
            defaultChecked
          />
          <ToggleRow
            title="Save conversations"
            description="Keep chat history for future reference"
            isLast
          />
        </SettingsCard>
      </SettingsSection>

      <SettingsSection title="Stored Context">
        <SettingsCard className="px-5 py-4">
          <p className="mb-3 text-sm font-medium text-gray-800 dark:text-white/90">
            Import Chat Histories
          </p>
          <div className="mb-5 grid grid-cols-2 gap-3 rounded-2xl border border-gray-200 bg-gray-100 p-1.5 sm:grid-cols-3 dark:border-gray-800 dark:bg-white/3">
            {importOptions.map((option) => {
              const Icon = option.icon;
              const selected = selectedImport === option.id;

              return (
                <button
                  key={option.id}
                  type="button"
                  onClick={() => setSelectedImport(option.id)}
                  className={`flex flex-col items-start justify-start gap-2 rounded-xl border bg-white p-4 text-sm font-medium dark:bg-gray-900 ${
                    selected
                      ? "border-brand-500 text-brand-500"
                      : "border-transparent text-gray-500 hover:bg-gray-50 dark:text-gray-400 dark:hover:bg-white/5"
                  }`}
                >
                  <Icon className="size-5" />
                  {option.label}
                </button>
              );
            })}
          </div>
          <div className="flex items-center justify-between gap-4 border-t border-gray-100 pt-4 dark:border-gray-800">
            <div>
              <p className="text-sm font-medium text-gray-800 dark:text-white/90">
                Clear Memory
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Permanently delete all stored facts and preferences
              </p>
            </div>
            <DangerButton icon={<TrashBinIcon className="size-5" />}>
              Delete
            </DangerButton>
          </div>
        </SettingsCard>
      </SettingsSection>
    </SettingsPanel>
  );
}
