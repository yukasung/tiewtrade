import type { ApexOptions } from "apexcharts";
import Chart from "react-apexcharts";
import { useTranslation } from "react-i18next";

export default function ChurnRateChart() {
  const { t } = useTranslation();

  const churnSeries = [
    {
      name: "Churn Rate",
      data: [4.5, 4.2, 4.6, 4.3, 4.1, 4.2, 4.26],
    },
  ];

  const churnOptions: ApexOptions = {
    chart: {
      type: "area",
      height: 60,
      sparkline: {
        enabled: true,
      },
      animations: {
        enabled: true,
        speed: 800,
      },
      toolbar: {
        show: false,
      },
    },
    colors: ["#ef4444"],
    stroke: {
      curve: "smooth",
      width: 2,
    },
    fill: {
      type: "gradient",
      gradient: {
        shadeIntensity: 1,
        opacityFrom: 0.6,
        opacityTo: 0.1,
        stops: [0, 100],
      },
    },
    tooltip: {
      fixed: {
        enabled: false,
      },
      x: {
        show: false,
      },
      y: {
        formatter: (value) => value.toFixed(2) + "%",
      },
      marker: {
        show: false,
      },
    },
  };

  return (
    <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-white/3">
      <div className="mb-6 flex justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">
            {t("saas.churnRate.title")}
          </h3>
          <p className="mt-1 text-theme-sm text-gray-500 dark:text-gray-400">
            {t("saas.churnRate.subtitle")}
          </p>
        </div>
      </div>
      <div className="flex justify-between">
        <div>
          <h3 className="text-title-xs font-semibold text-gray-800 dark:text-white/90">
            4.26%
          </h3>
          <p className="mt-1 text-theme-xs text-gray-500 dark:text-gray-400">
            <span className="me-1 inline-block text-error-500">0.31%</span>
            {t("saas.churnRate.thanLastWeek")}
          </p>
        </div>
        <div className="max-w-full">
          <div id="chartTwentyOne">
            <Chart
              className="h-12 w-24"
              options={churnOptions}
              series={churnSeries}
              type="area"
            />
          </div>
        </div>
      </div>
    </div>
  );
}
