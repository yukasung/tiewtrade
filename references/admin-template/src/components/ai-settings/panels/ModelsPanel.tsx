import { useMemo, useState } from "react";
import { initialModels } from "../data";
import {
  CompactSwitch,
  ModelAvatar,
  SelectControl,
  SettingsCard,
  SettingsPanel,
  SettingsSection,
} from "../shared";
import type { ModelItem } from "../types";

export function ModelsPanel() {
  const [models, setModels] = useState<ModelItem[]>(initialModels);
  const [search, setSearch] = useState("");
  const [provider, setProvider] = useState("Provider");
  const [generation, setGeneration] = useState("All Generation");

  const filteredModels = useMemo(() => {
    const query = search.trim().toLowerCase();

    return models.filter((model) => {
      const matchesSearch =
        !query ||
        model.name.toLowerCase().includes(query) ||
        model.provider.toLowerCase().includes(query);
      const matchesProvider =
        provider === "Provider" || model.provider === provider;
      const matchesGeneration =
        generation === "All Generation" || model.generation === generation;

      return matchesSearch && matchesProvider && matchesGeneration;
    });
  }, [generation, models, provider, search]);

  const toggleModel = (modelName: string, index: number) => {
    setModels((current) =>
      current.map((model, modelIndex) =>
        model.name === modelName && modelIndex === index
          ? { ...model, enabled: !model.enabled }
          : model,
      ),
    );
  };

  return (
    <SettingsPanel title="Models">
      <SettingsSection title="All Models">
        <SettingsCard>
          <div className="flex flex-col flex-wrap gap-3 border-b border-gray-100 px-4 py-3 sm:flex-row sm:items-center dark:border-gray-800">
            <div className="flex-1">
              <div className="relative">
                <span className="pointer-events-none absolute top-1/2 start-3 -translate-y-1/2 text-gray-500 dark:text-gray-400">
                  <svg
                    className="size-5"
                    viewBox="0 0 20 20"
                    fill="none"
                    aria-hidden="true"
                  >
                    <path
                      d="M14.382 14.384 17.707 17.709M16.458 9.375c0 3.911-3.171 7.081-7.083 7.081s-7.083-3.17-7.083-7.081 3.171-7.082 7.083-7.082 7.083 3.171 7.083 7.082Z"
                      stroke="currentColor"
                      strokeWidth="1.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </span>
                <input
                  type="text"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search Model ..."
                  className="dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-9 w-full rounded-lg border border-gray-200 bg-transparent py-2.5 pe-3 ps-12 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-800 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30"
                />
              </div>
            </div>
            <div className="flex  gap-3">
              <SelectControl
                value={provider}
                onChange={setProvider}
                options={["Provider", "OpenAI", "Google", "Anthropic", "xAI"]}
                size="sm"
              />
              <SelectControl
                value={generation}
                onChange={setGeneration}
                options={["All Generation", "Text", "Image", "Video", "Code"]}
                size="sm"
              />
            </div>
          </div>

          {filteredModels.map((model, index) => (
            <div
              key={`${model.name}-${model.provider}-${index}`}
              className={`flex items-center justify-between px-5 py-3.5 ${
                index < filteredModels.length - 1
                  ? "border-b border-gray-100 dark:border-gray-800"
                  : ""
              }`}
            >
              <div className="flex items-center gap-3">
                <ModelAvatar
                  label={model.icon}
                  provider={model.provider}
                  image={model.image}
                  darkImage={model.darkImage}
                />
                <span className="text-sm font-medium text-gray-800 dark:text-white/90">
                  {model.name}
                </span>
                {model.badge && (
                  <span className="inline-flex items-center justify-center rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-600 dark:bg-green-500/15 dark:text-green-400">
                    {model.badge}
                  </span>
                )}
              </div>
              <CompactSwitch
                checked={model.enabled}
                onChange={() => toggleModel(model.name, models.indexOf(model))}
              />
            </div>
          ))}

          {filteredModels.length === 0 && (
            <div className="px-5 py-8 text-center text-sm text-gray-500 dark:text-gray-400">
              No models match your filters.
            </div>
          )}
        </SettingsCard>
      </SettingsSection>
    </SettingsPanel>
  );
}
