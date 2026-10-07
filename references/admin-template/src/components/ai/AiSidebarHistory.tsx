import { useState, useEffect } from "react";
import { useModal } from "../../hooks/useModal";
import RenameModal from "./RenameModal";
import {
  ChevronDownIcon,
  CloseIcon,
  PencilIcon,
  PlusIcon,
  SearchIcon,
  StarFill,
  StarLine,
  TrashBinIcon,
} from "../../icons";

interface ChatItem {
  id: string;
  title: string;
}

interface AiSidebarHistoryProps {
  isSidebarOpen: boolean;
  onCloseSidebar: () => void;
}

export default function AiSidebarHistory({
  isSidebarOpen,
  onCloseSidebar,
}: AiSidebarHistoryProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [showMore, setShowMore] = useState(false);
  const [openDropdown, setOpenDropdown] = useState<string | null>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (openDropdown) {
        const target = event.target as HTMLElement;
        if (
          target.closest(".dropdown-menu") ||
          target.closest(".dropdown-toggle")
        ) {
          return;
        }
        setOpenDropdown(null);
      }
    };

    if (openDropdown) {
      document.addEventListener("mousedown", handleClickOutside);
    }

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [openDropdown]);

  const [todayChats, setTodayChats] = useState<ChatItem[]>([
    { id: "1", title: "Write a follow-up email to a client" },
    { id: "2", title: "Generate responsive login form layout" },
    { id: "3", title: "Create a warning state modal" },
    { id: "4", title: "Suggest color palette for dark theme" },
  ]);

  const [yesterdayChats, setYesterdayChats] = useState<ChatItem[]>([
    { id: "5", title: "Improve login page accessibility" },
    { id: "6", title: "Create a warning state modal with animation" },
    { id: "7", title: "Add password visibility toggle" },
    { id: "8", title: "Write validation logic for login form..." },
    { id: "9", title: "Fix mobile responsiveness of login UI..." },
  ]);

  const [lastWeekChats, setLastWeekChats] = useState<ChatItem[]>([
    { id: "10", title: "Improve login page accessi..." },
    { id: "11", title: "Improve login page accessi..." },
  ]);

  const renameModal = useModal();
  const [selectedChat, setSelectedChat] = useState<ChatItem | null>(null);

  const handleDropdownToggle = (itemId: string) => {
    setOpenDropdown(openDropdown === itemId ? null : itemId);
  };

  const handleDropdownClose = () => {
    setOpenDropdown(null);
  };

  const handleRenameClick = (chat: ChatItem) => {
    setSelectedChat(chat);
    renameModal.openModal();
    handleDropdownClose();
    onCloseSidebar();
  };

  const handleSaveRename = (newTitle: string) => {
    if (!selectedChat) return;

    const updateTitle = (chats: ChatItem[]) =>
      chats.map((c) =>
        c.id === selectedChat.id ? { ...c, title: newTitle } : c,
      );

    setTodayChats(updateTitle);
    setYesterdayChats(updateTitle);
    setLastWeekChats(updateTitle);
  };

  const handleDelete = (itemId: string) => {
    const filterOut = (chats: ChatItem[]) =>
      chats.filter((c) => c.id !== itemId);
    setTodayChats(filterOut);
    setYesterdayChats(filterOut);
    setLastWeekChats(filterOut);
    handleDropdownClose();
  };

  return (
    <div className="relative">
      {/* Backdrop */}
      {isSidebarOpen && (
        <div
          className="fixed inset-0 z-[99999] bg-black/50 xl:hidden dark:bg-black/80 transition-opacity"
          onClick={onCloseSidebar}
        >
          <div className="absolute top-4 end-[300px]">
            <button
              className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-white text-gray-800 transition hover:bg-gray-100 dark:bg-gray-800 dark:text-white/90 dark:hover:bg-white/3 hover:dark:text-white"
              onClick={(e) => {
                e.stopPropagation();
                onCloseSidebar();
              }}
            >
              <CloseIcon className="size-5" />
            </button>
          </div>
        </div>
      )}

      {/* Sidebar */}
      <aside
        className={`z-50  w-[280px] flex-col h-full border-s border-gray-200 bg-white p-6 ease-in-out dark:border-gray-800 dark:bg-gray-900 ${
          isSidebarOpen
            ? "flex fixed xl:static top-0 end-0 z-999999 h-screen bg-white dark:bg-gray-900"
            : "hidden xl:flex relative"
        }`}
      >
        {/* New Chat Button */}
        <button className="bg-brand-500 hover:bg-brand-600 flex w-full items-center justify-center gap-2 rounded-lg px-4 py-3 text-sm font-medium text-white transition">
          <PlusIcon className="size-5" />
          New Chat
        </button>

        {/* Search */}
        <div className="mt-5">
          <form>
            <div className="relative">
              <span className="pointer-events-none absolute top-1/2 start-4 -translate-y-1/2">
                <SearchIcon className="size-5 fill-gray-500 dark:fill-gray-400" />
              </span>
              <input
                type="text"
                placeholder="Search..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent py-2.5 pe-3.5 ps-[42px] text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30"
              />
            </div>
          </form>
        </div>
        {/* Chat Items */}
        <div className="custom-scrollbar mt-6 h-full flex-1 space-y-3 overflow-y-auto text-sm">
          {/* Today Section */}
          <div>
            <p className="mb-3 ps-3 text-xs text-gray-400 uppercase">Today</p>
            <ul className="space-y-1">
              {todayChats.map((chat) => (
                <ChatItem
                  key={chat.id}
                  chat={chat}
                  isOpen={openDropdown === chat.id}
                  onToggleDropdown={() => handleDropdownToggle(chat.id)}
                  onRename={() => handleRenameClick(chat)}
                  onDelete={() => handleDelete(chat.id)}
                />
              ))}
            </ul>
          </div>

          {/* Yesterday Section */}
          <div className="relative">
            <p className="mb-3 ps-3 text-xs text-gray-400 uppercase">
              Yesterday
            </p>
            <ul className="space-y-1">
              {yesterdayChats.map((chat) => (
                <ChatItem
                  key={chat.id}
                  chat={chat}
                  isOpen={openDropdown === chat.id}
                  onToggleDropdown={() => handleDropdownToggle(chat.id)}
                  onRename={() => handleRenameClick(chat)}
                  onDelete={() => handleDelete(chat.id)}
                />
              ))}
            </ul>
            {!showMore && (
              <div className="pointer-events-none absolute bottom-0 start-0 z-10 h-8 w-full bg-gradient-to-t from-white to-transparent dark:from-gray-900" />
            )}
          </div>

          {/* Show More Content */}
          {showMore && (
            <div className="ps-3">
              <div className="relative">
                <p className="mb-3 text-xs text-gray-400 uppercase">
                  Last Week
                </p>
                <ul className="space-y-1">
                  {lastWeekChats.map((chat) => (
                    <ChatItem
                      key={chat.id}
                      chat={chat}
                      isOpen={openDropdown === chat.id}
                      onToggleDropdown={() => handleDropdownToggle(chat.id)}
                      onRename={() => handleRenameClick(chat)}
                      onDelete={() => handleDelete(chat.id)}
                    />
                  ))}
                </ul>
              </div>
            </div>
          )}

          {/* Show more toggle */}
          <div className="mt-4 ps-3">
            <button
              onClick={() => setShowMore(!showMore)}
              className="text-primary-500 flex w-full items-center justify-between text-xs font-medium text-gray-400"
            >
              <span>{showMore ? "Show less..." : "Show more..."}</span>
              <ChevronDownIcon
                className={`size-4 ms-2 transition-transform ${
                  showMore ? "rotate-180" : ""
                }`}
              />
            </button>
          </div>
        </div>
      </aside>

      <RenameModal
        isOpen={renameModal.isOpen}
        onClose={renameModal.closeModal}
        currentTitle={selectedChat?.title || ""}
        onSave={handleSaveRename}
      />
    </div>
  );
}

// Chat Item Component
interface ChatItemProps {
  chat: ChatItem;
  isOpen: boolean;
  onToggleDropdown: () => void;
  onRename: () => void;
  onDelete: () => void;
}

function ChatItem({
  chat,
  isOpen,
  onToggleDropdown,
  onRename,
  onDelete,
}: ChatItemProps) {
  const [starred, setStarred] = useState(false);

  return (
    <li className="group relative rounded-full px-3 py-1.5 hover:bg-gray-50 dark:hover:bg-gray-950">
      <div className="flex cursor-pointer items-center justify-between">
        <a
          href="#"
          className="block truncate text-sm text-gray-700 dark:text-gray-400"
        >
          {chat.title}
        </a>

        {/* 3-dot menu button */}
        <button
          onMouseDown={(e) => e.stopPropagation()}
          onClick={onToggleDropdown}
          className="dropdown-toggle invisible ms-2 rounded-full p-1 text-gray-700 group-hover:visible hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-400"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="18"
            height="18"
            viewBox="0 0 18 18"
            fill="none"
          >
            <path
              d="M4.5 9.00384L4.5 8.99634M13.5 9.00384V8.99634M9 9.00384V8.99634"
              stroke="currentColor"
              strokeWidth="3"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </div>

      {/* Dropdown menu */}
      {isOpen && (
        <ul className="dropdown-menu absolute end-0 z-20 mt-1 w-45 space-y-0.5 rounded-xl bg-white p-1.5 shadow-md dark:bg-gray-800">
          {/* Star / Unstar */}
          <li>
            <button
              onClick={() => {
                setStarred((prev) => !prev);
                onToggleDropdown();
              }}
              className="flex w-full items-center gap-2 rounded-lg bg-transparent px-1.5 py-2 text-gray-700 hover:bg-gray-100 hover:text-gray-800 dark:text-gray-400 dark:hover:bg-gray-900 dark:hover:text-white/90"
            >
              {starred ? (
                <StarFill className="size-5" />
              ) : (
                <StarLine className="size-5" />
              )}
              {starred ? "Remove Starred" : "Add Starred"}
            </button>
          </li>

          {/* Rename */}
          <li>
            <button
              onClick={onRename}
              className="flex w-full items-center gap-2 rounded-lg bg-transparent px-1.5 py-2 text-gray-700 hover:bg-gray-100 hover:text-gray-800 dark:text-gray-400 dark:hover:bg-gray-900 dark:hover:text-white/90"
            >
              <PencilIcon className="size-5" />
              Rename
            </button>
          </li>

          <hr className="my-1 border-gray-200 dark:border-white/10" />

          {/* Delete */}
          <li>
            <button
              onClick={onDelete}
              className="flex w-full items-center gap-2 rounded-lg bg-transparent px-1.5 py-2 text-gray-700 hover:bg-gray-100 hover:text-gray-800 dark:text-gray-400 dark:hover:bg-gray-900 dark:hover:text-white/90"
            >
              <TrashBinIcon className="size-5" />
              Delete
            </button>
          </li>
        </ul>
      )}
    </li>
  );
}
