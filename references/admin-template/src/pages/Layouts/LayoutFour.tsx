import PageMeta from "@/components/common/PageMeta";
import HeaderAlt from "@/components/example-layout/example-header/header-alt";
import SidebarFour from "@/components/example-layout/example-sidebar/sidebar-four";
import { SidebarProvider } from "@/context/SidebarContext";
import Backdrop from "@/layout/Backdrop";

const LayoutFourContent: React.FC = () => {
  return (
    <div className="min-h-screen bg-gray-50 xl:flex dark:bg-gray-950">
      <SidebarFour />
      <Backdrop />
      <div className="flex-1 transition-all duration-300">
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
            <div className="grid auto-rows-min gap-6 lg:grid-cols-3">
              <div className="min-h-dvh rounded-xl border border-gray-200 bg-gray-50 lg:col-span-1 dark:border-gray-800 dark:bg-white/3"></div>
              <div className="min-h-dvh rounded-xl border border-gray-200 bg-gray-50 lg:col-span-1 dark:border-gray-800 dark:bg-white/3"></div>
              <div className="min-h-dvh rounded-xl border border-gray-200 bg-gray-50 lg:col-span-1 dark:border-gray-800 dark:bg-white/3"></div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
};

export default function LayoutFour() {
  return (
    <>
      <PageMeta
        title="React.js Layout Four Dashboard | TailAdmin - React.js Admin Dashboard Template"
        description="This is React.js Layout Four Dashboard page for TailAdmin - React.js Tailwind CSS Admin Dashboard Template"
      />
      <SidebarProvider>
        <LayoutFourContent />
      </SidebarProvider>
    </>
  );
}
