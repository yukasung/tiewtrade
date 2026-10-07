"use client";
import type { ApexAxisChartSeries, ApexOptions } from "apexcharts";
import { useState } from "react";
import Chart from "react-apexcharts";
import { useTranslation } from "react-i18next";

export default function UserRevenueAndStatistics() {
  const { t } = useTranslation();
  const [selected, setSelected] = useState("monthly");

  const getButtonClass = (value: string) =>
    `text-theme-sm h-10 rounded-md px-3 py-2.5 font-medium transition-colors 
    ${
      selected === value
        ? "shadow-theme-xs text-gray-900 dark:text-white bg-white dark:bg-gray-800"
        : "text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:bg-gray-800 dark:hover:text-white"
    }`;

  const series: ApexAxisChartSeries = [
    {
      name: "Users",
      data: [
        23000, 24500, 22500, 24800, 23200, 25240, 24600, 27000, 25800, 28500,
        27200, 31000,
      ],
    },
    {
      name: "Revenue",
      data: [
        13000, 14300, 12600, 14800, 13400, 15500, 14700, 17000, 16000, 18500,
        17200, 20000,
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
      },
      itemMargin: {
        horizontal: 10,
      },
    },
    colors: ["#465FFF", "#9CB9FF"],
    chart: {
      fontFamily: "Outfit, sans-serif",
      type: "area",
      toolbar: {
        show: false,
      },
      zoom: {
        enabled: false,
      },
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
      curve: "straight",
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
          formatter: (val: number): string => val.toLocaleString(),
        },
        {
          formatter: (val: number): string =>
            "$" + (val / 1000).toFixed(2) + "K",
        },
      ],
      marker: {
        show: true,
      },
    },
    xaxis: {
      type: "category",
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
      axisBorder: { show: false },
      axisTicks: { show: false },
      tooltip: { enabled: false },
      crosshairs: {
        show: true,
        position: "back",
        stroke: {
          color: "#D0D5DD",
          width: 1,
          dashArray: 4,
        },
      },
    },
    yaxis: {
      min: 0,
      max: 35000,
      tickAmount: 7,
      labels: {
        formatter: (val: number): string => {
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

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-white/3">
      {/* Header */}
      <div className="mb-8 flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">
            {t("aiDashboard.userRevenue.title")}
          </h3>
          <p className="mt-1 text-theme-sm text-gray-500 dark:text-gray-400">
            {t("aiDashboard.userRevenue.subtitle")}
          </p>
        </div>

        {/* Toggle Buttons */}
        <div className="inline-flex h-11 w-fit items-center gap-0.5 rounded-lg bg-gray-100 p-0.5 dark:bg-gray-900">
          <button
            onClick={() => setSelected("monthly")}
            className={getButtonClass("monthly")}
          >
            {t("aiDashboard.userRevenue.monthly")}
          </button>

          <button
            onClick={() => setSelected("quarterly")}
            className={getButtonClass("quarterly")}
          >
            {t("aiDashboard.userRevenue.quarterly")}
          </button>

          <button
            onClick={() => setSelected("annually")}
            className={getButtonClass("annually")}
          >
            {t("aiDashboard.userRevenue.annually")}
          </button>
        </div>
      </div>

      {/* Chart Area */}
      <div className="custom-scrollbar max-w-full overflow-x-auto">
        <div className="-ms-4 min-w-0 flex-shrink-0 ps-2 xl:min-w-full">
          <div>
            <Chart options={options} series={series} type="area" height={450} />
          </div>
        </div>
      </div>
    </div>
  );
}

