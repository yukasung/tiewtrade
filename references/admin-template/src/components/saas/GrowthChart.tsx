import type { ApexOptions } from "apexcharts";
import Chart from "react-apexcharts";
import { useTranslation } from "react-i18next";

export default function GrowthChart() {
  const { t } = useTranslation();

  const growthSeries = [
    {
      name: "Revenue",
      data: [12500, 14000, 15500, 14800, 16200, 17500, 18200],
    },
  ];

  const growthOptions: ApexOptions = {
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
    colors: ["#10b981"],
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
        formatter: (value) => "$" + value.toLocaleString(),
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
            {t("saas.userGrowth.title")}
          </h3>
          <p className="mt-1 text-theme-sm text-gray-500 dark:text-gray-400">
            {t("saas.userGrowth.subtitle")}
          </p>
        </div>
      </div>
      <div className="flex justify-between">
        <div>
          <h3 className="text-title-xs font-semibold text-gray-800 dark:text-white/90">
            3,768
          </h3>
          <p className="mt-1 text-theme-xs text-gray-500 dark:text-gray-400">
            <span className="me-1 inline-block text-success-600">+3.85%</span>
            {t("saas.userGrowth.thanLastWeek")}
          </p>
        </div>
        <div className="max-w-full">
          <div id="chartTwentyTwo">
            <Chart
              className="h-12 w-24"
              options={growthOptions}
              series={growthSeries}
              type="area"
            />
          </div>
        </div>
      </div>
    </div>
  );
}
