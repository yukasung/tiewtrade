import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { ArrowRightIcon, MoreDotIcon } from "../../icons";
import { Dropdown } from "../ui/dropdown/Dropdown";
import { DropdownItem } from "../ui/dropdown/DropdownItem";

export default function TopPages() {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);

  function toggleDropdown() {
    setIsOpen(!isOpen);
  }

  function closeDropdown() {
    setIsOpen(false);
  }

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 md:p-6 dark:border-gray-800 dark:bg-white/3">
      <div className="flex items-start justify-between">
        <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">
          {t("analytics.topPages.title")}
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

      <div className="my-6">
        <div className="flex items-center justify-between border-b border-gray-100 pb-4 dark:border-gray-800">
          <span className="text-theme-xs text-gray-400">
            {t("analytics.topPages.source")}
          </span>
          <span className="text-end text-theme-xs text-gray-400">
            {t("analytics.topPages.pageview")}
          </span>
        </div>

        <div className="flex items-center justify-between border-b border-gray-100 py-3 dark:border-gray-800">
          <span className="text-theme-sm text-gray-500 dark:text-gray-400">
            tailadmin.com
          </span>
          <span className="text-end text-theme-sm text-gray-500 dark:text-gray-400">
            4.7K
          </span>
        </div>

        <div className="flex items-center justify-between border-b border-gray-100 py-3 dark:border-gray-800">
          <span className="text-theme-sm text-gray-500 dark:text-gray-400">
            preview.tailadmin.com
          </span>
          <span className="text-end text-theme-sm text-gray-500 dark:text-gray-400">
            3.4K
          </span>
        </div>

        <div className="flex items-center justify-between border-b border-gray-100 py-3 dark:border-gray-800">
          <span className="text-theme-sm text-gray-500 dark:text-gray-400">
            docs.tailadmin.com
          </span>
          <span className="text-end text-theme-sm text-gray-500 dark:text-gray-400">
            2.9K
          </span>
        </div>

        <div className="flex items-center justify-between border-b border-gray-100 py-3 dark:border-gray-800">
          <span className="text-theme-sm text-gray-500 dark:text-gray-400">
            tailadmin.com/componetns
          </span>
          <span className="text-end text-theme-sm text-gray-500 dark:text-gray-400">
            1.5K
          </span>
        </div>
      </div>

      <Link
        to="/"
        className="flex items-center justify-center gap-2 rounded-lg border border-gray-300 bg-white p-2.5 text-theme-sm font-medium text-gray-700 shadow-theme-xs hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-white/3"
      >
        {t("analytics.topPages.channelsReport")}
        <ArrowRightIcon className="size-5 fill-current rtl:rotate-180" />
      </Link>
    </div>
  );
}
