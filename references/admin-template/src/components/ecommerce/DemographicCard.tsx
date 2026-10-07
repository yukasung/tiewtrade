import { useState } from "react";
import { useTranslation } from "react-i18next";
import { MoreDotIcon } from "../../icons";
import { Dropdown } from "../ui/dropdown/Dropdown";
import { DropdownItem } from "../ui/dropdown/DropdownItem";
import CountryMap from "./CountryMap";

export default function DemographicCard() {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);

  const toggleDropdown = () => {
    setIsOpen(!isOpen);
  };

  const closeDropdown = () => {
    setIsOpen(false);
  };

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 sm:p-6 dark:border-gray-800 dark:bg-white/3">
      <div className="flex justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">
            {t("ecommerce.demographic.title")}
          </h3>
          <p className="mt-1 text-theme-sm text-gray-500 dark:text-gray-400">
            {t("ecommerce.demographic.subtitle")}
          </p>
        </div>
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

      <div className="my-6 overflow-hidden rounded-2xl border border-gray-200 px-4 py-6 sm:px-6 dark:border-gray-800">
        <div
          id="mapOne"
          className="mapOne map-btn -mx-4 -my-6 h-53 w-63 2xsm:w-76.75 xsm:w-89.5 sm:-mx-6 md:w-167 lg:w-158.5 xl:w-98.25 2xl:w-138.5"
        >
          <CountryMap />
        </div>
      </div>

      <div className="space-y-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-full max-w-8 items-center rounded-full">
              <img src="./images/country/country-01.svg" alt="usa" />
            </div>
            <div>
              <p className="text-theme-sm font-semibold text-gray-800 dark:text-white/90">
                {t("ecommerce.demographic.usa")}
              </p>
              <span className="block text-theme-xs text-gray-500 dark:text-gray-400">
                {t("ecommerce.demographic.customers", { count: "2,379" })}
              </span>
            </div>
          </div>

          <div className="flex w-full max-w-35 items-center gap-3">
            <div className="relative block h-2 w-full max-w-25 rounded-sm bg-gray-200 dark:bg-gray-800">
              <div className="absolute inset-s-0 top-0 flex h-full w-[79%] items-center justify-center rounded-sm bg-brand-500 text-xs font-medium text-white"></div>
            </div>
            <p className="text-theme-sm font-medium text-gray-800 dark:text-white/90">
              79%
            </p>
          </div>
        </div>

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-full max-w-8 items-center rounded-full">
              <img src="./images/country/country-02.svg" alt="france" />
            </div>
            <div>
              <p className="text-theme-sm font-semibold text-gray-800 dark:text-white/90">
                {t("ecommerce.demographic.france")}
              </p>
              <span className="block text-theme-xs text-gray-500 dark:text-gray-400">
                {t("ecommerce.demographic.customers", { count: "589" })}
              </span>
            </div>
          </div>

          <div className="flex w-full max-w-35 items-center gap-3">
            <div className="relative block h-2 w-full max-w-25 rounded-sm bg-gray-200 dark:bg-gray-800">
              <div className="absolute inset-s-0 top-0 flex h-full w-[23%] items-center justify-center rounded-sm bg-brand-500 text-xs font-medium text-white"></div>
            </div>
            <p className="text-theme-sm font-medium text-gray-800 dark:text-white/90">
              23%
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
