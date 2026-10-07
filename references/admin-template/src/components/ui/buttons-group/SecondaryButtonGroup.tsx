export default function SecondaryButtonGroup() {
  return (
    <div className="custom-scrollbar max-w-full overflow-x-auto pb-3 xsm:pb-0">
      <div className="min-w-77.25">
        <div className="inline-flex items-center shadow-theme-xs">
          <button
            type="button"
            className="inline-flex items-center gap-2 bg-transparent px-4 py-3 text-sm font-medium text-gray-800 ring-1 ring-gray-300 transition ring-inset first:rounded-s-lg last:rounded-e-lg hover:bg-gray-50 dark:bg-white/3 dark:text-gray-200 dark:ring-gray-700 dark:hover:bg-white/3"
          >
            Button Text
          </button>
          <button
            type="button"
            className="-ms-px inline-flex items-center gap-2 bg-transparent px-4 py-3 text-sm font-medium text-gray-700 ring-1 ring-gray-300 transition ring-inset first:rounded-s-lg last:rounded-e-lg hover:bg-gray-50 hover:text-gray-800 dark:bg-transparent dark:text-gray-400 dark:ring-gray-700 dark:hover:bg-white/3"
          >
            Button Text
          </button>
          <button
            type="button"
            className="-ms-px inline-flex items-center gap-2 bg-transparent px-4 py-3 text-sm font-medium text-gray-700 ring-1 ring-gray-300 transition ring-inset first:rounded-s-lg last:rounded-e-lg hover:bg-gray-50 hover:text-gray-800 dark:bg-transparent dark:text-gray-400 dark:ring-gray-700 dark:hover:bg-white/3"
          >
            Button Text
          </button>
        </div>
      </div>
    </div>
  );
}
