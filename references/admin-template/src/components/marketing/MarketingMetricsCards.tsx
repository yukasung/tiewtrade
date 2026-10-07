import { DollarLineIcon, GroupIcon, ShootingStarIcon } from "@/icons";
import { useTranslation } from "react-i18next";

export default function MarketingMetricsCards() {
  const { t } = useTranslation();

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:gap-6 xl:grid-cols-3">
      {/* <!-- Metric Item Start --> */}
      <div className="rounded-2xl border border-gray-200 bg-white p-5 md:p-6 dark:border-gray-800 dark:bg-white/3">
        <div className="mb-6 flex h-[52px] w-[52px] items-center justify-center rounded-xl bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-white/[0.90]">
          <ShootingStarIcon className="size-6" />
        </div>

        <p className="text-theme-sm text-gray-500 dark:text-gray-400">
          {t("marketing.metrics.avgClientRating")}
        </p>

        <div className="mt-3 flex items-end justify-between">
          <div>
            <h4 className="text-title-sm font-bold text-gray-800 dark:text-white/90">
              7.8/10
            </h4>
          </div>

          <div className="flex items-center gap-1">
            <span className="flex items-center gap-1 rounded-full bg-success-50 px-2 py-0.5 text-theme-xs font-medium text-success-600 dark:bg-success-500/15 dark:text-success-500">
              +20%
            </span>

            <span className="text-theme-xs text-gray-500 dark:text-gray-400">
              {t("marketing.metrics.vsLastMonth")}
            </span>
          </div>
        </div>
      </div>
      {/* <!-- Metric Item End --> */}

      {/* <!-- Metric Item Start --> */}
      <div className="rounded-2xl border border-gray-200 bg-white p-5 md:p-6 dark:border-gray-800 dark:bg-white/3">
        <div className="mb-6 flex h-[52px] w-[52px] items-center justify-center rounded-xl bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-white/[0.90]">
          <GroupIcon className="size-6" />
        </div>

        <p className="text-theme-sm text-gray-500 dark:text-gray-400">
          {t("marketing.metrics.instagramFollowers")}
        </p>

        <div className="mt-3 flex items-end justify-between">
          <div>
            <h4 className="text-title-sm font-bold text-gray-800 dark:text-white/90">
              5,934
            </h4>
          </div>

          <div className="flex items-center gap-1">
            <span className="flex items-center gap-1 rounded-full bg-error-50 px-2 py-0.5 text-theme-xs font-medium text-error-600 dark:bg-error-500/15 dark:text-error-500">
              -3.59%
            </span>

            <span className="text-theme-xs text-gray-500 dark:text-gray-400">
              {t("marketing.metrics.vsLastMonth")}
            </span>
          </div>
        </div>
      </div>
      {/* <!-- Metric Item End --> */}

      {/* <!-- Metric Item Start --> */}
      <div className="rounded-2xl border border-gray-200 bg-white p-5 md:p-6 dark:border-gray-800 dark:bg-white/3">
        <div className="mb-6 flex h-[52px] w-[52px] items-center justify-center rounded-xl bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-white/[0.90]">
          <DollarLineIcon className="size-6" />
        </div>
        <p className="text-theme-sm text-gray-500 dark:text-gray-400">
          {t("marketing.metrics.totalRevenue")}
        </p>

        <div className="mt-3 flex items-end justify-between">
          <div>
            <h4 className="text-title-sm font-bold text-gray-800 dark:text-white/90">
              $9,758
            </h4>
          </div>

          <div className="flex items-center gap-1">
            <span className="flex items-center gap-1 rounded-full bg-success-50 px-2 py-0.5 text-theme-xs font-medium text-success-600 dark:bg-success-500/15 dark:text-success-500">
              +15%
            </span>

            <span className="text-theme-xs text-gray-500 dark:text-gray-400">
              {t("marketing.metrics.vsLastMonth")}
            </span>
          </div>
        </div>
      </div>
      {/* <!-- Metric Item End --> */}
    </div>
  );
}
