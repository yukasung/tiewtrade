"use client";

import React, { useState } from "react";
import { HorizontaLDots } from "../../../icons";
import { cn } from "../../../utils";
import { Dropdown } from "../../ui/dropdown/Dropdown";
import { DropdownItem } from "../../ui/dropdown/DropdownItem";
import TaskItem from "./TaskItem";
import type { Task } from "./types/Task";

interface TaskLaneProps {
  lane: string;
  tasks: Task[];
  onDragOver: (e: React.DragEvent<HTMLDivElement>) => void;
  onDrop: (e: React.DragEvent<HTMLDivElement>) => void;
  onDragStart: (e: React.DragEvent<HTMLDivElement>, taskId: string) => void;
}

const TaskLane: React.FC<TaskLaneProps> = ({
  lane,
  tasks,
  onDragOver,
  onDrop,
  onDragStart,
}) => {
  const [isOpen, setIsOpen] = useState(false);

  function toggleDropdown() {
    setIsOpen(!isOpen);
  }

  function closeDropdown() {
    setIsOpen(false);
  }
  return (
    <div onDragOver={onDragOver} onDrop={onDrop}>
      <div className="mb-2 flex items-center justify-between">
        <h3 className="flex items-center gap-3 text-base font-medium text-gray-800 capitalize dark:text-white/90">
          {lane}
          <span
            className={cn(
              "inline-flex rounded-full px-2 py-0.5 text-theme-xs font-medium",
              lane === "todo" &&
                "bg-gray-100 text-gray-700 dark:bg-white/3 dark:text-white/80",
              lane === "in-progress" &&
                "bg-warning-50 text-warning-700 dark:bg-warning-500/15 dark:text-orange-400",
              lane === "completed" &&
                "bg-success-50 text-success-700 dark:bg-success-500/15 dark:text-success-500",
            )}
          >
            {tasks.length}
          </span>
        </h3>

        <div className="relative">
          <button onClick={toggleDropdown} className="dropdown-toggle">
            <HorizontaLDots className="size-6 text-gray-400 hover:text-gray-700 dark:hover:text-gray-300" />
          </button>
          <Dropdown
            isOpen={isOpen}
            onClose={closeDropdown}
            className="absolute end-0 top-full z-40 w-[140px] space-y-1 rounded-2xl border border-gray-200 bg-white p-2 shadow-theme-md dark:border-gray-800 dark:bg-gray-dark"
          >
            <DropdownItem
              onItemClick={closeDropdown}
              className="flex w-full rounded-lg text-start font-normal text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-white/5 dark:hover:text-gray-300"
            >
              Edit
            </DropdownItem>
            <DropdownItem
              onItemClick={closeDropdown}
              className="flex w-full rounded-lg text-start font-normal text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-white/5 dark:hover:text-gray-300"
            >
              Delete
            </DropdownItem>
            <DropdownItem
              onItemClick={closeDropdown}
              className="flex w-full rounded-lg text-start font-normal text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-white/5 dark:hover:text-gray-300"
            >
              Clear All
            </DropdownItem>
          </Dropdown>
        </div>
      </div>
      {tasks.map((task) => (
        <TaskItem
          key={task.id}
          {...task}
          onDragStart={(e) => onDragStart(e, task.id)}
        />
      ))}
    </div>
  );
};

export default TaskLane;
