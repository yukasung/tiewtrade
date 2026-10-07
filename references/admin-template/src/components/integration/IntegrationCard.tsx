import Switch from "@/components/form/switch/Switch";
import IntegrationDeleteModal from "@/components/integration/IntegrationDeleteModal";
import IntegrationDetailsModal from "@/components/integration/IntegrationDetailsModal";
import IntegrationSettingsModal from "@/components/integration/IntegrationSettingsModal";
import { Dropdown } from "@/components/ui/dropdown/Dropdown";
import { DropdownItem } from "@/components/ui/dropdown/DropdownItem";
import { useModal } from "@/hooks/useModal";
import { HorizontaLDots } from "@/icons";
import { cn } from "@/utils";
import { type ReactNode, useState } from "react";

interface IntegrationCardProps {
  title: string;
  icon: ReactNode;
  description: string;
  connect: boolean;
  className?: string;
}

export default function IntegrationCard({
  title,
  icon,
  description,
  connect,
  className,
}: IntegrationCardProps) {
  const [isOpen, setIsOpen] = useState(false);
  const deleteModal = useModal();

  const toggleDropdown = () => {
    setIsOpen(!isOpen);
  };

  const closeDropdown = () => {
    setIsOpen(false);
  };

  return (
    <>
      <article
        className={cn(
          "rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/3",
          className,
        )}
      >
        <div className="relative p-5 pb-9">
          <div className="mb-5 inline-flex h-10 w-10 items-center justify-center">
            {icon}
          </div>
          <h3 className="mb-3 text-start text-lg font-semibold text-gray-800 dark:text-white/90">
            {title}
          </h3>
          <p className="max-w-xs text-start text-sm text-gray-500 dark:text-gray-400">
            {description}
          </p>
          <div className="absolute inset-e-5 top-5 h-fit">
            <button
              type="button"
              className="dropdown-toggle"
              onClick={toggleDropdown}
            >
              <HorizontaLDots className="size-6 text-gray-400 hover:text-gray-700 dark:hover:text-gray-300" />
            </button>
            <Dropdown
              isOpen={isOpen}
              onClose={closeDropdown}
              className="w-40 p-2"
            >
              <DropdownItem
                onItemClick={deleteModal.openModal}
                className="flex w-full rounded-lg text-start font-normal text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-white/5 dark:hover:text-gray-300"
              >
                Remove
              </DropdownItem>
            </Dropdown>
          </div>
        </div>

        <div className="flex items-center justify-between border-t border-gray-200 p-5 dark:border-gray-800">
          <div className="flex gap-3">
            <IntegrationSettingsModal />
            <IntegrationDetailsModal />
          </div>
          <Switch defaultChecked={connect} />
        </div>
      </article>
      <IntegrationDeleteModal
        isOpen={deleteModal.isOpen}
        onClose={deleteModal.closeModal}
      />
    </>
  );
}
