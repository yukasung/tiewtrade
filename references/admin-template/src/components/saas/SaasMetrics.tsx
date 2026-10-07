import { useTranslation } from "react-i18next";

export default function SaasMetrics() {
  const { t } = useTranslation();

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/3">
      <div className="mb-8 flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h3 className="text-lg font-semibold text-gray-800 dark:text-white">
            {t("saas.metrics.overview")}
          </h3>
        </div>
      </div>
      <div className="grid rounded-2xl border border-gray-200 bg-white sm:grid-cols-2 xl:grid-cols-4 dark:border-gray-800 dark:bg-gray-900">
        <div className="border-b border-gray-200 px-6 py-5 sm:border-e xl:border-b-0 dark:border-gray-800">
          <span className="text-sm text-gray-500 dark:text-gray-400">
            {t("saas.metrics.totalRevenue")}
          </span>
          <div className="mt-2 flex items-end gap-3">
            <h4 className="text-title-xs font-bold text-gray-800 sm:text-title-sm dark:text-white/90">
              $200,45.87
            </h4>
            <div>
              <span className="flex items-center gap-1 rounded-full bg-success-50 py-0.5 ps-2 pe-2.5 text-sm font-medium text-success-600 dark:bg-success-500/15 dark:text-success-500">
                +2.5%
              </span>
            </div>
          </div>
        </div>
        <div className="border-b border-gray-200 px-6 py-5 xl:border-e xl:border-b-0 dark:border-gray-800">
          <span className="text-sm text-gray-500 dark:text-gray-400">
            {t("saas.metrics.activeUsers")}
          </span>
          <div className="mt-2 flex items-end gap-3">
            <h4 className="text-title-xs font-bold text-gray-800 sm:text-title-sm dark:text-white/90">
              9,528
            </h4>
            <div>
              <span className="flex items-center gap-1 rounded-full bg-success-50 py-0.5 ps-2 pe-2.5 text-sm font-medium text-success-600 dark:bg-success-500/15 dark:text-success-500">
                + 9.5%
              </span>
            </div>
          </div>
        </div>
        <div className="border-b border-gray-200 px-6 py-5 sm:border-e sm:border-b-0 dark:border-gray-800">
          <div>
            <span className="text-sm text-gray-500 dark:text-gray-400">
              {t("saas.metrics.clv")}
            </span>
            <div className="mt-2 flex items-end gap-3">
              <h4 className="text-title-xs font-bold text-gray-800 sm:text-title-sm dark:text-white/90">
                $849.54
              </h4>
              <div>
                <span className="flex items-center gap-1 rounded-full bg-error-50 py-0.5 ps-2 pe-2.5 text-sm font-medium text-error-600 dark:bg-success-500/15 dark:text-error-500">
                  -1.6%
                </span>
              </div>
            </div>
          </div>
        </div>
        <div className="px-6 py-5">
          <span className="text-sm text-gray-500 dark:text-gray-400">
            {t("saas.metrics.cac")}
          </span>
          <div className="mt-2 flex items-end gap-3">
            <h4 className="text-title-xs font-bold text-gray-800 sm:text-title-sm dark:text-white/90">
              9,528
            </h4>
            <div>
              <span className="flex items-center gap-1 rounded-full bg-success-50 py-0.5 ps-2 pe-2.5 text-sm font-medium text-success-600 dark:bg-success-500/15 dark:text-success-500">
                +3.5%
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
