import ChatHeader from "@/components/chats/ChatHeader";
import ChatList from "@/components/chats/ChatList";
import { cn } from "@/utils";
import { useState } from "react";

export default function ChatSidebar() {
  const [isOpen, setIsOpen] = useState(false);
  const toggleSidebar = () => {
    setIsOpen(!isOpen);
  };
  return (
    <>
      {isOpen && (
        <div
          className={cn(
            "fixed inset-0 z-999999 bg-gray-900/50 transition-all duration-300",
          )}
          onClick={toggleSidebar}
        ></div>
      )}
      <div
        className={cn(
          "flex-col rounded-2xl border border-gray-200 bg-white xl:flex xl:h-full xl:w-1/4 xl:overflow-hidden dark:border-gray-800 dark:bg-white/3",
        )}
      >
        <ChatHeader onToggle={toggleSidebar} />
        <ChatList isOpen={isOpen} onToggle={toggleSidebar} />
      </div>
    </>
  );
}
