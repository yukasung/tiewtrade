import Badge from "@/components/ui/badge/Badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useTranslation } from "react-i18next";

interface Transaction {
  image: string;
  actionKey: "bought" | "sell";
  symbol: string;
  date: string;
  amount: string;
  categoryKey: "finance";
  status: "Success" | "Pending" | "Failed";
}

const transactionData: Transaction[] = [
  {
    image: "/images/brand/brand-08.svg",
    actionKey: "bought",
    symbol: "PYPL",
    date: "Nov 23, 01:00 PM",
    amount: "$2,567.88",
    categoryKey: "finance",
    status: "Success",
  },
  {
    image: "/images/brand/brand-07.svg",
    actionKey: "bought",
    symbol: "AAPL",
    date: "Nov 23, 01:00 PM",
    amount: "$2,567.88",
    categoryKey: "finance",
    status: "Pending",
  },
  {
    image: "/images/brand/brand-15.svg",
    actionKey: "sell",
    symbol: "KKST",
    date: "Nov 23, 01:00 PM",
    amount: "$2,567.88",
    categoryKey: "finance",
    status: "Success",
  },
  {
    image: "/images/brand/brand-02.svg",
    actionKey: "bought",
    symbol: "FB",
    date: "Nov 23, 01:00 PM",
    amount: "$2,567.88",
    categoryKey: "finance",
    status: "Success",
  },
  {
    image: "/images/brand/brand-10.svg",
    actionKey: "sell",
    symbol: "AMZN",
    date: "Nov 23, 01:00 PM",
    amount: "$2,567.88",
    categoryKey: "finance",
    status: "Failed",
  },
];

export default function LatestTransactions() {
  const { t } = useTranslation();

  const getStatusBadge = (status: Transaction["status"]) => {
    switch (status) {
      case "Success":
        return {
          color: "success" as const,
          text: t("stocks.latestTransactions.statuses.success"),
        };
      case "Pending":
        return {
          color: "warning" as const,
          text: t("stocks.latestTransactions.statuses.pending"),
        };
      case "Failed":
        return {
          color: "error" as const,
          text: t("stocks.latestTransactions.statuses.failed"),
        };
    }
  };

  return (
    <div className="rounded-2xl border border-gray-200 bg-white pt-4 dark:border-gray-800 dark:bg-white/3">
      <div className="mb-4 flex flex-col gap-2 px-5 sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <div>
          <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">
            {t("stocks.latestTransactions.title")}
          </h3>
        </div>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <form>
            <div className="relative">
              <span className="pointer-events-none absolute start-4 top-1/2 -translate-y-1/2">
                <svg
                  className="fill-gray-500 dark:fill-gray-400"
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
                    fill=""
                  />
                </svg>
              </span>
              <input
                type="text"
                placeholder={t("stocks.latestTransactions.searchPlaceholder")}
                className="dark:bg-dark-900 h-[42px] w-full rounded-lg border border-gray-300 bg-transparent py-2.5 ps-[42px] pe-4 text-sm text-gray-800 shadow-theme-xs placeholder:text-gray-400 focus:border-brand-300 focus:ring-3 focus:ring-brand-500/10 focus:outline-hidden xl:w-[300px] dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30 dark:focus:border-brand-800"
              />
            </div>
          </form>
        </div>
      </div>

      <div className="overflow-hidden">
        <div className="custom-scrollbar max-w-full overflow-x-auto px-5 sm:px-6">
          <Table>
            {/* <!-- table header start --> */}
            <TableHeader className="border-y border-gray-200 dark:border-gray-800">
              <TableRow>
                <TableCell
                  isHeader
                  className="py-3 text-start text-theme-sm font-normal whitespace-nowrap text-gray-500 dark:text-gray-400"
                >
                  {t("stocks.latestTransactions.table.name")}
                </TableCell>
                <TableCell
                  isHeader
                  className="px-4 py-3 text-start text-theme-sm font-normal whitespace-nowrap text-gray-500 dark:text-gray-400"
                >
                  {t("stocks.latestTransactions.table.date")}
                </TableCell>
                <TableCell
                  isHeader
                  className="px-4 py-3 text-start text-theme-sm font-normal whitespace-nowrap text-gray-500 dark:text-gray-400"
                >
                  {t("stocks.latestTransactions.table.price")}
                </TableCell>
                <TableCell
                  isHeader
                  className="px-4 py-3 text-start text-theme-sm font-normal whitespace-nowrap text-gray-500 dark:text-gray-400"
                >
                  {t("stocks.latestTransactions.table.category")}
                </TableCell>
                <TableCell
                  isHeader
                  className="px-4 py-3 text-start text-theme-sm font-normal whitespace-nowrap text-gray-500 dark:text-gray-400"
                >
                  {t("stocks.latestTransactions.table.status")}
                </TableCell>
              </TableRow>
            </TableHeader>
            {/* <!-- table header end --> */}
            <TableBody className="divide-y divide-gray-100 dark:divide-gray-800">
              {transactionData.map((item, i) => {
                const statusBadge = getStatusBadge(item.status);
                return (
                  <TableRow key={i + 1}>
                    <TableCell className="py-4 whitespace-nowrap dark:border-gray-800">
                      <div className="flex items-center gap-3">
                        <div className="h-8 w-8">
                          <img src={item.image} alt="brand" />
                        </div>
                        <div>
                          <span className="block text-theme-sm font-medium text-gray-700 dark:text-gray-400">
                            {t(
                              `stocks.latestTransactions.actions.${item.actionKey}`,
                              { symbol: item.symbol },
                            )}
                          </span>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell className="px-4 py-4 text-theme-sm whitespace-nowrap text-gray-700 dark:text-gray-400">
                      {item.date}
                    </TableCell>
                    <TableCell className="px-4 py-4 text-theme-sm whitespace-nowrap text-gray-700 dark:text-gray-400">
                      {item.amount}
                    </TableCell>
                    <TableCell className="px-4 py-4 text-theme-sm whitespace-nowrap text-gray-700 dark:text-gray-400">
                      {t(
                        `stocks.latestTransactions.categories.${item.categoryKey}`,
                      )}
                    </TableCell>
                    <TableCell className="px-4 py-4 text-theme-sm whitespace-nowrap text-gray-700 dark:text-gray-400">
                      <Badge size="sm" color={statusBadge.color}>
                        {statusBadge.text}
                      </Badge>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      </div>
    </div>
  );
}
