import type { ApexOptions } from "apexcharts";
import { useState } from "react";
import Chart from "react-apexcharts";
import { useTranslation } from "react-i18next";
import { MoreDotIcon } from "../../icons";
import { Dropdown } from "../ui/dropdown/Dropdown";
import { DropdownItem } from "../ui/dropdown/DropdownItem";

const darkCount = 14;
const lightCount = 14;
const grayCount = 14;

const chartOptions: ApexOptions = {
  series: [{ data: Array(darkCount + lightCount + grayCount).fill(100) }],
  colors: [
    ...Array(darkCount).fill("#465FFF"),
    ...Array(lightCount).fill("#36BFFA"),
    ...Array(grayCount).fill("#E4E7EC"),
  ],
  chart: {
    fontFamily: "Outfit, sans-serif",
    type: "bar",
    height: 32,
    sparkline: { enabled: true },
    toolbar: { show: false },
    animations: { enabled: false },
  },
  plotOptions: {
    bar: {
      horizontal: false,
      distributed: true,
      columnWidth: "70%",
      borderRadius: 1,
      borderRadiusApplication: "around",
    },
  },
  dataLabels: { enabled: false },
  xaxis: {
    labels: { show: false },
    axisBorder: { show: false },
    axisTicks: { show: false },
  },
  yaxis: { show: false },
  grid: {
    show: false,
    padding: { top: 0, right: 0, bottom: 0, left: 0 },
  },
  tooltip: { enabled: false },
  legend: { show: false },
};

const chartSeries: ApexOptions["series"] = [
  { data: Array(darkCount + lightCount + grayCount).fill(100) },
];

export default function SalesChannel() {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);

  function toggleDropdown() {
    setIsOpen(!isOpen);
  }

  function closeDropdown() {
    setIsOpen(false);
  }
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/3">
      <div className="mb-4 flex items-center justify-between gap-2">
        <div>
          <h3 className="text-lg font-medium text-gray-800 dark:text-white/90">
            {t("sales.salesByChannel.title")}
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {t("sales.salesByChannel.subtitle")}
          </p>
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
      <div className="mb-6 flex items-center gap-2">
        <h3 className="text-3xl text-gray-800 dark:text-white/90">75</h3>
        <span className="flex items-center text-sm text-success-600">
          <svg
            width="16"
            height="16"
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
          3.2%
        </span>
        <span className="text-sm text-gray-500 dark:text-gray-400">
          {t("sales.salesByChannel.increasedVsLastWeek")}
        </span>
      </div>
      <Chart
        options={chartOptions}
        series={chartSeries}
        type="bar"
        height={32}
      />
      <div className="mt-5 rounded-xl border border-gray-200 dark:border-gray-800">
        <div className="flex gap-6 border-b border-gray-200 px-4 py-3 dark:border-gray-800">
          <div className="flex items-center gap-1.5">
            <span className="inline-block size-2 rounded-full bg-brand-500"></span>
            <span className="text-sm text-gray-700 dark:text-gray-400">
              {t("sales.salesByChannel.channels.website")}
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="inline-block size-2 rounded-full bg-blue-light-400"></span>
            <span className="text-sm text-gray-700 dark:text-gray-400">
              {t("sales.salesByChannel.channels.email")}
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="inline-block size-2 rounded-full bg-gray-200"></span>
            <span className="text-sm text-gray-700 dark:text-gray-400">
              {t("sales.salesByChannel.channels.socialMedia")}
            </span>
          </div>
        </div>
        <div className="p-4">
          <table className="w-full">
            <thead>
              <tr>
                <th className="pb-2 text-start text-sm font-normal text-gray-400">
                  {t("sales.salesByChannel.table.channels")}
                </th>
                <th className="pb-2 text-start text-sm font-normal text-gray-400">
                  {t("sales.salesByChannel.table.metric")}
                </th>
                <th className="pb-2 text-end text-sm font-normal text-gray-400">
                  {t("sales.salesByChannel.table.total")}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="py-2 text-sm text-gray-700 dark:text-gray-400">
                  {t("sales.salesByChannel.channels.website")}
                </td>
                <td className="py-2 text-sm text-gray-700 dark:text-gray-400">
                  35
                </td>
                <td className="py-2 text-end text-sm text-gray-700 dark:text-gray-400">
                  <span className="flex items-center justify-end gap-1.5">
                    <svg
                      width="16"
                      height="16"
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
                    5.2%
                  </span>
                </td>
              </tr>
              <tr>
                <td className="py-2 text-sm text-gray-700 dark:text-gray-400">
                  {t("sales.salesByChannel.channels.email")}
                </td>
                <td className="py-2 text-sm text-gray-700 dark:text-gray-400">
                  25
                </td>
                <td className="py-2 text-end text-sm text-gray-700 dark:text-gray-400">
                  <span className="flex items-center justify-end gap-1.5 text-error-600">
                    <svg
                      width="16"
                      height="16"
                      viewBox="0 0 16 16"
                      fill="none"
                      xmlns="http://www.w3.org/2000/svg"
                    >
                      <path
                        d="M7.9974 13.3336L7.9974 2.66602M4 9.33619L7.99987 13.3335L12 9.33619"
                        stroke="#D92D20"
                        strokeWidth="1.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                    5.2%
                  </span>
                </td>
              </tr>
              <tr>
                <td className="py-2 text-sm text-gray-700 dark:text-gray-400">
                  {t("sales.salesByChannel.channels.socialMedia")}
                </td>
                <td className="py-2 text-sm text-gray-700 dark:text-gray-400">
                  59
                </td>
                <td className="py-2 text-end text-sm text-gray-700 dark:text-gray-400">
                  <span className="flex items-center justify-end gap-1.5 text-success-600">
                    <svg
                      width="16"
                      height="16"
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
                    5.2%
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
