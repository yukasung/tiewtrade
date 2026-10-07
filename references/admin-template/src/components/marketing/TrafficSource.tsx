import { Dropdown } from "@/components/ui/dropdown/Dropdown";
import { DropdownItem } from "@/components/ui/dropdown/DropdownItem";
import { MoreDotIcon } from "@/icons";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

export default function TrafficSource() {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);

  function toggleDropdown() {
    setIsOpen(!isOpen);
  }

  function closeDropdown() {
    setIsOpen(false);
  }
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 sm:p-6 dark:border-gray-800 dark:bg-white/3">
      <div className="mb-6 flex items-center justify-between gap-2">
        <div>
          <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">
            {t("marketing.trafficSource.title")}
          </h3>
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

      <div>
        <div className="flex items-center justify-between border-b border-gray-100 py-3 last:border-b-0 dark:border-gray-800">
          <div className="flex items-center gap-4">
            <div className="w-full max-w-8 items-center rounded-full">
              <img src="/images/brand/brand-05.svg" alt="brand" />
            </div>
            <div>
              <p className="text-theme-sm font-medium text-gray-700 dark:text-gray-300">
                Google
              </p>
            </div>
          </div>

          <div className="flex w-full max-w-[140px] items-center gap-3">
            <div className="relative block h-2 w-full max-w-[100px] rounded-sm bg-gray-200 dark:bg-gray-800">
              <div className="absolute start-0 top-0 flex h-full w-[79%] items-center justify-center rounded-sm bg-brand-500 text-xs font-medium text-white"></div>
            </div>
            <p className="text-theme-sm font-medium text-gray-700 dark:text-gray-400">
              79%
            </p>
          </div>
        </div>

        <div className="flex items-center justify-between border-b border-gray-100 py-3 last:border-b-0 dark:border-gray-800">
          <div className="flex items-center gap-4">
            <div className="w-full max-w-8 items-center rounded-full">
              <img src="/images/brand/brand-06.svg" alt="brand" />
            </div>
            <div>
              <p className="text-theme-sm font-medium text-gray-700 dark:text-gray-300">
                Youtube
              </p>
            </div>
          </div>

          <div className="flex w-full max-w-[140px] items-center gap-3">
            <div className="relative block h-2 w-full max-w-[100px] rounded-sm bg-gray-200 dark:bg-gray-800">
              <div className="absolute start-0 top-0 flex h-full w-[55%] items-center justify-center rounded-sm bg-brand-500 text-xs font-medium text-white"></div>
            </div>
            <p className="text-theme-sm font-medium text-gray-700 dark:text-gray-400">
              55%
            </p>
          </div>
        </div>

        <div className="flex items-center justify-between border-b border-gray-100 py-3 last:border-b-0 dark:border-gray-800">
          <div className="flex items-center gap-4">
            <div className="w-full max-w-8 items-center rounded-full">
              <img src="/images/brand/brand-02.svg" alt="brand" />
            </div>
            <div>
              <p className="text-theme-sm font-medium text-gray-700 dark:text-gray-300">
                Facebook
              </p>
            </div>
          </div>

          <div className="flex w-full max-w-[140px] items-center gap-3">
            <div className="relative block h-2 w-full max-w-[100px] rounded-sm bg-gray-200 dark:bg-gray-800">
              <div className="absolute start-0 top-0 flex h-full w-[48%] items-center justify-center rounded-sm bg-brand-500 text-xs font-medium text-white"></div>
            </div>
            <p className="text-theme-sm font-medium text-gray-700 dark:text-gray-400">
              48%
            </p>
          </div>
        </div>

        <div className="flex items-center justify-between border-b border-gray-100 py-3 last:border-b-0 dark:border-gray-800">
          <div className="flex items-center gap-4">
            <div className="w-full max-w-8 items-center rounded-full">
              <img src="/images/brand/brand-04.svg" alt="brand" />
            </div>
            <div>
              <p className="text-theme-sm font-medium text-gray-700 dark:text-gray-300">
                Instagram
              </p>
            </div>
          </div>

          <div className="flex w-full max-w-[140px] items-center gap-3">
            <div className="relative block h-2 w-full max-w-[100px] rounded-sm bg-gray-200 dark:bg-gray-800">
              <div className="absolute start-0 top-0 flex h-full w-[48%] items-center justify-center rounded-sm bg-brand-500 text-xs font-medium text-white"></div>
            </div>
            <p className="text-theme-sm font-medium text-gray-700 dark:text-gray-400">
              48%
            </p>
          </div>
        </div>
      </div>

      <Link
        to="/"
        className="mt-6 flex items-center justify-center gap-2 rounded-lg border border-gray-300 bg-white p-2.5 text-theme-sm font-medium text-gray-700 shadow-theme-xs hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-white/3"
      >
        {t("marketing.trafficSource.viewAll")}
      </Link>
    </div>
  );
}
