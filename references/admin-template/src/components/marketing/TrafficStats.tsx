import ChartTab from "@/components/common/ChartTab";
import type { ApexOptions } from "apexcharts";
import Chart from "react-apexcharts";

import { Dropdown } from "@/components/ui/dropdown/Dropdown";
import { DropdownItem } from "@/components/ui/dropdown/DropdownItem";
import { MoreDotIcon } from "@/icons";
import { useState } from "react";
import { useTranslation } from "react-i18next";

export default function TrafficStats() {
  const { t } = useTranslation();

  const optionsOne: ApexOptions = {
    grid: {
      show: false,
    },
    colors: ["#12B76A"],
    fill: {
      gradient: {
        opacityFrom: 0.55,
        opacityTo: 0,
      },
    },
    legend: {
      show: false,
    },
    chart: {
      fontFamily: "Outfit, sans-serif",
      height: 70,
      type: "area",
      parentHeightOffset: 0,

      toolbar: {
        show: false,
      },
    },
    tooltip: {
      enabled: false,
    },
    dataLabels: {
      enabled: false,
    },
    stroke: {
      curve: "smooth",
      width: 1,
    },
    xaxis: {
      type: "datetime",
      categories: [
        "2018-09-19T00:00:00.000Z",
        "2018-09-19T01:30:00.000Z",
        "2018-09-19T02:30:00.000Z",
        "2018-09-19T03:30:00.000Z",
        "2018-09-19T04:30:00.000Z",
        "2018-09-19T05:30:00.000Z",
        "2018-09-19T06:30:00.000Z",
        "2018-09-19T07:30:00.000Z",
        "2018-09-19T08:30:00.000Z",
        "2018-09-19T09:30:00.000Z",
        "2018-09-19T10:30:00.000Z",
        "2018-09-19T11:30:00.000Z",
        "2018-09-19T12:30:00.000Z",
      ],
      labels: {
        show: false,
      },
      axisBorder: {
        show: false,
      },
      axisTicks: {
        show: false,
      },
      tooltip: {
        enabled: false,
      },
    },
    yaxis: {
      labels: {
        show: false,
      },
    },
  };

  const series = [
    {
      name: t("marketing.trafficStats.newSales"),
      data: [300, 350, 310, 370, 248, 187, 295, 191, 269, 201, 185, 252, 151],
    },
  ];

  const [isOpen, setIsOpen] = useState(false);

  function toggleDropdown() {
    setIsOpen(!isOpen);
  }

  function closeDropdown() {
    setIsOpen(false);
  }
  return (
    <div className="rounded-2xl border border-gray-200 bg-white px-5 pt-5 pb-1 sm:px-6 sm:pt-6 dark:border-gray-800 dark:bg-white/3">
      <div className="mb-6 flex items-center justify-between gap-2">
        <div>
          <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">
            {t("marketing.trafficStats.title")}
          </h3>
        </div>
        <div className="relative inline-block">
          <button className="dropdown-toggle" onClick={toggleDropdown}>
            <MoreDotIcon className="size-6 text-gray-400 hover:text-gray-700 dark:hover:text-gray-300" />
          </button>
          <Dropdown
            isOpen={isOpen}
            onClose={closeDropdown}
            className="w-40 p-2"
          >
            <DropdownItem
              onItemClick={closeDropdown}
              className="flex w-full rounded-lg text-start font-normal text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-white/5 dark:hover:text-gray-300"
            >
              {t("common.viewMore")}
            </DropdownItem>
            <DropdownItem
              onItemClick={closeDropdown}
              className="flex w-full rounded-lg text-start font-normal text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-white/5 dark:hover:text-gray-300"
            >
              {t("common.delete")}
            </DropdownItem>
          </Dropdown>
        </div>
      </div>
      <ChartTab />
      <div>
        {/* <!-- Stats item --> */}
        <div className="flex items-end justify-between py-5">
          <div>
            <p className="mb-1 text-theme-sm text-gray-500 dark:text-gray-400">
              {t("marketing.trafficStats.newSubscribers")}
            </p>
            <h4 className="mb-1 text-2xl font-semibold text-gray-800 dark:text-white/90">
              567K
            </h4>
            <span className="flex items-center gap-1.5">
              <span className="text-success-600"> +3.85% </span>
              <span className="text-theme-xs text-gray-500 dark:text-gray-400">
                {t("marketing.trafficStats.thenLastWeek")}
              </span>
            </span>
          </div>
          <div className="w-full max-w-[150px]">
            <div className="chartNine chartNine-01">
              <Chart
                options={optionsOne}
                series={series}
                type="area"
                height={70}
              />
            </div>
          </div>
        </div>
        {/* <!-- Stats item --> */}
        <div className="flex items-end justify-between border-y border-gray-100 py-5 dark:border-gray-800">
          <div>
            <p className="mb-1 text-theme-sm text-gray-500 dark:text-gray-400">
              {t("marketing.trafficStats.conversionRate")}
            </p>
            <h4 className="mb-1 text-2xl font-semibold text-gray-800 dark:text-white/90">
              276K
            </h4>
            <span className="flex items-center gap-1.5">
              <span className="text-error-600"> -5.39% </span>
              <span className="text-theme-xs text-gray-500 dark:text-gray-400">
                {t("marketing.trafficStats.thenLastWeek")}
              </span>
            </span>
          </div>

          <div className="w-full max-w-[150px]">
            <div className="chartTen">
              <Chart
                options={optionsOne}
                series={series}
                type="area"
                height={70}
              />
            </div>
          </div>
        </div>
        {/* <!-- Stats item --> */}
        <div className="flex items-end justify-between py-5">
          <div>
            <p className="mb-1 text-theme-sm text-gray-500 dark:text-gray-400">
              {t("marketing.trafficStats.pageBounceRate")}
            </p>
            <h4 className="mb-1 text-2xl font-semibold text-gray-800 dark:text-white/90">
              285
            </h4>
            <span className="flex items-center gap-1.5">
              <span className="text-success-600"> +12.74% </span>
              <span className="text-theme-xs text-gray-500 dark:text-gray-400">
                {t("marketing.trafficStats.thenLastWeek")}
              </span>
            </span>
          </div>

          <div className="w-full max-w-[150px]">
            <div className="chartNine chartNine-02">
              <Chart
                options={optionsOne}
                series={series}
                type="area"
                height={70}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
