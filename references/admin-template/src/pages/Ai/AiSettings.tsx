import { useState } from "react";
import {
  AccountPanel,
  BillingPanel,
  ConnectorPanel,
  DataControlPanel,
  FileMediaPanel,
  GeneralPanel,
  MemoryPanel,
  ModelsPanel,
  PersonalizationPanel,
  SettingsSidebar,
  type TabId,
} from "../../components/ai-settings";
import PageMeta from "../../components/common/PageMeta";

const tabLabels: Record<TabId, string> = {
  account: "Account",
  general: "General",
  billing: "Credit and Billing",
  personalization: "Personalization",
  memory: "Memory",
  "file-media": "File & Media",
  model: "Models",
  connector: "Connector",
  "data-control": "Data Control",
};

export default function AiSettings() {
  const [activeTab, setActiveTab] = useState<TabId>("account");
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  const handleTabChange = (tab: TabId) => {
    setActiveTab(tab);
    setIsSidebarOpen(false);
  };

  return (
    <>
      <PageMeta
        title="React.js AI Settings | TailAdmin - React.js Admin Dashboard Template"
        description="This is React.js AI Settings page for TailAdmin - React.js Tailwind CSS Admin Dashboard Template"
      />

      <div className="relative overflow-hidden bg-white p-5 xl:flex xl:h-[calc(100vh-76px)] xl:p-0 dark:border-gray-800 dark:bg-gray-900">
        <div className="mt-4 flex items-center justify-between rounded-2xl border border-gray-200 bg-white p-3 ps-5 xl:hidden dark:border-gray-800 dark:bg-white/3">
          <span className="text-lg font-medium text-gray-800 dark:text-white/90">
            {tabLabels[activeTab]}
          </span>
          <button
            type="button"
            onClick={() => setIsSidebarOpen(true)}
            className="flex size-10 items-center justify-center rounded-lg border border-gray-300 text-gray-800 dark:border-gray-800 dark:text-white/90"
            aria-label="Open settings menu"
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

        {isSidebarOpen && (
          <div
            className="fixed inset-0 z-[99999] bg-black/60 xl:hidden"
            onClick={() => setIsSidebarOpen(false)}
          />
        )}

        <aside
          className={`fixed start-0 top-0 z-[99999] h-full w-72 overflow-y-auto bg-white p-3 shadow-xl transition-transform duration-300 ease-in-out xl:static xl:z-auto xl:block xl:w-62.5 xl:translate-x-0 xl:border-e xl:border-gray-200 xl:shadow-none xl:rtl:translate-x-0 dark:border-gray-800 dark:bg-gray-900 ${
            isSidebarOpen
              ? "translate-x-0"
              : "-translate-x-full rtl:translate-x-full"
          }`}
        >
          <SettingsSidebar
            activeTab={activeTab}
            onTabChange={handleTabChange}
          />
        </aside>

        {isSidebarOpen && (
          <div className="fixed start-75 top-4 z-[999999] xl:hidden">
            <button
              type="button"
              onClick={() => setIsSidebarOpen(false)}
              className="flex size-9 items-center justify-center rounded-full bg-white text-gray-500 shadow-lg hover:bg-gray-50 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700"
              aria-label="Close sidebar"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
              >
                <path
                  d="M18 6L6 18M6 6l12 12"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />
              </svg>
            </button>
          </div>
        )}

        <main className="no-scrollbar h-full flex-1 overflow-y-auto">
          {activeTab === "account" && <AccountPanel />}
          {activeTab === "general" && <GeneralPanel />}
          {activeTab === "billing" && <BillingPanel />}
          {activeTab === "personalization" && <PersonalizationPanel />}
          {activeTab === "memory" && <MemoryPanel />}
          {activeTab === "file-media" && <FileMediaPanel />}
          {activeTab === "model" && <ModelsPanel />}
          {activeTab === "connector" && <ConnectorPanel />}
          {activeTab === "data-control" && <DataControlPanel />}
        </main>
      </div>
    </>
  );
}
