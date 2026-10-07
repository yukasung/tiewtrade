import { useTheme } from "@/context/ThemeContext";
import { useClickOutside } from "@/hooks/useClickOutside";
import type { ApexOptions } from "apexcharts";
import { useMemo, useRef, useState } from "react";
import ReactApexChart from "react-apexcharts";
import { useTranslation } from "react-i18next";

const years = ["2025", "2024", "2023", "2022", "2021", "2020"];
const timeframeOptions = ["3 Month", "6 Month", "1 Year"];

export default function CashflowOverview() {
  const { t } = useTranslation();
  const { theme } = useTheme();
  const [isYearOpen, setIsYearOpen] = useState(false);
  const [selectedYear, setSelectedYear] = useState(years[0]);
  const [isTimeframeOpen, setIsTimeframeOpen] = useState(false);
  const [selectedTimeframe, setSelectedTimeframe] = useState(
    timeframeOptions[0],
  );

  const [incomeHidden, setIncomeHidden] = useState(false);
  const [expenseHidden, setExpenseHidden] = useState(false);

  // Refs for outside click handling
  const yearDropdownRef = useRef<HTMLDivElement>(null);
  const timeframeDropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdowns on outside click
  useClickOutside(yearDropdownRef, () => setIsYearOpen(false));
  useClickOutside(timeframeDropdownRef, () => setIsTimeframeOpen(false));

  const series = useMemo(
    () => [
      {
        name: "Income",
        data: [
          9500, 6400, 14000, 7500, 9500, 10200, 7000, 11600, 9200, 12500, 7600,
          6400,
        ],
      },
      {
        name: "Expense",
        data: [
          6200, 4100, 9200, 5000, 6300, 6800, 4600, 7600, 6000, 8200, 5000,
          4100,
        ],
      },
    ],
    [],
  );

  // Filter series based on visibility
  const visibleSeries = useMemo(() => {
    return series.filter((s) => {
      if (s.name === "Income") return !incomeHidden;
      if (s.name === "Expense") return !expenseHidden;
      return true;
    });
  }, [series, incomeHidden, expenseHidden]);

  const options: ApexOptions = useMemo(
    () => ({
      colors: ["#465FFF", "#9CB9FF"],
      chart: {
        type: "bar",
        height: 250,
        stacked: true,
        toolbar: {
          show: false,
        },
        zoom: {
          enabled: false,
        },
        fontFamily: "Outfit, sans-serif",
      },
      plotOptions: {
        bar: {
          horizontal: false,
          columnWidth: "40%",
          borderRadius: 6,
          borderRadiusApplication: "end",
        },
      },
      fill: {
        opacity: 1,
      },
      dataLabels: {
        enabled: false,
      },
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
        axisBorder: {
          show: false,
        },
        axisTicks: {
          show: false,
        },
        labels: {
          style: {
            colors: "#98A2B3",
            fontSize: "12px",
          },
        },
      },
      yaxis: {
        labels: {
          style: {
            colors: "#98A2B3",
            fontSize: "12px",
          },
          formatter: (value: number) => {
            if (value >= 1000) return `${value / 1000}K`;
            return value.toString();
          },
        },
      },
      grid: {
        xaxis: {
          lines: {
            show: false,
          },
        },
        yaxis: {
          lines: {
            show: true,
          },
        },
        borderColor: theme === "dark" ? "#2E3545" : "#E9EDF5",
        strokeDashArray: 0,
      },
      legend: {
        show: false,
      },
      tooltip: {
        enabled: true,
        x: {
          show: false,
        },
        y: {
          formatter: (value: number) => `$${value}`,
        },
      },
    }),
    [theme],
  );

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-white/3">
      <div className="mb-6 flex flex-col justify-between gap-5 sm:flex-row">
        <div>
          <h3 className="text-base font-medium text-gray-800 dark:text-white/90">
            {t("finance.cashflow.title")}
          </h3>
        </div>
        <div className="flex gap-2">
          {/* Year Dropdown */}
          <div className="relative" ref={yearDropdownRef}>
            <button
              onClick={() => setIsYearOpen(!isYearOpen)}
              className="flex h-9 items-center justify-center gap-1.5 rounded-lg border border-gray-300 px-2.5 text-sm font-medium text-gray-700 shadow-xs dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400"
            >
              <span>{selectedYear}</span>
              <svg
                className={`transition-transform ${isYearOpen ? "rotate-180" : ""}`}
                width="18"
                height="18"
                viewBox="0 0 18 18"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d="M4.3125 7.21875L9 11.9063L13.6875 7.21875"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
            {isYearOpen && (
              <div className="absolute inset-e-0 z-50 mt-1.5 w-38 rounded-xl border border-gray-200 bg-white p-1.5 shadow-lg dark:border-gray-700 dark:bg-gray-900">
                {years.map((year) => (
                  <button
                    key={year}
                    onClick={() => {
                      setSelectedYear(year);
                      setIsYearOpen(false);
                    }}
                    className={`w-full rounded-lg px-2.5 py-2 text-start text-sm text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-white/5 ${
                      selectedYear === year
                        ? "bg-gray-100 font-medium dark:bg-white/5"
                        : "font-normal"
                    }`}
                  >
                    {year}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Timeframe Dropdown */}
          <div className="relative" ref={timeframeDropdownRef}>
            <button
              onClick={() => setIsTimeframeOpen(!isTimeframeOpen)}
              className="flex h-9 items-center justify-center gap-1.5 rounded-lg border border-gray-300 px-2.5 text-sm font-medium text-gray-700 shadow-xs dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400"
            >
              <span>{selectedTimeframe}</span>
              <svg
                className={`transition-transform ${isTimeframeOpen ? "rotate-180" : ""}`}
                width="18"
                height="18"
                viewBox="0 0 18 18"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d="M4.3125 7.21875L9 11.9063L13.6875 7.21875"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
            {isTimeframeOpen && (
              <div className="absolute inset-e-0 z-50 mt-1.5 w-38 rounded-xl border border-gray-200 bg-white p-1.5 shadow-lg dark:border-gray-700 dark:bg-gray-900">
                {timeframeOptions.map((tf) => (
                  <button
                    key={tf}
                    onClick={() => {
                      setSelectedTimeframe(tf);
                      setIsTimeframeOpen(false);
                    }}
                    className={`w-full rounded-lg px-2.5 py-2 text-start text-sm text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-white/5 ${
                      selectedTimeframe === tf
                        ? "bg-gray-100 font-medium dark:bg-white/5"
                        : "font-normal"
                    }`}
                  >
                    {tf}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
      <div className="flex flex-wrap items-end justify-between gap-5">
        <div>
          <p className="mb-1.5 text-sm text-gray-500 dark:text-gray-400">
            {t("finance.cashflow.totalRevenue")}
          </p>
          <div className="flex items-center gap-3">
            <h4 className="text-2xl font-medium text-gray-800 dark:text-white/90">
              $9,758.00
            </h4>
            <span className="flex items-center gap-1 rounded-full bg-success-50 px-2 py-0.5 text-xs font-medium text-success-600 dark:bg-success-500/10 dark:text-success-500">
              +7.96%
            </span>
          </div>
        </div>

        <div className="flex items-center gap-5">
          <button
            onClick={() => setIncomeHidden(!incomeHidden)}
            className={`flex cursor-pointer items-center gap-2 transition-opacity duration-200 select-none hover:opacity-80 ${
              incomeHidden ? "opacity-40" : ""
            }`}
          >
            <span className="block size-2.5 rounded-full bg-brand-500"></span>
            <span className="text-sm font-normal text-gray-800 dark:text-white/90">
              Income
            </span>
          </button>
          <button
            onClick={() => setExpenseHidden(!expenseHidden)}
            className={`flex cursor-pointer items-center gap-2 transition-opacity duration-200 select-none hover:opacity-80 ${
              expenseHidden ? "opacity-40" : ""
            }`}
          >
            <span className="block size-2.5 rounded-full bg-brand-300"></span>
            <span className="text-sm font-normal text-gray-800 dark:text-white/90">
              Expense
            </span>
          </button>
        </div>
      </div>

      <div className="-ms-4 h-62.5">
        <ReactApexChart
          options={options}
          series={visibleSeries}
          type="bar"
          height={250}
        />
      </div>
    </div>
  );
}
