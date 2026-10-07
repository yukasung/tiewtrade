import { useTranslation } from "react-i18next";
import Badge from "../ui/badge/Badge";

const transactions = [
  {
    id: "#DF429",
    date: "April 28, 2016",
    user: "Jenny Wilson",
    amount: "$473.85",
    status: "Complete" as const,
  },
  {
    id: "#HTY274",
    date: "October 30, 2017",
    user: "Wade Warren",
    amount: "$293.01",
    status: "Complete" as const,
  },
  {
    id: "#LKE600",
    date: "May 29, 2017",
    user: "Darlene Robertson",
    amount: "$782.01",
    status: "Pending" as const,
  },
  {
    id: "#HRP447",
    date: "May 20, 2015",
    user: "Arlene McCoy",
    amount: "$202.87",
    status: "Cancelled" as const,
  },
  {
    id: "#WRH647",
    date: "March 13, 2014",
    user: "Bessie Cooper",
    amount: "$490.51",
    status: "Complete" as const,
  },
];

export default function SaasInvoiceTable() {
  const { t } = useTranslation();

  return (
    <div className="rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/3">
      <div className="px-6 py-4">
        <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">
          {t("saas.recentInvoices.title")}
        </h3>
      </div>
      <div className="custom-scrollbar overflow-x-auto">
        <table className="min-w-full">
          <thead>
            <tr className="bg-gray-50 dark:bg-gray-900">
              <th className="px-6 py-4 text-start text-sm font-medium whitespace-nowrap text-gray-500 dark:text-gray-400">
                {t("saas.recentInvoices.table.serialNo")}
              </th>
              <th className="px-6 py-4 text-start text-sm font-medium whitespace-nowrap text-gray-500 dark:text-gray-400">
                {t("saas.recentInvoices.table.closeDate")}
              </th>
              <th className="px-6 py-4 text-start text-sm font-medium whitespace-nowrap text-gray-500 dark:text-gray-400">
                {t("saas.recentInvoices.table.user")}
              </th>
              <th className="px-6 py-4 text-start text-sm font-medium whitespace-nowrap text-gray-500 dark:text-gray-400">
                {t("saas.recentInvoices.table.amount")}
              </th>
              <th className="px-6 py-4 text-start text-sm font-medium whitespace-nowrap text-gray-500 dark:text-gray-400">
                {t("saas.recentInvoices.table.status")}
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 dark:divide-gray-800">
            {transactions.map((transaction) => (
              <tr key={transaction.id}>
                <td className="px-6 py-4 text-start text-sm whitespace-nowrap text-gray-700 dark:text-gray-400">
                  {transaction.id}
                </td>
                <td className="px-6 py-4 text-start text-sm whitespace-nowrap text-gray-700 dark:text-gray-400">
                  {transaction.date}
                </td>
                <td className="px-6 py-4 text-start text-sm whitespace-nowrap text-gray-700 dark:text-gray-400">
                  {transaction.user}
                </td>
                <td className="px-6 py-4 text-start text-sm whitespace-nowrap text-gray-700 dark:text-gray-400">
                  {transaction.amount}
                </td>
                <td className="px-6 py-4 text-start">
                  <Badge
                    size="sm"
                    color={
                      transaction.status === "Complete"
                        ? "success"
                        : transaction.status === "Pending"
                          ? "warning"
                          : "error"
                    }
                  >
                    {transaction.status === "Complete"
                      ? t("saas.recentInvoices.statuses.complete")
                      : transaction.status === "Pending"
                        ? t("saas.recentInvoices.statuses.pending")
                        : t("saas.recentInvoices.statuses.cancelled")}
                  </Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
