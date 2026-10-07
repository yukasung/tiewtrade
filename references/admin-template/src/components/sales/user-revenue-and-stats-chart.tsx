"use client";

import { useState } from "react";
import Chart from "react-apexcharts";
import type { ApexOptions } from "apexcharts";
import { useTranslation } from "react-i18next";

type ViewType = "daily" | "weekly" | "monthly";

export default function SalesStatistics() {
  const { t } = useTranslation();
  const [selected, setSelected] = useState<ViewType>("monthly");

  const series: ApexOptions["series"] = [
    {
      name: "Online Sales",
      data: [
        [new Date("2026-01-01").getTime(), 13000],
        [new Date("2026-02-01").getTime(), 13800],
        [new Date("2026-03-01").getTime(), 13200],
        [new Date("2026-04-01").getTime(), 14200],
        [new Date("2026-05-01").getTime(), 13900],
        [new Date("2026-06-01").getTime(), 15240],
        [new Date("2026-07-01").getTime(), 15600],
        [new Date("2026-08-01").getTime(), 17000],
        [new Date("2026-09-01").getTime(), 16500],
        [new Date("2026-10-01").getTime(), 17500],
        [new Date("2026-11-01").getTime(), 17200],
        [new Date("2026-12-01").getTime(), 18000],
      ],
    },
    {
      name: "Offline Sales",
      data: [
        [new Date("2026-01-01").getTime(), 8500],
        [new Date("2026-02-01").getTime(), 9200],
        [new Date("2026-03-01").getTime(), 8800],
        [new Date("2026-04-01").getTime(), 9800],
        [new Date("2026-05-01").getTime(), 9400],
        [new Date("2026-06-01").getTime(), 10490],
        [new Date("2026-07-01").getTime(), 10800],
        [new Date("2026-08-01").getTime(), 11500],
        [new Date("2026-09-01").getTime(), 10800],
        [new Date("2026-10-01").getTime(), 11800],
        [new Date("2026-11-01").getTime(), 11200],
        [new Date("2026-12-01").getTime(), 11800],
      ],
    },
  ];

  const options: ApexOptions = {
    legend: {
      show: true,
      position: "top",
      horizontalAlign: "left",
      markers: {
        size: 5,
        shape: "circle",
        strokeWidth: 0,
      },
      itemMargin: {
        horizontal: 10,
      },
    },

    colors: ["#465FFF", "#9CB9FF"],

    chart: {
      fontFamily: "Outfit, sans-serif",
      type: "area",
      height: 250,
      toolbar: { show: false },
      zoom: { enabled: false },
    },

    fill: {
      type: "gradient",
      gradient: {
        shadeIntensity: 1,
        opacityFrom: 0.45,
        opacityTo: 0,
        stops: [0, 100],
      },
    },

    stroke: {
      curve: "smooth",
      width: [2, 2],
    },

    markers: {
      size: 0,
    },

    grid: {
      xaxis: {
        lines: { show: false },
      },
      yaxis: {
        lines: { show: true },
      },
    },

    dataLabels: {
      enabled: false,
    },

    tooltip: {
      x: {
        format: "MMM dd, yyyy",
      },
      y: [
        {
          formatter: (val: number) => val.toLocaleString(),
        },
        {
          formatter: (val: number) => "$" + val.toLocaleString(),
        },
      ],
    },

    xaxis: {
      type: "datetime",
      axisBorder: { show: false },
      axisTicks: { show: false },
      tooltip: { enabled: false },
      labels: {
        format: "MMM",
        datetimeUTC: false,
      },

      // ✅ fixed placement
      crosshairs: {
        show: true,
        position: "back",
        stroke: {
          color: "#465FFF",
          width: 1,
          dashArray: 4,
        },
      },
    },

    yaxis: {
      min: 0,
      max: 20000,
      tickAmount: 4,
      labels: {
        formatter: (val: number) => {
          if (val === 0) return "0";
          return (val / 1000).toFixed(0) + "K";
        },
      },
      title: {
        style: {
          fontSize: "0px",
        },
      },
    },
  };

  const getBtnClass = (value: ViewType) =>
    `text-theme-sm h-10 rounded-md px-3 py-2.5 font-medium transition-colors ${
      selected === value
        ? "shadow-theme-xs text-gray-900 dark:text-white bg-white dark:bg-gray-800"
        : "text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:bg-gray-800 dark:hover:text-white"
    }`;

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-white/3">
      {/* Header */}
      <div className="mb-8 flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-lg font-medium text-gray-800 dark:text-white/90">
            {t("sales.userRevenueStats.title")}
          </h3>
          <p className="text-theme-sm mt-1 text-gray-500 dark:text-gray-400">
            {t("sales.userRevenueStats.subtitle")}
          </p>
        </div>

        {/* Toggle */}
        <div className="inline-flex h-11 w-fit items-center gap-0.5 rounded-lg bg-gray-100 p-0.5 dark:bg-gray-900">
          <button
            onClick={() => setSelected("daily")}
            className={getBtnClass("daily")}
          >
            {t("sales.userRevenueStats.daily")}
          </button>
          <button
            onClick={() => setSelected("weekly")}
            className={getBtnClass("weekly")}
          >
            {t("sales.userRevenueStats.weekly")}
          </button>
          <button
            onClick={() => setSelected("monthly")}
            className={getBtnClass("monthly")}
          >
            {t("sales.userRevenueStats.monthly")}
          </button>
        </div>
      </div>

      {/* Chart */}
      <div className="custom-scrollbar max-w-full overflow-x-auto">
        <div className="min-w-[1000px] xl:min-w-full">
          <Chart options={options} series={series} type="area" height={250} />
        </div>
      </div>
    </div>
  );
}
