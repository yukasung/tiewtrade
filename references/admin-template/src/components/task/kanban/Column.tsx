import { HorizontaLDots } from "@/icons";
import { cn } from "@/utils";
import { useRef, useState } from "react";
import { useDrop } from "react-dnd";
import { Dropdown } from "../../ui/dropdown/Dropdown";
import { DropdownItem } from "../../ui/dropdown/DropdownItem";
import TaskItem from "./TaskItem";
import type { Task } from "./types/types";

interface ColumnProps {
  title: string;
  tasks: Task[];
  status: string;
  moveTask: (dragIndex: number, hoverIndex: number) => void;
  changeTaskStatus: (taskId: string, newStatus: string) => void;
  isDragging?: boolean;
  onDragStart?: () => void;
  onDragEnd?: () => void;
}

const Column: React.FC<ColumnProps> = ({
  title,
  tasks,
  status,
  moveTask,
  changeTaskStatus,
  isDragging = false,
  onDragStart,
  onDragEnd,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const [{ isOver, canDrop }, drop] = useDrop({
    accept: "task",
    drop: () => ({ name: status }),
    collect: (monitor) => ({
      isOver: monitor.isOver(),
      canDrop: monitor.canDrop(),
    }),
  });

  drop(ref);

  function toggleDropdown() {
    setIsOpen(!isOpen);
  }

  function closeDropdown() {
    setIsOpen(false);
  }
  return (
    <div
      ref={ref}
      className={cn(
        "swim-lane relative flex flex-col gap-5 p-4 transition-all duration-200 xl:p-6",
        isOver && canDrop
          ? "bg-blue-50/80 dark:bg-blue-500/5"
          : canDrop && isDragging
            ? "bg-gray-50/50 dark:bg-gray-500/5"
            : isDragging
              ? "opacity-80"
              : "",
      )}
    >
      {/* Drop zone indicator */}
      {isOver && canDrop && (
        <div className="pointer-events-none absolute inset-2 z-10 rounded-xl bg-blue-50/20 dark:bg-blue-500/10" />
      )}

      {/* Column header stays the same */}
      <div className="mb-1 flex items-center justify-between">
        <h3 className="flex items-center gap-3 text-base font-medium text-gray-800 dark:text-white/90">
          {title}
          <span
            className={cn(
              "inline-flex rounded-full px-2 py-0.5 text-theme-xs font-medium",
              status === "todo"
                ? "bg-gray-100 text-gray-700 dark:bg-white/3 dark:text-white/80"
                : status === "inProgress"
                  ? "bg-warning-50 text-warning-700 dark:bg-warning-500/15 dark:text-orange-400"
                  : status === "completed"
                    ? "bg-success-50 text-success-700 dark:bg-success-500/15 dark:text-success-500"
                    : "",
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
      {tasks.map((task, index) => (
        <TaskItem
          key={task.id}
          task={task}
          index={index}
          moveTask={moveTask}
          changeTaskStatus={changeTaskStatus}
          onDragStart={onDragStart}
          onDragEnd={onDragEnd}
        />
      ))}
    </div>
  );
};

export default Column;
