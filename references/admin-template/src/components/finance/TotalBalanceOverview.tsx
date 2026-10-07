import { useClickOutside } from "@/hooks/useClickOutside";
import type { ApexOptions } from "apexcharts";
import { useRef, useState } from "react";
import ReactApexChart from "react-apexcharts";
import { useTranslation } from "react-i18next";

interface Currency {
  name: string;
  flag: string;
}

const currencies: Currency[] = [
  { name: "USD", flag: "/images/flag/flag-01.png" },
  { name: "EUR", flag: "/images/flag/flag-02.png" },
  { name: "GBP", flag: "/images/flag/flag-03.png" },
  { name: "JPY", flag: "/images/flag/flag-04.png" },
];

const periods = [
  "June 2025",
  "May 2025",
  "Apr 2025",
  "Q1 2025",
  "Last 30 Days",
  "Last 7 Days",
];

export default function TotalBalanceOverview() {
  const { t } = useTranslation();
  const [isCurrencyOpen, setIsCurrencyOpen] = useState(false);
  const [selectedCurrency, setSelectedCurrency] = useState(currencies[0]);
  const [isDateOpen, setIsDateOpen] = useState(false);
  const [selectedDate, setSelectedDate] = useState(periods[0]);
  const [isCopied, setIsCopied] = useState(false);

  // Refs for outside click handling
  const currencyDropdownRef = useRef<HTMLDivElement>(null);
  const dateDropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdowns on outside click
  useClickOutside(currencyDropdownRef, () => setIsCurrencyOpen(false));
  useClickOutside(dateDropdownRef, () => setIsDateOpen(false));

  const handleCopy = () => {
    navigator.clipboard.writeText("•••• •••• •••• 5332");
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  const chartOptions: ApexOptions = {
    colors: ["#465FFF"],
    chart: {
      fontFamily: "Outfit, sans-serif",
      type: "area",
      height: 70,
      sparkline: {
        enabled: true,
      },
      toolbar: {
        show: false,
      },
      animations: {
        enabled: true,
      },
    },
    stroke: {
      curve: "smooth",
      width: 2,
    },
    fill: {
      type: "gradient",
      gradient: {
        opacityFrom: 0.65,
        opacityTo: 0,
      },
    },
    markers: {
      size: 0,
    },
    tooltip: {
      enabled: false,
    },
  };

  const chartSeries = [
    {
      name: "Balance",
      data: [
        20, 24, 23, 25, 30, 35, 40, 30, 32, 33, 29, 28, 27, 29, 45, 58, 70, 80,
        72, 68, 85, 79, 77, 75,
      ],
    },
  ];

  return (
    <div className="rounded-[18px] border border-gray-200 bg-gray-100 p-1.5 dark:border-gray-800 dark:bg-white/3">
      <div className="rounded-xl bg-white p-6 pb-8 dark:bg-gray-900">
        <div className="mb-10 flex flex-col justify-between gap-4 sm:flex-row">
          <div>
            <h3 className="text-base font-medium text-gray-800 dark:text-white/90">
              {t("finance.totalBalanceOverview.title")}
            </h3>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {t("finance.totalBalanceOverview.overview")}
            </p>
          </div>
          <div className="flex shrink-0 gap-2">
            {/* Currency Dropdown */}
            <div className="relative" ref={currencyDropdownRef}>
              <button
                type="button"
                onClick={() => setIsCurrencyOpen(!isCurrencyOpen)}
                className="flex h-9 items-center justify-center gap-1.5 rounded-lg border border-gray-300 px-2.5 text-sm font-medium text-gray-700 shadow-xs dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400"
              >
                <img
                  src={selectedCurrency.flag}
                  alt={selectedCurrency.name}
                  className="size-4 rounded-full"
                />
                <span>{selectedCurrency.name}</span>
                <svg
                  className={`transition-transform ${isCurrencyOpen ? "rotate-180" : ""}`}
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

              {isCurrencyOpen && (
                <div className="absolute inset-e-0 z-50 mt-1.5 w-36 rounded-xl border border-gray-200 bg-white p-1.5 shadow-lg dark:border-gray-700 dark:bg-gray-900">
                  {currencies.map((currency) => (
                    <button
                      key={currency.name}
                      type="button"
                      onClick={() => {
                        setSelectedCurrency(currency);
                        setIsCurrencyOpen(false);
                      }}
                      className={`flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-white/5 ${
                        selectedCurrency.name === currency.name
                          ? "bg-gray-100 font-medium dark:bg-white/5"
                          : "font-normal"
                      }`}
                    >
                      <img
                        src={currency.flag}
                        alt={currency.name}
                        className="size-4 rounded-full"
                      />
                      <span>{currency.name}</span>
                      {selectedCurrency.name === currency.name && (
                        <svg
                          className="ms-auto"
                          width="14"
                          height="14"
                          viewBox="0 0 14 14"
                          fill="none"
                          xmlns="http://www.w3.org/2000/svg"
                        >
                          <path
                            d="M2.625 7L5.25 9.625L11.375 3.5"
                            stroke="#465FFF"
                            strokeWidth="1.5"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                        </svg>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Date Dropdown */}
            <div className="relative" ref={dateDropdownRef}>
              <button
                type="button"
                onClick={() => setIsDateOpen(!isDateOpen)}
                className="flex h-9 items-center justify-center gap-1.5 rounded-lg border border-gray-300 px-2.5 text-sm font-medium text-gray-700 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400"
              >
                <span>{selectedDate}</span>
                <svg
                  className={`transition-transform ${isDateOpen ? "rotate-180" : ""}`}
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

              {isDateOpen && (
                <div className="absolute inset-e-0 z-50 mt-1.5 w-38 rounded-xl border border-gray-200 bg-white p-1.5 shadow-lg dark:border-gray-700 dark:bg-gray-900">
                  {periods.map((period) => (
                    <button
                      key={period}
                      type="button"
                      onClick={() => {
                        setSelectedDate(period);
                        setIsDateOpen(false);
                      }}
                      className={`w-full rounded-lg px-2.5 py-2 text-start text-sm text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-white/5 ${
                        selectedDate === period
                          ? "bg-gray-100 font-medium dark:bg-white/5"
                          : "font-normal"
                      }`}
                    >
                      {period}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-end border-b border-dashed border-gray-200 pb-7 dark:border-gray-800">
          <div>
            <h3 className="mb-2 text-3xl font-medium text-gray-800 dark:text-white/90">
              19,857.00
            </h3>
            <p className="flex items-center gap-1.5 text-sm font-normal text-gray-500 dark:text-gray-400">
              <span className="flex items-center gap-1 font-medium text-success-600">
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
              {t("finance.totalBalanceOverview.thanLastMonth")}
            </p>
          </div>
          {/* Chart */}
          <div className="ms-auto w-25 sm:w-37.5">
            <ReactApexChart
              options={chartOptions}
              series={chartSeries}
              type="area"
              height={70}
            />
          </div>
        </div>
        <div className="pt-7.5">
          {/* Content */}
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            {/* Label */}
            <p className="shrink-0 text-sm text-gray-700 dark:text-gray-400">
              {t("finance.totalBalanceOverview.primaryAccount")}
            </p>
            <div className="flex items-center gap-2">
              {/* Account Number */}
              <p className="shrink-0 text-lg font-medium text-gray-700 dark:text-gray-400">
                •••• •••• •••• 5332
              </p>

              {/* Copy Button */}
              <div className="shrink-0">
                <button
                  type="button"
                  onClick={handleCopy}
                  className="relative flex h-8 w-9 items-center justify-center rounded-lg border border-gray-300 text-gray-700 shadow-xs hover:bg-gray-100 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-900"
                >
                  {!isCopied ? (
                    <svg
                      width="20"
                      height="20"
                      fill="none"
                      viewBox="0 0 20 20"
                      className="absolute"
                    >
                      <path
                        d="M14.1559 14.1628H7.08724C6.39688 14.1628 5.83724 13.6032 5.83724 12.9128V5.84416M14.1559 14.1628V15.4161C14.1559 16.1065 13.5963 16.6661 12.9059 16.6661H4.58398C3.89363 16.6661 3.33398 16.1065 3.33398 15.4161V7.09416C3.33398 6.4038 3.89363 5.84416 4.58398 5.84416H5.83724M14.1559 14.1628H15.4144C16.1048 14.1628 16.6644 13.6032 16.6644 12.9128V4.58398C16.6644 3.89363 16.1048 3.33398 15.4144 3.33398H7.08724C6.39688 3.33398 5.83724 3.89363 5.83724 4.58398V5.84416"
                        stroke="currentColor"
                        strokeWidth="1.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  ) : (
                    <svg
                      width="20"
                      height="20"
                      fill="none"
                      viewBox="0 0 20 20"
                      className="absolute text-success-500"
                    >
                      <path
                        d="M16.6668 5L7.50016 14.1667L3.3335 10"
                        stroke="currentColor"
                        strokeWidth="1.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  )}
                </button>
              </div>

              {/* Details Button */}
              <button className="flex h-8 shrink-0 items-center justify-center rounded-lg border border-gray-300 px-3 text-sm text-gray-700 shadow-xs hover:bg-gray-100 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-900">
                {t("finance.totalBalanceOverview.seeDetails")}
              </button>
            </div>
          </div>
        </div>
      </div>
      <div className="flex gap-3 px-3.5 pt-5 pb-4">
        <button className="flex h-11 flex-1 shrink-0 items-center justify-center gap-2 rounded-lg bg-brand-500 px-4 py-3 text-sm font-medium text-white hover:bg-brand-600">
          <svg
            className="rtl:-scale-x-100"
            width="20"
            height="20"
            viewBox="0 0 20 20"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M14.9968 5.00356L5 15.0003M14.9977 12.4949L14.9953 5.00214L7.49917 4.99951"
              stroke="white"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          {t("finance.totalBalanceOverview.transfer")}
        </button>
        <button className="flex h-11 flex-1 shrink-0 items-center justify-center gap-2 rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm font-medium text-gray-700 transition dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-900">
          <svg
            className="rtl:-scale-x-100"
            width="20"
            height="20"
            viewBox="0 0 20 20"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M5.00095 14.9963L14.9977 4.99954M5 7.50539L5.00238 14.9981L12.4985 15.0007"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          {t("finance.totalBalanceOverview.received")}
        </button>
        <button className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border border-gray-300 bg-white text-gray-700 transition dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-900">
          <svg
            width="20"
            height="20"
            viewBox="0 0 20 20"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M5 10.0002H15.0006M10.0002 5V15.0006"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </div>
    </div>
  );
}
