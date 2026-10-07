import { Dropdown } from "@/components/ui/dropdown/Dropdown";
import { DropdownItem } from "@/components/ui/dropdown/DropdownItem";
import { MoreDotIcon } from "@/icons";
import type { ApexOptions } from "apexcharts";
import { useState } from "react";
import Chart from "react-apexcharts";
import { useTranslation } from "react-i18next";

export default function EstimatedRevenue() {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);

  // ApexCharts configuration
  const options: ApexOptions = {
    colors: ["#465FFF"],
    chart: {
      fontFamily: "Outfit, sans-serif",
      type: "radialBar",
      height: 360,
      sparkline: {
        enabled: true,
      },
    },
    plotOptions: {
      radialBar: {
        startAngle: -85,
        endAngle: 85,
        hollow: {
          size: "80%",
        },
        track: {
          background: "#E4E7EC",
          strokeWidth: "100%",
          margin: 5, // margin is in pixels
        },
        dataLabels: {
          name: {
            show: false,
          },
          value: {
            fontSize: "36px",
            fontWeight: "600",
            offsetY: -25,
            color: "#1D2939",
            formatter: function (val) {
              return "$" + val;
            },
          },
        },
      },
    },
    fill: {
      type: "solid",
      colors: ["#465FFF"],
    },
    stroke: {
      lineCap: "round",
    },
    labels: [t("crm.estimatedRevenue.goals")],
  };
  const series = [90];

  const toggleDropdown = () => {
    setIsOpen(!isOpen);
  };

  const closeDropdown = () => {
    setIsOpen(false);
  };

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 sm:p-6 dark:border-gray-800 dark:bg-white/3">
      <div className="flex justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">
            {t("crm.estimatedRevenue.title")}
          </h3>
          <p className="mt-1 text-theme-sm text-gray-500 dark:text-gray-400">
            {t("crm.estimatedRevenue.subtitle")}
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

      <div className="relative">
        <div id="chartDarkStyle" className="max-h-42">
          <Chart
            options={options}
            series={series}
            type="radialBar"
            height={360}
          />
        </div>
        <span className="absolute top-[60%] left-1/2 -translate-x-1/2 translate-y-[-60%] text-xs font-normal text-gray-500 dark:text-gray-400">
          {t("crm.estimatedRevenue.goals")}
        </span>
      </div>

      <div className="mt-6 space-y-5 border-t border-gray-200 pt-6 dark:border-gray-800">
        <div>
          <p className="mb-2 text-theme-sm text-gray-500 dark:text-gray-400">
            {t("crm.estimatedRevenue.marketing")}
          </p>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div>
                <p className="text-base font-semibold text-gray-800 dark:text-white/90">
                  $30,569.00
                </p>
              </div>
            </div>

            <div className="flex w-full max-w-35 items-center gap-3">
              <div className="relative block h-2 w-full max-w-25 rounded-sm bg-gray-200 dark:bg-gray-800">
                <div className="absolute inset-s-0 top-0 flex h-full w-[85%] items-center justify-center rounded-sm bg-brand-500 text-xs font-medium text-white"></div>
              </div>
              <p className="text-theme-sm font-medium text-gray-700 dark:text-gray-400">
                85%
              </p>
            </div>
          </div>
        </div>

        <div>
          <p className="mb-2 text-theme-sm text-gray-500 dark:text-gray-400">
            {t("crm.estimatedRevenue.sales")}
          </p>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div>
                <p className="text-base font-semibold text-gray-800 dark:text-white/90">
                  $20,486.00
                </p>
              </div>
            </div>

            <div className="flex w-full max-w-35 items-center gap-3">
              <div className="relative block h-2 w-full max-w-25 rounded-sm bg-gray-200 dark:bg-gray-800">
                <div className="absolute inset-s-0 top-0 flex h-full w-[55%] items-center justify-center rounded-sm bg-brand-500 text-xs font-medium text-white"></div>
              </div>
              <p className="text-theme-sm font-medium text-gray-700 dark:text-gray-400">
                55%
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
