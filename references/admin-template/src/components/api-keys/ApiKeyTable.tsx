import AddApiKeyModal from "@/components/api-keys/AddApiKeyModal";
import Switch from "@/components/form/switch/Switch";
import {
  CheckLineIcon,
  CopyIcon,
  PencilIcon,
  RegenerateIcon,
  TrashBinIcon,
} from "@/icons";
import { cn } from "@/utils";
import { useState } from "react";

interface ApiKey {
  id: string;
  name: string;
  value: string;
  status: "Active" | "Disabled";
  created: string;
  lastUsed: string;
  hasToggle: boolean;
}

const apiKeysData: ApiKey[] = [
  {
    id: "1",
    name: "Production API key",
    value: "sk_live_**********4248",
    status: "Disabled",
    created: "25 Jan, 2025",
    lastUsed: "Today, 10:45 AM",
    hasToggle: true,
  },
  {
    id: "2",
    name: "Development API key",
    value: "dev_live_**********4923",
    status: "Active",
    created: "29 Dec, 2024",
    lastUsed: "Today, 12:40 AM",
    hasToggle: false,
  },
  {
    id: "3",
    name: "Legacy API Key",
    value: "leg_live_**********0932",
    status: "Active",
    created: "12 Mar, 2024",
    lastUsed: "Today, 11:45 PM",
    hasToggle: false,
  },
];

interface ApiKeyTableProps {
  className?: string;
}

export default function ApiKeyTable({ className }: ApiKeyTableProps) {
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const handleCopy = async (apiKey: ApiKey) => {
    try {
      await navigator.clipboard.writeText(apiKey.value);
      setCopiedId(apiKey.id);
      setTimeout(() => setCopiedId(null), 1500);
    } catch {
      // Optionally handle error
    }
  };

  return (
    <div
      className={cn(
        "rounded-2xl border border-gray-200 bg-white px-5 sm:px-6 dark:border-gray-800 dark:bg-white/3",
        className,
      )}
    >
      <div className="flex flex-col justify-between gap-5 border-b border-gray-100 py-4 sm:flex-row sm:items-center dark:border-gray-800">
        <div>
          <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">
            API Keys
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            API keys are used to authentication requests to the tailadmin API
          </p>
        </div>
        <div>
          <AddApiKeyModal />
        </div>
      </div>
      <div className="custom-scrollbar overflow-x-auto px-1 pb-4">
        <table className="min-w-full">
          <thead>
            <tr className="border-b border-gray-100 dark:border-gray-800">
              <th className="py-3 pe-5 text-start text-xs font-medium text-gray-500 dark:text-gray-400">
                Name
              </th>
              <th className="px-5 py-3 text-start text-xs font-medium text-gray-500 dark:text-gray-400">
                Status
              </th>
              <th className="px-5 py-3 text-start text-xs font-medium text-gray-500 dark:text-gray-400">
                Created
              </th>
              <th className="px-5 py-3 text-start text-xs font-medium text-gray-500 dark:text-gray-400">
                Last used
              </th>
              <th className="px-5 py-3 text-start text-xs font-medium text-gray-500 dark:text-gray-400">
                Disable/Enable
              </th>
              <th className="px-5 py-3 text-start text-xs font-medium text-gray-500 dark:text-gray-400">
                Action
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
            {apiKeysData.map((apiKey) => (
              <tr key={apiKey.id}>
                <td className="py-3 pe-5 whitespace-nowrap">
                  <div>
                    <label
                      htmlFor={`api-${apiKey.id}`}
                      className="mb-2 inline-block text-sm text-gray-700 dark:text-gray-400"
                    >
                      {apiKey.name}
                    </label>
                    <div className="flex items-center gap-3">
                      <div className="relative">
                        <input
                          value={apiKey.value}
                          type="text"
                          id={`api-${apiKey.id}`}
                          className="h-11 w-full min-w-[360px] rounded-lg border border-gray-300 bg-transparent py-3 ps-4 pe-[90px] text-sm text-gray-800 shadow-theme-xs placeholder:text-gray-400 focus:border-brand-300 focus:ring-3 focus:ring-brand-500/10 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30 dark:focus:border-brand-800"
                          readOnly
                        />
                        <button
                          type="button"
                          id={`copy-button-${apiKey.id}`}
                          className="absolute end-0 top-1/2 inline-flex h-11 -translate-y-1/2 cursor-pointer items-center gap-1 rounded-e-lg border border-gray-300 py-3 ps-3.5 pe-3 text-sm font-medium text-gray-700 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400"
                          onClick={() => handleCopy(apiKey)}
                          disabled={copiedId === apiKey.id}
                        >
                          {copiedId === apiKey.id ? (
                            <>
                              <CheckLineIcon className="size-5 text-success-500" />
                              <span id="copy-text">Copied</span>
                            </>
                          ) : (
                            <>
                              <CopyIcon className="size-5" />
                              <span id="copy-text">Copy</span>
                            </>
                          )}
                        </button>
                      </div>

                      <div className="group relative inline-block">
                        <button
                          type="button"
                          className="inline-flex h-11 w-11 items-center justify-center rounded-lg border border-gray-300 text-gray-700 dark:border-gray-700 dark:text-gray-400"
                        >
                          <RegenerateIcon className="size-5" />
                        </button>
                        <div className="invisible absolute start-1/2 bottom-full z-9999 mb-2.5 -translate-x-1/2 opacity-0 transition-opacity duration-300 group-hover:visible group-hover:opacity-100 rtl:translate-x-1/2">
                          <div className="relative">
                            <div className="rounded-lg bg-white px-3 py-2 text-xs font-medium whitespace-nowrap text-gray-700 shadow-xs dark:bg-[#1E2634] dark:text-white">
                              Regenerate
                            </div>
                            <div className="absolute start-1/2 -bottom-1 h-3 w-4 -translate-x-1/2 rotate-45 bg-white rtl:translate-x-1/2 dark:bg-[#1E2634]"></div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </td>
                <td className="px-5 py-3 whitespace-nowrap">
                  <span
                    className={cn(
                      "inline-flex items-center justify-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium",
                      apiKey.status === "Active"
                        ? "bg-green-50 text-green-600 dark:bg-green-500/15 dark:text-green-500"
                        : "bg-error-50 text-error-600 dark:bg-error-500/15 dark:text-error-500",
                    )}
                  >
                    {apiKey.status}
                  </span>
                </td>
                <td className="px-5 py-3 text-sm whitespace-nowrap text-gray-500 dark:text-gray-400">
                  {apiKey.created}
                </td>
                <td className="px-5 py-3 text-sm whitespace-nowrap text-gray-500 dark:text-gray-400">
                  {apiKey.lastUsed}
                </td>
                <td className="px-5 py-3 whitespace-nowrap">
                  <Switch defaultChecked={apiKey.status === "Active"} />
                </td>
                <td className="px-5 py-3 whitespace-nowrap">
                  <div className="flex w-full items-center gap-3">
                    <button
                      type="button"
                      className="text-gray-500 hover:text-error-500 dark:text-gray-400 dark:hover:text-error-500"
                    >
                      <TrashBinIcon className="size-5" />
                    </button>
                    <button
                      type="button"
                      className="text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-white/90"
                    >
                      <PencilIcon className="size-5" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
