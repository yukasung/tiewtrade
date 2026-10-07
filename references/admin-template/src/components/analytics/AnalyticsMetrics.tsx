import React from "react";
import { useTranslation } from "react-i18next";
import Badge from "../ui/badge/Badge";

interface MetricItem {
  id: number;
  titleKey:
    "uniqueVisitors" | "totalPageviews" | "bounceRate" | "visitDuration";
  value: string;
  change: string;
  direction: "up" | "down";
}

const mockData: MetricItem[] = [
  {
    id: 1,
    titleKey: "uniqueVisitors",
    value: "24.7K",
    change: "+20%",
    direction: "up",
  },
  {
    id: 2,
    titleKey: "totalPageviews",
    value: "55.9K",
    change: "+4%",
    direction: "up",
  },
  {
    id: 3,
    titleKey: "bounceRate",
    value: "54%",
    change: "-1.59%",
    direction: "down",
  },
  {
    id: 4,
    titleKey: "visitDuration",
    value: "2m 56s",
    change: "+7%",
    direction: "up",
  },
];

const AnalyticsMetrics: React.FC = () => {
  const { t } = useTranslation();

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:gap-6 xl:grid-cols-4">
      {/* <!-- Metric Item Start --> */}
      {mockData.map((item) => (
        <div
          key={item.id}
          className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/3"
        >
          <p className="text-theme-sm text-gray-500 dark:text-gray-400">
            {t(`analytics.metrics.${item.titleKey}`)}
          </p>
          <div className="mt-3 flex items-end justify-between">
            <div>
              <h4 className="text-2xl font-bold text-gray-800 dark:text-white/90">
                {item.value}
              </h4>
            </div>
            <div className="flex items-center gap-1">
              <Badge
                color={
                  item.direction === "up"
                    ? "success"
                    : item.direction === "down"
                      ? "error"
                      : "warning"
                }
              >
                <span className="text-xs"> {item.change}</span>
              </Badge>
              <span className="text-theme-xs text-gray-500 dark:text-gray-400">
                {t("analytics.metrics.vsLastMonth")}
              </span>
            </div>
          </div>
        </div>
      ))}

      {/* <!-- Metric Item End --> */}
    </div>
  );
};

export default AnalyticsMetrics;
