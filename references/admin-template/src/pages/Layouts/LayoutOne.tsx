import PageMeta from "@/components/common/PageMeta";
import HeaderSix from "@/components/example-layout/example-header/header-six";
import SidebarOne from "@/components/example-layout/example-sidebar/sidebar-one";
import { SidebarProvider, useSidebar } from "@/context/SidebarContext";
import Backdrop from "@/layout/Backdrop";
import { cn } from "@/utils";
import React from "react";

const LayoutOneContent: React.FC = () => {
  const { isExpanded, isHovered, isMobileOpen } = useSidebar();

  return (
    <div className="min-h-screen bg-white xl:flex dark:bg-black">
      <SidebarOne />
      <Backdrop />
      <div
        className={cn(
          "flex-1 transition-all duration-300 ease-in-out",
          isExpanded || isHovered ? "xl:ms-[290px]" : "xl:ms-[90px]",
          isMobileOpen ? "ms-0" : "",
        )}
      >
        <HeaderSix />
        <main className="mx-auto w-full max-w-screen-2xl flex-1 p-4 pb-20 md:p-6">
          {/* Page content goes here */}
          <div className="space-y-6">
            <div className="grid auto-rows-min gap-6 sm:grid-cols-2 xl:grid-cols-4">
              <div className="h-40 rounded-xl border border-gray-200 bg-gray-50 dark:border-gray-800 dark:bg-white/3"></div>
              <div className="h-40 rounded-xl border border-gray-200 bg-gray-50 dark:border-gray-800 dark:bg-white/3"></div>
              <div className="h-40 rounded-xl border border-gray-200 bg-gray-50 dark:border-gray-800 dark:bg-white/3"></div>
              <div className="h-40 rounded-xl border border-gray-200 bg-gray-50 dark:border-gray-800 dark:bg-white/3"></div>
            </div>

            <div className="grid auto-rows-min gap-6 sm:grid-cols-2 xl:grid-cols-3">
              <div className="col-span-2 min-h-dvh rounded-xl border border-gray-200 bg-gray-50 dark:border-gray-800 dark:bg-white/3"></div>
              <div className="col-span-1 min-h-dvh rounded-xl border border-gray-200 bg-gray-50 dark:border-gray-800 dark:bg-white/3"></div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
};

export default function LayoutOne() {
  return (
    <>
      <PageMeta
        title="React.js Layout One Dashboard | TailAdmin - React.js Admin Dashboard Template"
        description="This is React.js Layout One Dashboard page for TailAdmin - React.js Tailwind CSS Admin Dashboard Template"
      />
      <SidebarProvider>
        <LayoutOneContent />
      </SidebarProvider>
    </>
  );
}
