export default function TransactionHeader() {
  return (
    <div className="flex flex-col justify-between gap-6 rounded-2xl border border-gray-200 bg-white px-6 py-5 sm:flex-row sm:items-center dark:border-gray-800 dark:bg-white/3">
      <div className="flex flex-col gap-2.5 divide-gray-300 sm:flex-row sm:divide-x dark:divide-gray-700">
        <div className="flex items-center gap-2 sm:pe-3">
          <span className="text-base font-medium text-gray-700 dark:text-gray-400">
            Order ID : #34834
          </span>
          <span className="inline-flex items-center justify-center gap-1 rounded-full bg-success-50 px-2.5 py-0.5 text-sm font-medium text-success-600 dark:bg-success-500/15 dark:text-success-500">
            Completed
          </span>
        </div>
        <p className="text-sm text-gray-500 sm:ps-3 dark:text-gray-400">
          Due date: 25 August 2025
        </p>
      </div>

      <div className="flex gap-3">
        <button className="inline-flex items-center justify-center gap-2 rounded-lg bg-brand-500 px-4 py-3 text-sm font-medium text-white shadow-theme-xs transition hover:bg-brand-600">
          View Receipt
        </button>
        <button className="inline-flex items-center justify-center gap-2 rounded-lg bg-white px-4 py-3 text-sm font-medium text-gray-700 shadow-theme-xs ring-1 ring-gray-300 transition hover:bg-gray-50 dark:bg-gray-800 dark:text-gray-400 dark:ring-gray-700 dark:hover:bg-white/3">
          Refund
        </button>
      </div>
    </div>
  );
}
