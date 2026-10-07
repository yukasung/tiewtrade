import { SidebarProvider, useSidebar } from "@/context/SidebarContext";
import { cn } from "@/utils";
import { Outlet } from "react-router";
import AppHeader from "./AppHeader";
import AppSidebar from "./AppSidebar";
import Backdrop from "./Backdrop";

const AlternativeLayoutContent: React.FC = () => {
  const { isExpanded, isHovered, isMobileOpen } = useSidebar();

  return (
    <div className="min-h-screen xl:flex">
      <div>
        <AppSidebar />
        <Backdrop />
      </div>
      <div
        className={cn(
          "flex-1 transition-all duration-300 ease-in-out",
          isExpanded || isHovered ? "xl:ms-72.5" : "xl:ms-22.5",
          isMobileOpen ? "ms-0" : "",
        )}
      >
        <AppHeader />
        {/* Alternative layout with different container styles */}
        <div>
          <Outlet />
        </div>
      </div>
    </div>
  );
};

const AlternativeLayout: React.FC = () => {
  return (
    <SidebarProvider>
      <AlternativeLayoutContent />
    </SidebarProvider>
  );
};

export default AlternativeLayout;
