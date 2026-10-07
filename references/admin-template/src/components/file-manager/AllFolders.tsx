import { ArrowRightIcon } from "@/icons";
import { Link } from "react-router";
import FolderCard from "./FolderCard";

export default function AllFolders() {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/3">
      <div className="px-4 py-4 sm:ps-6 sm:pe-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">
            All Folders
          </h3>

          <Link
            to="/"
            className="inline-flex items-center gap-2 text-sm font-medium text-gray-500 hover:text-brand-500 dark:text-gray-400 dark:hover:text-brand-500"
          >
            View All
            <ArrowRightIcon className="rtl:rotate-180" />
          </Link>
        </div>
      </div>
      <div className="border-t border-gray-100 p-5 sm:p-6 dark:border-gray-800">
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 sm:gap-6">
          <FolderCard title="Images" fileCount="345" size="26.40 GB" />
          <FolderCard title="Documents" fileCount="130" size="26.40 GB" />
          <FolderCard title="Apps" fileCount="130 Files" size="26.40 GB" />
          <FolderCard title="Downloads" fileCount="345" size="26.40 GB" />
        </div>
      </div>
    </div>
  );
}
