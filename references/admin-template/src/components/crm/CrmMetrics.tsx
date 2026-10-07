import Badge from "@/components/ui/badge/Badge";
import { useTranslation } from "react-i18next";

export default function CrmMetrics() {
  const { t } = useTranslation();

  const mockData = [
    {
      id: 1,
      title: t("crm.metrics.activeDeal"),
      value: "$120,369",
      change: "+20%",
      direction: "up",
      comparisonText: t("crm.metrics.lastMonth"),
    },
    {
      id: 2,
      title: t("crm.metrics.revenueTotal"),
      value: "$234,210",
      change: "+9.0%",
      direction: "up",
      comparisonText: t("crm.metrics.lastMonth"),
    },
    {
      id: 3,
      title: t("crm.metrics.closedDeals"),
      value: "874",
      change: "-4.5%",
      direction: "down",
      comparisonText: t("crm.metrics.lastMonth"),
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:gap-6 xl:grid-cols-3">
      {/* <!-- Metric Item Start --> */}
      {mockData.map((item) => (
        <div
          key={item.id}
          className="rounded-2xl border border-gray-200 bg-white p-5 md:p-6 dark:border-gray-800 dark:bg-white/3"
        >
          <h4 className="text-title-sm font-bold text-gray-800 dark:text-white/90">
            {item.value}
          </h4>

          <div className="mt-4 flex items-end justify-between sm:mt-5">
            <div>
              <p className="text-theme-sm text-gray-700 dark:text-gray-400">
                {item.title}
              </p>
            </div>

            <div className="flex items-center gap-1">
              <Badge
                size="sm"
                color={
                  item.direction === "up"
                    ? "success"
                    : item.direction === "down"
                      ? "error"
                      : "warning"
                }
              >
                {item.change}
              </Badge>
              <span className="text-theme-xs text-gray-500 dark:text-gray-400">
                {item.comparisonText}
              </span>
            </div>
          </div>
        </div>
      ))}
      {/* <!-- Metric Item End --> */}
    </div>
  );
}
