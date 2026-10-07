import { useTranslation } from "react-i18next";
import {
  DollarIcon,
  FilesIcon,
  MultiUserIcon,
  UserMoneyIcon,
} from "../../icons";

function StatChangeIcon({ type }: { type: "up" | "down" }) {
  return type === "up" ? (
    <svg
      width={16}
      height={16}
      viewBox="0 0 16 16"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M7.9974 2.66602L7.9974 13.3336M4 6.66334L7.99987 2.66602L12 6.66334"
        stroke="#039855"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  ) : (
    <svg
      width={16}
      height={16}
      viewBox="0 0 16 16"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M7.9974 13.3339L7.9974 2.66634M4 9.33652L7.99987 13.3338L12 9.33652"
        stroke="#D92D20"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function AiStats() {
  const { t } = useTranslation();

  const statsData = [
    {
      label: t("aiDashboard.stats.users"),
      value: "10,590",
      icon: MultiUserIcon,
      iconClass: "size-6 text-brand-400",
      change: "+3.52%",
      changeType: "up",
      changeColor: "success",
    },
    {
      label: t("aiDashboard.stats.projects"),
      value: "15,682",
      icon: FilesIcon,
      iconClass: "size-6",
      change: "+3.52%",
      changeType: "up",
      changeColor: "success",
    },
    {
      label: t("aiDashboard.stats.revenue"),
      value: "$90,369",
      icon: DollarIcon,
      iconClass: "size-6 text-success-500",
      change: "+14.8%",
      changeType: "up",
      changeColor: "success",
    },
    {
      label: t("aiDashboard.stats.paidUsers"),
      value: "520",
      icon: UserMoneyIcon,
      iconClass: "size-6",
      change: "-9.05%",
      changeType: "down",
      changeColor: "error",
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 xl:grid-cols-4">
      {statsData.map((stat, index) => {
        const Icon = stat.icon;
        return (
          <div
            key={index}
            className="flex flex-col rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/3"
          >
            <div className="mb-4 flex items-center justify-between">
              <span className="text-sm font-medium text-gray-500 dark:text-gray-400">
                {stat.label}
              </span>
              <Icon className={stat.iconClass} />
            </div>
            <h2 className="mb-2 text-3xl font-semibold text-gray-800 dark:text-white/90">
              {stat.value}
            </h2>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-500 dark:text-gray-400">
                {t("aiDashboard.stats.last30Days")}
              </span>
              <span
                className={`flex items-center text-sm font-medium text-${stat.changeColor}-600 dark:text-${stat.changeColor}-500`}
              >
                <StatChangeIcon type={stat.changeType as "up" | "down"} />
                {stat.change}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

