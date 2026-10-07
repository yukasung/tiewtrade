import { useState } from "react";
import { MoreDotIcon } from "../../icons";
import { Dropdown } from "../ui/dropdown/Dropdown";
import { DropdownItem } from "../ui/dropdown/DropdownItem";
import { useTranslation } from "react-i18next";

export default function DeliveryVehicle() {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);

  function toggleDropdown() {
    setIsOpen(!isOpen);
  }

  function closeDropdown() {
    setIsOpen(false);
  }
  return (
    <div className="space-y-5 rounded-xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-white/3">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">
            {t("logistics.deliveryVehicle.title")}
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {t("logistics.deliveryVehicle.subtitle")}
          </p>
        </div>
        <div className="relative inline-block">
          <button className="dropdown-toggle" onClick={toggleDropdown}>
            <MoreDotIcon className="text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 size-6" />
          </button>
          <Dropdown
            isOpen={isOpen}
            onClose={closeDropdown}
            className="w-40 p-2"
          >
            <DropdownItem
              onItemClick={closeDropdown}
              className="flex w-full font-normal text-start text-gray-500 rounded-lg hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-white/5 dark:hover:text-gray-300"
            >
              {t("common.viewMore")}
            </DropdownItem>
            <DropdownItem
              onItemClick={closeDropdown}
              className="flex w-full font-normal text-start text-gray-500 rounded-lg hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-white/5 dark:hover:text-gray-300"
            >
              {t("common.delete")}
            </DropdownItem>
          </Dropdown>
        </div>
      </div>
      <div className="relative mt-5 flex justify-between">
        <div>
          <h3 className="mb-1 text-3xl font-medium text-gray-800 dark:text-white/90">
            29
          </h3>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            <span className="text-success-600 font-medium">+3.85% </span>
            {t("logistics.deliveryVehicle.thanLastWeek")}
          </p>
          <div className="mt-5 flex items-center gap-2">
            <div className="ring-success-500 flex h-6 w-6 items-center justify-center rounded-full ring-2 ring-inset">
              <div className="bg-success-500 h-2.5 w-2.5 rounded-full"></div>
            </div>
            <div>
              <span className="text-success-500 text-sm font-medium">
                {t("logistics.deliveryVehicle.onRoute")}
              </span>
            </div>
          </div>
        </div>
        <div>
          <img
            className="absolute -end-6 -bottom-2 rtl:-scale-x-100"
            src="/images/logistics/truck.png"
            alt=""
          />
        </div>
      </div>
    </div>
  );
}
