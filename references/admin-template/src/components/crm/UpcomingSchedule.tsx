import Checkbox from "@/components/form/input/Checkbox";
import { Dropdown } from "@/components/ui/dropdown/Dropdown";
import { DropdownItem } from "@/components/ui/dropdown/DropdownItem";
import { MoreDotIcon } from "@/icons";
import { useState } from "react";
import { useTranslation } from "react-i18next";

export default function UpcomingSchedule() {
  const { t } = useTranslation();

  // Define the state with an index signature for dynamic string keys
  const [checkedItems, setCheckedItems] = useState<{ [key: string]: boolean }>({
    "wed-11-jan": false,
    "fri-15-feb": false,
    "thu-18-mar": false,
  });

  const handleCheckboxChange = (id: string) => {
    setCheckedItems((prevState) => ({
      ...prevState,
      [id]: !prevState[id], // Toggle the checkbox state
    }));
  };

  const [isOpen, setIsOpen] = useState(false);

  function toggleDropdown() {
    setIsOpen(!isOpen);
  }

  function closeDropdown() {
    setIsOpen(false);
  }
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 sm:p-6 dark:border-gray-800 dark:bg-white/3">
      <div className="mb-6 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">
          {t("crm.upcomingSchedule.title")}
        </h3>

        <div className="relative inline-block">
          <button className="dropdown-toggle" onClick={toggleDropdown}>
            <MoreDotIcon className="size-6 text-gray-400 hover:text-gray-700 dark:hover:text-gray-300" />
          </button>
          <Dropdown
            isOpen={isOpen}
            onClose={closeDropdown}
            className="w-40 p-2"
          >
            <DropdownItem
              onItemClick={closeDropdown}
              className="flex w-full rounded-lg text-start font-normal text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-white/5 dark:hover:text-gray-300"
            >
              {t("common.viewMore")}
            </DropdownItem>
            <DropdownItem
              onItemClick={closeDropdown}
              className="flex w-full rounded-lg text-start font-normal text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-white/5 dark:hover:text-gray-300"
            >
              {t("common.delete")}
            </DropdownItem>
          </Dropdown>
        </div>
      </div>

      <div className="custom-scrollbar max-w-full overflow-x-auto">
        <div className="min-w-[500px] xl:min-w-full">
          <div className="flex flex-col gap-2">
            {/* Item 1 */}
            <div className="flex cursor-pointer items-center gap-9 rounded-lg p-3 hover:bg-gray-50 dark:hover:bg-white/3">
              <div className="flex items-start gap-3">
                <div>
                  <Checkbox
                    className="h-5 w-5 rounded-md"
                    checked={checkedItems["wed-11-jan"]}
                    onChange={() => handleCheckboxChange("wed-11-jan")}
                  />
                </div>
                <div>
                  <span className="mb-0.5 block text-theme-xs text-gray-500 dark:text-gray-400">
                    Wed, 11 Jan
                  </span>
                  <span className="text-theme-sm font-medium text-gray-700 dark:text-gray-400">
                    09:20 AM
                  </span>
                </div>
              </div>
              <div>
                <span className="mb-1 block text-theme-sm font-medium text-gray-700 dark:text-gray-400">
                  {t("crm.upcomingSchedule.schedules.item1.title")}
                </span>
                <span className="text-theme-xs text-gray-500 dark:text-gray-400">
                  {t("crm.upcomingSchedule.schedules.item1.description")}
                </span>
              </div>
            </div>

            {/* Item 2 */}
            <div className="flex cursor-pointer items-center gap-9 rounded-lg p-3 hover:bg-gray-50 dark:hover:bg-white/3">
              <div className="flex items-start gap-3">
                <div>
                  <Checkbox
                    className="h-5 w-5 rounded-md"
                    checked={checkedItems["fri-15-feb"]}
                    onChange={() => handleCheckboxChange("fri-15-feb")}
                  />
                </div>
                <div>
                  <span className="mb-0.5 block text-theme-xs text-gray-500 dark:text-gray-400">
                    Fri, 15 Feb
                  </span>
                  <span className="text-theme-sm font-medium text-gray-700 dark:text-gray-400">
                    10:35 AM
                  </span>
                </div>
              </div>
              <div>
                <span className="mb-1 block text-theme-sm font-medium text-gray-700 dark:text-gray-400">
                  {t("crm.upcomingSchedule.schedules.item2.title")}
                </span>
                <span className="text-theme-xs text-gray-500 dark:text-gray-400">
                  {t("crm.upcomingSchedule.schedules.item2.description")}
                </span>
              </div>
            </div>

            {/* Item 3 */}
            <div className="flex cursor-pointer items-center gap-9 rounded-lg p-3 hover:bg-gray-50 dark:hover:bg-white/3">
              <div className="flex items-start gap-3">
                <div>
                  <Checkbox
                    className="h-5 w-5 rounded-md"
                    checked={checkedItems["thu-18-mar"]}
                    onChange={() => handleCheckboxChange("thu-18-mar")}
                  />
                </div>
                <div>
                  <span className="mb-0.5 block text-theme-xs text-gray-500 dark:text-gray-400">
                    Thu, 18 Mar
                  </span>
                  <span className="text-theme-sm font-medium text-gray-700 dark:text-gray-400">
                    1:15 AM
                  </span>
                </div>
              </div>
              <div>
                <span className="mb-1 block text-theme-sm font-medium text-gray-700 dark:text-gray-400">
                  {t("crm.upcomingSchedule.schedules.item3.title")}
                </span>
                <span className="text-theme-xs text-gray-500 dark:text-gray-400">
                  {t("crm.upcomingSchedule.schedules.item3.description")}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
