import { useEffect, useRef, useState } from "react";
import { CheckLineIcon, PlusAltIcon } from "../../icons";
import { navGroups, workspaces } from "./data";
import type { TabId, Workspace } from "./types";

interface SettingsSidebarProps {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
}

export default function SettingsSidebar({
  activeTab,
  onTabChange,
}: SettingsSidebarProps) {
  const [workspaceOpen, setWorkspaceOpen] = useState(false);
  const [selectedWorkspace, setSelectedWorkspace] = useState(workspaces[0]);
  const workspaceRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!workspaceOpen) {
      return;
    }

    const handlePointerDown = (event: PointerEvent) => {
      if (!workspaceRef.current?.contains(event.target as Node)) {
        setWorkspaceOpen(false);
      }
    };

    document.addEventListener("pointerdown", handlePointerDown, true);

    return () => {
      document.removeEventListener("pointerdown", handlePointerDown, true);
    };
  }, [workspaceOpen]);

  return (
    <div className="space-y-4">
      <div ref={workspaceRef} className="relative">
        <button
          type="button"
          onClick={() => setWorkspaceOpen((open) => !open)}
          className="flex w-full items-center justify-between rounded-lg border border-gray-100 p-3 hover:bg-gray-50 dark:border-gray-800 dark:hover:bg-white/5"
        >
          <WorkspaceLabel workspace={selectedWorkspace} />
          <svg
            className="size-5 shrink-0 text-gray-500 dark:text-gray-400"
            viewBox="0 0 20 20"
            fill="none"
            aria-hidden="true"
          >
            <path
              d="M5.833 7.5 10 3.333 14.167 7.5M5.833 12.5 10 16.667 14.167 12.5"
              stroke="currentColor"
              strokeWidth="1.333"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>

        {workspaceOpen && (
          <div className="absolute top-full start-0 end-0 z-50 mt-1 rounded-xl border border-gray-200 bg-white p-1.5 shadow-lg dark:border-gray-700 dark:bg-gray-800">
            {workspaces.map((workspace) => (
              <button
                key={workspace.id}
                type="button"
                onClick={() => {
                  setSelectedWorkspace(workspace);
                  setWorkspaceOpen(false);
                }}
                className="flex w-full items-center justify-between rounded-lg px-1.5 py-2 hover:bg-gray-50 dark:hover:bg-white/5"
              >
                <WorkspaceLabel workspace={workspace} />
                {selectedWorkspace.id === workspace.id && (
                  <CheckLineIcon className="size-5 text-gray-700 dark:text-gray-400" />
                )}
              </button>
            ))}
            <div className="my-1 border-t border-gray-100 dark:border-gray-700" />
            <button
              type="button"
              className="flex w-full items-center gap-2.5 rounded-lg px-1.5 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-white/5"
            >
              <PlusAltIcon className="size-5" />
              Create Workspace
            </button>
          </div>
        )}
      </div>

      {navGroups.map((group) => (
        <div key={group.title}>
          <p className="mb-0.5 block px-3 py-1 text-xs text-gray-400 uppercase">
            {group.title}
          </p>
          <div className="space-y-0.5">
            {group.items.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;

              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => onTabChange(item.id)}
                  className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm transition ${
                    isActive
                      ? "bg-gray-100 font-medium text-gray-800 dark:bg-white/5 dark:text-white/90"
                      : "text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-white/5"
                  }`}
                >
                  <Icon className="size-5" />
                  {item.label}
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

function WorkspaceLabel({ workspace }: { workspace: Workspace }) {
  return (
    <div className="flex items-center gap-2.5">
      <div
        className={`${workspace.colorClass} inline-flex size-9 shrink-0 items-center justify-center rounded-full text-sm font-medium text-white`}
      >
        {workspace.initial}
      </div>
      <div className="text-start">
        <h4 className="text-sm font-medium text-gray-800 dark:text-white/90">
          {workspace.name}
        </h4>
        <p className="text-xs text-gray-500 dark:text-gray-400">
          {workspace.plan}
        </p>
      </div>
    </div>
  );
}
