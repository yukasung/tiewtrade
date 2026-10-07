import PageMeta from "@/components/common/PageMeta";
import HeaderAlt from "@/components/example-layout/example-header/header-alt";
import SidebarFive from "@/components/example-layout/example-sidebar/sidebar-five";
import { SidebarProvider, useSidebar } from "@/context/SidebarContext";
import Backdrop from "@/layout/Backdrop";

const LayoutFiveContent: React.FC = () => {
  const { isExpanded, isMobileOpen } = useSidebar();

  return (
    <div className="min-h-screen bg-gray-50 xl:flex dark:bg-gray-950">
      <SidebarFive sidebarToggle={isMobileOpen} docsSidebarOpen={isExpanded} />
      <Backdrop />
      <div className="flex min-w-0 flex-1 flex-col">
        <HeaderAlt />
        <main className="mx-auto w-full max-w-screen-2xl flex-1 p-4 pb-20 md:p-6">
          {/* Page content goes here */}
          <div className="space-y-6">
            <div className="grid auto-rows-min gap-6 lg:grid-cols-3">
              <div className="aspect-video rounded-xl border border-gray-200 bg-gray-50 lg:col-span-1 dark:border-gray-800 dark:bg-white/3"></div>
              <div className="rounded-xl border border-gray-200 bg-gray-50 lg:col-span-2 dark:border-gray-800 dark:bg-white/3"></div>
              <div className="h-80 rounded-xl border border-gray-200 bg-gray-50 lg:col-span-full dark:border-gray-800 dark:bg-white/3"></div>
              <div className="h-80 rounded-xl border border-gray-200 bg-gray-50 lg:col-span-full dark:border-gray-800 dark:bg-white/3"></div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
};

export default function LayoutFive() {
  return (
    <>
      <PageMeta
        title="React.js Layout Five Dashboard | TailAdmin - React.js Admin Dashboard Template"
        description="This is React.js Layout Five Dashboard page for TailAdmin - React.js Tailwind CSS Admin Dashboard Template"
      />
      <SidebarProvider>
        <LayoutFiveContent />
      </SidebarProvider>
    </>
  );
}
