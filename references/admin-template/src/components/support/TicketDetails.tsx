import { cn } from "@/utils";

export default function TicketDetails() {
  return (
    <div>
      {" "}
      <div className="rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/3">
        <div className="border-b border-gray-200 px-6 py-5 dark:border-gray-800">
          <h3 className="text-lg font-medium text-gray-800 dark:text-white/90">
            Ticket Details
          </h3>
        </div>
        <ul className="divide-y divide-gray-100 px-6 py-3 dark:divide-gray-800">
          <li className="grid grid-cols-2 gap-5 py-2.5">
            <span className="text-sm text-gray-500 dark:text-gray-400">
              Customer
            </span>
            <span className={cn("text-gray-700 dark:text-gray-400")}>
              John Doe
            </span>
          </li>
          <li className="grid grid-cols-2 gap-5 py-2.5">
            <span className="text-sm text-gray-500 dark:text-gray-400">
              Email
            </span>
            <span
              className={cn(
                "text-sm break-words text-gray-700 dark:text-gray-400",
              )}
            >
              jhondelin@gmail.com
            </span>
          </li>
          <li className="grid grid-cols-2 gap-5 py-2.5">
            <span className="text-sm text-gray-500 dark:text-gray-400">
              Ticket ID
            </span>
            <span className={cn("text-sm text-gray-700 dark:text-gray-400")}>
              #346520
            </span>
          </li>
          <li className="grid grid-cols-2 gap-5 py-2.5">
            <span className="text-sm text-gray-500 dark:text-gray-400">
              Category
            </span>
            <span className={cn("text-sm text-gray-700 dark:text-gray-400")}>
              General Support
            </span>
          </li>
          <li className="grid grid-cols-2 gap-5 py-2.5">
            <span className="text-sm text-gray-500 dark:text-gray-400">
              Created
            </span>
            <span className={cn("text-sm text-gray-700 dark:text-gray-400")}>
              Dec 20, 2028
            </span>
          </li>
          <li className="grid grid-cols-2 gap-5 py-2.5">
            <span className="text-sm text-gray-500 dark:text-gray-400">
              Status
            </span>
            <div>
              <span
                className={cn(
                  "inline-block rounded-full px-2 py-0.5 text-theme-xs font-medium",
                  "bg-blue-light-50 text-blue-light-500 dark:bg-blue-light-500/15 dark:text-blue-light-500",
                )}
              >
                In Progress
              </span>
            </div>
          </li>
        </ul>
      </div>
    </div>
  );
}
