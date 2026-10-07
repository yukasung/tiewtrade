import { useState } from "react";
import { useTranslation } from "react-i18next";
import TableDropdown from "../common/TableDropdown";

interface Transaction {
  id: string;
  activity: string;
  price: string;
  date: string;
  status: "Completed" | "In Progress";
}

const transactions: Transaction[] = [
  {
    id: "NIV_034834",
    activity: "Hotel Booking",
    price: "$9,234.87",
    date: "15 Mar, 2028 08:22 AM",
    status: "Completed",
  },
  {
    id: "NIV_034345",
    activity: "Online Shopping",
    price: "$4,567.23",
    date: "28 Feb, 2028 09:15 AM",
    status: "Completed",
  },
  {
    id: "NIV_093854",
    activity: "Game Purchase",
    price: "$22,101.76",
    date: "14 Feb, 2028 02:55 PM",
    status: "In Progress",
  },
  {
    id: "NIV_005378",
    activity: "Utility Bill Payment",
    price: "$7,890.45",
    date: "02 Feb, 2028 06:30 PM",
    status: "Completed",
  },
  {
    id: "NIV_823930",
    activity: "Online Course Enrollment",
    price: "$11,223.90",
    date: "22 Jan, 2028 11:02 AM",
    status: "Completed",
  },
];

export default function FinanceTransactionTable() {
  const { t } = useTranslation();
  const [selectedItems, setSelectedItems] = useState<string[]>([]);

  const toggleAll = () => {
    if (selectedItems.length === transactions.length) {
      setSelectedItems([]);
    } else {
      setSelectedItems(transactions.map((t) => t.id));
    }
  };

  const toggleItem = (id: string) => {
    setSelectedItems((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id],
    );
  };

  const getActivityTranslation = (activity: string) => {
    const map: Record<string, string> = {
      "Hotel Booking": "hotelBooking",
      "Online Shopping": "onlineShopping",
      "Game Purchase": "gamePurchase",
      "Utility Bill Payment": "utilityBillPayment",
      "Online Course Enrollment": "onlineCourseEnrollment",
    };
    const key = map[activity];
    return key ? t(`finance.transactionsTable.activities.${key}`) : activity;
  };

  const getStatusTranslation = (status: string) => {
    const map: Record<string, string> = {
      Completed: "completed",
      "In Progress": "inProgress",
    };
    const key = map[status];
    return key ? t(`finance.transactionsTable.statuses.${key}`) : status;
  };

  return (
    <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white pt-4 dark:border-gray-800 dark:bg-white/3">
      <div className="mb-4 flex flex-col gap-5 px-6 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">
            {t("finance.transactionsTable.title")}
          </h3>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="relative">
            <span className="pointer-events-none absolute start-4 top-1/2 -translate-y-1/2">
              <svg
                className="text-gray-500 dark:text-gray-400"
                width="20"
                height="20"
                viewBox="0 0 20 20"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  fillRule="evenodd"
                  clipRule="evenodd"
                  d="M3.04199 9.37381C3.04199 5.87712 5.87735 3.04218 9.37533 3.04218C12.8733 3.04218 15.7087 5.87712 15.7087 9.37381C15.7087 12.8705 12.8733 15.7055 9.37533 15.7055C5.87735 15.7055 3.04199 12.8705 3.04199 9.37381ZM9.37533 1.54218C5.04926 1.54218 1.54199 5.04835 1.54199 9.37381C1.54199 13.6993 5.04926 17.2055 9.37533 17.2055C11.2676 17.2055 13.0032 16.5346 14.3572 15.4178L17.1773 18.2381C17.4702 18.531 17.945 18.5311 18.2379 18.2382C18.5308 17.9453 18.5309 17.4704 18.238 17.1775L15.4182 14.3575C16.5367 13.0035 17.2087 11.2671 17.2087 9.37381C17.2087 5.04835 13.7014 1.54218 9.37533 1.54218Z"
                  fill="currentColor"
                />
              </svg>
            </span>
            <input
              type="text"
              placeholder={t("finance.transactionsTable.searchPlaceholder")}
              className="dark:bg-dark-900 h-10 w-full rounded-lg border border-gray-300 bg-transparent py-2.5 ps-[42px] pe-4 text-sm text-gray-800 shadow-theme-xs placeholder:text-gray-400 focus:border-brand-300 focus:ring-3 focus:ring-brand-500/10 focus:outline-hidden xl:w-[300px] dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30 dark:focus:border-brand-800"
            />
          </div>
          <button className="inline-flex h-10 items-center gap-2 rounded-lg border border-gray-300 bg-white px-4 py-2.5 text-theme-sm font-medium text-gray-700 shadow-theme-xs hover:bg-gray-50 hover:text-gray-800 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-white/3 dark:hover:text-gray-200">
            <svg
              className="fill-white stroke-current dark:fill-gray-800"
              width="20"
              height="20"
              viewBox="0 0 20 20"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M2.29004 5.90393H17.7067"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <path
                d="M17.7075 14.0961H2.29085"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <path
                d="M12.0826 3.33331C13.5024 3.33331 14.6534 4.48431 14.6534 5.90414C14.6534 7.32398 13.5024 8.47498 12.0826 8.47498C10.6627 8.47498 9.51172 7.32398 9.51172 5.90415C9.51172 4.48432 10.6627 3.33331 12.0826 3.33331Z"
                stroke="currentColor"
                strokeWidth="1.5"
              />
              <path
                d="M7.91745 11.525C6.49762 11.525 5.34662 12.676 5.34662 14.0959C5.34661 15.5157 6.49762 16.6667 7.91745 16.6667C9.33728 16.6667 10.4883 15.5157 10.4883 14.0959C10.4883 12.676 9.33728 11.525 7.91745 11.525Z"
                stroke="currentColor"
                strokeWidth="1.5"
              />
            </svg>
            {t("finance.transactionsTable.filter")}
          </button>
        </div>
      </div>

      <div className="custom-scrollbar max-w-full overflow-x-auto">
        <table className="min-w-full">
          <thead className="border-y border-gray-100 bg-gray-50 dark:border-gray-800 dark:bg-gray-900">
            <tr>
              <th className="px-6 py-3 text-start whitespace-nowrap">
                <div className="flex items-center gap-3">
                  <div
                    onClick={toggleAll}
                    className={`flex h-5 w-5 cursor-pointer items-center justify-center rounded-md border-[1.25px] ${
                      selectedItems.length === transactions.length
                        ? "border-brand-500 bg-brand-500"
                        : "border-gray-300 bg-white dark:border-gray-700 dark:bg-white/0"
                    }`}
                  >
                    {selectedItems.length === transactions.length && (
                      <svg
                        width="14"
                        height="14"
                        viewBox="0 0 14 14"
                        fill="none"
                        xmlns="http://www.w3.org/2000/svg"
                      >
                        <path
                          d="M11.6668 3.5L5.25016 9.91667L2.3335 7"
                          stroke="white"
                          strokeWidth="1.94437"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
                    )}
                  </div>
                  <span className="block text-theme-xs font-medium text-gray-500 dark:text-gray-400">
                    {t("finance.transactionsTable.table.orderId")}
                  </span>
                </div>
              </th>
              <th className="px-6 py-3 text-start whitespace-nowrap">
                <p className="text-theme-xs font-medium text-gray-500 dark:text-gray-400">
                  {t("finance.transactionsTable.table.activity")}
                </p>
              </th>
              <th className="px-6 py-3 text-start whitespace-nowrap">
                <p className="text-theme-xs font-medium text-gray-500 dark:text-gray-400">
                  {t("finance.transactionsTable.table.price")}
                </p>
              </th>
              <th className="px-6 py-3 text-start whitespace-nowrap">
                <p className="text-theme-xs font-medium text-gray-500 dark:text-gray-400">
                  {t("finance.transactionsTable.table.date")}
                </p>
              </th>
              <th className="px-6 py-3 text-start whitespace-nowrap">
                <p className="text-theme-xs font-medium text-gray-500 dark:text-gray-400">
                  {t("finance.transactionsTable.table.status")}
                </p>
              </th>
              <th className="px-6 py-3 text-end whitespace-nowrap"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
            {transactions.map((transaction) => (
              <tr key={transaction.id}>
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="flex items-center gap-3">
                    <div
                      onClick={() => toggleItem(transaction.id)}
                      className={`flex h-5 w-5 cursor-pointer items-center justify-center rounded-md border-[1.25px] ${
                        selectedItems.includes(transaction.id)
                          ? "border-brand-500 bg-brand-500"
                          : "border-gray-300 bg-white dark:border-gray-700 dark:bg-white/0"
                      }`}
                    >
                      {selectedItems.includes(transaction.id) && (
                        <svg
                          width="14"
                          height="14"
                          viewBox="0 0 14 14"
                          fill="none"
                          xmlns="http://www.w3.org/2000/svg"
                        >
                          <path
                            d="M11.6668 3.5L5.25016 9.91667L2.3335 7"
                            stroke="white"
                            strokeWidth="1.94437"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                        </svg>
                      )}
                    </div>
                    <span className="text-theme-sm font-medium text-gray-700 dark:text-gray-400">
                      {transaction.id}
                    </span>
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <p className="text-theme-sm text-gray-700 dark:text-gray-400">
                    {getActivityTranslation(transaction.activity)}
                  </p>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <p className="text-theme-sm text-gray-700 dark:text-gray-400">
                    {transaction.price}
                  </p>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <p className="text-theme-sm text-gray-700 dark:text-gray-400">
                    {transaction.date}
                  </p>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span
                    className={`inline-flex rounded-full px-2 py-0.5 text-theme-xs font-medium ${
                      transaction.status === "Completed"
                        ? "bg-success-50 text-success-600 dark:bg-success-500/15 dark:text-success-500"
                        : "bg-warning-50 text-warning-600 dark:bg-warning-500/15 dark:text-warning-400"
                    }`}
                  >
                    {getStatusTranslation(transaction.status)}
                  </span>
                </td>
                <td className="px-6 py-4 text-end whitespace-nowrap">
                  <TableDropdown
                    dropdownButton={
                      <button className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300">
                        <svg
                          className="fill-current"
                          width="24"
                          height="24"
                          viewBox="0 0 24 24"
                          fill="none"
                          xmlns="http://www.w3.org/2000/svg"
                        >
                          <path
                            fillRule="evenodd"
                            clipRule="evenodd"
                            d="M5.99902 10.245C6.96552 10.245 7.74902 11.0285 7.74902 11.995V12.005C7.74902 12.9715 6.96552 13.755 5.99902 13.755C5.03253 13.755 4.24902 12.9715 4.24902 12.005V11.995C4.24902 11.0285 5.03253 10.245 5.99902 10.245ZM17.999 10.245C18.9655 10.245 19.749 11.0285 19.749 11.995V12.005C19.749 12.9715 18.9655 13.755 17.999 13.755C17.0325 13.755 16.249 12.9715 16.249 12.005V11.995C16.249 11.0285 17.0325 10.245 17.999 10.245ZM13.749 11.995C13.749 11.0285 12.9655 10.245 11.999 10.245C11.0325 10.245 10.249 11.0285 10.249 11.995V12.005C10.249 12.9715 11.0325 13.755 11.999 13.755C12.9655 13.755 13.749 12.9715 13.749 12.005V11.995Z"
                          />
                        </svg>
                      </button>
                    }
                    dropdownContent={
                      <>
                        <button className="flex w-full rounded-lg px-3 py-2 text-start text-theme-xs font-medium text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-white/5 dark:hover:text-gray-300">
                          {t("common.viewMore")}
                        </button>
                        <button className="flex w-full rounded-lg px-3 py-2 text-start text-theme-xs font-medium text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-white/5 dark:hover:text-gray-300">
                          {t("common.delete")}
                        </button>
                      </>
                    }
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
