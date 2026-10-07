import PageMeta from "@/components/common/PageMeta";
import HeaderAlt from "@/components/example-layout/example-header/header-alt";
import SidebarThree from "@/components/example-layout/example-sidebar/sidebar-three";
import { SidebarProvider, useSidebar } from "@/context/SidebarContext";
import Backdrop from "@/layout/Backdrop";
import { cn } from "@/utils";

const LayoutThreeContent: React.FC = () => {
  const { isExpanded, isMobileOpen } = useSidebar();
  const sidebarVisible = isExpanded || isMobileOpen;

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
      <SidebarThree />
      <Backdrop />
      <div
        className={cn(
          "transition-all duration-300",
          sidebarVisible ? "xl:ms-[290px]" : "xl:ms-0",
        )}
      >
        <HeaderAlt />
        <main className="mx-auto w-full max-w-screen-2xl flex-1 p-4 pb-20 md:p-6">
          {/* Page content goes here */}
          <div className="space-y-6">
            <div className="grid auto-rows-min gap-6 sm:grid-cols-2 xl:grid-cols-4">
              <div className="h-40 rounded-xl border border-gray-200 bg-gray-50 dark:border-gray-800 dark:bg-white/3"></div>
              <div className="h-40 rounded-xl border border-gray-200 bg-gray-50 dark:border-gray-800 dark:bg-white/3"></div>
              <div className="h-40 rounded-xl border border-gray-200 bg-gray-50 dark:border-gray-800 dark:bg-white/3"></div>
              <div className="h-40 rounded-xl border border-gray-200 bg-gray-50 dark:border-gray-800 dark:bg-white/3"></div>
            </div>
            <div className="min-h-dvh rounded-xl border border-gray-200 bg-gray-50 dark:border-gray-800 dark:bg-white/3"></div>
          </div>
        </main>
      </div>
    </div>
  );
};

export default function LayoutThree() {
  return (
    <>
      <PageMeta
        title="React.js Layout Three Dashboard | TailAdmin - React.js Admin Dashboard Template"
        description="This is React.js Layout Three Dashboard page for TailAdmin - React.js Tailwind CSS Admin Dashboard Template"
      />
      <SidebarProvider>
        <LayoutThreeContent />
      </SidebarProvider>
    </>
  );
}
