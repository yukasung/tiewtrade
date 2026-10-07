import { useState } from "react";
import { MoreDotIcon } from "../../icons";
import { Dropdown } from "../ui/dropdown/Dropdown";
import { DropdownItem } from "../ui/dropdown/DropdownItem";

export default function ChatHeaderTitle() {
  const [isOpen, setIsOpen] = useState(false);

  function toggleDropdown() {
    setIsOpen(!isOpen);
  }

  function closeDropdown() {
    setIsOpen(false);
  }
  return (
    <div className="flex items-start justify-between">
      <div>
        <h3 className="text-theme-xl font-semibold text-gray-800 sm:text-2xl dark:text-white/90">
          Chats
        </h3>
      </div>
      <div className="relative inline-block">
        <button onClick={toggleDropdown}>
          <MoreDotIcon className="size-6 text-gray-400 hover:text-gray-700 dark:hover:text-gray-300" />
        </button>
        <Dropdown isOpen={isOpen} onClose={closeDropdown} className="w-40 p-2">
          <DropdownItem
            onItemClick={closeDropdown}
            className="flex w-full rounded-lg text-start font-normal text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-white/5 dark:hover:text-gray-300"
          >
            View More
          </DropdownItem>
          <DropdownItem
            onItemClick={closeDropdown}
            className="flex w-full rounded-lg text-start font-normal text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-white/5 dark:hover:text-gray-300"
          >
            Delete
          </DropdownItem>
        </Dropdown>
      </div>
    </div>
  );
}
