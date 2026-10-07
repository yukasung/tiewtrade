"use client";
import type { ApexOptions } from "apexcharts";
import flatpickr from "flatpickr";
import { useEffect, useRef } from "react";
import Chart from "react-apexcharts";
import { useTranslation } from "react-i18next";
import { CalenderIcon } from "../../icons";

const getChartOptions = (color: string): ApexOptions => ({
  colors: [color],
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
    sparkline: {
      enabled: true,
    },
  },
  tooltip: {
    enabled: false,
  },
  grid: {
    show: false,
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
    labels: { show: false },
    axisBorder: { show: false },
    axisTicks: { show: false },
    tooltip: { enabled: false },
  },
  yaxis: {
    labels: { show: false },
  },
});

const chartSeries = [
  {
    name: "New Sales",
    data: [300, 350, 310, 370, 248, 187, 295, 191, 269, 201, 185, 252, 151],
  },
];

export default function SalesStats() {
  const { t } = useTranslation();
  const datePickerRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!datePickerRef.current) return;

    const today = new Date();
    const sevenDaysAgo = new Date();
    sevenDaysAgo.setDate(today.getDate() - 6);

    const fp = flatpickr(datePickerRef.current, {
      mode: "range",
      static: true,
      monthSelectorType: "static",
      dateFormat: "M d",
      defaultDate: [sevenDaysAgo, today],
      clickOpens: true,
      prevArrow:
        '<svg class="stroke-current rtl:rotate-180" width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12.5 15L7.5 10L12.5 5" stroke="" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>',
      nextArrow:
        '<svg class="stroke-current rtl:rotate-180" width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M7.5 15L12.5 10L7.5 5" stroke="" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>',
    });

    return () => {
      if (!Array.isArray(fp)) {
        fp.destroy();
      }
    };
  }, []);
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/3">
      <div className="mb-5 flex flex-col justify-between gap-5 sm:flex-row sm:items-center">
        <div>
          <h2 className="mb-1 text-xl font-semibold text-gray-800 dark:text-white/90">
            {t("sales.salesStats.title")}
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {t("sales.salesStats.subtitle")}
          </p>
        </div>
        <div className="flex items-center gap-3 sm:justify-end lg:flex-row">
          {/* <!-- Date input --> */}
          <div className="relative hidden items-center xl:inline-flex">
            <CalenderIcon className="pointer-events-none absolute start-1/2 top-1/2 z-10 size-5 -translate-x-1/2 -translate-y-1/2 text-gray-500 lg:start-3 lg:top-1/2 lg:translate-x-0 lg:-translate-y-1/2 dark:text-gray-400" />
            <input
              ref={datePickerRef}
              className="h-11 w-11 cursor-pointer rounded-lg border border-gray-300 bg-white text-sm font-medium text-transparent outline-none lg:w-40 lg:py-2 lg:ps-10 lg:pe-3 lg:text-gray-700 dark:border-gray-700 dark:bg-gray-800 dark:lg:text-gray-300"
              placeholder={t("sales.salesStats.selectDateRange")}
            />
          </div>
          <button className="inline-flex h-11 items-center gap-2 rounded-lg bg-white px-4 py-3 text-sm font-medium text-gray-700 shadow-theme-xs ring-1 ring-gray-300 transition ring-inset hover:bg-gray-50 dark:bg-gray-800 dark:text-gray-400 dark:ring-gray-700 dark:hover:bg-white/3">
            <svg
              width="20"
              height="20"
              viewBox="0 0 20 20"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M14.6547 5.90384C14.6547 4.48402 13.5037 3.33301 12.0839 3.33301C10.664 3.33301 9.51304 4.48403 9.51302 5.90384M14.6547 5.90384C14.6547 7.32367 13.5037 8.47467 12.0839 8.47467C10.664 8.47467 9.51302 7.32367 9.51302 5.90384M14.6547 5.90384L17.7096 5.90381M9.51302 5.90384L2.29297 5.90381M5.34792 14.0955C5.34792 12.6757 6.49892 11.5247 7.91875 11.5247C9.33858 11.5247 10.4896 12.6757 10.4896 14.0955M5.34792 14.0955C5.34792 15.5153 6.49892 16.6663 7.91875 16.6663C9.33858 16.6663 10.4896 15.5153 10.4896 14.0955M5.34792 14.0955L2.29297 14.0955M10.4896 14.0955L17.7096 14.0955"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            {t("common.filter")}
          </button>
          <button className="inline-flex h-11 items-center gap-2 rounded-lg bg-brand-500 px-4 py-3 text-sm font-medium text-white shadow-theme-xs transition hover:bg-brand-600">
            <svg
              width="20"
              height="20"
              viewBox="0 0 20 20"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M16.6661 13.333V15.4163C16.6661 16.1067 16.1064 16.6663 15.4161 16.6663H4.58203C3.89168 16.6663 3.33203 16.1067 3.33203 15.4163V13.333M10.0004 3.33301L10.0004 13.333M6.14456 7.18684L9.9986 3.33525L13.8529 7.18684"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            {t("sales.salesStats.export")}
          </button>
        </div>
      </div>
      <div className="rounded-2xl bg-gray-100 p-1 dark:bg-white/3">
        <div className="grid grid-cols-1 gap-1 sm:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-xl bg-white p-5 dark:bg-gray-900">
            <div className="mb-5 flex items-center justify-between">
              <div>
                <h3 className="text-base font-semibold text-gray-700 dark:text-gray-400">
                  {t("sales.salesStats.totalRevenue")}
                </h3>
                <div className="mt-1.5 flex gap-1.5">
                  <p className="flex items-center gap-1 text-sm font-medium text-success-600">
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
                    32%
                  </p>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    {t("sales.salesStats.vsLastMonth")}
                  </p>
                </div>
              </div>
              <div>
                <svg
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    d="M15.484 7.72335C15.484 6.28004 14.314 5.11 12.8707 5.11H11.8138C9.99228 5.11 8.51562 6.58666 8.51562 8.4082C8.51562 9.783 9.36841 11.0136 10.6557 11.4964L13.344 12.5046C14.6312 12.9873 15.484 14.2179 15.484 15.5927C15.484 17.4143 14.0074 18.8909 12.1858 18.8909H11.129C9.68566 18.8909 8.51562 17.7209 8.51562 16.2776M11.9996 19.2831L11.9996 21.2085M11.9996 2.79199L11.9996 4.71734"
                    stroke="#12B76A"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </div>
            </div>
            <div className="flex items-end justify-between">
              <h2 className="w-1/2 text-3xl font-semibold text-gray-800 dark:text-white/90">
                $10,590
              </h2>
              <div className="h-11 w-1/2">
                <Chart
                  options={getChartOptions("#12B76A")}
                  series={chartSeries}
                  type="area"
                  height={44}
                />
              </div>
            </div>
          </div>
          <div className="rounded-xl bg-white p-5 dark:bg-gray-900">
            <div className="mb-5 flex items-center justify-between">
              <div>
                <h3 className="text-base font-semibold text-gray-700 dark:text-gray-400">
                  {t("sales.salesStats.totalSales")}
                </h3>
                <div className="mt-1.5 flex gap-1.5">
                  <p className="flex items-center gap-1 text-sm font-medium text-success-600">
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
                    32%
                  </p>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    {t("sales.salesStats.vsLastMonth")}
                  </p>
                </div>
              </div>
              <div>
                <svg
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    d="M4.25 8L2 8M3.5 12H2M2.75 16H2M7.91619 19.1243H19.1489C19.9166 19.1243 20.5603 18.5448 20.6407 17.7814L21.8249 6.53203C21.9181 5.64637 21.2237 4.875 20.3331 4.875H9.10039C8.33275 4.875 7.68899 5.45455 7.60863 6.21796L6.42443 17.4673C6.3312 18.3529 7.02564 19.1243 7.91619 19.1243ZM13.5391 4.875H16.2108L15.4608 9.86401H12.7891L13.5391 4.875Z"
                    stroke="#7A5AF8"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </div>
            </div>
            <div className="flex items-end justify-between">
              <h2 className="w-1/2 text-3xl font-semibold text-gray-800 dark:text-white/90">
                1,320
              </h2>
              <div className="h-11 w-1/2">
                <Chart
                  options={getChartOptions("#7C3AED")}
                  series={chartSeries}
                  type="area"
                  height={44}
                />
              </div>
            </div>
          </div>
          <div className="rounded-xl bg-white p-5 dark:bg-gray-900">
            <div className="mb-5 flex items-center justify-between">
              <div>
                <h3 className="text-base font-semibold text-gray-700 dark:text-gray-400">
                  {t("sales.salesStats.conversionRate")}
                </h3>
                <div className="mt-1.5 flex gap-1.5">
                  <p className="flex items-center gap-1 text-sm font-medium text-success-600">
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
                    32%
                  </p>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    {t("sales.salesStats.vsLastMonth")}
                  </p>
                </div>
              </div>
              <div>
                <svg
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    d="M18.752 7.37695H5.25196M15.3773 4.00098L18.75 7.37587L15.3773 10.751M5.25 16.625H18.75M8.62471 20.001L5.25196 16.6261L8.62471 13.251"
                    stroke="#0BA5EC"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </div>
            </div>
            <div className="flex items-end justify-between">
              <h2 className="w-1/2 text-3xl font-semibold text-gray-800 dark:text-white/90">
                4.38%
              </h2>
              <div className="h-11 w-1/2">
                <Chart
                  options={getChartOptions("#38BDF8")}
                  series={chartSeries}
                  type="area"
                  height={44}
                />
              </div>
            </div>
          </div>
          <div className="rounded-xl bg-white p-5 dark:bg-gray-900">
            <div className="mb-5 flex items-center justify-between">
              <div>
                <h3 className="text-base font-semibold text-gray-700 dark:text-gray-400">
                  {t("sales.salesStats.refundRate")}
                </h3>
                <div className="mt-1.5 flex gap-1.5">
                  <p className="flex items-center gap-1 text-sm font-medium text-success-600">
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
                    32%
                  </p>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    {t("sales.salesStats.vsLastMonth")}
                  </p>
                </div>
              </div>
              <div>
                <svg
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    d="M20.6389 10.8655V8.16168C20.6389 7.3664 19.9942 6.72168 19.1989 6.72168H4.31891C3.52361 6.72168 2.87891 7.3664 2.87891 8.16168V16.3217C2.87891 17.117 3.52361 17.7617 4.31891 17.7617H8.96575M12.7199 10.2372C12.429 10.0976 12.1032 10.0193 11.759 10.0193C10.5315 10.0193 9.53656 11.0144 9.53656 12.2417C9.53656 12.587 9.61532 12.914 9.75587 13.2056M11.7589 15.1717H18.1689C19.5331 15.1717 20.6389 16.2776 20.6389 17.6417C20.6389 19.0058 19.5331 20.1116 18.1689 20.1116H14.2357M11.7589 15.1717L13.6777 13.2517M11.7589 15.1717L13.6777 17.0917"
                    stroke="#F04438"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                  <path
                    d="M6.20312 12.2422H6.21312"
                    stroke="#F04438"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </div>
            </div>
            <div className="flex items-end justify-between">
              <h2 className="w-1/2 text-3xl font-semibold text-gray-800 dark:text-white/90">
                1.2%
              </h2>
              <div className="h-11 w-1/2">
                <Chart
                  options={getChartOptions("#F04438")}
                  series={chartSeries}
                  type="area"
                  height={44}
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
