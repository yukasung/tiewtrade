import type { ApexOptions } from "apexcharts";
import Chart from "react-apexcharts";
import { useTranslation } from "react-i18next";

export default function DeliveryStatisticsChart() {
  const { t } = useTranslation();

  const options: ApexOptions = {
    chart: {
      type: "bar",
      height: 265,
      toolbar: { show: false },
      fontFamily: "Outfit, sans-serif",
    },
    plotOptions: {
      bar: {
        horizontal: false,
        columnWidth: "50%",
        borderRadius: 4,
        borderRadiusApplication: "end",
      },
    },
    dataLabels: {
      enabled: false,
    },
    stroke: {
      show: true,
      width: 4,
      colors: ["transparent"],
    },
    colors: ["#C2D6FF", "#465FFF"],
    xaxis: {
      categories: [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
      ],
      axisTicks: { show: false },
      axisBorder: { show: false },
    },
    yaxis: {
      labels: {
        formatter: (val: number) => `${val}%`,
        style: { fontSize: "12px", colors: "#344054" },
      },
      max: 100,
    },
    fill: {
      opacity: 1,
    },
    tooltip: {
      y: {
        formatter: (val: number) => `${val}%`,
      },
    },
    legend: { show: false },
    grid: {
      borderColor: "#F2F4F7",
      strokeDashArray: 0,
    },
  };

  const series = [
    {
      name: "2023",
      data: [80, 60, 70, 40, 65, 45, 48, 55, 58, 50, 67, 75],
    },
    {
      name: "2024",
      data: [90, 50, 65, 25, 78, 68, 75, 90, 30, 70, 90, 95],
    },
  ];

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-white/3">
      <div className="flex items-center justify-between gap-5">
        <div>
          <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">
            {t("logistics.deliveryStatistics.title")}
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {t("logistics.deliveryStatistics.subtitle")}
          </p>
        </div>
        <div>
          <div className="relative z-20 bg-transparent">
            <select className="h-11 w-full appearance-none rounded-lg border border-gray-300 bg-transparent bg-none px-4 py-2.5 pe-11 text-sm text-gray-800 shadow-theme-xs placeholder:text-gray-400 focus:border-brand-300 focus:ring-3 focus:ring-brand-500/10 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30 dark:focus:border-brand-800">
              <option
                value=""
                className="text-gray-700 dark:bg-gray-900 dark:text-gray-400"
              >
                {t("logistics.deliveryStatistics.monthly")}
              </option>

              <option
                value=""
                className="text-gray-700 dark:bg-gray-900 dark:text-gray-400"
              >
                {t("logistics.deliveryStatistics.yearly")}
              </option>
            </select>
            <span className="pointer-events-none absolute inset-e-4 top-1/2 z-30 -translate-y-1/2 text-gray-500 dark:text-gray-400">
              <svg
                className="stroke-current"
                width="20"
                height="20"
                viewBox="0 0 20 20"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d="M4.79175 7.396L10.0001 12.6043L15.2084 7.396"
                  stroke=""
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </span>
          </div>
        </div>
      </div>

      <div>
        <div className="flex items-center gap-5 pt-5">
          <div className="flex items-center gap-1.5">
            <div className="h-2.5 w-2.5 rounded-full bg-brand-200"></div>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {t("logistics.deliveryStatistics.shipment")}
            </p>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="h-2.5 w-2.5 rounded-full bg-brand-500"></div>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {t("logistics.deliveryStatistics.delivery")}
            </p>
          </div>
        </div>
        <div id="chartTwentyThree" className="h-66.25 w-full">
          <Chart options={options} series={series} type="bar" height={265} />
        </div>
      </div>
    </div>
  );
}
