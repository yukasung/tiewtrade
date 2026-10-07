import { useState } from "react";
import { useTranslation } from "react-i18next";
import { MoreDotIcon } from "../../icons";
import { Dropdown } from "../ui/dropdown/Dropdown";
import { DropdownItem } from "../ui/dropdown/DropdownItem";
import CountryMapTwo from "./country-map-two";

export default function SalesChannelCountry() {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);

  function toggleDropdown() {
    setIsOpen(!isOpen);
  }

  function closeDropdown() {
    setIsOpen(false);
  }
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/3">
      <div className="mb-7 flex items-center justify-between gap-2">
        <div>
          <h3 className="text-lg font-medium text-gray-800 dark:text-white/90">
            {t("sales.salesByCountry.title")}
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {t("sales.salesByCountry.subtitle")}
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

      <div
        id="mapTwo"
        className="mapTwo -mt-6! h-45! w-full! bg-transparent! p-3"
      >
        <CountryMapTwo />
      </div>

      <ul className="space-y-4 pt-3">
        <li className="grid grid-cols-4 justify-between gap-4">
          <div className="col-span-2">
            <div className="flex items-center gap-2.5">
              <img
                src="/images/flag/flag-01.png"
                className="size-4 rounded-full"
                alt="flag"
              />
              <span className="text-sm text-gray-800 dark:text-white/90">
                {t("sales.salesByCountry.countries.usa")}
              </span>
            </div>
          </div>
          <div className="col-span-1">
            <span className="text-sm text-gray-700 dark:text-gray-400">
              $20.594
            </span>
          </div>
          <div className="col-span-1 text-end">
            <span className="text-sm text-gray-700 dark:text-gray-400">
              79%
            </span>
          </div>
        </li>
        <li className="grid grid-cols-4 justify-between gap-4">
          <div className="col-span-2">
            <div className="flex items-center gap-2.5">
              <img
                src="/images/flag/flag-02.png"
                className="size-4 rounded-full"
                alt="flag"
              />
              <span className="text-sm text-gray-800 dark:text-white/90">
                {t("sales.salesByCountry.countries.france")}
              </span>
            </div>
          </div>
          <div className="col-span-1">
            <span className="text-sm text-gray-700 dark:text-gray-400">
              $20.594
            </span>
          </div>
          <div className="col-span-1 text-end">
            <span className="text-sm text-gray-700 dark:text-gray-400">
              779%
            </span>
          </div>
        </li>
        <li className="grid grid-cols-4 justify-between gap-4">
          <div className="col-span-2">
            <div className="flex items-center gap-2.5">
              <img
                src="/images/flag/flag-03.png"
                className="size-4 rounded-full"
                alt="flag"
              />
              <span className="text-sm text-gray-800 dark:text-white/90">
                {t("sales.salesByCountry.countries.japan")}
              </span>
            </div>
          </div>
          <div className="col-span-1">
            <span className="text-sm text-gray-700 dark:text-gray-400">
              $15.230
            </span>
          </div>
          <div className="col-span-1 text-end">
            <span className="text-sm text-gray-700 dark:text-gray-400">
              68%
            </span>
          </div>
        </li>
        <li className="grid grid-cols-4 justify-between gap-4">
          <div className="col-span-2">
            <div className="flex items-center gap-2.5">
              <img
                src="/images/flag/flag-04.png"
                className="size-4 rounded-full"
                alt="flag"
              />
              <span className="text-sm text-gray-800 dark:text-white/90">
                {t("sales.salesByCountry.countries.germany")}
              </span>
            </div>
          </div>
          <div className="col-span-1">
            <span className="text-sm text-gray-700 dark:text-gray-400">
              $16.450
            </span>
          </div>
          <div className="col-span-1 text-end">
            <span className="text-sm text-gray-700 dark:text-gray-400">
              72%
            </span>
          </div>
        </li>
      </ul>
    </div>
  );
}
