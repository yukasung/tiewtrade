import { MoreDotIcon } from "@/icons";
import type { ApexOptions } from "apexcharts";
import { useState } from "react";
import Chart from "react-apexcharts";
import { useTranslation } from "react-i18next";
import { Dropdown } from "../ui/dropdown/Dropdown";
import { DropdownItem } from "../ui/dropdown/DropdownItem";

export default function RevenueEarnedChart() {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);

  const options: ApexOptions = {
    chart: {
      fontFamily: "Outfit, sans-serif",
      height: 70,
      type: "area",
      parentHeightOffset: 0,
      toolbar: { show: false },
    },
    grid: { show: false },
    colors: ["#12B76A"],
    fill: {
      gradient: {
        opacityFrom: 0.55,
        opacityTo: 0,
      },
    },
    legend: { show: false },
    tooltip: { enabled: false },
    dataLabels: { enabled: false },
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
      labels: { show: false },
      axisBorder: { show: false },
      axisTicks: { show: false },
      tooltip: { enabled: false },
    },
    yaxis: {
      labels: { show: false },
    },
  };

  const series = [
    {
      name: "New Sales",
      data: [300, 350, 310, 370, 248, 287, 295, 191, 269, 201, 185, 252, 151],
    },
  ];

  const toggleDropdown = () => {
    setIsOpen(!isOpen);
  };

  const closeDropdown = () => {
    setIsOpen(false);
  };

  return (
    <div className="flex flex-col justify-between space-y-6 rounded-xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-white/3">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {t("logistics.revenueEarned.totalRevenue")}
          </p>
          <h3 className="text-3xl font-medium text-gray-800 dark:text-white/90">
            $23,445,700
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
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {t("logistics.revenueEarned.shippedQuantities")}
          </p>
          <h3 className="text-3xl font-medium text-gray-800 dark:text-white/90">
            9,258
          </h3>
        </div>
        <div className="h-15 w-full max-w-37.5">
          <Chart options={options} series={series} type="area" height={70} />
        </div>
      </div>
    </div>
  );
}
