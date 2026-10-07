import { Dropdown } from "@/components/ui/dropdown/Dropdown";
import { DropdownItem } from "@/components/ui/dropdown/DropdownItem";
import { MoreDotIcon } from "@/icons";
import type { ApexOptions } from "apexcharts";
import { useState } from "react";
import Chart from "react-apexcharts";
import { useTranslation } from "react-i18next";

export default function SalePieChart() {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);

  // ApexCharts configuration
  const options: ApexOptions = {
    colors: ["#3641f5", "#7592ff", "#dde9ff"],
    labels: ["Affiliate", "Direct", "Adsense"],
    chart: {
      fontFamily: "Outfit, sans-serif",
      type: "donut",
      width: 280,
      height: 280,
    },
    stroke: {
      show: false,
      width: 4, // Creates a gap between the series
    },
    plotOptions: {
      pie: {
        donut: {
          size: "65%",
          background: "transparent",
          labels: {
            show: true,
            name: {
              show: true,
              offsetY: 0,
              color: "#1D2939",
              fontSize: "12px",
              fontWeight: "normal",
              formatter: () => "Total 3.5K",
            },
            value: {
              show: true,
              offsetY: 10,
              color: "#667085",
              fontSize: "14px",
              formatter: () => "Used of 1.1K",
            },
            total: {
              show: true,
              label: "Total",
              color: "#000000",
              fontSize: "20px",
              fontWeight: "bold",
            },
          },
        },
      },
    },
    states: {
      hover: {
        filter: {
          type: "none",
        },
      },
      active: {
        allowMultipleDataPointsSelection: false,
        filter: {
          type: "darken",
        },
      },
    },
    dataLabels: {
      enabled: false,
    },

    tooltip: {
      enabled: false,
    },

    legend: {
      show: false,
    },

    responsive: [
      {
        breakpoint: 640,
        options: {
          chart: {
            width: 280,
            height: 280,
          },
        },
      },
      {
        breakpoint: 2600,
        options: {
          chart: {
            width: 240,
            height: 240,
          },
        },
      },
    ],
  };

  const series = [900, 700, 850];

  const toggleDropdown = () => {
    setIsOpen(!isOpen);
  };

  const closeDropdown = () => {
    setIsOpen(false);
  };

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 sm:p-6 dark:border-gray-800 dark:bg-white/3">
      <div className="mb-5 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">
          {t("crm.salesCategory.title")}
        </h3>
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
      <div className="flex flex-col items-center gap-8 xl:flex-row">
        <div id="chartDarkStyle">
          <Chart options={options} series={series} type="donut" height={280} />
        </div>
        <div className="flex flex-col items-start gap-6 sm:flex-row xl:flex-col">
          <div className="flex items-start gap-2.5">
            <div className="mt-1.5 h-2 w-2 rounded-full bg-brand-500"></div>
            <div>
              <h5 className="mb-1 text-theme-sm font-medium text-gray-800 dark:text-white/90">
                {t("crm.salesCategory.affiliateProgram")}
              </h5>
              <div className="flex items-center gap-2">
                <p className="text-theme-sm font-medium text-gray-700 dark:text-gray-400">
                  48%
                </p>
                <div className="h-1 w-1 rounded-full bg-gray-400"></div>
                <p className="text-theme-sm text-gray-500 dark:text-gray-400">
                  2,040 {t("crm.salesCategory.products")}
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-start gap-2.5">
            <div className="mt-1.5 h-2 w-2 rounded-full bg-brand-500"></div>
            <div>
              <h5 className="mb-1 text-theme-sm font-medium text-gray-800 dark:text-white/90">
                {t("crm.salesCategory.directBuy")}
              </h5>
              <div className="flex items-center gap-2">
                <p className="text-theme-sm font-medium text-gray-700 dark:text-gray-400">
                  33%
                </p>
                <div className="h-1 w-1 rounded-full bg-gray-400"></div>
                <p className="text-theme-sm text-gray-400 dark:text-gray-400">
                  1,402 {t("crm.salesCategory.products")}
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-start gap-2.5">
            <div className="mt-1.5 h-2 w-2 rounded-full bg-brand-300"></div>
            <div>
              <h5 className="mb-1 text-theme-sm font-medium text-gray-800 dark:text-white/90">
                {t("crm.salesCategory.adsense")}
              </h5>
              <div className="flex items-center gap-2">
                <p className="text-theme-sm font-medium text-gray-700 dark:text-gray-400">
                  19%
                </p>
                <div className="h-1 w-1 rounded-full bg-gray-400"></div>
                <p className="text-theme-sm text-gray-500 dark:text-gray-400">
                  510 {t("crm.salesCategory.products")}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
